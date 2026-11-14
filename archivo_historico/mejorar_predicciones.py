"""Experimento v3: historia de exposicion y horizontes 1, 6 y 12 horas.

Protocolo fijado antes de abrir test. No modifica el mecanismo de mortalidad.
Ejecutar: py -u mejorar_predicciones.py
"""
from pathlib import Path
import json
import hashlib
import joblib
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import average_precision_score, precision_recall_curve
from xgboost import XGBClassifier
from entrenar_mortalidad import pipeline
from experimento_mortalidad import BASE, FEATURES, generar, metricas, predecir, escribir_json

SALIDA = BASE/'experimento_v3'
HORIZONTES = [1, 6, 12]
CONFIGS = [
    {'max_depth':3, 'n_estimators':180, 'learning_rate':.05, 'peso':1.},
    {'max_depth':4, 'n_estimators':240, 'learning_rate':.04, 'peso':3.},
    {'max_depth':5, 'n_estimators':180, 'learning_rate':.05, 'peso':6.},
]


def historia(df):
    d = df.sort_values(['corrida_id','pez_id','hora_sim']).reset_index(drop=True).copy()
    nuevas = []
    for c in ['nh3_mg_n_l','ox_deficit','temp_desvio','ph_desvio']:
        g = d.groupby(['corrida_id','pez_id'],sort=False)[c]
        for ventana in [6,12,24]:
            nombre = f'{c}_media_{ventana}h'
            d[nombre] = g.transform(lambda s:s.rolling(ventana,min_periods=1).mean())
            nuevas.append(nombre)
        for sufijo, fun in [('acumulado',lambda s:s.cumsum()),('max24h',lambda s:s.rolling(24,min_periods=1).max())]:
            nombre = c+'_'+sufijo
            d[nombre] = g.transform(fun)
            nuevas.append(nombre)
    return d, FEATURES+nuevas


def objetivo(d, eventos, horizonte, fin=96):
    # Exigir horizonte completo ANTES del fin administrativo tanto a positivos
    # como a negativos evita favorecer positivos con seguimiento mas corto.
    e = eventos[eventos.evento.eq('muerte')][['corrida_id','pez_id','hora_evento']]
    x = d[d.hora_sim+horizonte <= fin].merge(e,on=['corrida_id','pez_id'],how='left',validate='many_to_one')
    assert (x.hora_evento.isna() | x.hora_evento.gt(x.hora_sim)).all()
    y = (x.hora_evento.gt(x.hora_sim)&x.hora_evento.le(x.hora_sim+horizonte)).astype(int)
    if horizonte == 1:
        assert np.array_equal(y, x.muere_siguiente_hora)
    x['target'] = y
    return x.drop(columns=['hora_evento'])


def modelo(config):
    p = dict(config)
    peso = p.pop('peso')
    return XGBClassifier(**p,scale_pos_weight=peso,subsample=.85,colsample_bytree=.85,
        min_child_weight=8,reg_lambda=5,tree_method='hist',n_jobs=4,random_state=42,eval_metric='logloss')


def calibrar(m, ca, features):
    p = m.predict_proba(ca[features])[:,1]
    return LogisticRegression(C=1e6).fit(logit(np.clip(p,1e-6,1-1e-6)).reshape(-1,1),ca.target)


def umbrales(y,p):
    pr,re,th = precision_recall_curve(y,p)
    f2 = 5*pr[:-1]*re[:-1]/np.maximum(4*pr[:-1]+re[:-1],1e-12)
    # Se informan alternativas definidas solo en validacion: mejor F2 y
    # maxima precision entre puntos con recall >=80% (no promesa en test).
    candidatos = np.flatnonzero(re[:-1]>=.8)
    idx = candidatos[np.argmax(pr[candidatos])] if len(candidatos) else 0
    return {'F2':float(th[np.argmax(f2)]),'recall80_validacion':float(th[idx])}


def ejecutar():
    SALIDA.mkdir(exist_ok=True)
    protocolo = {'semilla_base':9022026,'replicas_por_escenario':16,'horizontes_h':HORIZONTES,
        'configuraciones':CONFIGS,'seleccion_config':'AP media de GroupKFold(3) por corrida en train',
        'seleccion_horizonte':'Mayor F2 de validacion; objetivos distintos, no equivalentes',
        'politicas':['F2','recall80_validacion'],'fin_h':96,
        'advertencia':'Mecanismo de mortalidad intacto. No optimizar usando test.',
        'codigo_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    ruta = SALIDA/'protocolo.json'
    if (SALIDA/'evaluacion_final.csv').exists():
        raise RuntimeError('Experimento terminado; no sobrescribir test. Use un experimento nuevo.')
    escribir_json(ruta,protocolo)
    # Reanudar solo datos de este protocolo; se comprueba semilla y archivo.
    if (SALIDA/'datos.csv').exists():
        meta = json.loads((SALIDA/'metadatos.json').read_text())
        assert meta['semilla_base']==9022026 and meta['replicas_por_escenario']==16
        d = pd.read_csv(SALIDA/'datos.csv')
    else:
        d = generar(BASE/'exportaciones/MEGA_DATOS_ML.csv',SALIDA,replicas=16,horas=96,semilla_base=9022026)
    e = pd.read_csv(SALIDA/'eventos.csv')
    d, features = historia(d)
    escribir_json(SALIDA/'predictores.json',features)
    validaciones, cv, bundles, bases = [], [], {}, {}
    for h in HORIZONTES:
        x = objetivo(d,e,h)
        partes = {p:x[x.particion.eq(p)].reset_index(drop=True) for p in ['train','calibracion','validacion','test']}
        for pa,a in partes.items():
            assert a.target.nunique()==2
            for pb,b in partes.items():
                if pa!=pb: assert not set(a.corrida_id)&set(b.corrida_id)
        tr,ca,va = [partes[p] for p in ['train','calibracion','validacion']]
        folds = list(GroupKFold(3).split(tr,tr.target,tr.corrida_id))
        for ci,config in enumerate(CONFIGS):
            for fold,(i,j) in enumerate(folds):
                print(f'Horizonte {h}h config {ci+1}/3 fold {fold+1}/3',flush=True)
                m = pipeline(modelo(config),tr[features]).fit(tr.iloc[i][features],tr.target.iloc[i])
                p = m.predict_proba(tr.iloc[j][features])[:,1]
                cv.append({'horizonte_h':h,'config':ci,'fold':fold,'ap':average_precision_score(tr.target.iloc[j],p)})
        scores = pd.DataFrame(cv)
        elegido = int(scores[scores.horizonte_h.eq(h)].groupby('config').ap.mean().idxmax())
        m = pipeline(modelo(CONFIGS[elegido]),tr[features]).fit(tr[features],tr.target)
        cal = calibrar(m,ca,features)
        pv = predecir(m,cal,va[features])
        ths = umbrales(va.target,pv)
        for politica,th in ths.items():
            met = metricas(va.target,pv,th)
            f2 = 5*met['precision']*met['recall']/max(4*met['precision']+met['recall'],1e-12)
            validaciones.append({'horizonte_h':h,'politica':politica,'config':elegido,'umbral':th,'f2':f2,**met})
        bundles[h] = {'pipeline':m,'calibrador':cal,'features':features,'umbrales':ths,'horizonte_h':h,'config':elegido}
        bases[h] = partes
    pd.DataFrame(cv).to_csv(SALIDA/'busqueda_cv.csv',index=False)
    v = pd.DataFrame(validaciones)
    v.to_csv(SALIDA/'validacion.csv',index=False)
    preferido = int(v[v.politica.eq('F2')].sort_values('f2',ascending=False).iloc[0].horizonte_h)
    escribir_json(SALIDA/'seleccion_antes_de_test.json',{'horizonte_preferido':preferido,'politica':'F2'})
    # Baseline sin historia nueva: misma familia de modelo y las mismas corridas.
    # Se fija antes de calcular cualquier metrica de test.
    tr,ca,va = [bases[1][p] for p in ['train','calibracion','validacion']]
    base = pipeline(modelo(CONFIGS[0]),tr[FEATURES]).fit(tr[FEATURES],tr.target)
    bc = calibrar(base,ca,FEATURES)
    bt = umbrales(va.target,predecir(base,bc,va[FEATURES]))['F2']
    resultados, por_grupo, predicciones = [], [], []
    for h,b in bundles.items():
        print(f'Evaluacion final cerrada {h}h',flush=True)
        te = bases[h]['test']
        p = predecir(b['pipeline'],b['calibrador'],te[features])
        joblib.dump(b,SALIDA/f'modelo_{h}h.joblib')
        for politica,th in b['umbrales'].items():
            resultados.append({'horizonte_h':h,'politica':politica,'version':'historia_24h',
                'n':len(te),'positivos':int(te.target.sum()),'prevalencia':float(te.target.mean()),
                'umbral':th,**metricas(te.target,p,th)})
        th = b['umbrales']['F2']
        pr = te[['corrida_id','pecera_id','pez_id','hora_sim','especie_nombre','escenario','target']].copy()
        pr['horizonte_h']=h; pr['probabilidad']=p; pr['alerta']=p>=th
        predicciones.append(pr)
        for escenario,g in pr.groupby('escenario'):
            por_grupo.append({'horizonte_h':h,'escenario':escenario,'n':len(g),**metricas(g.target,g.probabilidad.to_numpy(),th)})
        if h==1:
            pb = predecir(base,bc,te[FEATURES])
            resultados.append({'horizonte_h':1,'politica':'F2','version':'sin_historia_nueva',
                'n':len(te),'positivos':int(te.target.sum()),'prevalencia':float(te.target.mean()),
                'umbral':bt,**metricas(te.target,pb,bt)})
    tabla = pd.DataFrame(resultados)
    tabla.to_csv(SALIDA/'evaluacion_final.csv',index=False)
    pd.concat(predicciones).to_csv(SALIDA/'predicciones_finales.csv',index=False)
    pd.DataFrame(por_grupo).to_csv(SALIDA/'test_por_escenario.csv',index=False)
    texto = ['# Comparacion de horizontes y mejora de XGBoost','',
        f'Horizonte elegido en validacion antes de abrir test: {preferido} horas. Politica principal F2.',
        '96 corridas nuevas (72 entrenamiento, 6 calibracion, 6 validacion, 12 test). '
        'Semillas distintas al experimento anterior. El mecanismo de mortalidad no se modifico.',
        'La historia usa solo mediciones disponibles hasta t, incluidas medias de 6, 12 y 24 h, maximos y exposicion acumulada.',
        'Se compararon profundidad, numero de arboles y peso de muertes con validacion cruzada agrupada por corrida.',
        'Los objetivos 1, 6 y 12 h tienen distintas prevalencias y muestras por censura. '
        'Una mejor metrica a 12 h no demuestra mejora para predecir muertes a 1 h.',
        'Para horizontes largos una misma muerte puede producir varias filas positivas previas. '
        'TP no equivale al numero de peces muertos distintos. Las metricas son por observacion pez/hora.',
        'La politica recall80 exige 80% en validacion; no garantiza ese recall en test.', '', '## Test']
    for r in resultados:
        texto.append(f"- {r['version']} {r['horizonte_h']}h {r['politica']}: precision={r['precision']:.2%}, "
            f"recall={r['recall']:.2%}, F1={r['f1']:.4f}, AP={r['pr_auc_ap']:.4f}, "
            f"referencia AP={r['prevalencia']:.4f}; TP={r['tp']}, FP={r['fp']}, FN={r['fn']}.")
    texto += ['', 'Los supuestos biologicos y la aleatoriedad siguen limitando las predicciones. '
        'No se reclama un resultado excelente por haber cambiado horizonte o aumentado alertas. '
        'No reajustar modelos con estos test; nuevos cambios requieren semillas finales nuevas.']
    (SALIDA/'INFORME.md').write_text('\n'.join(texto),encoding='utf-8')
    print(tabla.to_string(index=False),flush=True)


if __name__=='__main__':
    from mejorar_predicciones import ejecutar
    ejecutar()
