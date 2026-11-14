# Pisciber BSF · Mortalidad

Aplicación local universitaria: React + Vite y FastAPI/Python. Conserva el modelo XGBoost calibrado del experimento local v3. No incluye demanda ni chatbot.

## Ejecutar

Abre `INICIAR.bat` y visita http://127.0.0.1:8000. Deja la ventana de ejecución abierta. Para detener, pulsa Ctrl+C. También puedes ejecutar `powershell -NoProfile -ExecutionPolicy Bypass -File iniciar.ps1`.

Desarrollo de interfaz: `cd web/frontend`, `npm install`, `npm run dev`. Vite reenvía `/api` a Python en el puerto 8000. Para actualizar la interfaz servida por Python, ejecuta `npm run build` y reinicia Python.

## Funciones

- **Simulación en vivo por pasos**: en Simulaciones elige «En vivo» e inicia una corrida. El backend calcula únicamente la hora actual; a continuación avanza una hora por segundo real. La vista general consulta el estado del servidor sin vaciar la pantalla en cada actualización.
- Pausa/reanuda y cambia la velocidad (0,5, 1, 2 o 5 segundos por hora). El selector permite revisar horas calculadas; «Volver al presente» restaura el seguimiento automático.
- El reloj sigue aunque se cierre la pestaña, mientras Python y PostgreSQL estén activos. Un reinicio del servidor recupera el checkpoint en pausa; no inventa horas durante el apagado. Para empezar otra vez crea una corrida nueva: se conserva el historial anterior.
- El motor incremental v1 usa las ecuaciones del simulador original y flujos aleatorios separados por pecera. Una semilla reproduce corridas del mismo motor; no tiene por qué coincidir con la antigua ejecución por lotes.
- Una hora se publica después de calcular sus mediciones y predicciones. Las muertes de la transición se sortean al avanzar a la hora siguiente. Cada pronóstico emitido se guarda sin recalcularlo con información posterior. Los desenlaces permanecen pendientes hasta completar el plazo de seguimiento.
- Checkpoints propios y atómicos en `datos/corridas/vivo_*.checkpoint`: estado de peces, generadores aleatorios, historial y probabilidades emitidas. La tabla `pisciber_vivo` registra estado y reloj. Solo se ejecuta una corrida en vivo activa a la vez y **un worker Uvicorn**; no iniciar varios servidores contra los mismos checkpoints.
- El límite objetivo es una hora por segundo. Si el cálculo o disco tardan más, el reloj avanza más despacio y conserva todos los pasos; no omite horas para alcanzar el tiempo de pared. Al llegar a 96 se detiene automáticamente. Las predicciones posteriores al fin de seguimiento quedan sin evaluar.

- Resumen por pecera: peces vivos, suma de probabilidades (muertes esperadas), riesgo individual medio, alertas y condiciones del agua.
- Riesgo por pez a 1, 6 o 12 horas, con filtros, orden por probabilidad y detalle del historial hasta el corte.
- Selector de hora 0–84: permite visualizar siempre el horizonte completo de 12 horas dentro de una corrida de 96 horas.
- Evaluación del modelo: matriz de confusión, precisión, recall, F1, ROC-AUC, AP, intervalos y muertes distintas anticipadas.
- Nuevas simulaciones de seis ambientes, con semillas reproducibles y hasta cinco repeticiones. No reentrenan ni cambian los umbrales.
- Comparación por corrida y descarga XLSX del corte, todas sus observaciones, probabilidades a tres horizontes y métricas. Los Excel se conservan en `resultados/exportaciones/`.
- API documentada en http://127.0.0.1:8000/docs.

## Datos y persistencia

`simulacion/modelos/` contiene los tres modelos locales de Windows. `simulacion/ml/` conserva las funciones de simulación, historia y selección que necesitan los modelos. `simulacion/datos_base/` contiene los insumos y resultados del experimento v3; se importan solo las 12 corridas de test. Al arrancar se verifican los conteos de confusión contra la evaluación original. No se mezclan métricas de Colab con modelos locales: sus bibliotecas/plataformas produjeron resultados ligeramente diferentes.

Por defecto el registro usa SQLite. Se puede configurar PostgreSQL con `DATABASE_URL` en `.env` (ver `.env.example`). Solo se crean tablas de la aplicación con prefijo `pisciber_`; no se modifican tablas del simulador original. Los historiales y predicciones completos se guardan en CSV dentro de `datos/corridas/`. Respaldar tanto la base como `datos/corridas/` para conservar las corridas.

Una misma semilla y ambiente producen las mismas condiciones y desenlaces. Los modelos se mantienen fijos. Las semillas nuevas empiezan en 100000000 para no reutilizar las semillas de entrenamiento. Los estados pendientes o ejecutando interrumpidos se marcan como error al reiniciar, para no simular que terminaron.

## Interpretación

Cada fila representa un pez vivo en una hora. Las observaciones no son independientes. La suma de probabilidades tiene sentido para peces de una misma hora; no se suman horas superpuestas. El promedio de riesgos de una pecera no es la probabilidad de al menos una muerte. Las condiciones observadas son descripciones y no causas confirmadas.

Los modelos reciben exclusivamente variables permitidas y su historia hasta t. Los desenlaces futuros se conservan solo para evaluación. Cuando el horizonte supera el fin de seguimiento, el resultado observado queda vacío. El escenario, los IDs, semillas y eventos futuros no entran como predictores.

## Verificar

`powershell -File verificar.ps1`

## Documentación de tecnologías

- FastAPI: https://fastapi.tiangolo.com/tutorial/background-tasks/
- React: https://react.dev/learn/
- Vite: https://vite.dev/guide/build


## Estadísticas, seguimiento y atención

Estadísticas de corrida presenta población inicial, vivos, muertes únicas y mortalidad acumulada al corte por especie y pecera, además de la evolución y lecturas del agua.

Seguimiento de alertas conserva cada observación, riesgo emitido, hora límite y resultado conocido al corte. Se puede filtrar por pendientes, avisos correctos, falsas alarmas, muertes sin aviso y supervivencias correctas. La atención se registra una vez por pez/hora/horizonte con nota opcional y demora en horas simuladas. No cambia las condiciones ni convierte el aviso en acierto.

La comparación de escenarios usa corridas completas de 96 h, separadas por motor y ambiente. Excluye repeticiones con igual semilla/ambiente/motor. Las tasas se calculan sumando conteos; las corridas en curso no se mezclan con las completas.

El Excel añade mortalidad por grupo, evolución poblacional, seguimiento al corte y sugerencias basadas en reglas de revisión. Los desenlaces siguen pendientes hasta completar el horizonte.

Consulta [la estructura](documentacion/ESTRUCTURA.md) y [la guía de presentación](documentacion/GUIA_PRESENTACION.md). El motor puede ejecutarse sin la web con `python -m simulacion.ejecutar`.
