# Cómo usamos el machine learning en Pisciber BSF

## 1. La idea general

El **simulador** genera peces, condiciones de agua y eventos de muerte simulados. El modelo de machine learning, entrenado previamente con otras simulaciones, usa la información disponible para estimar el riesgo de cada pez. Después, la página permite comparar sus avisos con lo que ocurrió.

Para explicarlo: «El simulador produce los escenarios. XGBoost analiza los datos de los peces y estima su riesgo futuro. Comparamos cada aviso con el resultado simulado para medir aciertos y errores».

## 2. Qué se predice

Hay tres modelos: muerte en las próximas **1, 6 o 12 horas simuladas**. Cada predicción corresponde a un pez vivo en una hora concreta. Por ejemplo, en la hora 10 el modelo de 12 horas estima si el pez morirá entre las horas 11 y 22.

Un riesgo estimado de 60 % es una probabilidad del modelo; no asegura que el pez morirá. Una misma muerte puede generar varias filas positivas en horas previas. Por ello distinguimos **observaciones pez/hora** de **peces muertos distintos**.

## 3. Datos que usamos

El experimento local v3 contiene **311.433 filas y 96 corridas simuladas**, con escenarios estables, de amoníaco, oxígeno bajo, temperatura, pH y combinados. Cada corrida principal tiene tres peceras, 16 peces iniciales por pecera y 96 horas de seguimiento.

Las variables candidatas incluyen especie, peso, pH, temperatura, oxígeno, amoníaco total y NH3-N, volumen, densidad, estado del filtro y la aireación, cambios recientes, desviaciones respecto a la ficha de la especie e historial ambiental. El historial usa medias de 6, 12 y 24 horas, máximos de 24 horas y acumulados de determinadas variables.

La preparación elimina constantes o variables muy correlacionadas según lo aprendido en entrenamiento. Algunas variables candidatas pueden no quedar en el modelo final. Las mediciones y tasas de mortalidad son **simuladas y dependen de supuestos**; no son registros de mortalidad proporcionados por la empresa.

## 4. Cómo evitamos mirar la respuesta

La **fuga de datos** ocurre si el modelo recibe información que revela el resultado futuro. Aquí se excluyen de los predictores los identificadores, la semilla, el escenario, la partición, los eventos futuros y la probabilidad interna usada por el simulador para sortear una muerte. Los desenlaces se usan después para evaluar.

La historia ambiental utiliza datos hasta la hora actual. En vivo primero se calculan las mediciones de esa hora y la predicción; la transición a la siguiente hora ocurre cuando se avanza. Una probabilidad emitida no se recalcula con el futuro.

Para evaluar un plazo se exige seguimiento completo: una predicción de 12 horas emitida en la hora 10 se evalúa al llegar a la hora 22. Si el seguimiento termina antes, queda pendiente o sin evaluar.

## 5. Algoritmo y entrenamiento

Usamos **XGBoost**, que combina muchos árboles de decisión para estimar probabilidades y puede aprender relaciones no lineales entre las variables. El flujo también selecciona columnas, imputa valores, escala datos numéricos y codifica categorías. Un calibrador, ajustado en datos separados, intenta mejorar la correspondencia entre probabilidades estimadas y frecuencias observadas.

Se dividieron las 96 corridas completas: **72 para entrenamiento, 6 para calibración, 6 para validación y 12 para prueba final**. En entrenamiento se compararon tres configuraciones de XGBoost por horizonte mediante `GroupKFold` de tres particiones, agrupando por corrida. Esto evita repartir filas de una misma corrida entre entrenamiento y validación de un mismo pliegue.

La configuración se eligió por precisión promedio (`AP`). En validación se eligieron umbrales y el horizonte preferido, antes de consultar prueba final. El horizonte preferido fue 12 horas: eso no demuestra que la predicción de la siguiente hora haya mejorado, porque son preguntas diferentes.

## 6. Cuándo se emite una alerta

La página compara la probabilidad con un umbral elegido previamente. Para el modelo local de **12 horas**, con política principal F2, es aproximadamente **8,51 %**. Un riesgo igual o superior activa alerta; uno inferior no.

El umbral no es la precisión del modelo. Se eligió con F2, que da más peso a detectar casos positivos. Si se baja, suelen detectarse más casos y aumentar las falsas alarmas; si se sube, pueden reducirse avisos y omitirse más muertes. El valor cambia según el horizonte.

## 7. Resultados de la prueba local v3

Estos valores corresponden al modelo local de Windows, a las 12 corridas de prueba reservadas y al umbral F2. Colab puede dar cifras ligeramente distintas por el entorno; no se deben mezclar resultados y modelos de ejecuciones diferentes.

| Horizonte | Observaciones | Precisión | Recall | F1 | ROC-AUC | AP |
|---|---:|---:|---:|---:|---:|---:|
| 1 hora | 40.555 | 10,76 % | 25,91 % | 0,152 | 0,889 | 0,077 |
| 6 horas | 39.041 | 14,98 % | 80,54 % | 0,253 | 0,885 | 0,350 |
| 12 horas | 37.203 | 24,23 % | 83,15 % | 0,375 | 0,871 | 0,508 |

### Matriz a 12 horas

| Resultado observado dentro del plazo | Sin alerta | Con alerta |
|---|---:|---:|
| Sobrevivió | 25.794 aciertos de supervivencia | 8.240 falsas alarmas |
| Murió | 534 muertes sin aviso | 2.635 avisos correctos |

Son **observaciones pez/hora**, no peces distintos. De 37.203 observaciones hubo 28.429 aciertos y 8.774 errores: exactitud de **76,42 %** y error de **23,58 %**.

De las alertas evaluadas, **24,23 % fueron correctas** y **75,77 % falsas**. De las observaciones con muerte dentro del plazo, el modelo detectó **83,15 %**. Cada porcentaje tiene un denominador distinto.

Si contamos cada pez muerto una sola vez, hubo al menos un aviso dentro de las 12 horas anteriores para **247 de 274 muertes: 90,15 %**. Esto no significa que el 90,15 % de las alertas fueran correctas. Una falsa alarma significa que el pez no murió *dentro del plazo*; podría morir más tarde.

## 8. Qué significa cada métrica

- **Exactitud:** aciertos entre todas las observaciones. Puede parecer alta si casi todos sobreviven.
- **Error:** errores entre todas las observaciones.
- **Precisión:** alertas correctas entre alertas evaluadas. De cada 100 avisos, ¿cuántos correspondieron a una muerte en el plazo?
- **Recall:** casos positivos detectados entre todos los casos positivos. De cada 100 observaciones con muerte en el plazo, ¿cuántas tuvieron alerta?
- **F1:** combina precisión y recall, entre 0 y 1; no reemplaza examinarlas por separado.
- **ROC-AUC:** capacidad de ordenar casos por riesgo a diferentes umbrales; no es el porcentaje de muertes acertadas.
- **PR-AUC / AP:** resume la relación entre precisión y recall; es útil cuando las muertes son poco frecuentes.
- **Brier:** error de las probabilidades; menor es mejor al comparar el mismo problema y datos.
- **Intervalos:** estiman variación entre corridas. Para 12 horas, el intervalo bootstrap del 95 % fue aproximadamente **78,47–88,05 % para recall** y **16,86–33,92 % para precisión**. No garantizan un resultado individual.

## 9. Cómo obtenemos el resumen por pecera

El modelo predice por pez. Para una misma hora y pecera, la web presenta peces vivos, peces con alerta, promedio de riesgos y **muertes esperadas**, calculadas sumando las probabilidades individuales.

Ejemplo inventado: tres peces con riesgos de 20 %, 30 % y 50 % suman **1,0 muerte esperada**. Es un valor esperado, no una promesa de que morirá exactamente un pez. El riesgo medio tampoco es la probabilidad de que muera al menos uno. No se deben sumar resultados de horas consecutivas, pues los peces y plazos se repiten.

## 10. Qué pasa en una simulación nueva

El usuario elige ambiente y semilla. El backend genera cada hora y los modelos guardados producen los riesgos con la información hasta ese momento. La semilla permite reproducir una corrida del mismo motor.

**Una corrida nueva no reentrena el modelo:** utiliza los pesos y umbrales existentes. El motor en vivo usa las ecuaciones generales del simulador por lotes, pero flujos aleatorios separados por pecera; la misma semilla no tiene por qué producir la misma corrida que el motor anterior.

El reloj intenta avanzar una hora por segundo. Si un cálculo tarda más, avanza más lento sin saltar pasos. Sigue con la pestaña cerrada mientras el servidor esté activo y se recupera en pausa si el servidor se reinicia.

## 11. Cómo demostrarlo

1. Inicia una corrida en vivo y explica la hora simulada.
2. Abre un pez y muestra su riesgo, horizonte y condiciones registradas.
3. Enseña la suma de probabilidades por pecera como valor esperado.
4. En **Seguimiento de alertas**, muestra pendientes, avisos correctos y falsas alarmas. Registrar atención documenta una revisión; no modifica el agua ni demuestra que se evitó una muerte.
5. En **Evaluación del modelo**, explica la matriz, precisión y recall sin confundir filas con peces distintos.
6. Compara escenarios y descarga el Excel. La comparación agrupa corridas completas, separa motores y excluye semillas repetidas en el mismo escenario y motor.

## 12. Límites de la conclusión

Los resultados dependen de los supuestos del simulador. El modelo produce falsas alarmas y también omite muertes. La predicción no identifica por sí sola la causa; las sugerencias de revisión usan reglas de fichas y equipos simulados, no son diagnósticos de XGBoost.

No se ha demostrado con estos datos una reducción real de mortalidad o costos de la empresa ni se ha validado con mortalidad observada en una granja. Para el trabajo universitario, se puede explicar su desempeño **en los escenarios simulados evaluados**.

## 13. Archivos de respaldo

**Revisión v4 terminada:** se entrenó con 96 corridas nuevas, separadas por corrida completa: 60 entrenamiento, 12 calibración, 12 validación y 12 test. Las nuevas simulaciones usan v3 a 1 hora y v4 a 6 y 12 horas. En el mismo test nuevo, a 12 h las alertas correctas subieron de 25,45 % a 44,56 % y las falsas alarmas bajaron de 3975 a 1249; a cambio, el recall bajó de 75,14 % a 55,59 %. Por tanto, se reducen las falsas alarmas pero se dejan más observaciones de muerte sin aviso. A 6 h la precisión subió de 20,91 % a 28,23 % con recall de 62,19 % a 61,07 %. El candidato de 1 h se descartó para uso porque perdió precisión y F1. Los umbrales se eligieron en validación y quedaron congelados antes del test. La comparación y sus límites están en la sección final de [SIMULACION_V2.md](proycto%20innovador/documentacion/SIMULACION_V2.md); los resultados completos están en `proycto innovador/resultados/entrenamiento_v4/`.

**Actualización del simulador:** las nuevas corridas usan el motor v2, que permite elegir especies y condiciones, actuar sobre el agua, registrar fallos de sensores y crear ramas históricas. Se mantienen los mismos modelos v3. Las métricas de las secciones anteriores pertenecen al experimento original y no se transfieren automáticamente a v2. La web muestra también la prueba independiente de 36 corridas: a 12 horas, recall 71,98 %, precisión 21,80 % y cobertura 89,63 %. Consulta [la explicación del motor v2](proycto%20innovador/documentacion/SIMULACION_V2.md) para el protocolo, interpretación, sensores e intervenciones.

- `proycto innovador/simulacion/ml/mejorar_predicciones.py`: historia, horizontes y protocolo de entrenamiento.
- `proycto innovador/simulacion/ml/entrenar_mortalidad.py`: selección y preparación.
- `proycto innovador/simulacion/modelos/`: modelos guardados.
- `proycto innovador/simulacion/datos_base/evaluacion_final.csv`: métricas y matriz local.
- `proycto innovador/simulacion/datos_base/deteccion_muertes_distintas.csv`: muertes distintas anticipadas.
- `proycto innovador/simulacion/datos_base/intervalos_por_corrida.csv`: intervalos.
- `proycto innovador/web/backend/live.py` y `analysis.py`: predicciones en vivo y seguimiento.
- `proycto innovador/documentacion/GUIA_PRESENTACION.md`: recorrido práctico para exponer.

## Pronóstico comercial añadido

Para el nuevo experimento de pedidos, ventas, stock y pronóstico semanal, consulta [DEMANDA.md](proycto%20innovador/documentacion/DEMANDA.md). Allí se explican los modelos entrenados, el método seleccionado y los errores de la prueba temporal.
