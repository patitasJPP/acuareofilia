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
