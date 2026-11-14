"""Reentrenamiento v4 con semillas y particiones fijadas antes de evaluar.

Desde la raíz: .venv/Scripts/python.exe -u -m simulacion.ml.entrenar_motor_v2
Conserva modelos v3 y las evaluaciones previas. No modifica la mortalidad.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import joblib
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve
from xgboost import XGBClassifier

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'simulacion/ml'))
from simulacion.motor.realistic_engine import RealisticEngine, DEFAULT_CONFIG
from simulacion.motor.features import prepare
from entrenar_mortalidad import pipeline
from experimento_mortalidad import metricas, predecir

OUT=ROOT/'resultados/entrenamiento_v4'
DEST=ROOT/'simulacion/modelos/v4'
SCENARIOS=['estable','amonio','hipoxia','termico','ph','combinado']

def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def threshold(y,prob):
    precision,recall,values=precision_recall_curve(y,prob)
    f1=2*precision[:-1]*recall[:-1]/np.maximum(precision[:-1]+recall[:-1],1e-12)
    allowed=np.flatnonzero(recall[:-1]>=.65)
    # Aumentar precisión sin permitir que la selección descarte casi todas las muertes.
    index=allowed[np.argmax(f1[allowed])] if len(allowed) else int(np.argmax(f1))
    return float(values[index])

def main():
    OUT.mkdir(parents=True,exist_ok=True);DEST.mkdir(parents=True,exist_ok=True)
    if (OUT/'informe.json').exists():raise RuntimeError('Evaluación cerrada; no volver a ajustar con estas semillas')
    protocol={'version':'v4','semilla_base':471140000,'corridas':96,'roles':['train']*10+['calibracion']*2+['validacion']*2+['test']*2,
        'regla_semilla':'base + escenario*10000 + replica*101','seleccion':'F1 en validación sujeto a recall >= 65 %',
        'configuraciones':[{'max_depth':3,'n_estimators':180},{'max_depth':4,'n_estimators':240}],
        'calibracion':'Platt en corridas exclusivas de calibración','comparador':'v3 sin modificar sobre el mismo test nuevo',
        'horizontes':[1,6,12],'motor_sha256':hashlib.sha256((ROOT/'simulacion/motor/realistic_engine.py').read_bytes()).hexdigest(),
        'nota':'No se usan las 36 corridas previamente evaluadas ni datos posteriores a t. Sin intervenciones programadas.'}
    write('protocolo.json',protocol)
    fichas=pd.read_csv(ROOT/'simulacion/datos_base/fichas_origen.csv')
    allframes=[];runs=[]
    for si,scenario in enumerate(SCENARIOS):
        for replica,role in enumerate(protocol['roles']):
            cid=si*16+replica;seed=471140000+si*10000+replica*101
            rng=np.random.default_rng(seed+1);config=deepcopy(DEFAULT_CONFIG)
            config.update(intensidad=str(rng.choice(['leve','moderado','severo'])),inicio=int(rng.integers(6,37)),duracion=int(rng.integers(12,49)),sensores='intermitente' if replica%4==3 else 'normal')
            for tank in config['peceras']:
                tank.update(especie=str(rng.choice(fichas.especie_nombre)),peces=int(rng.integers(12,49)),volumen_l=float(rng.integers(600,4001)))
            engine=RealisticEngine(fichas,cid,seed,scenario,config);raw=[]
            for _ in range(97):raw.extend(engine.step())
            obs,features,names=prepare(pd.DataFrame(raw))
            death={e['pez_id']:e['hora_evento'] for e in engine.events}
            x=features.copy()
            for col in ['corrida_id','pez_id','pecera_id','hora_sim','prediccion_disponible']:x[col]=obs[col]
            x['hora_evento']=obs.pez_id.map(death);x['particion']=role
            allframes.append(x)
            runs.append({'corrida_id':cid,'semilla':seed,'escenario':scenario,'particion':role,'muertes':len(engine.events),'configuracion':json.dumps(config,ensure_ascii=False)})
            print(f'Generación {cid+1}/96 · {role} · {scenario}',flush=True)
    data=pd.concat(allframes,ignore_index=True)
    data.to_pickle(OUT/'datos.pkl.gz',compression='gzip');pd.DataFrame(runs).to_csv(OUT/'corridas.csv',index=False)
    assert not {'hora_evento','particion','corrida_id','pez_id','pecera_id','hora_sim','escenario','target'}&set(names)
    results=[];validation=[];bundles={};predictions=[]
    for h in [1,6,12]:
        d=data[data.prediccion_disponible & (data.hora_sim+h<=96)].copy()
        d['target']=(d.hora_evento.gt(d.hora_sim)&d.hora_evento.le(d.hora_sim+h)).astype(int)
        parts={role:d[d.particion.eq(role)] for role in set(protocol['roles'])}
        tr,ca,va=[parts[role] for role in ['train','calibracion','validacion']]
        for a in parts:
            for b in parts:
                if a!=b:assert not set(parts[a].corrida_id)&set(parts[b].corrida_id)
        candidates=[]
        for config in protocol['configuraciones']:
            print(f'Entrenamiento {h} h · {config}',flush=True)
            model=pipeline(XGBClassifier(**config,learning_rate=.045,subsample=.85,colsample_bytree=.9,min_child_weight=10,reg_lambda=6,n_jobs=4,tree_method='hist',random_state=42,eval_metric='logloss'),tr[names]).fit(tr[names],tr.target)
            pc=model.predict_proba(ca[names])[:,1]
            calibrator=LogisticRegression(C=1e6).fit(logit(np.clip(pc,1e-6,1-1e-6)).reshape(-1,1),ca.target)
            pv=predecir(model,calibrator,va[names]);th=threshold(va.target,pv)
            metrics=metricas(va.target,pv,th)
            validation.append({'horizonte_h':h,**config,'umbral':th,**metrics})
            candidates.append((metrics['f1'],{'pipeline':model,'calibrador':calibrator,'features':names,'umbrales':{'F2':th},'politica':'F1_recall65','horizonte_h':h,'version':'v4'},config))
        chosen=max(candidates,key=lambda c:c[0]);bundles[h]=chosen[1]
        write(f'seleccion_{h}h.json',{'configuracion':chosen[2],'umbral':chosen[1]['umbrales']['F2'],'regla':protocol['seleccion']})
    pd.DataFrame(validation).to_csv(OUT/'validacion.csv',index=False)
    # Todas las decisiones están fijadas antes de consultar test.
    for h,new in bundles.items():
        te=data[data.particion.eq('test') & data.prediccion_disponible & (data.hora_sim+h<=96)].copy()
        y=(te.hora_evento.gt(te.hora_sim)&te.hora_evento.le(te.hora_sim+h)).astype(int)
        old=joblib.load(ROOT/f'simulacion/modelos/modelo_{h}h.joblib')
        for version,b in [('v3',old),('v4',new)]:
            prob=predecir(b['pipeline'],b['calibrador'],te[b['features']]);th=b['umbrales']['F2']
            m=metricas(y,prob,th)
            total=int((data.particion.eq('test') & (data.hora_sim+h<=96)).sum())
            results.append({'version':version,'horizonte_h':h,'n':len(te),'prevalencia':float(y.mean()),
                            'cobertura':len(te)/total,'sin_prediccion':total-len(te),'umbral':th,**m})
            pr=te[['corrida_id','pez_id','hora_sim']].copy();pr['target']=y;pr['probabilidad']=prob;pr['version']=version;pr['horizonte_h']=h;predictions.append(pr)
        joblib.dump(new,DEST/f'modelo_{h}h.joblib')
    pd.DataFrame(results).to_csv(OUT/'metricas.csv',index=False)
    pd.concat(predictions).to_csv(OUT/'predicciones_test.csv.gz',compression='gzip',index=False)
    # Decisión de despliegue posterior a la evaluación, sin reajustar modelos.
    deployment={}
    for h in [1,6,12]:
        old,new=[next(r for r in results if r['horizonte_h']==h and r['version']==v) for v in ['v3','v4']]
        deployment[str(h)]='v4' if new['f1']>old['f1'] and new['precision']>old['precision'] else 'v3'
    report={'estado':'evaluado','modelo':'v4','nota':'12 corridas de test nuevas; selección y umbrales definidos en validación, con corridas distintas para calibrar.',
        'comparacion':results,'modelos':[r for r in results if r['version']=='v4'],
        'conclusion':'Comparación sobre las mismas observaciones del test nuevo. Reducir falsas alarmas puede reducir recall. Datos simulados; los porcentajes son por pez/hora y no validan intervenciones nuevas.',
        'despliegue':deployment,'nota_despliegue':'Se conserva v3 en los plazos donde el candidato pierde precisión o F1. La decisión de despliegue se toma después de evaluar; no se cambian umbrales ni parámetros con test.',
        'protocolo':protocol}
    write('informe.json',report)
    (DEST.parent/'activo.json').write_text(json.dumps({'version':'v4','horizontes':deployment,
        'experimento':'resultados/entrenamiento_v4','nota':report['nota_despliegue']},ensure_ascii=False,indent=2),encoding='utf-8')
    print(pd.DataFrame(results).to_string(index=False),flush=True)

if __name__=='__main__':main()
