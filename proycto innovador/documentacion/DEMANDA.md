# Pronóstico de demanda de Pisciber: explicación para el proyecto

Este módulo responde: **¿cuántos peces de cada especie podrían solicitar los clientes en las próximas una a cuatro semanas?** Se usa dentro de la misma página, en **Ventas y demanda**. Sus datos son simulados y su calendario comercial es independiente del reloj de 96 horas de mortalidad.

Ahora incluye una **simulación semanal en segundo plano**: al pulsar **Iniciar simulación de ventas**, cada segundo real avanza una semana comercial. Recorre 52 semanas nuevas después del historial inicial, guardando pedidos, ventas, stock y pronósticos. Los controles permiten pausar, reanudar, acelerar, consultar el pasado y repetir conservando sesiones anteriores. La sección 11 explica este funcionamiento.

## 1. Qué reutilizamos

Reutilizamos React, FastAPI, Python, las dependencias instaladas y el catálogo de siete especies de `simulacion/datos_base/fichas_origen.csv`. Las mediciones de agua y el modelo XGBoost de muerte conservan su función original. Para ventas se generó otro historial y se compararon otros métodos: la temperatura no permite conocer por sí sola cuántos peces pedirá un cliente.

El experimento inicial se guarda en CSV. La simulación en vivo conserva sesiones en `datos/ventas/en_vivo.db`, una base SQLite local independiente de las corridas de mortalidad. Entrar a la sección o mover un filtro no genera datos ni entrena otra vez; el reloj del servidor produce semanas nuevas cuando está activo.

## 2. Qué representa cada registro

`datos/ventas/ventas_diarias.csv` tiene 5.096 filas: 728 días completos por siete especies, desde el lunes 11 de noviembre de 2024 hasta el domingo 8 de noviembre de 2026. Cada fila representa una especie en una fecha, incluso si ese día no se vendió nada.

- `pedidos_solicitados`: cantidad de peces que solicitaron los clientes simulados. Es la demanda registrada, incluyendo los pedidos sin stock.
- `cantidad_vendida`: peces que se pudieron vender. Nunca supera los pedidos ni el stock disponible.
- `pedidos_no_atendidos`: pedidos solicitados menos cantidad vendida.
- `precio_unitario_pen`: precio supuesto en soles. No representa una cotización de Pisciber.
- `ingreso_pen`: cantidad vendida multiplicada por precio supuesto; no equivale a utilidad.
- `stock_inicial`, `reposicion`, `merma_simulada`, `stock_final`: movimiento de inventario comercial.
- `promocion`: indicador simulado de descuento en ese día.
- `semana_indice`: semana comercial completa, de lunes a domingo; empieza en 0.
- `origen`: siempre `simulado`.

La igualdad comprobada es: **stock final = stock inicial + reposiciones − mermas − ventas**. El stock inicial del día siguiente coincide con el final del anterior.

El generador incluye variación entre especies, diferencias entre días de la semana, estacionalidad suave, cambios graduales, promociones, demanda aleatoria y algunas reposiciones incompletas. Las reposiciones se deciden con pedidos pasados. Los supuestos de precios y cantidades se guardan en el informe; no se presentan como observaciones reales.

Las mermas comerciales se simulan como pérdidas aleatorias pequeñas. No provienen del modelo XGBoost: sus corridas usan otras poblaciones y otro calendario. Para conectar ambas poblaciones en el futuro haría falta un inventario común con entradas, ventas y muertes identificadas. Por ahora el proyecto muestra los dos experimentos con sus propios datos.

## 3. Qué se intenta predecir

Se agregan los pedidos por especie y semana completa. Se pronostican directamente cuatro cantidades: pedidos en la semana siguiente, en la segunda, tercera y cuarta semana desde el corte. El selector de plazo acumula las primeras semanas correspondientes. No representa una probabilidad de muerte ni un porcentaje de venta segura.

Ejemplo: si una especie tiene un pronóstico de 120 peces para la semana siguiente, significa una estimación de 120 pedidos de peces, siempre que los patrones del historial continúen. Una falta de stock puede impedir atender una parte de esos pedidos.

Se usa demanda registrada como objetivo porque tenemos pedidos simulados atendidos y no atendidos. Si se trabajara solo con ventas, una semana sin stock podría parecer una semana sin interés de los clientes. Los pedidos no registrados tampoco se pueden reconstruir con certeza.

## 4. Qué métodos se compararon

1. **Última semana:** repite los pedidos de la semana más reciente.
2. **Promedio de cuatro semanas:** utiliza el promedio de las cuatro semanas observadas más recientes.
3. **Random Forest:** árboles entrenados con pedidos pasados, promedios, dispersión, tendencia, especie, horizonte y calendario.
4. **Gradient Boosting:** `HistGradientBoostingRegressor` con pérdida Poisson para cantidades no negativas; usa las mismas variables.

Los árboles usan los pedidos de las últimas 1, 2, 3, 4, 8 y 12 semanas; promedios y desviaciones de 4, 8 y 12 semanas; tendencia reciente; calendario futuro conocido; especie y plazo. Se desactiva la validación aleatoria interna de Gradient Boosting. No reciben pedidos futuros, ventas futuras, stock futuro ni datos de muerte.

El método principal se elige por el menor error WAPE en validación. **Con la semilla inicial ganó el promedio de cuatro semanas.** Es un método estadístico de referencia; Random Forest y Gradient Boosting sí se entrenaron y están disponibles para comparar. No sería correcto llamar Random Forest al método activo solo por ser más complejo.

## 5. Cómo evitamos usar el futuro

Las 104 semanas se dividen cronológicamente:

- Semanas 0–55: entrenamiento de los candidatos.
- Semanas 56–71: validación para seleccionar un método.
- Semanas 72–87: calibración de amplitud de los intervalos.
- Semanas 88–103: prueba reservada, utilizada para medir resultados finales.

Al entrenar se descartan las etiquetas cuyo horizonte termina después del corte. Así, un ejemplo de cuatro semanas no introduce datos del siguiente período. Hay una prueba automática que modifica todos los pedidos posteriores a un corte y comprueba que ni las variables ni el pronóstico de ese corte cambian.

Tras elegir el método se ajusta hasta la semana 71 y se mantiene fijo durante calibración y prueba. Los cortes avanzan de cuatro en cuatro semanas y reciben únicamente observaciones que ya ocurrieron. Cada una de las 16 semanas de prueba aparece una vez por especie: **112 casos**. Para una especie y un horizonte hay solo cuatro casos; esos filtros ofrecen evidencia más limitada.

Después de cerrar la evaluación se reajusta el método seleccionado con las 104 semanas para producir el pronóstico de uso. El informe distingue este ajuste de los resultados del modelo congelado de evaluación. La prueba no se usa para cambiar el ganador, aunque otro método resulte mejor en ese período.

Esta separación temporal sigue la recomendación de evaluar series con información pasada, como explica el [ejemplo oficial de scikit-learn sobre variables rezagadas](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html).

## 6. Cómo explicar los indicadores

**MAE:** error absoluto medio, en peces por especie y semana. Si se pronosticaron 100 pedidos y se observaron 120, el error absoluto es 20. Se promedian estos errores.

**WAPE:** suma de errores absolutos dividida por la suma de pedidos observados. Con la semilla inicial el método seleccionado obtuvo **17,27 %**. Describe el volumen de error relativo; restarlo de 100 % no produce una probabilidad de confiabilidad.

**Sesgo:** suma de errores con signo dividida por pedidos observados. Un valor positivo indica sobreestimación y uno negativo, subestimación. Errores positivos y negativos pueden compensarse aquí, por eso también mostramos WAPE.

**Dentro de ±20 %:** proporción de casos cuya predicción quedó a una distancia máxima del 20 % del pedido observado. No es la accuracy de un clasificador. En la prueba inicial fue **62,5 %**.

**Intervalo empírico:** rango alrededor de cada estimación, calculado con errores relativos absolutos del período de calibración y separado por plazo. Se busca 90 % de cobertura; la cobertura observada en la prueba inicial fue **96,43 %**. La dependencia temporal y la muestra pequeña impiden prometer que un futuro rango contendrá el resultado con esa frecuencia.

Los intervalos corresponden a una especie y una semana. La gráfica global suma estimaciones centrales y omite una banda global: sumar límites individuales no obtiene automáticamente un intervalo válido para el total. Tampoco se afirma cobertura conjunta de las cuatro semanas.

**Diferencia sin cubrir:** demanda central prevista menos stock comercial al corte, con mínimo cero. Es una comparación orientativa. No es una orden de compra: faltan plazos de entrega, lotes, entradas futuras y pérdidas futuras.

## 7. Qué muestra la página

- Filtros por especie y plazo de una a cuatro semanas.
- Pedidos previstos, pedidos y ventas del período anterior, WAPE y MAE del test.
- Gráfica de pedidos históricos, ventas y pronóstico; intervalos al seleccionar una especie.
- Tabla de demanda prevista por especie y comparación con stock comercial.
- Detalle de cada especie/semana y sus límites individuales.
- Comparación gráfica y detallada del período reservado.
- Tabla de los cuatro métodos y motivo de selección.
- Fechas del protocolo, supuestos y limitaciones.
- Descarga de todos los datos en ZIP, con CSV que se abren en Excel e informe JSON.

Los filtros recalculan las métricas sobre los casos correspondientes. El error de validación para seleccionar el modelo sigue siendo global y se identifica como tal. Las métricas se calculan por especie/semana, aunque una gráfica de todas las especies muestre totales: estos pueden ocultar errores que se compensan.

## 8. Dónde está cada archivo

- `demanda/generar.py`: simulación de pedidos, ventas y stock.
- `demanda/modelo.py`: variables pasadas, entrenamiento, pronóstico, métricas e intervalos.
- `demanda/ejecutar.py`: proceso reproducible completo.
- `demanda/modelos`: modelo seleccionado con historial y los dos modelos entrenados de comparación.
- `datos/ventas`: historial diario y agregado semanal.
- `resultados/demanda`: informe, calibración, prueba y pronóstico futuro.
- `web/backend/demand.py`: consulta de resultados y descarga ZIP.
- `web/frontend/src/features/demanda/Demand.jsx`: vista de ventas y demanda.
- `web/backend/test_demand.py`: pruebas de datos, separación temporal, agregados, descarga y API.

## 9. Cómo repetirlo

Usa las mismas dependencias de `requirements.txt`. Desde `proycto innovador`:

```powershell
.\.venv\Scripts\python.exe -m demanda.ejecutar --semilla 20261114
```

La misma semilla reproduce el historial y los resultados. Para otra realización cambia el número, por ejemplo `20261115`. El comando reemplaza los archivos comerciales actuales; copia primero `datos/ventas`, `resultados/demanda` y `demanda/modelos` si quieres conservar la comparación. No altera corridas de mortalidad.

Al terminar, pulsa otra sección y vuelve a **Ventas y demanda** o recarga la página. La API detecta las fechas de modificación de los resultados. Evita consultar mientras se reescriben los archivos. El botón de descarga incluye el experimento comercial completo, con independencia del filtro elegido.

Para abrir los CSV: descomprime el ZIP y, en Excel, usa **Datos → Desde texto/CSV**, codificación UTF-8 y separador coma. Los porcentajes del informe están guardados como fracciones: 0,1727 representa 17,27 %.

Para verificar el módulo desde `proycto innovador`:

```powershell
$env:PYTHONPATH='web'
$env:DATABASE_URL='sqlite://'
.\.venv\Scripts\python.exe -m unittest backend.test_demand -v
```

## 10. Una explicación para la exposición

«Creamos un historial comercial simulado de dos años con las especies del proyecto. Distinguimos pedidos y ventas, porque la falta de stock puede impedir vender. Comparamos dos métodos sencillos con Random Forest y Gradient Boosting, y elegimos por su error en un período de validación. Después medimos el error con semanas reservadas que no se usaron para elegir. La página estima los pedidos de las próximas cuatro semanas, permite revisar los errores y muestra rangos de incertidumbre. Con estos datos ganó el promedio de cuatro semanas. Los resultados describen el experimento simulado de la universidad».

## 11. Simulación semanal en vivo

### Qué hace cada segundo

1. Al crear una sesión se reconstruye exactamente el historial inicial y se verifica que coincida con los CSV y el modelo guardado. La comprobación evita mezclar un modelo con otro experimento.
2. Se emite y guarda el pronóstico de las próximas cuatro semanas, antes de generar pedidos futuros.
3. Cada segundo el motor produce los siete días de una semana nueva: pedidos, ventas limitadas por disponibilidad, reposiciones y mermas. Conserva el stock final como inventario inicial del día siguiente.
4. Compara los pedidos ya observados con los pronósticos que habían sido emitidos y conserva sus errores.
5. Con la nueva semana observada calcula otro pronóstico para las siguientes cuatro semanas. Los valores antiguos permanecen guardados con su fecha de corte.

El algoritmo seleccionado y la calibración de intervalos se mantienen fijos durante la sesión. Se actualizan las variables con el pasado recién observado. El promedio de cuatro semanas cambia al incorporar cada semana nueva; no es necesario volver a entrenar árboles en cada paso.

### Controles

- **Iniciar simulación de ventas:** crea una sesión y empieza a recorrer sus 52 semanas nuevas.
- **Pausar / Reanudar:** detiene o continúa el motor en el servidor; conserva datos y estado aleatorio.
- **Velocidad:** de una semana cada cinco segundos hasta una semana cada 0,1 segundos. El valor inicial es **1 segundo = 1 semana**. Si el cálculo y el guardado tardan más, el avance se adapta al equipo sin omitir semanas.
- **Semana consultada:** permite revisar cualquier paso ya guardado, incluido el 0. Consultar el pasado no retrocede el motor ni revela ventas que aún no habían ocurrido en ese corte.
- **Volver al presente:** sigue de nuevo la semana más reciente.
- **Nueva simulación desde el inicio:** cuando la actual está pausada o finalizada, crea otra sesión desde el mismo historial y semilla. Conserva las anteriores en el selector **Sesión**. La misma semilla reproduce los mismos pedidos, también si cambia la velocidad.

El reloj funciona sin mantener abierta la pestaña, mientras el servidor siga ejecutándose. Al reiniciar el servidor, la sesión se recupera en pausa y continúa al pulsar Reanudar. Usa una sola instancia Uvicorn, igual que para las peceras.

### Cómo se evalúan las semanas nuevas

Las tarjetas principales muestran el error acumulado **de la simulación actual**, separado del test inicial. Antes de que termine el primer plazo muestran **Pendiente**, no cero. La tabla comparativa de métodos y la prueba reservada inicial siguen disponibles abajo, con sus períodos originales.

El selector de plazo también determina la evaluación en vivo. Si eliges cuatro semanas, se comparan pronósticos emitidos con cuatro semanas de anticipación. La primera evaluación aparece al terminar la semana nueva 4. Si eliges una semana, se comparan avisos a una semana y la primera evaluación aparece al terminar la semana nueva 1. Así cada especie y semana se cuenta una vez dentro de un plazo fijo.

En **Predicciones frente a las semanas que van ocurriendo** se muestran casos completados y pendientes, WAPE, MAE, proporción dentro de ±20 %, cobertura observada de intervalos, gráfica y comparación individual. El historial permite consultar pedidos, ventas, faltantes, mermas, stock e ingresos simulados. Los filtros por especie se aplican a estos datos.

La sesión termina tras **52 semanas nuevas**. Mantiene los pronósticos que superan ese final como pendientes; no inventa sus resultados. Puedes revisar el historial o crear otra sesión.

### Guardado y descarga

Cada semana se guarda en una transacción SQLite que conserva juntos el motor aleatorio, inventario, historial y pronósticos emitidos. Si falla un paso, el motor recupera el estado anterior y permite reintentar sin saltar ni duplicar semanas. Esta ruta evita reemplazar repetidamente archivos abiertos en Windows.

Con una sesión seleccionada, **Descargar todos los datos** entrega un ZIP con historial diario y semanal completo, pronósticos emitidos con fecha de corte, evaluación con resultados pendientes vacíos y metadatos de la sesión. Para respaldar las sesiones conserva `datos/ventas/en_vivo.db` con el servidor detenido. Para respaldar también el experimento inicial conserva los CSV, informe y modelos comerciales.

Los archivos del reloj comercial son `web/backend/demand_live.py`, `web/frontend/src/features/demanda/DemandLive.jsx` y `web/backend/test_demand_live.py`. El motor `MercadoSemanal` en `demanda/generar.py` sirve tanto para reproducir las 104 semanas iniciales como para continuar generando nuevas semanas.
