"""Empaqueta solo datos simulados y codigo de entrenamiento, sin credenciales."""
from pathlib import Path
import json
import zipfile

BASE = Path(__file__).resolve().parent
codigo = '''# Pisciber BSF: reproduccion del experimento universitario
# Los datos son simulados. Test ya fue evaluado localmente: esto reproduce
# el protocolo, no constituye una prueba nueva e independiente.
from pathlib import Path
import zipfile
import sys
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import files
from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay

print("Selecciona Pisciber_Colab.zip, preparado con los datos vigentes.")
subidos = files.upload()
nombre = next(n for n in subidos if n.endswith('.zip'))
carpeta = Path('/content/pisciber')
carpeta.mkdir(exist_ok=True)
permitidos = {'datos.csv', 'experimento_mortalidad.py', 'entrenar_mortalidad.py', 'SUPUESTOS_SIMULACION.md'}
with zipfile.ZipFile(nombre) as z:
    assert set(z.namelist()) == permitidos, 'El paquete no es el esperado'
    for fichero in permitidos:
        (carpeta/fichero).write_bytes(z.read(fichero))
sys.path.insert(0, str(carpeta))
from experimento_mortalidad import entrenar, FEATURES

df = pd.read_csv(carpeta/'datos.csv')
assert len(df) == 158451, 'Usa el dataset vigente'
assert not df.duplicated(['corrida_id', 'pez_id', 'hora_sim']).any()
assert df.groupby('corrida_id').particion.nunique().eq(1).all()
assert df[FEATURES].notna().all().all()
assert set(df.particion.unique()) == {'train', 'calibracion', 'validacion', 'test'}
print('Filas:', len(df), '| Corridas:', df.corrida_id.nunique())
display(df.groupby('particion').agg(filas=('pez_id','size'), corridas=('corrida_id','nunique'), muertes=('muere_siguiente_hora','sum')))

# Compara Logistica, Random Forest y XGBoost. Elige por AP en validacion,
# calibra en corridas reservadas y elige umbral F2 sin usar test.
salida = carpeta/'resultados'
salida.mkdir(exist_ok=True)
entrenar(df, salida)
print('Comparacion de modelos:')
display(pd.read_csv(salida/'comparativa_validacion.csv'))
pred = pd.read_csv(salida/'predicciones_test.csv')
import json
resultado = json.loads((salida/'evaluacion_test.json').read_text())
print('Modelo seleccionado:', resultado['modelo'])
print('Datos simulados: el rendimiento no acredita validez en acuarios reales.')
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
ConfusionMatrixDisplay.from_predictions(pred.muere_siguiente_hora, pred.alerta.astype(bool),
    display_labels=['Sobrevive 1 h', 'Muere en 1 h'], ax=axes[0], colorbar=False)
axes[0].set_title('Mortalidad: matriz de confusion en test')
PrecisionRecallDisplay.from_predictions(pred.muere_siguiente_hora, pred.probabilidad_muerte_1h, ax=axes[1])
axes[1].axhline(pred.muere_siguiente_hora.mean(), linestyle='--', color='gray', label='Prevalencia')
axes[1].set_title('Mortalidad: precision y recall en test')
axes[1].legend()
plt.tight_layout()
plt.show()
print('Alertas por pecera y especie (numero esperado, no certeza de muerte):')
display(pd.read_csv(salida/'alertas_por_pecera.csv').head(15))
print('Archivos guardados en', salida)
import shutil
paquete = shutil.make_archive('/content/Resultados_Pisciber', 'zip', salida)
display(__import__('IPython').display.FileLink(paquete))
print('TERMINADO: entrenamiento, calibracion y evaluacion completados.')
'''

if __name__ == '__main__':
    archivos = {
        'datos.csv': BASE/'experimento_v2/datos.csv',
        'experimento_mortalidad.py': BASE/'experimento_mortalidad.py',
        'entrenar_mortalidad.py': BASE/'entrenar_mortalidad.py',
        'SUPUESTOS_SIMULACION.md': BASE/'SUPUESTOS_SIMULACION.md',
    }
    with zipfile.ZipFile(BASE/'Pisciber_Colab.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for nombre, origen in archivos.items():
            z.write(origen, nombre)
    nb = {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','name':'python3'},'language_info':{'name':'python'}},
        'cells':[{'cell_type':'markdown','metadata':{},'source':['# Pisciber BSF — Mortalidad con XGBoost\n','Datos simulados. Reproduccion del protocolo local; no es una prueba biologica nueva.\n']},
                 {'cell_type':'code','metadata':{},'source':codigo.splitlines(True),'outputs':[],'execution_count':None}]}
    (BASE/'Pisciber_BSF_Colab.ipynb').write_text(json.dumps(nb, ensure_ascii=False, indent=2), encoding='utf-8')
    compile(codigo, '<colab>', 'exec')
    print('Paquete y notebook preparados:', (BASE/'Pisciber_Colab.zip').stat().st_size, 'bytes')
