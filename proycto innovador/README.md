# Pisciber BSF: aplicación universitaria

Aplicación local de simulación y predicción de mortalidad de peces, con un experimento comercial de pedidos, ventas e inventario simulados. Usa React/Vite y FastAPI/Python.

## Instalación e inicio

La guía completa de requisitos, instalación, SQLite/PostgreSQL y solución de problemas está en el [README principal](../README.md). No requiere instalar paquetes adicionales por la reorganización.

Desde esta carpeta, abre `INICIAR.bat` o ejecuta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar.ps1
```

Después visita http://127.0.0.1:8000. Mantén el servidor encendido. Para detenerlo, usa Ctrl+C. Ejecuta una sola instancia Uvicorn para conservar la coordinación de los relojes.

Para desarrollar la interfaz, entra en `web/frontend` y ejecuta `npm.cmd run dev`. Para actualizar la versión que sirve Python, ejecuta `npm.cmd run build` en esa misma carpeta. Vite reenvía `/api` a Python en el puerto 8000 durante el desarrollo.

## Funciones actuales

- **Mortalidad:** simulaciones de 96 horas, configuración de tres peceras y seis ambientes, pausa, reanudación, velocidad y consulta de horas guardadas. Las predicciones a 1, 6 y 12 horas conservan la versión del modelo de cada corrida; las nuevas usan v3 a una hora y v4 a seis y doce horas.
- **Evaluación:** vista general por pecera, detalle de peces, estadísticas de corrida, seguimiento de alertas, comparación de ambientes y descarga Excel con observaciones, predicciones y resultados conocidos al corte.
- **Ventas y demanda:** historial inicial simulado de dos años y sesiones de 52 semanas nuevas. El ritmo inicial es una semana por segundo, con pausa, reanudación, velocidad, consulta del pasado y conservación de sesiones anteriores.
- **Pronóstico comercial:** estima pedidos a una–cuatro semanas y conserva cada pronóstico antes de simular su resultado. Muestra errores y casos pendientes; los datos se descargan como CSV para Excel dentro de un ZIP.
- **API:** documentación en http://127.0.0.1:8000/docs mientras el servidor esté activo.

Los relojes continúan al cerrar la pestaña mientras el servidor permanezca encendido. Al reiniciar el servidor, las sesiones incrementales se recuperan en pausa. Los resultados son experimentales y todos los datos de simulación son sintéticos.

## Organización y persistencia

- `web/frontend/src/features`: interfaz agrupada en mortalidad, simulación y demanda.
- `web/frontend/src/styles`: estilos compartidos; `main.jsx` conserva el punto de entrada de React.
- `web/backend`: API, persistencia, relojes y pruebas Python.
- `simulacion`: motor de peces, entrenamiento, modelos y datos base.
- `demanda`: generador y pronóstico comercial con sus modelos.
- `datos/corridas`: historiales y checkpoints de peces; conserva también la base SQLite o PostgreSQL utilizada por el registro de corridas.
- `datos/ventas`: historial comercial inicial y sesiones en `en_vivo.db` (SQLite local).
- `resultados`: evaluaciones, pronósticos, exportaciones y capturas.
- `documentacion`: explicaciones y registros de verificación y limpieza.
- `herramientas`: utilidad de configuración de PostgreSQL conservada.

Para un respaldo completo conserva datos, modelos y bases utilizadas; copia las bases locales con el servidor detenido. La configuración privada se mantiene en `.env` y no se versiona. Los archivos de compatibilidad, modelos antiguos y checkpoints conservan sus rutas.

## Explicación para la exposición

- [Cómo se usa el machine learning de mortalidad](../EXPLICACION_MACHINE_LEARNING.md).
- [Pronóstico de demanda y reloj comercial](documentacion/DEMANDA.md).
- [Motor de simulación v2](documentacion/SIMULACION_V2.md).
- [Organización detallada](documentacion/ESTRUCTURA.md).
- [Guía de presentación](documentacion/GUIA_PRESENTACION.md).

## Verificación

Desde esta carpeta:

```powershell
powershell -File .\verificar.ps1
```

El script ejecuta las pruebas Python y el build React. No hay un linter configurado en el repositorio. El registro de la reorganización está en [LIMPIEZA_REFACTOR.md](documentacion/LIMPIEZA_REFACTOR.md).
