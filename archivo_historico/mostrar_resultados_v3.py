"""Tablas y figuras del entrenamiento v3 ejecutado en Colab."""
from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, HTML
from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay

out=Path(__file__).resolve().parent/'experimento_v3'
r=pd.read_csv(out/'tablas_resumen.csv')
s=json.loads((out/'seleccion_antes_de_test.json').read_text())
display(HTML('<h1>Resultados del entrenamiento completo v3</h1><p>Datos simulados; 96 corridas y tres horizontes. El conjunto final ya se evaluó localmente: esta ejecución reproduce el protocolo.</p>'))
print('Horizonte preferido en validación:',s['horizonte_preferido'],'horas')
columnas=['horizonte_h','version','politica','aciertos','errores','tp','fp','fn','precision_porcentaje','recall_porcentaje','f1','pr_auc_ap']
tabla=r[columnas].rename(columns={'horizonte_h':'Plazo (h)','version':'Versión','politica':'Política',
    'aciertos':'Aciertos','errores':'Errores','tp':'Avisos correctos','fp':'Falsas alarmas','fn':'Muertes sin aviso (filas)',
    'precision_porcentaje':'Precisión (%)','recall_porcentaje':'Recall (%)','f1':'F1','pr_auc_ap':'AP'})
display(HTML('<h2>1. Aciertos y errores por observación pez/hora</h2><p>En 6 y 12 horas una misma muerte genera varias filas positivas. La política F2 es la principal; recall80 es una alternativa elegida en validación.</p>'))
display(tabla.round(4))
display(HTML('<h2>2. Muertes distintas anticipadas</h2><p>Cuenta una sola vez cada pez muerto que recibió al menos un aviso dentro del plazo.</p>'))
display(pd.read_csv(out/'deteccion_muertes_distintas.csv').round(4))
p=pd.read_csv(out/'predicciones_finales.csv')
fig,axes=plt.subplots(1,3,figsize=(15,4))
for ax,h in zip(axes,[1,6,12]):
    g=p[p.horizonte_h.eq(h)]
    ConfusionMatrixDisplay.from_predictions(g.target,g.alerta.astype(bool),
        display_labels=['Sobrevive','Muere'],ax=ax,colorbar=False)
    ax.set_title(f'Matriz de confusión: {h} horas')
plt.tight_layout();plt.show()
fig,ax=plt.subplots(figsize=(8,5))
for h in [1,6,12]:
    g=p[p.horizonte_h.eq(h)]
    PrecisionRecallDisplay.from_predictions(g.target,g.probabilidad,ax=ax,name=f'{h} h (positivos {g.target.mean():.1%})')
ax.set_title('Precisión y recall: objetivos diferentes según plazo')
plt.tight_layout();plt.show()
display(HTML('<h2>3. Resultados por escenario</h2>'))
display(pd.read_csv(out/'test_por_escenario.csv').round(4))
display(HTML('<h2>4. Búsqueda de configuraciones solo en entrenamiento</h2>'))
display(pd.read_csv(out/'busqueda_cv.csv').groupby(['horizonte_h','config']).ap.agg(['mean','std']).round(4))
display(HTML('<h2>5. Cómo interpretar los resultados</h2>'))
print((out/'LECTURA_RESULTADOS.md').read_text())
print('FINALIZADO: modelos entrenados, verificados y resultados disponibles.')
