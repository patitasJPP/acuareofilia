# Organización del proyecto

La carpeta principal conserva `INICIAR.bat`, `iniciar.ps1`, las dependencias y el archivo privado `.env`.

| Carpeta | Contenido |
|---|---|
| `web/frontend` | React, estilos, componentes, configuración Vite y compilación `dist`. |
| `web/backend` | API FastAPI, conexión, estadísticas, atención de alertas, exportación y reloj del servidor. |
| `simulacion/motor` | Motor incremental que genera las condiciones y muertes simuladas. Funciona sin interfaz web. |
| `simulacion/ml` | Funciones de historia ambiental, preprocesamiento y experimentos de entrenamiento. |
| `simulacion/modelos` | Modelos XGBoost calibrados a 1, 6 y 12 horas. |
| `simulacion/datos_base` | Insumos y evaluaciones del experimento local v3. |
| `datos/corridas` | CSV de corridas, checkpoints en vivo y respaldo SQLite inicial. |
| `resultados/exportaciones` | Excel y capturas generados por la aplicación. |
| `resultados/simulaciones` | Resultados CSV del motor ejecutado de forma independiente. |
| `logs` | Registros del servidor. |
| `documentacion` | Guía de presentación, funcionalidades y estructura. |
| `herramientas` | Utilidades de mantenimiento y migraciones ya realizadas. |

El backend coordina los módulos; el motor no importa componentes de React ni endpoints. `web/backend/live_engine.py` es una referencia de compatibilidad para abrir checkpoints previos a la reorganización. Los modelos y las corridas se conservaron.

Ejecutar el motor por separado desde la carpeta principal:

```powershell
.\.venv\Scripts\python.exe -m simulacion.ejecutar --escenario hipoxia --semilla 100000501 --horas 96
```

Este comando genera mediciones y eventos simulados, sin ejecutar el modelo de predicción. La aplicación web combina el motor con XGBoost para obtener las probabilidades.

No mover archivos dentro de `datos/corridas` manualmente: los registros de PostgreSQL apuntan a sus nombres. Para respaldar, conservar esa carpeta y la base PostgreSQL.
