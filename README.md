# Pisciber BSF: instalación y ejecución

Aplicación universitaria que simula peces y peceras y usa XGBoost para estimar el riesgo de muerte. Para explicar los datos, el entrenamiento y los resultados, lee [EXPLICACION_MACHINE_LEARNING.md](EXPLICACION_MACHINE_LEARNING.md).

## 1. Qué instalar

Instrucciones para **Windows**. El proyecto se comprobó con Python 3.13.7 y Node.js 22.22.3.

1. **Python 3.13 de 64 bits**, con `pip` y el lanzador `py`. Activa la opción de agregar Python al PATH durante su instalación: https://www.python.org/downloads/.
2. **Node.js y npm**, necesarios para instalar y construir React. Recomendamos Node.js 22.12 o posterior; Vite también acepta Node 20.19 o posterior dentro de la versión 20: https://nodejs.org/.
3. Un navegador, como Edge o Chrome.
4. **PostgreSQL es opcional**. Sin configuración se usa SQLite, incluido con Python. Para PostgreSQL el servicio debe estar iniciado y la base creada.

Comprueba lo instalado en PowerShell:

```powershell
py --version
py -m pip --version
node --version
npm.cmd --version
```

Si un comando no se reconoce, instala el programa y vuelve a abrir PowerShell. La primera instalación necesita Internet para descargar las dependencias.

## 2. Instalación inicial

Abre PowerShell en la carpeta principal `Peses`, donde se encuentran este archivo e `INICIAR.bat`, y ejecuta:

```powershell
cd "proycto innovador"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd web\frontend
npm.cmd ci
npm.cmd run build
cd ..\..
```

`.venv` contiene las dependencias de Python del proyecto; no necesitas activarlo si usas los comandos anteriores. `requirements.txt` incluye FastAPI, Uvicorn, pandas, NumPy, scikit-learn, XGBoost, SQLAlchemy y openpyxl. `npm ci` instala React y Vite según `package-lock.json`; `npm run build` construye la interfaz.

En otra computadora instala las dependencias allí: no copies `.venv` ni `node_modules`. Los modelos se guardaron en Windows y pueden requerir conversión o nuevo entrenamiento en otro sistema o con otras versiones.

## 3. Base de datos

**SQLite:** no requiere configuración adicional. Si no existe `DATABASE_URL`, el sistema crea `proycto innovador/datos/corridas/pisciber.db`.

**PostgreSQL:** instala e inicia PostgreSQL, crea una base y añade un archivo `.env` dentro de `proycto innovador`, usando `.env.example` como referencia:

```text
DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5432/NOMBRE_BASE
```

Reemplaza los datos por los de tu instalación. Los caracteres especiales de la contraseña deben codificarse para una URL. No compartas ni subas `.env`: contiene credenciales. La aplicación crea sus propias tablas con prefijo `pisciber_`.

SQLite y PostgreSQL son bases distintas: cambiar de una a otra no traslada automáticamente corridas ni atenciones. Para un respaldo completo conserva la base usada y la carpeta `datos/corridas`.

## 4. Iniciar la aplicación

1. Haz doble clic en **`INICIAR.bat`** de la carpeta principal.
2. Mantén abierta la ventana del servidor y espera a que termine de iniciar.
3. Abre **http://127.0.0.1:8000** en el navegador.
4. Para detenerla, vuelve a la ventana del servidor, pulsa `Ctrl+C` y después ciérrala.

También puedes iniciarla desde PowerShell dentro de `proycto innovador`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar.ps1
```

El iniciador intenta instalar Python si falta `.venv` y construir React si falta `web/frontend/dist/index.html`. Para una instalación limpia, usa primero la sección 2. Si `.venv` ya existe, el iniciador supone que sus paquetes ya están instalados; si falta alguno, vuelve a ejecutar el comando `pip install -r requirements.txt` de la sección 2. La primera carga puede tardar mientras se cargan los modelos y datos.

## 5. Cómo usarla

1. En **Simulaciones**, elige escenario, semilla y **En vivo**. Configura especie, número de peces y litros por pecera; intensidad, inicio y duración del incidente; y perfil de sensores. Pulsa **Iniciar las 96 horas**. La prueba arranca automáticamente y recorre la duración completa. La hora del historial solo sirve para consultar resultados, no para elegir cuánto dura la corrida.
2. En **Vista general**, observa las peceras y usa pausar, reanudar y velocidad. Por defecto se intenta avanzar una hora simulada por segundo real. Si el cálculo tarda más, avanza más despacio sin saltar horas.
3. En **Vista general**, consulta las tablas y gráficas por pecera y abre el detalle de un pez para ver su riesgo y las condiciones registradas.
4. En **Estadísticas de corrida** y **Seguimiento de alertas**, revisa mortalidad, avisos pendientes, aciertos y errores. Puedes registrar que revisaste una alerta.
5. Con **Exportar Excel** descarga el detalle, historial, estadísticas y evaluación. También se guarda una copia en `proycto innovador/resultados/exportaciones`.

El reloj sigue si cierras la pestaña mientras el servidor esté encendido. Si reinicias el servidor, la corrida en vivo se recupera en pausa. Ejecuta solo un servidor de esta aplicación a la vez.

### Pausar, retroceder y empezar otra vez

En **Velocidad de simulación** puedes elegir 2×, 4×, 10× o **Máxima**. 10× solicita una hora simulada cada 0,1 segundos; Máxima avanza en cuanto termina cada cálculo y guardado. Si el equipo tarda más, el reloj avanza más despacio y conserva todas las horas. La pantalla puede mostrar varias horas de avance entre actualizaciones, pero el historial mantiene cada paso. El tiempo del último cálculo aparece junto al reloj.

**Velocidad del historial** controla solamente la reproducción de observaciones guardadas: 1×, 3× y 10×. Para detener el cálculo nuevo usa **Pausar**; para detener la reproducción usa **Detener reproducción**.

- **Pausar / Reanudar** detiene o continúa el cálculo. Al reanudar otra corrida, se pausa automáticamente la que estuviera activa.
- **Hora anterior / siguiente**, el número de hora y el deslizador consultan observaciones guardadas. El motor no retrocede: puedes estar viendo la hora 10 mientras la corrida ya llegó a 40.
- **Reproducir historial** recorre las horas ya guardadas. Funciona incluso después de terminar las 96 horas y no genera muertes nuevas.
- **Volver al presente** vuelve a seguir la última hora del motor.
- **Empezar desde cero** crea otra corrida pausada en la hora 0, con la misma semilla y configuración, sin las intervenciones anteriores. Conserva el historial original. Pulsa **Reanudar** para empezar. Las corridas incrementales antiguas conservan su motor v1; para usar v2 crea una prueba desde **Simulaciones**.

### Consultar la duración

Cada corrida indica su duración total en el selector, el resumen y el historial de simulaciones: actualmente 96 horas simuladas (4 días). El historial también muestra inicio, fin y duración del incidente para el motor v2. En el ambiente estable no hay incidente; en motores anteriores el incidente puede variar por pecera.

El Laboratorio de decisiones se retiró de la interfaz. Las acciones históricas registradas se conservan como evidencia de esas corridas. El tiempo real de ejecución depende de la velocidad elegida y del equipo.

El nuevo motor y sus supuestos se explican en [SIMULACION_V2.md](proycto%20innovador/documentacion/SIMULACION_V2.md). En **Evaluación del modelo** se muestran por separado las métricas originales y la prueba con 36 corridas del motor v2.

Las nuevas corridas usan el conjunto de modelos revisado: v3 a 1 hora y v4 a 6 y 12 horas. La web muestra la versión correspondiente al horizonte elegido. Las corridas ya guardadas y sus reinicios conservan la versión con la que comenzaron; para usar el modelo revisado crea una prueba en **Simulaciones**. El Excel identifica versiones y umbrales e incluye la comparación v3/v4 del test nuevo. La mejora reduce falsas alarmas a 6 y 12 horas, con pérdida de detección especialmente a 12 horas; consulta ambos porcentajes.

## 6. Si algo falla

- **La página no abre:** revisa que el servidor siga abierto y haya terminado de iniciar; recarga la dirección.
- **Puerto 8000 ocupado:** cierra la instancia anterior o ejecuta, desde `proycto innovador`, `powershell -File .\iniciar.ps1 -Puerto 8001` y abre `http://127.0.0.1:8001`.
- **Falta un paquete de Python:** desde `proycto innovador`, ejecuta `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- **React no compila:** verifica Node, entra en `web/frontend` y ejecuta `npm.cmd ci` y `npm.cmd run build`.
- **Error PostgreSQL:** verifica el servicio, la base y `.env`. Para usar SQLite retira `DATABASE_URL` del entorno y de `.env`; se abrirá una base distinta.
- **Error al cargar modelos:** revisa las versiones, especialmente `scikit-learn==1.7.1` y `xgboost==3.4.1`, e instala de nuevo los requisitos.
- **Reanudar aparece como “Finalizada (96 h)”:** esa corrida ya terminó. Usa **Reproducir historial** para revisarla o **Empezar desde cero** para repetirla. Mover la hora hacia atrás no reinicia el motor.
- **No aparecen los botones nuevos:** reconstruye React (`npm.cmd run build` desde `web/frontend`), reinicia el servidor y recarga la página.
- **Predicción vacía o “Sin predicción”:** revisa los sensores y la bitácora. No significa riesgo cero. El perfil intermitente puede dejar lecturas ausentes.

Para comprobar el proyecto, desde `proycto innovador` ejecuta `powershell -File .\verificar.ps1`. La API está documentada en http://127.0.0.1:8000/docs mientras el servidor está activo.

## 7. Organización

- `proycto innovador/web`: interfaz React y API Python.
- `proycto innovador/simulacion`: motor, código de machine learning, modelos y datos base.
- `proycto innovador/datos/corridas`: registros y checkpoints; no los muevas manualmente.
- `proycto innovador/resultados`: Excel y salidas.
- `proycto innovador/documentacion`: guía de presentación y estructura.
- `archivo_historico`: experimentos y notebooks anteriores.

Para más detalle, consulta [la estructura](proycto%20innovador/documentacion/ESTRUCTURA.md).
