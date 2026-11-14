"""Evaluación congelada del modelo v3 sobre el motor v2, sin entrenar con test.

Ejecutar desde la raíz del proyecto: .venv/Scripts/python.exe -m simulacion.ml.evaluar_motor_v2
El protocolo y las semillas se escriben antes de calcular los resultados.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from simulacion.motor.realistic_engine import RealisticEngine, DEFAULT_CONFIG, VERSION
from simulacion.motor.features import prepare
from experimento_mortalidad import metricas, predecir

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'resultados/validacion_motor_v2'
SCENARIOS=['estable','amonio','hipoxia','termico','ph','combinado']


def dump(name,value):
    (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if (OUTPUT/'informe.json').exists():raise RuntimeError('La prueba ya fue evaluada; no reutilizar test para ajustar el motor o el modelo.')
    fichas=pd.read_csv(ROOT/'simulacion/datos_base/fichas_origen.csv')
    bundles={h:joblib.load(ROOT/f'simulacion/modelos/modelo_{h}h.joblib') for h in [1,6,12]}
    protocol={'motor':VERSION,'modelo':'XGBoost local v3 sin modificar','semilla_base':183114000,
        'corridas':36,'regla_semilla':'base + escenario*1000 + replica*101','replicas_por_ambiente':6,
        'intensidades':['leve','moderado','severo'],'sensores':'replicas 0-3 normal; 4-5 intermitente',
        'seleccion':'Evaluación de transferencia del modelo congelado; no selecciona hiperparámetros ni umbrales.',
        'motor_sha256':hashlib.sha256((ROOT/'simulacion/motor/realistic_engine.py').read_bytes()).hexdigest(),
        'features_sha256':hashlib.sha256((ROOT/'simulacion/motor/features.py').read_bytes()).hexdigest(),
        'modelos_sha256':{str(h):hashlib.sha256((ROOT/f'simulacion/modelos/modelo_{h}h.joblib').read_bytes()).hexdigest() for h in bundles}}
    dump('protocolo.json',protocol)
    predictions=[];runs=[];raw_all=[];events_all=[]
    for index,scenario in enumerate(SCENARIOS):
        for replica in range(6):
            seed=183114000+index*1000+replica*101;cid=index*6+replica
            config=deepcopy(DEFAULT_CONFIG)
            config.update(intensidad=['leve','moderado','severo'][replica%3],inicio=18+(replica%3)*6,
                          duracion=12+(replica%3)*12,sensores='intermitente' if replica>=4 else 'normal')
            for tid,tank in enumerate(config['peceras']):
                tank.update(especie=str(fichas.iloc[(replica+tid)%len(fichas)].especie_nombre),
                            peces=12+replica*4,volumen_l=800+tid*500+replica*200)
            engine=RealisticEngine(fichas,cid,seed,scenario,config);raw=[]
            for _ in range(97):raw.extend(engine.step())
            observations,features,names=prepare(pd.DataFrame(raw))
            assert not {'hora_evento','target','pez_id','pecera_id','escenario','particion'}&set(names)
            death={e['pez_id']:e['hora_evento'] for e in engine.events}
            observations['hora_evento']=observations.pez_id.map(death)
            raw_all.append(observations);events_all.extend(engine.events)
            runs.append({'corrida_id':cid,'semilla':seed,'escenario':scenario,'configuracion':json.dumps(config,ensure_ascii=False),
                         'peces_iniciales':sum(t['peces'] for t in config['peceras']), 'muertes':len(engine.events)})
            for h,b in bundles.items():
                complete=observations.hora_sim+h<=96
                valid=complete&observations.prediccion_disponible
                rows=observations.loc[valid,['corrida_id','pecera_id','pez_id','hora_sim','escenario']].copy()
                rows['target']=(observations.loc[valid,'hora_evento'].gt(observations.loc[valid,'hora_sim']) & observations.loc[valid,'hora_evento'].le(observations.loc[valid,'hora_sim']+h)).astype(int)
                rows['probabilidad']=predecir(b['pipeline'],b['calibrador'],features.loc[valid,b['features']])
                rows['horizonte_h']=h
                rows['umbral']=b['umbrales']['F2'];rows['alerta']=rows.probabilidad.ge(rows.umbral)
                predictions.append(rows)
            print(f'Validación {cid+1}/36 · {scenario} · {len(engine.events)} muertes / {sum(t["peces"] for t in config["peceras"])} peces',flush=True)
    pred=pd.concat(predictions,ignore_index=True);raw=pd.concat(raw_all,ignore_index=True)
    raw.to_csv(OUTPUT/'observaciones.csv',index=False)
    pd.DataFrame(events_all,columns=['corrida_id','pez_id','pecera_id','hora_evento','evento']).to_csv(OUTPUT/'eventos.csv',index=False)
    pd.DataFrame(runs).to_csv(OUTPUT/'corridas.csv',index=False);pred.to_csv(OUTPUT/'predicciones.csv',index=False)
    models=[];per_scenario=[];intervals=[]
    for h,b in bundles.items():
        x=pred[pred.horizonte_h.eq(h)];m=metricas(x.target,x.probabilidad,b['umbrales']['F2'])
        complete=int((raw.hora_sim+h<=96).sum())
        m.update(horizonte_h=h,n=len(x),prevalencia=float(x.target.mean()),cobertura=len(x)/complete,
                 sin_prediccion=complete-len(x),umbral=b['umbrales']['F2'])
        models.append(m)
        byrun=[]
        for cid,g in x.groupby('corrida_id'):
            met=metricas(g.target,g.probabilidad,b['umbrales']['F2'])
            byrun.append([met[k] for k in ['tp','fp','fn','tn']])
        rng=np.random.default_rng(42);counts=np.array(byrun)
        boot=counts[rng.integers(0,len(counts),(1000,len(counts)))].sum(axis=1)
        for key,numerator,denominator in [('precision',boot[:,0],boot[:,0]+boot[:,1]),('recall',boot[:,0],boot[:,0]+boot[:,2])]:
            samples=np.divide(numerator,denominator,out=np.full(1000,np.nan),where=denominator>0)
            intervals.append({'horizonte_h':h,'metrica':key,'inferior':float(np.nanquantile(samples,.025)),'superior':float(np.nanquantile(samples,.975))})
        for scenario,g in x.groupby('escenario'):
            per_scenario.append({'horizonte_h':h,'escenario':scenario,'n':len(g),**metricas(g.target,g.probabilidad,b['umbrales']['F2'])})
    pd.DataFrame(models).to_csv(OUTPUT/'metricas.csv',index=False)
    pd.DataFrame(intervals).to_csv(OUTPUT/'intervalos.csv',index=False)
    pd.DataFrame(per_scenario).to_csv(OUTPUT/'por_ambiente.csv',index=False)
    info={'estado':'evaluada','nota':'36 corridas nuevas y semillas distintas. Modelo v3 y umbrales congelados; estas métricas solo describen el motor v2 evaluado.',
          'modelos':models,'intervalos':intervals,'por_ambiente':per_scenario,
          'conclusion':'La tasa de mortalidad y la disponibilidad de sensores cambiaron. Compara recall, precisión, cobertura y AP con la prevalencia; accuracy alta por sí sola puede reflejar muchos supervivientes. No se entrenó ni ajustó con estas semillas.',
          'auditoria':'Lista positiva de variables observables; sin IDs, escenario, probabilidad generadora ni desenlaces. Historia causal, ausencia actual suprime inferencia. Los parámetros de mortalidad se conservaron; el ambiente cambió. Los casos son pez/hora, no peces independientes.'}
    dump('informe.json',info)
    print(pd.DataFrame(models).to_string(index=False),flush=True)


if __name__=='__main__':main()
