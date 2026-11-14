"""Recupera predicciones de los modelos entrenados en Colab, sin reajustarlos."""
from pathlib import Path
import zipfile
import sys
import joblib
import pandas as pd

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from mejorar_predicciones import historia, objetivo
from experimento_mortalidad import predecir
from estadisticas_colab_v3 import estadisticas

out = BASE/'experimento_v3'
d = pd.read_csv(out/'datos.csv')
e = pd.read_csv(out/'eventos.csv')
d, features = historia(d[d.particion.eq('test')])
r = pd.read_csv(out/'evaluacion_final.csv')
predicciones = []
for h in [1, 6, 12]:
    x = objetivo(d,e,h)
    b = joblib.load(out/f'modelo_{h}h.joblib')
    p = predecir(b['pipeline'],b['calibrador'],x[b['features']])
    a = p >= b['umbrales']['F2']
    y = x.target.eq(1).to_numpy()
    fila = r[r.horizonte_h.eq(h)&r.version.eq('historia_24h')&r.politica.eq('F2')].iloc[0]
    assert [int((y&a).sum()),int((~y&a).sum()),int((y&~a).sum()),int((~y&~a).sum())] == [fila.tp,fila.fp,fila.fn,fila.tn], 'Predicciones distintas de las originales'
    t=x[['corrida_id','pecera_id','pez_id','hora_sim','especie_nombre','escenario','target']].copy()
    t['horizonte_h']=h; t['probabilidad']=p; t['alerta']=a
    predicciones.append(t)
pd.concat(predicciones).to_csv(out/'predicciones_finales.csv',index=False)
print('Predicciones recuperadas: coinciden con los conteos del entrenamiento original de Colab.')
estadisticas(out)
with zipfile.ZipFile(BASE/'Porcentajes_Pisciber.zip','w',zipfile.ZIP_DEFLATED) as z:
    for nombre in ['porcentajes_completos.csv','intervalos_por_corrida.csv','porcentajes_por_grupo.csv','evaluacion_final.csv','deteccion_muertes_distintas.csv']:
        z.write(out/nombre,nombre)
