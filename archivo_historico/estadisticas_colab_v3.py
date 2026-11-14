"""Porcentajes e intervalos por corrida; no modifica ni entrena el modelo."""
from pathlib import Path
import numpy as np
import pandas as pd
from IPython.display import display, HTML


def estadisticas(out):
    out=Path(out)
    r=pd.read_csv(out/'evaluacion_final.csv')
    p=pd.read_csv(out/'predicciones_finales.csv')
    def div(a,b): return np.divide(a,b,out=np.full(np.shape(a),np.nan),where=np.asarray(b)!=0)
    def porcentajes(t):
        t=t.copy()
        t['Aciertos (%)']=100*div(t.tp+t.tn,t.n)
        t['Errores (%)']=100*div(t.fp+t.fn,t.n)
        t['Muertes detectadas (%)']=100*div(t.tp,t.tp+t.fn)
        t['Muertes omitidas (%)']=100*div(t.fn,t.tp+t.fn)
        t['Alertas correctas (%)']=100*div(t.tp,t.tp+t.fp)
        t['Alertas falsas (%)']=100*div(t.fp,t.tp+t.fp)
        t['Falsa alarma entre supervivencias (%)']=100*div(t.fp,t.fp+t.tn)
        t['Supervivencias identificadas (%)']=100*div(t.tn,t.fp+t.tn)
        t['Supervivencia entre casos sin alerta (%)']=100*div(t.tn,t.tn+t.fn)
        return t
    tablas=porcentajes(r)
    display(HTML('<h1>Porcentajes de errores y evaluación estadística v3</h1><p>Porcentajes por observación pez/hora, no por peces distintos. No existe un único porcentaje que certifique confiabilidad.</p>'))
    cols=['horizonte_h','version','politica','n','Aciertos (%)','Errores (%)','Muertes detectadas (%)',
        'Muertes omitidas (%)','Alertas correctas (%)','Alertas falsas (%)']
    display(tablas[cols].round(2))
    display(HTML('<h2>Falsas alarmas y predicciones de supervivencia</h2>'))
    display(tablas[['horizonte_h','version','politica','Falsa alarma entre supervivencias (%)',
        'Supervivencias identificadas (%)','Supervivencia entre casos sin alerta (%)']].round(2))
    display(HTML('<h2>Intervalos de incertidumbre del 95 %</h2><p>Se remuestrean corridas completas. Describen variación de esta prueba simulada; no son una garantía de que el modelo vaya a acertar ese porcentaje.</p>'))
    rng=np.random.default_rng(814)
    intervalos=[]
    for h,g in p.groupby('horizonte_h'):
        g=g.copy(); y=g.target.eq(1); a=g.alerta.astype(bool)
        g['tp']=(y&a).astype(int); g['fp']=(~y&a).astype(int)
        g['fn']=(y&~a).astype(int); g['tn']=(~y&~a).astype(int)
        bloques=g.groupby('corrida_id')[['tp','fp','fn','tn']].sum().to_numpy()
        seleccion=rng.integers(0,len(bloques),size=(500,len(bloques)))
        sums=bloques[seleccion].sum(axis=1)
        a,b,c,d=sums.T
        medidas={'Muertes detectadas (%)':100*div(a,a+c),'Alertas correctas (%)':100*div(a,a+b),
            'Errores (%)':100*div(b+c,a+b+c+d)}
        for nombre,valores in medidas.items():
            lo,hi=np.nanquantile(valores,[.025,.975])
            intervalos.append({'Plazo (h)':h,'Política':'F2','Indicador':nombre,'Límite inferior (%)':lo,'Límite superior (%)':hi})
    ic=pd.DataFrame(intervalos)
    display(ic.round(2))
    display(HTML('<h2>Desglose por escenario y especie</h2><p>Los grupos pequeños tienen más incertidumbre. No usar estos test para cambiar umbrales.</p>'))
    desgloses=[]
    for dimension in ['escenario','especie_nombre']:
        filas=[]
        for (h,grupo),g in p.groupby(['horizonte_h',dimension]):
            y=g.target.eq(1);a=g.alerta.astype(bool)
            filas.append({'horizonte_h':h,'Grupo':grupo,'n':len(g),'tp':int((y&a).sum()),
                'fp':int((~y&a).sum()),'fn':int((y&~a).sum()),'tn':int((~y&~a).sum())})
        t=porcentajes(pd.DataFrame(filas)); t['dimension']=dimension;desgloses.append(t)
        print('Agrupación:',dimension)
        display(t[['horizonte_h','Grupo','n','tp','fp','fn','Aciertos (%)','Errores (%)',
            'Muertes detectadas (%)','Alertas correctas (%)']].round(2))
    display(HTML('<h2>Guía para leerlo</h2><p><b>Muertes detectadas:</b> cuántas muertes consiguió anticipar. <b>Alertas correctas:</b> cuántos avisos terminaron en muerte dentro del plazo. <b>Alertas falsas:</b> avisos que no terminaron en muerte dentro de ese plazo. Un mismo pez puede generar varios avisos. La exactitud alta puede deberse a que casi todos sobreviven.</p>'))
    tablas.to_csv(out/'porcentajes_completos.csv',index=False)
    ic.to_csv(out/'intervalos_por_corrida.csv',index=False)
    pd.concat(desgloses).to_csv(out/'porcentajes_por_grupo.csv',index=False)
    print('ESTADÍSTICAS COMPLETAS: porcentajes e intervalos calculados sin modificar el modelo.')


if __name__=='__main__':
    import sys
    estadisticas(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parent/'experimento_v3')
