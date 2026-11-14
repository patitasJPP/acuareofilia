# Simulación v2: uso, supuestos y evaluación

El proyecto continúa usando React, FastAPI, el registro de corridas existente y los modelos XGBoost calibrados a 1, 6 y 12 horas. Las nuevas simulaciones utilizan `simulacion/motor/realistic_engine.py`. El motor v1 se mantiene para leer checkpoints antiguos y reproducir aquellas corridas. Los datos originales y los modelos no fueron sustituidos.

## Qué cambió

1. Cada pecera contiene una especie y arranca cerca del centro de sus rangos de temperatura y pH. Se evita mezclar una trucha de agua fría con especies de agua cálida bajo una misma condición inicial arbitraria.
2. Se configuran 1–80 peces, 100–10000 litros y una de las siete fichas existentes por pecera. Las fichas son datos del proyecto; no se presentan como recomendaciones de manejo verificadas.
3. Los incidentes pueden ser leves, moderados o severos, con inicio y duración explícitos. Comienzan gradualmente durante tres horas. Al finalizar, el agua se recupera progresivamente; no vuelve instantáneamente a su estado inicial.
4. Se relacionan biomasa, consumo de oxígeno, excreción, filtración y TAN. El calor reduce la saturación de oxígeno; la actividad del filtro depende del oxígeno y tarda en recuperarse. El perfil diario introduce variaciones suaves.
5. El usuario puede actuar sobre equipos y agua. Cada decisión guarda hora solicitada, hora efectiva, pecera, valor y duración.
6. Se conserva una bitácora con incidentes, muertes, fallos de sensores y acciones. Las lecturas de agua continúan aunque una pecera quede vacía.
7. La navegación histórica no recibe actualizaciones atrasadas del presente. Se añaden botones anterior/siguiente, entrada de hora, reproducción histórica, reinicio y ramas.

## Qué representa el agua

Cada avance corresponde a una hora. El motor calcula el agua y las intervenciones de ese intervalo, aplica la mortalidad estocástica y registra los supervivientes y mediciones del cierre. El modelo utiliza mediciones disponibles hasta ese cierre para predecir el siguiente plazo. La probabilidad interna que decide muertes y la vulnerabilidad oculta no se entregan al modelo.

- Temperatura: relajación hacia una referencia por especie, ciclo diario e incidente; cambio máximo de 0,6 °C por paso. Este límite es un supuesto numérico del proyecto.
- pH: relajación hacia una referencia, ciclo e incidente, con cambio máximo de 0,12 por paso. No modela alcalinidad ni equilibrio ácido-base completo.
- TAN: entradas en mg N/L por biomasa, alimentación y residuos; salida por filtro. No hay recambio automático oculto cada 24 horas.
- NH₃-N: fracción de TAN dependiente de temperatura y pH, usando la función existente `nh3_desde_tan`. TAN y NH₃-N se expresan como masa de nitrógeno, no de molécula NH₃.
- Oxígeno: intercambio gaseoso hacia saturación, menos respiración y demanda por filtración/nitrificación y residuos. Se incluye una oscilación diaria pequeña. La aproximación de saturación supone agua dulce a nivel del mar; no modela salinidad ni altitud.
- Mortalidad: conserva `riesgo_horario` y la distribución de `parametros_corrida` del experimento previo. Depende de exposición actual, carga acumulada y variabilidad oculta. No se fuerza una cuota de muertos ni se garantiza supervivencia tras una acción.

Las relaciones generales entre temperatura, oxígeno y aireación se apoyan en [FAO, Aeration and Oxygenation in Aquaculture](https://www.fao.org/4/x5744e/x5744e0m.htm). La dependencia de la toxicidad del amoníaco respecto a pH y temperatura se describe en [EPA, Aquatic Life Criteria – Ammonia](https://www.epa.gov/wqc/aquatic-life-criteria-ammonia). Estas fuentes apoyan relaciones generales; **no validan los coeficientes, intensidades ni tasas de muerte elegidos para este proyecto**. Los valores del código siguen siendo supuestos declarados.

## Intervenciones

Las acciones se aceptan con la corrida pausada y la hora actual exacta. Se rechazan envíos de una pantalla atrasada o duplicados del mismo tipo para la misma pecera y hora.

- Aireación: restablece intercambio gaseoso durante la duración elegida.
- Filtro: restablece el equipo; su eficiencia se recupera gradualmente.
- Recambio: sustituye del 5 al 30 % por agua con TAN supuesto cero, temperatura y pH de referencia. Mantiene volumen y peces. La mezcla del pH es una aproximación, no una ecuación química completa. Se aplica una sola vez.
- Temperatura: persigue una referencia dentro de la ficha de la especie, respetando el límite de cambio por hora.

La acción empieza en `efectiva_hora = solicitada_hora + 1`. Si se solicita en 20 durante 12 h, afecta los pasos 21 a 32. Las predicciones de la hora 20 se conservan: el modelo no conocía la decisión futura. El seguimiento marca `intervencion_en_plazo` cuando hubo una acción posterior durante el horizonte pronosticado. Una alerta seguida de supervivencia tras intervenir no demuestra por sí sola que la alerta fuera injustificada.

## Tiempo, reinicio y comparación justa

El motor tiene un único reloj activo en el servidor. Las consultas históricas no lo modifican. Las corridas terminan en 96 h. Reanudar solo continúa corridas con horas pendientes; reproducir historial únicamente cambia la hora que se está mostrando.

Empezar desde cero crea un registro diferente, con igual semilla y configuración y sin acciones previas. Crear copia desde una hora reconstruye exactamente el estado y las decisiones conocidas hasta ese corte, copia las predicciones ya emitidas y elimina de esa copia los desenlaces posteriores al corte. No borra ni altera la corrida de origen.

Cada pecera usa flujos aleatorios separados para inicialización, agua, sensores y mortalidad. En cada paso se extrae un número para todos los peces iniciales, incluso para los ya muertos. Así, una intervención no desplaza los números aleatorios que reciben otros peces. Una acción en una pecera no cambia la aleatoriedad de las otras dos.

La comparación exige igual semilla, ambiente, motor y configuración, y utiliza la hora menor entre ambas corridas. Puede comparar una original sin acciones con una rama intervenida. No garantiza que una acción siempre ayude; el resultado depende del estado, la acción y el azar. Las ramas con una misma semilla no son réplicas independientes. Para evaluar una política, hay que repetir parejas con varias semillas y reservar otras para la evaluación final.

## Sensores y datos faltantes

El perfil normal contiene ruido; el intermitente añade deriva limitada y cortes de una a tres horas. Los valores internos del agua siguen evolucionando durante el corte, pero no se muestran como mediciones.

Una lectura actual ausente impide emitir una nueva predicción. El riesgo queda vacío, no vale 0 %, y no se cuenta como supervivencia correcta en las métricas. El resumen informa cuántos peces pudieron evaluarse y cuántos quedaron sin predicción.

Para formar historia se permite arrastrar hasta dos lecturas anteriores, nunca usar datos futuros. Desde ese momento la salida se marca `historia_estimada`, porque también se utilizan acumulados. Si un hueco queda sin resolver después de ese límite, se marca `historial_incompleto` y se suspende la inferencia restante de ese pez: el modelo actual necesita una historia acumulada completa. Esta es una limitación explícita, no un sistema de reconstrucción de sensores. El Excel conserva mediciones ausentes y estados de calidad.

## Evaluación independiente del modelo original

Se ejecutaron 36 corridas nuevas, seis por ambiente, con semillas fijadas antes de mirar los resultados, variación de especies, población, volumen, intensidad y sensores. Se conservaron los modelos y umbrales v3; no se entrenó ni ajustó con estas corridas. El protocolo, hashes, observaciones, eventos, predicciones, métricas e intervalos están en `resultados/validacion_motor_v2/`.

Resultados por observación con predicción y seguimiento completo:

- 1 h: recall 19,39 %, precisión 10,25 %, ROC-AUC 0,913; cobertura 88,63 %.
- 6 h: recall 64,02 %, precisión 15,48 %, ROC-AUC 0,914; cobertura 89,17 %.
- 12 h: recall 71,98 %, precisión 21,80 %, ROC-AUC 0,906; cobertura 89,63 %.

La cobertura es la fracción de observaciones con horizonte completo que dispone de predicción. Los casos sin lectura/historia suficiente se informan por separado. Estos porcentajes no cuentan peces únicos y no se deben mezclar con la prueba original v3 ni con Colab. La evaluación no incluye políticas de intervención; sus resultados no validan probabilidades después de una política nueva.

A 1 h, accuracy es 99,42 % pero solo el 0,23 % de las observaciones evaluadas termina en muerte. Predecir siempre supervivencia daría aproximadamente 99,77 % de accuracy y recall cero. Se revisó la lista positiva de variables y el uso temporal: no entran desenlaces, identificadores, escenarios, parámetros ocultos ni valores futuros. La accuracy alta aquí procede del fuerte desbalance; **no permite afirmar que el modelo sea 99 % confiable**. A 12 h, AP es 0,382 frente a una prevalencia de 0,030, con muchas falsas alarmas todavía.

No se afirma que el modelo mejore por cambiar el simulador. Para reentrenarlo se necesitará otro experimento con particiones por corrida/semilla para entrenamiento, calibración, selección y test nuevo. Las 36 corridas de este informe ya se utilizaron para evaluación y deben conservarse como evidencia de esta versión.

## Comprobar el sistema

Desde la carpeta del proyecto:

```powershell
powershell -File .\verificar.ps1
```

Las pruebas cubren compatibilidad v1, pausa/reanudación repetida, cambio de corrida activa, reinicio preservando el origen, ramas reproducibles, predicciones congeladas, ausencia de futuro, efectos del recambio/aireación, independencia entre peceras, datos ausentes y lecturas de peceras vacías.

El evaluador es `simulacion/ml/evaluar_motor_v2.py`. Se ejecuta como módulo desde la carpeta del proyecto y se niega a sobrescribir `informe.json` si la evaluación ya terminó. No borres el informe para ajustar usando las mismas semillas; crea un nuevo protocolo y conjunto final.

## Revisión del modelo y velocidad: experimento v4

Se completó un experimento nuevo con 96 corridas del mismo motor, sin cambiar su ecuación de mortalidad. Se reservaron corridas completas: 60 para entrenamiento, 12 para calibración, 12 para validación y 12 para test. Semilla base: 471140000; las semillas son distintas de la evaluación v2 anterior. Varían especies, volumen, población, inicio e intensidad del incidente y sensores. Los datos, protocolo, configuraciones, predicciones de test y métricas están en `resultados/entrenamiento_v4/`; el código es `simulacion/ml/entrenar_motor_v2.py`.

Se compararon dos configuraciones XGBoost usando las mismas variables observables. Se calibraron las probabilidades en corridas exclusivas mediante regresión logística sobre el logit. Se eligió configuración y umbral por F1 de validación, exigiendo recall de al menos 65 % allí. El campo interno `umbrales.F2` se conserva por compatibilidad; en los modelos v4 la política real se identifica como `F1_recall65`. Este nombre interno no cambia el criterio usado.

Una vez cerrada la selección, se evaluaron ambos modelos sobre las mismas observaciones del test nuevo:

- A 1 hora, v4 perdió precisión y F1. **Se conserva v3**: precisión 10,67 %, recall 36,99 %. La propuesta v4 permanece guardada como evidencia del experimento y no se utiliza en inferencia.
- A 6 horas, precisión 20,91 % → 28,23 %; falsas alarmas 2103 → 1388; recall 62,19 % → 61,07 %; F1 0,313 → 0,386.
- A 12 horas, precisión 25,45 % → 44,56 %; falsas alarmas 3975 → 1249 (reducción de 68,58 %); recall 75,14 % → 55,59 %; F1 0,380 → 0,495. Las observaciones positivas sin aviso aumentaron de 449 a 802.

El mínimo de detección se exigió en validación y no se alcanzó en test. Se acepta el cambio a 6 y 12 horas por su precisión y F1, mostrando expresamente la pérdida de recall. La decisión de desplegar se tomó después de evaluar; no se volvió a ajustar ningún modelo ni umbral con test. Estas cifras no se comparan directamente con las del apartado anterior: el nuevo test tiene otra población y prevalencia. La comparación válida es v3 contra v4 en estas mismas 12 corridas.

La cobertura fue 84,60 %, 85,29 % y 86,22 % a 1, 6 y 12 horas, respectivamente. Se excluyen del cálculo de métricas las observaciones sin predicción por sensores/historia incompleta y se informa su número. Los casos siguen siendo pez/hora; no equivalen al número de peces muertos distintos. No se validaron políticas de intervención con este experimento.

La accuracy de 1 hora supera 98 % porque solo el 0,19 % de sus casos es positivo. Se revisaron lista de predictores, separación por corrida y causalidad de la historia; no se incluyen muerte, IDs, escenario ni parámetros ocultos. La precisión baja y el recall parcial descartan interpretar esa accuracy como predicción casi perfecta. Se conserva la misma lista de 40 variables observables del modelo anterior.

Las nuevas corridas guardan versión y umbral de cada plazo. Reiniciar o crear una rama preserva esa versión. Las corridas previas continúan con v3. El archivo `simulacion/modelos/activo.json` registra qué modelo se utiliza en cada horizonte de las nuevas corridas. La pantalla y el Excel identifican el modelo aplicado; la evaluación histórica v3 permanece rotulada con su origen.

Para acelerar el motor se sustituyó el recálculo de todo el historial en cada paso por una actualización de la hora nueva. El estado de las variables se guarda dentro del checkpoint. Para checkpoints anteriores se reconstruye una sola vez usando únicamente observaciones guardadas. Una prueba compara todas las variables, disponibilidad y calidad con el cálculo completo durante las 97 observaciones de una corrida, incluidos cortes de sensores.

La medición en la hora 72 pasó de 0,838 s a 0,0133 s para preparar variables, unas 63 veces menos tiempo en esa operación. Excluye inferencia, escritura y navegador: no significa que toda la aplicación sea 63 veces más rápida. El resultado medido está en `resultados/velocidad.json`.

El reloj permite 4× (0,25 s/h), 10× (0,1 s/h) y Máxima (sin espera adicional, salvo cesión breve para atender controles). El ritmo efectivo depende del equipo. Los pasos se procesan en orden sin saltar horas y Pausar conserva el estado. La vista consulta cada 250 ms; puede presentar varias horas de avance entre actualizaciones. El selector del historial permite acelerar su reproducción sin generar observaciones nuevas.
