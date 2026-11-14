"""Reconciliacion y resumen v3, sin seleccionar ni ajustar con test."""
import json
import zipfile
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from mejorar_predicciones import SALIDA, HORIZONTES
from experimento_mortalidad import BASE, predecir


def revisar():
    out=SALIDA
    res=pd.read_csv(out/'evaluacion_final.csv')
    pred=pd.read_csv(out/'predicciones_finales.csv')
    eventos=pd.read_csv(out/'eventos.csv')
    datos=pd.read_csv(out/'datos.csv')
    from mejorar_predicciones import historia, objetivo
    historicos, features=historia(datos)
    seleccion=json.loads((out/'seleccion_antes_de_test.json').read_text())
    controles=[]
    for h in HORIZONTES:
        p=pred[pred.horizonte_h.eq(h)]
        assert not p.duplicated(['corrida_id','pez_id','hora_sim']).any()
        row=res[(res.horizonte_h.eq(h)) & res.version.eq('historia_24h') & res.politica.eq('F2')].iloc[0]
        y=p.target.eq(1); a=p.alerta.astype(bool)
        tn=int((~y & ~a).sum()); fp=int((~y & a).sum())
        fn=int((y & ~a).sum()); tp=int((y & a).sum())
        assert [tn,fp,fn,tp] == [row.tn,row.fp,row.fn,row.tp]
        muertes=eventos[eventos.corrida_id.isin(p.corrida_id.unique()) & eventos.evento.eq('muerte')]
        detectadas=len(p[y & a][['corrida_id','pez_id']].drop_duplicates())
        assert detectadas<=len(muertes)
        controles.append({'horizonte_h':h,'muertes_distintas_test':len(muertes),
            'muertes_con_al_menos_un_aviso':detectadas,
            'recall_por_muerte_distinta':detectadas/len(muertes),
            'observaciones_test':len(p),'tp_observaciones':tp,'falsas_alarmas_observaciones':fp})
        bundle=joblib.load(out/f'modelo_{h}h.joblib')
        assert set(bundle['features']).isdisjoint({'target','corrida_id','pez_id','escenario','particion','hora_sim'})
        candidatos=objetivo(historicos,eventos,h)
        primeros=candidatos[candidatos.particion.eq('test')].head(100)
        replay=predecir(bundle['pipeline'],bundle['calibrador'],primeros[features])
        np.testing.assert_allclose(replay,p.probabilidad.head(100),rtol=1e-7,atol=1e-9)
        anticipos=p[y & a].merge(muertes[['corrida_id','pez_id','hora_evento']],on=['corrida_id','pez_id'])
        anticipos['anticipacion_h']=anticipos.hora_evento-anticipos.hora_sim
        assert anticipos.anticipacion_h.between(1,h).all()
        primero=anticipos.groupby(['corrida_id','pez_id']).anticipacion_h.max()
        controles[-1]['anticipacion_mediana_h_en_detectados']=float(primero.median())
    pd.DataFrame(controles).to_csv(out/'deteccion_muertes_distintas.csv',index=False)
    versiones={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
        'scikit-learn':sklearn.__version__,'xgboost':xgboost.__version__,'joblib':joblib.__version__}
    (out/'versiones.json').write_text(json.dumps(versiones,indent=2),encoding='utf-8')
    resumen=res.copy()
    resumen['aciertos']=res.tn+res.tp
    resumen['errores']=res.fp+res.fn
    resumen['alertas']=res.tp+res.fp
    for c in ['precision','recall','prevalencia','accuracy']:
        resumen[c+'_porcentaje']=100*res[c]
    resumen.to_csv(out/'tablas_resumen.csv',index=False)
    texto=['# Como interpretar los resultados mejorados','',
        f'Filas nuevas: {len(datos):,}; corridas: {datos.corrida_id.nunique()}.',
        f"Horizonte preferido antes de test: {seleccion['horizonte_preferido']} h.",
        'Los resultados con historia y sin historia a 1 h usan las mismas corridas de test. '
        'La version con historia incorpora tambien seleccion de configuracion; la diferencia no aisla solo el efecto de historia.',
        'Comparar recall entre 1 y 12 h cambia la pregunta. Se presentan todas las filas, no solo la mejor.', '',
        '## Muertes distintas anticipadas (al menos un aviso dentro del horizonte)']
    for c in controles:
        texto.append(f"- {c['horizonte_h']} h: {c['muertes_con_al_menos_un_aviso']} de {c['muertes_distintas_test']} "
                     f"muertes distintas ({c['recall_por_muerte_distinta']:.1%}). "
                     f"Falsas alarmas por observacion: {c['falsas_alarmas_observaciones']}.")
    texto += ['', 'Un aviso puede repetirse para un mismo pez en distintas horas. '
        'No sumar las muertes anticipadas de distintos horizontes ni confundir TP de observaciones con peces distintos.',
        'Una falsa alarma significa que no murio dentro del horizonte evaluado, no que nunca murio.',
        'El rendimiento es el obtenido; no se garantiza alcanzar una precision o recall deseados.',
        'Si se modifican modelos tras observar este test, debe reservarse otro conjunto de semillas nuevas.']
    texto += ['', '## Revision de exactitud elevada',
        'La exactitud a 1 h supera 0,98, pero siempre predecir supervivencia alcanza '
        f"{1-res[res.horizonte_h.eq(1)].prevalencia.iloc[0]:.4%}. "
        'No se considera por ello un resultado casi perfecto: se revisaron variables permitidas, '
        'causalidad de la historia, eventos, censura, corridas disjuntas y reproduccion de predicciones guardadas. '
        'El ROC-AUC no supera 0,98. Estos controles no prueban ausencia absoluta de fuga.']
    (out/'LECTURA_RESULTADOS.md').write_text('\n'.join(texto),encoding='utf-8')
    archivos=['evaluacion_final.csv','tablas_resumen.csv','validacion.csv','busqueda_cv.csv',
        'deteccion_muertes_distintas.csv','test_por_escenario.csv','INFORME.md','LECTURA_RESULTADOS.md',
        'protocolo.json','seleccion_antes_de_test.json','versiones.json','predictores.json',
        'modelo_1h.joblib','modelo_6h.joblib','modelo_12h.joblib','corridas.csv','metadatos.json']
    with zipfile.ZipFile(BASE/'Resultados_Pisciber_v3.zip','w',zipfile.ZIP_DEFLATED) as z:
        for n in archivos:z.write(out/n,n)
        for n in ['mejorar_predicciones.py','experimento_mortalidad.py','entrenar_mortalidad.py',
                  'revisar_mejora.py','test_mejora.py','requirements-ml.txt','SUPUESTOS_SIMULACION.md']:
            z.write(BASE/n,'codigo/'+n)
    print(res[['horizonte_h','version','politica','precision','recall','f1','pr_auc_ap','tp','fp','fn']].to_string(index=False))
    print('VERIFICADO:',len(datos),'filas;',len(controles),'horizontes; modelo y etiquetas reconciliados.')


if __name__=='__main__':revisar()
