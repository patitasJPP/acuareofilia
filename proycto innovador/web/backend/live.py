from .paths import DATA, SEED, MODELS, EXPORTS
"""Reloj del servidor y checkpoints atómicos para simulación incremental.

Un solo worker Uvicorn. Nunca calcula ni guarda observaciones de una hora futura.
El checkpoint conserva RNG, daño interno, mediciones y predicciones ya emitidas.
"""
import os, pickle, threading, time, logging
import numpy as np
import pandas as pd
from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .storage import Base, engine as database_engine, ROOT, Session, Run, as_dict
from . import service
from .live_engine import LiveEngine
from simulacion.motor.realistic_engine import RealisticEngine, configuration
from simulacion.motor.features import prepare

class LiveRun(Base):
    __tablename__='pisciber_vivo'
    run_id:Mapped[int]=mapped_column(ForeignKey('pisciber_corridas.id'),primary_key=True)
    estado:Mapped[str]=mapped_column(String(20),default='pausada')
    hora:Mapped[int]=mapped_column(Integer,default=0)
    segundos:Mapped[float]=mapped_column(Float,default=1.)
Base.metadata.create_all(database_engine)

_entries={};_guard=threading.RLock()
class Entry:
    def __init__(self,payload):
        self.payload=payload;self.lock=threading.RLock();self.wake=threading.Event();self.thread=None

def file(rid):return DATA/f'vivo_{rid}.checkpoint'

def save(entry):
    p=entry.payload;rid=p['rid'];temp=file(rid).with_suffix('.tmp')
    with temp.open('wb') as f:
        pickle.dump(p,f,protocol=pickle.HIGHEST_PROTOCOL);f.flush();os.fsync(f.fileno())
    os.replace(temp,file(rid))
    with Session() as s:
        row=s.get(LiveRun,rid);row.hora=p['engine'].hour;row.estado=p['estado'];row.segundos=p['segundos'];s.commit()

def entry_for(rid):
    with _guard:
        if rid not in _entries:
            if not file(rid).exists():raise ValueError('La corrida no es una simulación en vivo')
            # Solo checkpoints creados por esta aplicación; no se admiten uploads.
            with file(rid).open('rb') as f:p=pickle.load(f)
            _entries[rid]=Entry(p)
        return _entries[rid]

def meta(p):
    return {'estado':p['estado'],'hora':p['engine'].hour,'segundos':p['segundos'],'fin':96,
        'motor':getattr(p['engine'],'version','incremental_v1'),'version':p['engine'].hour,'duracion_paso':p.get('duracion_paso',0),
        'configuracion':getattr(p['engine'],'config',None),'rama_de':p.get('rama_de'),
        'error':p.get('error',''),'nota':p.get('nota','')}

def statuses():
    with Session() as s:return {r.run_id:{'estado':r.estado,'hora':r.hora,'segundos':r.segundos,'fin':96} for r in s.query(LiveRun)}

def read(rid):
    e=entry_for(rid)
    with e.lock:
        p=e.payload
        return p['scored'].copy(),meta(p),list(getattr(p['engine'],'water_history',p['engine'].water))


def score_v2(raw):
    """Una fila sin lectura no se convierte en un riesgo igual a cero."""
    result, features, _ = prepare(pd.DataFrame(raw))
    available = result.prediccion_disponible
    for h, b in service.models().items():
        result[f'riesgo_{h}h'] = np.nan
        if available.any():
            result.loc[available,f'riesgo_{h}h'] = service.predecir(b['pipeline'],b['calibrador'],features.loc[available,b['features']])
        result[f'alerta_{h}h'] = result[f'riesgo_{h}h'].ge(b['umbrales']['F2'])
    return result


def labels(p):
    d = p['scored']; hour = p['engine'].hour
    death = {ev['pez_id']:ev['hora_evento'] for ev in p['engine'].events}
    d['hora_evento'] = d.pez_id.map(death)
    for h in service.HORIZONS:
        d[f'observado_{h}h'] = np.where(d.hora_sim+h<=hour,
            (d.hora_evento.gt(d.hora_sim)&d.hora_evento.le(d.hora_sim+h)).astype(int),np.nan)

def advance(e):
    """Solo crea la hora siguiente; no vuelve a predecir las filas pasadas."""
    start=time.monotonic();p=e.payload
    rows=p['engine'].step();p['raw'].extend(rows)
    hour=p['engine'].hour
    if rows:
        if isinstance(p['engine'],RealisticEngine):
            originals, features, _ = prepare(pd.DataFrame(p['raw']))
            now = originals[originals.hora_sim.eq(hour)].copy()
            inputs = features.loc[now.index]
            available = now.prediccion_disponible
        else:
            allrows,_=service.historia(pd.DataFrame(p['raw']))
            now=allrows[allrows.hora_sim.eq(hour)].copy()
            inputs = now
            available = pd.Series(True,index=now.index)
        for h,b in service.models().items():
            now[f'riesgo_{h}h']=np.nan
            if available.any():
                now.loc[available,f'riesgo_{h}h']=service.predecir(b['pipeline'],b['calibrador'],inputs.loc[available,b['features']])
            now[f'alerta_{h}h']=now[f'riesgo_{h}h'].ge(b['umbrales']['F2'])
        p['scored']=pd.concat([p['scored'],now],ignore_index=True)
    labels(p)
    if hour==96:p['estado']='terminada'
    p['duracion_paso']=time.monotonic()-start
    save(e)

def worker_loop(e,delay=None):
    while True:
        with e.lock:
            if e.payload['estado']!='activa':return
            wait=e.payload['segundos'] if delay is None else delay
        delay=None
        if e.wake.wait(wait):e.wake.clear();continue
        start=time.monotonic()
        with e.lock:
            if e.payload['estado']!='activa':return
            before=pickle.dumps(e.payload,protocol=pickle.HIGHEST_PROTOCOL)
            try:advance(e)
            except Exception as exc:
                logging.exception('Error de simulación incremental')
                e.payload=pickle.loads(before)
                e.payload['estado']='error';e.payload['error']=str(exc);save(e);return
            delay=max(0.,e.payload['segundos']-(time.monotonic()-start))

def start(e):
    if e.thread and e.thread.is_alive():return
    e.wake.clear();e.thread=threading.Thread(target=worker_loop,args=(e,),daemon=True);e.thread.start()

def create(scenario,seed,seconds,config=None,version='incremental_v2',require_idle=True):
    with _guard:
        fichas = pd.read_csv(SEED/'fichas_origen.csv')
        if version == 'incremental_v2': config = configuration(config,fichas)
        if require_idle and any(s['estado']=='activa' for s in statuses().values()):
            raise ValueError('Pausa la simulación activa antes de iniciar otra')
        with Session() as s:
            r=Run(nombre=f'{"Motor v2" if version=="incremental_v2" else "En vivo v1"} · {service.LABELS[scenario]} · {seed}',escenario=scenario,semilla=seed,origen='vivo',estado='lista',archivo='')
            s.add(r);s.commit();rid=r.id
            r.archivo=f'vivo_{rid}.csv';s.add(LiveRun(run_id=rid));s.commit();run=as_dict(r)
        motor = RealisticEngine(fichas,100000+rid,seed,scenario,config) if version == 'incremental_v2' else LiveEngine(fichas,100000+rid,seed,scenario)
        e=Entry({'rid':rid,'engine':motor,
            'estado':'pausada','segundos':seconds,'raw':[],'scored':pd.DataFrame(),'nota':''})
        advance(e) # Solo hora cero; no ocurre ninguna muerte antes de predecir.
        _entries[rid]=e
        return run|{'vivo':meta(e.payload)}


def finish(rid):
    """Lote v2 con el mismo motor y features que el reloj incremental."""
    e = entry_for(rid)
    with e.lock:
        p = e.payload
        try:
            while p['engine'].hour < 96:
                p['raw'].extend(p['engine'].step())
            p['scored'] = score_v2(p['raw']); labels(p)
            p['estado'] = 'terminada'; save(e)
            with Session() as s:
                r = s.get(Run,rid);r.estado='lista';s.commit()
        except Exception as exc:
            logging.exception('Error al terminar lote v2')
            p['estado']='error';p['error']=str(exc);save(e)
            with Session() as s:
                r=s.get(Run,rid);r.estado='error';r.error=str(exc);s.commit()


def intervene(rid,tid,kind,value,duration,expected_hour):
    e = entry_for(rid)
    with e.lock:
        p=e.payload
        if not isinstance(p['engine'],RealisticEngine): raise ValueError('Las acciones requieren una corrida del motor v2')
        if p['estado']!='pausada' or p['engine'].hour!=expected_hour:
            raise ValueError('Pausa la corrida y vuelve al presente antes de aplicar una acción')
        result=p['engine'].schedule(tid,kind,value,duration)
        save(e)
        return result


def details(rid,hour):
    e=entry_for(rid)
    with e.lock:
        p=e.payload;motor=p['engine']
        if not 0<=hour<=motor.hour: raise ValueError('Esa hora no está disponible')
        return {'configuracion':getattr(motor,'config',None), 'motor':getattr(motor,'version','incremental_v1'),
                'acciones':[dict(a) for a in getattr(motor,'actions',[]) if a['solicitada_hora']<=hour],
                'bitacora':[dict(a) for a in getattr(motor,'log',[]) if a['hora']<=hour],
                'rama_de':p.get('rama_de')}


def branch(rid,hour):
    """Reproduce el pasado hasta t, conserva predicciones y crea otra corrida pausada."""
    e=entry_for(rid)
    with _guard, e.lock:
        p=e.payload;original=p['engine']
        if not isinstance(original,RealisticEngine): raise ValueError('Crea una corrida v2 para usar ramas históricas')
        if not 0<=hour<96 or hour>original.hour: raise ValueError('Elige una hora disponible anterior a 96')
        with Session() as s:
            parent=s.get(Run,rid)
            r=Run(nombre=f'Rama de {rid} · hora {hour}',escenario=parent.escenario,semilla=parent.semilla,origen='vivo',estado='lista',archivo='')
            s.add(r);s.commit();newid=r.id;r.archivo=f'vivo_{newid}.csv';s.add(LiveRun(run_id=newid));s.commit();row=as_dict(r)
        engine=RealisticEngine(pd.read_csv(SEED/'fichas_origen.csv'),100000+newid,original.seed,original.scenario,original.config)
        raw=[]
        for t in range(hour+1):
            raw.extend(engine.step())
            for a in original.actions:
                if a['solicitada_hora']==t: engine.schedule(a['pecera_id'],a['accion'],a['valor'],a['duracion'])
        scored=p['scored'][p['scored'].hora_sim.le(hour)].copy()
        scored['corrida_id']=100000+newid
        child=Entry({'rid':newid,'engine':engine,'raw':raw,'scored':scored,'estado':'pausada','segundos':p['segundos'],
                     'rama_de':{'id':rid,'hora':hour},'nota':'Rama creada desde el historial; puedes probar otra decisión.'})
        labels(child.payload);save(child);_entries[newid]=child
        return row|{'vivo':meta(child.payload)}


def paired(rid,other):
    # read() entrega copias consistentes sin tomar dos candados simultáneos.
    a,ma,_=read(rid);b,mb,_=read(other)
    with Session() as s:
        ra=s.get(Run,rid);rb=s.get(Run,other)
        if rid==other or (ra.semilla,ra.escenario)!=(rb.semilla,rb.escenario) or ma['configuracion']!=mb['configuracion'] or ma['motor']!='incremental_v2' or mb['motor']!='incremental_v2':
            raise ValueError('Compara dos corridas v2 con la misma semilla, ambiente y configuración')
    hour=min(ma['hora'],mb['hora'])
    def stats(frame):
        initial=int(frame[frame.hora_sim.eq(0)].pez_id.nunique())
        dead=int(frame[frame.hora_evento.le(hour)].pez_id.nunique())
        return {'iniciales':initial,'muertos':dead,'vivos':initial-dead}
    left,right=stats(a),stats(b)
    return {'hora':hour,'base':{'id':rid,**left},'alternativa':{'id':other,**right},
            'diferencia_muertes':right['muertos']-left['muertos'],
            'acciones_base':details(rid,hour)['acciones'],'acciones_alternativa':details(other,hour)['acciones'],
            'nota':'Misma configuración y números aleatorios por pez/hora. Una pareja es exploratoria; repite con distintas semillas. La diferencia no prueba un efecto en peces reales.'}

def control(rid,action,seconds=None):
    with _guard:
        e=entry_for(rid)
        switched=[]
        if action=='reanudar':
            # Valida el destino antes de pausar otra corrida.
            with e.lock:
                if e.payload['engine'].hour>=96:raise ValueError('La corrida terminó. Usa Reproducir historial o Empezar desde cero.')
                already_running=e.payload['estado']=='activa'
            # Un hilo que acaba de fallar puede seguir vivo unos instantes tras
            # soltar el candado. Esperar su salida antes de crear el reemplazo.
            if not already_running and e.thread and e.thread.is_alive():
                e.wake.set();e.thread.join(timeout=5)
                if e.thread.is_alive():raise ValueError('El paso anterior está finalizando; vuelve a intentar reanudar en unos segundos')
            for other,state in statuses().items():
                if other!=rid and state['estado']=='activa':
                    control(other,'pausar');switched.append(other)
        with e.lock:
            p=e.payload
            if action=='reanudar':
                p['estado']='activa';p['error']=''
                p['nota']=f'Se pausó la corrida {switched} para continuar esta.' if switched else ''
            elif action=='pausar':
                if p['estado']=='activa':p['estado']='pausada'
            if seconds is not None:p['segundos']=seconds
            save(e);result=meta(p)
        # Espera al hilo anterior antes de reanudar, evitando dos relojes.
        if action=='pausar' and e.thread:
            e.wake.set();e.thread.join(timeout=5)
        elif action=='velocidad':e.wake.set()
        if p['estado']=='activa':start(e)
        return result


def restart(rid):
    """Reinicia en otra fila; no destruye resultados ni altera semillas."""
    with _guard:
        with Session() as s:
            run=s.get(Run,rid)
            if not run:raise ValueError('La corrida no existe')
            scenario,seed,origin=run.escenario,run.semilla,run.origen
        config,version,seconds=None,'incremental_v2',1.
        if origin=='vivo':
            e=entry_for(rid)
            with e.lock:
                config=getattr(e.payload['engine'],'config',None)
                version=getattr(e.payload['engine'],'version','incremental_v1')
                seconds=e.payload['segundos']
            control(rid,'pausar')
        row=create(scenario,seed,seconds,config,version,require_idle=False)
        with Session() as s:
            run=s.get(Run,row['id']);run.nombre=f'Reinicio de {rid} · {service.LABELS[scenario]} · {seed}';s.commit()
            row['nombre']=run.nombre
        e=entry_for(row['id'])
        with e.lock:
            e.payload['nota']=f'Reinicio de la corrida {rid}. Misma semilla y configuración; sin intervenciones previas.'
            save(e);row['vivo']=meta(e.payload)
        return row

def recover():
    # Reiniciar el servidor no adelanta el tiempo que estuvo apagado.
    for rid in statuses():
        e=entry_for(rid)
        with e.lock:
            if e.payload['estado']=='activa':
                e.payload['estado']='pausada';e.payload['nota']='Servidor reiniciado. Puedes reanudar desde esta hora.';save(e)

def shutdown():
    for rid in list(_entries):
        if _entries[rid].payload['estado']=='activa':control(rid,'pausar')
