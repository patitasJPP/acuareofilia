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
        'motor':'incremental_v1','version':p['engine'].hour,'duracion_paso':p.get('duracion_paso',0),
        'error':p.get('error',''),'nota':p.get('nota','')}

def statuses():
    with Session() as s:return {r.run_id:{'estado':r.estado,'hora':r.hora,'segundos':r.segundos,'fin':96} for r in s.query(LiveRun)}

def read(rid):
    e=entry_for(rid)
    with e.lock:
        p=e.payload
        return p['scored'].copy(),meta(p),list(p['engine'].water)

def advance(e):
    """Solo crea la hora siguiente; no vuelve a predecir las filas pasadas."""
    start=time.monotonic();p=e.payload
    rows=p['engine'].step();p['raw'].extend(rows)
    hour=p['engine'].hour
    if rows:
        allrows,_=service.historia(pd.DataFrame(p['raw']))
        now=allrows[allrows.hora_sim.eq(hour)].copy()
        for h,b in service.models().items():
            now[f'riesgo_{h}h']=service.predecir(b['pipeline'],b['calibrador'],now[b['features']])
            now[f'alerta_{h}h']=now[f'riesgo_{h}h'].ge(b['umbrales']['F2'])
        p['scored']=pd.concat([p['scored'],now],ignore_index=True)
    d=p['scored']
    death={ev['pez_id']:ev['hora_evento'] for ev in p['engine'].events}
    d['hora_evento']=d.pez_id.map(death)
    for h in service.HORIZONS:
        d[f'observado_{h}h']=np.where(d.hora_sim+h<=hour,
            (d.hora_evento.gt(d.hora_sim)&d.hora_evento.le(d.hora_sim+h)).astype(int),np.nan)
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
            try:advance(e)
            except Exception as exc:
                logging.exception('Error de simulación incremental')
                e.payload['estado']='error';e.payload['error']=str(exc);save(e);return
            delay=max(0.,e.payload['segundos']-(time.monotonic()-start))

def start(e):
    if e.thread and e.thread.is_alive():return
    e.wake.clear();e.thread=threading.Thread(target=worker_loop,args=(e,),daemon=True);e.thread.start()

def create(scenario,seed,seconds):
    with _guard:
        if any(s['estado']=='activa' for s in statuses().values()):
            raise ValueError('Pausa la simulación activa antes de iniciar otra')
        with Session() as s:
            r=Run(nombre=f'En vivo · {service.LABELS[scenario]} · {seed}',escenario=scenario,semilla=seed,origen='vivo',estado='lista',archivo='')
            s.add(r);s.commit();rid=r.id
            r.archivo=f'vivo_{rid}.csv';s.add(LiveRun(run_id=rid));s.commit();run=as_dict(r)
        e=Entry({'rid':rid,'engine':LiveEngine(pd.read_csv(SEED/'fichas_origen.csv'),100000+rid,seed,scenario),
            'estado':'pausada','segundos':seconds,'raw':[],'scored':pd.DataFrame(),'nota':''})
        advance(e) # Solo hora cero; no ocurre ninguna muerte antes de predecir.
        _entries[rid]=e
        return run|{'vivo':meta(e.payload)}

def control(rid,action,seconds=None):
    with _guard:
        e=entry_for(rid)
        with e.lock:
            p=e.payload
            if action=='reanudar':
                if p['engine'].hour>=96:raise ValueError('La corrida terminó. Crea otra para reiniciar sin borrar el historial.')
                if p['estado']=='error':raise ValueError('La corrida tiene un error; crea una prueba nueva.')
                if any(k!=rid and v['estado']=='activa' for k,v in statuses().items()):raise ValueError('Ya hay otra simulación activa')
                p['estado']='activa';p['nota']=''
            elif action=='pausar':
                if p['estado']=='activa':p['estado']='pausada'
            if seconds is not None:p['segundos']=seconds
            save(e);result=meta(p)
        # Espera al hilo anterior antes de reanudar, evitando dos relojes.
        if action=='pausar' and e.thread:
            e.wake.set();e.thread.join(timeout=5)
        if p['estado']=='activa':start(e)
        return result

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
