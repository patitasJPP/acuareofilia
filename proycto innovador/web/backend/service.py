from .paths import DATA, SEED, MODELS as MODEL_DIR, EXPORTS
"""Inferencia causal con historia hasta t; ningún desenlace entra al modelo."""
from pathlib import Path
import sys, json, hashlib
from functools import lru_cache
import numpy as np
import pandas as pd
import joblib
from .storage import ROOT, Session, Run, as_dict

from .paths import ML
sys.path.insert(0,str(ML))
from mejorar_predicciones import historia
from experimento_mortalidad import predecir, simular_corrida, metricas

HORIZONS=[1,6,12]
SCENARIOS=['estable','amonio','hipoxia','termico','ph','combinado']
LABELS={'estable':'Estable','amonio':'Amoníaco','hipoxia':'Oxígeno bajo','termico':'Temperatura','ph':'pH','combinado':'Combinado'}
MODELS={}

def models():
    if not MODELS:
        for h in HORIZONS: MODELS[h]=joblib.load(MODEL_DIR/f'modelo_{h}h.joblib')
    return MODELS

def clean(df):
    return json.loads(df.replace([np.inf,-np.inf],np.nan).to_json(orient='records',force_ascii=False))

def score(d,events):
    d,features=historia(d)
    deaths=events[events.evento.eq('muerte')][['corrida_id','pez_id','hora_evento']]
    d=d.merge(deaths,on=['corrida_id','pez_id'],how='left',validate='many_to_one')
    for h,b in models().items():
        d[f'riesgo_{h}h']=predecir(b['pipeline'],b['calibrador'],d[b['features']])
        d[f'alerta_{h}h']=d[f'riesgo_{h}h'].ge(b['umbrales']['F2'])
        # Todos los casos, positivos y negativos, necesitan seguimiento completo.
        d[f'observado_{h}h']=np.where(d.hora_sim+h<=96,
            (d.hora_evento.gt(d.hora_sim)&d.hora_evento.le(d.hora_sim+h)).astype(int),np.nan)
    d=d.drop(columns=['muere_siguiente_hora','particion'],errors='ignore')
    return d

def initialize():
    models()
    with Session() as s:
        if s.query(Run).filter(Run.origen=='test_v3').first(): return
    src=SEED
    d=pd.read_csv(src/'datos.csv')
    d=d[d.particion.eq('test')].copy()
    scored=score(d,pd.read_csv(src/'eventos.csv'))
    # Reconciliar con el modelo local, sin mezclar métricas de Colab.
    expected=pd.read_csv(src/'evaluacion_final.csv')
    for h in HORIZONS:
        x=scored[scored[f'observado_{h}h'].notna()]
        met=metricas(x[f'observado_{h}h'],x[f'riesgo_{h}h'],models()[h]['umbrales']['F2'])
        e=expected[expected.horizonte_h.eq(h)&expected.politica.eq('F2')&expected.version.eq('historia_24h')].iloc[0]
        assert all(met[k]==e[k] for k in ['tp','fp','fn','tn']), 'Modelo y métricas locales no coinciden'
    corridas=pd.read_csv(src/'corridas.csv').set_index('corrida_id')
    with Session() as s:
        for cid,x in scored.groupby('corrida_id'):
            path=DATA/f'test_{cid}.csv'
            x.to_csv(path,index=False)
            r=corridas.loc[cid]
            s.add(Run(nombre=f'Prueba {cid:02d}',escenario=str(r.escenario),semilla=int(r.semilla),origen='test_v3',estado='lista',archivo=path.name))
        s.commit()

@lru_cache(maxsize=24)
def data(archivo): return pd.read_csv(DATA/archivo)

def get_run(rid):
    with Session() as s:
        r=s.get(Run,rid)
        if not r: raise ValueError('La simulación no existe')
        if r.estado!='lista': raise ValueError('La simulación todavía no está lista')
        if r.origen=='vivo':
            from .live import read
            frame,state,water=read(rid)
            return as_dict(r)|{'vivo':state,'agua_actual':water},frame
        return as_dict(r),data(r.archivo)

def conditions(row):
    notes=[]
    if row.get('calidad_prediccion') in ['sin_lectura','historial_incompleto']:
        notes.append('Sin predicción: lectura ausente o historial incompleto')
    elif row.get('calidad_prediccion')=='historia_estimada':
        notes.append('Historia con lecturas estimadas a partir del pasado')
    if row['temp_desvio']>0.1: notes.append('Temperatura fuera del rango de la especie')
    if row['ox_deficit']>0.1: notes.append('Oxígeno por debajo del mínimo de la especie')
    if row['ph_desvio']>0.05: notes.append('pH fuera del rango de la especie')
    if not row['aireacion_activa']: notes.append('Aireación inactiva')
    if not row['filtro_activo']: notes.append('Filtro inactivo')
    return notes or ['Consultar la exposición acumulada y el historial del agua']

def snapshot(rid,hour,horizon):
    r,d=get_run(rid)
    return snapshot_data(r,d,hour,horizon)

def snapshot_data(r,d,hour,horizon):
    if r.get('vivo') and hour>r['vivo']['hora']:
        raise ValueError('Esa hora todavía no ha ocurrido')
    x=d[d.hora_sim.eq(hour)].copy()
    risk=f'riesgo_{horizon}h'; alert=f'alerta_{horizon}h'
    tanks=[]
    # Se conservan las tres peceras aun si ya no hay peces vivos.
    for tid in range(3):
        g=x[x.pecera_id.eq(tid)]
        past=d[d.pecera_id.eq(tid)&d.hora_sim.le(hour)]
        readings=past.sort_values('hora_sim').tail(1)
        ref=readings.iloc[0] if len(readings) else None
        available=int(g[risk].notna().sum())
        tanks.append({'id':tid,'nombre':f'Pecera {tid+1:02d}','peces':len(g),'evaluados':available,'sin_prediccion':len(g)-available,
            'esperadas':float(g[risk].sum()) if available or not len(g) else None,'riesgo_medio':float(g[risk].mean()) if available else None,
            'riesgo_maximo':float(g[risk].max()) if available else None,'alertas':int(g[alert].sum()),
            'sobre_60':int(g[risk].ge(.6).sum()),
            'ph':float(ref.ph) if ref is not None else None,'temperatura':float(ref.temperatura) if ref is not None else None,
            'oxigeno':float(ref.oxigeno) if ref is not None else None,'nh3':float(ref.nh3_mg_n_l) if ref is not None else None,
            'hora_lectura':int(ref.hora_sim) if ref is not None else None})
        if r.get('vivo'):
            water=next((w for w in reversed(r['agua_actual']) if w['id']==tid and w['hora_lectura']==hour),{})
            tanks[-1].update({k:(None if isinstance(v,float) and not np.isfinite(v) else v) for k,v in water.items() if k in ['ph','temperatura','oxigeno','nh3','hora_lectura','sensor_disponible']})
    fish=x.sort_values(risk,ascending=False).copy()
    fish['condiciones']=fish.apply(lambda row:'; '.join(conditions(row)),axis=1)
    fields=['pez_id','pecera_id','especie_nombre','peso_gramos',risk,alert,'ph','temperatura','oxigeno','nh3_mg_n_l','condiciones']
    fields += [c for c in ['calidad_prediccion','prediccion_disponible'] if c in fish]
    public={k:v for k,v in r.items() if k!='agua_actual'}
    return {'corrida':public,'hora':hour,'horizonte':horizon,'umbral':models()[horizon]['umbrales']['F2'],
        'peces':len(x),'evaluados':int(x[risk].notna().sum()),'sin_prediccion':int(x[risk].isna().sum()),
        'alertas':int(x[alert].sum()),'esperadas':float(x[risk].sum()) if x[risk].notna().any() or x.empty else None,
        'peceras':tanks,'detalle':clean(fish[fields])}

def timeline(rid,horizon,tid=None):
    r,d=get_run(rid)
    return timeline_data(d,horizon,tid,r.get('vivo',{}).get('hora',84))

def timeline_data(d,horizon,tid=None,maximum=84):
    if tid is not None: d=d[d.pecera_id.eq(tid)]
    out=[]
    for hour in range(maximum+1):
        g=d[d.hora_sim.eq(hour)]
        out.append({'hora':hour,'vivos':len(g),'esperadas':float(g[f'riesgo_{horizon}h'].sum()) if g[f'riesgo_{horizon}h'].notna().any() or g.empty else None,
            'alertas':int(g[f'alerta_{horizon}h'].sum()),'riesgo_medio':float(g[f'riesgo_{horizon}h'].mean()) if g[f'riesgo_{horizon}h'].notna().any() else None,
            'sin_prediccion':int(g[f'riesgo_{horizon}h'].isna().sum())})
    return out

def evaluate(d,h):
    x=d[d[f'observado_{h}h'].notna() & d[f'riesgo_{h}h'].notna()]
    if x.empty:
        return {k:None for k in ['accuracy','precision','recall','f1','roc_auc','pr_auc_ap','brier','tn','fp','fn','tp']}|{
            'observaciones':0,'muertes_distintas':0,'anticipadas_distintas':0,'pendiente':True}
    m=metricas(x[f'observado_{h}h'],x[f'riesgo_{h}h'],models()[h]['umbrales']['F2'])
    m['observaciones']=len(x)
    deaths=x[x[f'observado_{h}h'].eq(1)][['corrida_id','pez_id']].drop_duplicates()
    hit=x[x[f'observado_{h}h'].eq(1)&x[f'alerta_{h}h']][['corrida_id','pez_id']].drop_duplicates()
    m['muertes_distintas']=len(deaths); m['anticipadas_distintas']=len(hit)
    return m

def metrics():
    src=SEED
    fixed=pd.read_csv(src/'evaluacion_final.csv')
    fixed=fixed[fixed.politica.eq('F2')&fixed.version.eq('historia_24h')]
    intervals=pd.read_csv(src/'intervalos_por_corrida.csv')
    deaths=pd.read_csv(src/'deteccion_muertes_distintas.csv')
    importance=[]
    b=models()[12]['pipeline']
    names=b.named_steps['preparar'].get_feature_names_out()
    for name,v in zip(names,b.named_steps['modelo'].feature_importances_):
        importance.append({'variable':str(name).split('__')[-1],'importancia':float(v)})
    return {'fuente':'Experimento local v3 · 12 corridas reservadas de prueba',
        'modelos':clean(fixed),'intervalos':clean(intervals),'muertes':clean(deaths),
        'importancia':sorted(importance,key=lambda v:v['importancia'],reverse=True)[:10],
        'versiones':json.loads((src/'versiones.json').read_text()),
        'nota':'Las métricas por observación cuentan pez/hora. Las muertes distintas cuentan cada pez una sola vez.'}

def create_runs(escenario,semilla,repeticiones):
    with Session() as s:
        rows=[]
        for i in range(repeticiones):
            r=Run(nombre=f'{LABELS[escenario]} · {semilla+i*101}',escenario=escenario,semilla=semilla+i*101,origen='nueva')
            s.add(r);rows.append(r)
        s.commit()
        return [as_dict(r) for r in rows]

def execute_run(rid):
    try:
        with Session() as s:
            r=s.get(Run,rid);r.estado='ejecutando';s.commit();seed=r.semilla;sc=r.escenario
        fichas=pd.read_csv(SEED/'fichas_origen.csv')
        f,e,_,_=simular_corrida(fichas,100000+rid,seed,sc,'nueva',horas=96)
        scored=score(pd.DataFrame(f),pd.DataFrame(e))
        path=DATA/f'nueva_{rid}.csv';scored.to_csv(path,index=False)
        with Session() as s:
            r=s.get(Run,rid);r.archivo=path.name;r.estado='lista';s.commit()
    except Exception as exc:
        import logging
        logging.exception('Error al simular')
        with Session() as s:
            r=s.get(Run,rid);r.estado='error';r.error=str(exc);s.commit()

def comparison():
    with Session() as s: runs=s.query(Run).filter(Run.estado=='lista').all()
    rows=[]
    for r in runs:
        if r.origen=='vivo':
            _,d=get_run(r.id)
        else:d=data(r.archivo)
        for h in HORIZONS:
            rows.append(as_dict(r)|{'horizonte':h}|evaluate(d,h))
    return rows
