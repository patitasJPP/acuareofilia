# Proyecto universitario de simulación de mortalidad acuícola

## Experimento más reciente: v3

`experimento_v3/` contiene 96 corridas con semillas nuevas, historia ambiental hasta 24 horas y objetivos de mortalidad a 1, 6 y 12 horas. Ejecutar `py mejorar_predicciones.py` para generar/entrenar (protege un test ya terminado), y `py revisar_mejora.py` para verificar y empaquetar resultados. Consultar `experimento_v3/INFORME.md` y `experimento_v3/LECTURA_RESULTADOS.md`. La comparación por horizonte cambia el objetivo; las métricas por observación no equivalen a contar peces muertos distintos. La carpeta v2 conserva el experimento anterior.

## Experimento recomendado: v2

Ejecutar `py experimento_mortalidad.py`. Genera corridas independientes y entrena con cuatro particiones completas: entrenamiento, calibración, validación y test. El modelo usa solo mediciones sintéticas e historia ambiental, sin salud interna. Resultados vigentes de este experimento en `experimento_v2/INFORME.md`; datos completos en `experimento_v2/datos.csv`. Supuestos y unidades en [SUPUESTOS_SIMULACION.md](SUPUESTOS_SIMULACION.md). Pruebas: `py -m unittest test_experimento test_mortalidad -v`. El motor y los resultados históricos siguientes corresponden a una versión anterior.

> **Actualización del 13/11/2026:** ya existen el motor Python, los generadores y el entrenamiento sin interfaz gráfica. Las secciones históricas siguientes describen etapas anteriores y no deben usarse para determinar el estado actual. Ver `resultados_ml/INFORME.md` para los resultados y limitaciones de la revisión actual.

Para entrenar con el Excel original, sin abrir ventanas ni conectar a PostgreSQL:

```powershell
py -m pip install -r requirements-ml.txt
py entrenar_mortalidad.py
py -m unittest test_mortalidad -v
```

El entrenamiento guarda en `resultados_ml/` los datos modelables, la lista de exclusiones, la comparación de regresión logística/Random Forest/XGBoost, métricas y matrices por fold, predicciones fuera de muestra, importancias y un modelo exploratorio. Usa cinco particiones por pez, repite la comparación con identificación de pecera y deja fuera cada pecera completa. La selección, imputación, escalado y codificación se ajustan dentro de cada partición de entrenamiento.

`ml_prediccion_mortalidad.py` es una entrada compatible al mismo proceso. Su versión anterior se conserva en `backups/auditoria_ml/`. Las interfaces visuales siguen siendo opcionales y no intervienen en entrenamiento ni validación.

Se corrigieron los conteos por especie de los dos generadores y la censura/conteo de muertes del generador limpio. **Los Excel existentes conservan los valores producidos por el generador anterior**; estas correcciones solo se reflejan al generar corridas nuevas. Los generadores conservan exportaciones existentes y eligen un archivo con sufijo temporal si ya existe el nombre de destino. No usar `unir_mega_excel.py` sobre toda la carpeta: puede volver a incorporar archivos agregados, mezclar datos originales/limpios y repetir una misma exportación en CSV y XLSX. Para futuras corridas se necesita `corrida_id`, semillas y ambientes variados.

Este documento concentra el contexto funcional, biológico, técnico y de datos del proyecto. Está escrito para que una persona o una IA pueda entender qué existe, por qué existe, cuál es el objetivo y qué partes siguen abiertas, sin depender de conversaciones anteriores.

## 1. Resumen ejecutivo

El proyecto explora, mediante simulación computacional, cómo la especie, las condiciones del agua y la convivencia podrían afectar la mortalidad de peces en peceras o tanques. El resultado que se busca es comparar escenarios: por ejemplo, una especie sola frente a varias juntas; agua dentro de rangos frente a episodios de estrés; diferentes densidades, duraciones o supuestos de interacción.

Es un trabajo universitario. La base actual no contiene mortalidad observada ni historial suficiente para aprender o validar tasas reales. Por tanto, las salidas serán resultados de un modelo hipotético y dependerán de supuestos explícitos. No son pronósticos biológicos comprobados.

**Decisión de arquitectura:** PostgreSQL sirve como fuente referencial de especies, peceras, poblaciones, equipos y lecturas iniciales. El motor de simulación calculará fuera de la base y los resultados, tanto crudos como resumidos, se guardarán en archivos Excel. Las tablas `simulacion_corrida` y `simulacion_resultado` fueron retiradas del esquema activo.

## 2. Qué existe hoy y qué no

### Implementado

- Base PostgreSQL con tablas originales y tablas referenciales añadidas.
- Consulta Python que conecta a PostgreSQL y muestra datos actuales en una ventana tabular.
- Función SQL `simular_tick()` que calcula cambios de amoniaco y oxígeno, pero no muertes.
- Vista `v_peligro`, que detecta lecturas fuera de límites por especie.
- Migraciones 001 y 002, respaldo previo al cambio 002 y archivo SQL maestro del esquema actual.

### Aún no implementado

- No existe motor Python de simulación de mortalidad.
- No existen parámetros de mortalidad base ni factores cuantificados de estrés.
- No existen interacciones cargadas para los pares que comparten tanque.
- No existe exportación Excel desde Python.
- No hay datos reales de mortalidad, enfermedades o evolución del agua para calibrar ni validar el cálculo.

## 3. Estado actual de PostgreSQL

Última auditoría y prueba de la conexión del proyecto: PostgreSQL 17.4. La base tenía 8 especies, 7 peceras, 9 asociaciones pecera-especie, 7 estados actuales, 5 alimentos y 7 registros de equipos. La migración 001 añadió las tablas de contexto y ocho fichas supuestas. La migración 002 eliminó las tablas vacías de resultados y se registró en `schema_migrations`.

Conteos comprobados después de la migración 002:

| Tabla | Filas | Uso actual |
|---|---:|---|
| `especies` | 8 | Catálogo y rangos nominales de cada especie. |
| `peceras` | 7 | Tanques, nombres y volúmenes. |
| `pecera_especie` | 9 | Composición, cantidad y peso promedio por tanque. |
| `estado_pecera` | 7 | Una lectura actual por tanque, sin fecha. |
| `alimentos` | 5 | Catálogo de alimento y coeficiente de amoniaco declarado. |
| `equipos_pecera` | 7 | Filtración y aireación declaradas por tanque. |
| `especie_ficha` | 8 | Rasgos adicionales, cargados como supuestos. |
| `especie_interaccion` | 0 | Catálogo de interacciones aún sin definir. |
| `parametro_simulacion` | 0 | Parámetros de mortalidad/estrés aún sin definir. |
| `lectura_agua` | 0 | Historial preparado para mediciones fechadas. |
| `registro_mortalidad` | 0 | Historial preparado para observaciones reales. |
| `evento_enfermedad` | 0 | Historial preparado para eventos reales. |
| `schema_migrations` | 2 | Registros `001_base_simulacion` y `002_eliminar_tablas_resultados`. |
| `simulacion_corrida` | No existe | Eliminada por 002; resultados fuera de PostgreSQL. |
| `simulacion_resultado` | No existe | Eliminada por 002; resultados fuera de PostgreSQL. |

`v_peligro` consulta correctamente y devolvió cero filas en la última comprobación. Esto solo indica que, al comparar las lecturas actuales con los límites cargados, la vista no detectó valores fuera de esos límites. No demuestra ausencia de riesgo o mortalidad.

## 4. Catálogo de datos y significado

### Tablas originales

| Tabla y columnas principales | Función en el proyecto | Alcance y cautelas |
|---|---|---|
| `especies`: `id_especie`, `nombre_comun`, `ph_min`, `ph_max`, `temp_min_c`, `temp_max_c`, `oxigeno_min_mg_l`, `amoniaco_max_mg_l`, `consumo_o2_mg_kg_h` | Identifica especies, rangos nominales de agua y consumo de oxígeno estimado. | La fuente biológica no se documentó. Los rangos no deben interpretarse automáticamente como umbrales de muerte. |
| `peceras`: `id_pecera`, `nombre_pecera`, `volumen_l` | Identifica unidades de simulación y volumen para aproximar densidad y concentración. | No contiene geometría, volumen útil, circulación ni refugios. |
| `pecera_especie`: `id_pecera`, `id_especie`, `id_alimento`, `cantidad_peces`, `peso_promedio_g`, `alimento_g_por_hora` | Define población y alimento por especie y tanque. | No representa edades ni distribución de peso. Debe aclararse si alimento/hora corresponde al grupo o a cada pez. |
| `estado_pecera`: `id_pecera`, `ph`, `temperatura_c`, `oxigeno_mg_l`, `amoniaco_mg_l` | Estado inicial o lectura actual del tanque. | No tiene fecha ni historial: no permite conocer duración, variaciones ni acumulación de exposición. |
| `alimentos`: `id_alimento`, `nombre_alimento`, `amoniaco_mg_por_g` | Identifica alimento y coeficiente usado por la función SQL. | No está documentado qué forma de amoniaco representa ni el origen experimental del coeficiente. |
| `equipos_pecera`: `id_pecera`, `filtro_remocion_mg_h`, `aireacion_mg_h` | Capacidad declarada de filtración/aireación. | No se sabe si son capacidades nominales o tasas efectivas medidas en cada tanque. |
| `v_peligro` | Deriva banderas `ph_fuera`, `temp_fuera`, `oxigeno_bajo` y `amoniaco_alto` por combinación de pecera-especie. | Es una alerta de rangos, no un modelo causal ni una estimación de mortalidad. |

### Tablas referenciales añadidas en 001

| Tabla y columnas principales | Propósito | Estado actual |
|---|---|---|
| `especie_ficha`: `nombre_cientifico`, `temperamento`, `dieta`, `talla_adulta_cm`, `longevidad_anios`, `volumen_min_l`, `zona_agua`, `es_depredador`, `es_supuesto`, `fuente` | Rasgos para contextualizar compatibilidad, dieta, talla y posibles interacciones. | 8 filas; todas supuestas. Hay datos desconocidos (`NULL`), que no equivalen a cero o falso. |
| `especie_interaccion`: especies A/B, `tipo`, `multiplicador_riesgo_min`, `multiplicador_riesgo_probable`, `multiplicador_riesgo_max`, observaciones y fuente | Representa relaciones dirigidas o por pareja: depredación, agresividad, competencia, enfermedad o compatibilidad. | Vacía. La dirección A→B importa para depredación y agresividad. |
| `parametro_simulacion`: `nombre`, descripción, rango mínimo/probable/máximo, unidad, `es_supuesto`, `fuente` | Catálogo de valores inciertos del modelo. | Vacía. No contiene tasa base ni multiplicadores ambientales. |
| `lectura_agua`: pecera, `fecha_hora`, pH, temperatura, oxígeno, amoniaco, nitrito, nitrato, observaciones | Historial temporal de condiciones del agua. | Vacía; preparada para mediciones fechadas, no para datos inventados que parezcan observaciones. |
| `registro_mortalidad`: pecera, especie, fecha, población inicial, muertos, causa y observaciones | Historial real para calibración y contraste futuro. | Vacía. |
| `evento_enfermedad`: pecera, especie opcional, enfermedad, fechas y peces afectados | Historial de enfermedades para una posible capa epidemiológica. | Vacía. |
| `schema_migrations`: versión, descripción, fecha | Historial de cambios estructurales. | Registra 001 y 002 en la base activa. |

Todas las tablas nuevas usan claves foráneas hacia las entidades originales y restricciones de integridad. En las tablas con supuestos, `es_supuesto` distingue valores hipotéticos de observaciones; `fuente` describe su procedencia o criterio.

## 5. Poblaciones, tanques y condiciones existentes

Valores observados en la base durante la última lectura de solo lectura. Las cantidades y mediciones son exactamente lo que está almacenado; el origen o si fueron medidos en campo no está documentado.

| Tanque | Volumen (L) | pH | °C | O₂ (mg/L) | Amoniaco (mg/L) | Filtración (mg/h) | Aireación (mg/h) | Población |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Tanque Tilapia | 5000 | 7.40 | 27 | 7.500 | 0.0100 | 450 | 12000 | 100 Tilapias, 200 g promedio |
| Estanque Mixto | 3000 | 7.30 | 25 | 7.500 | 0.0100 | 350 | 8000 | 40 Tilapias, 150 g; 20 Carpas, 300 g |
| Tanque Trucha | 2000 | 7.20 | 14 | 8.500 | 0.0000 | 200 | 6000 | 50 Truchas arcoíris, 120 g |
| Acuario Comunitario | 200 | 6.90 | 25 | 7.000 | 0.0000 | 10 | 300 | 30 Guppys, 0.50 g; 20 Tetras neón, 0.40 g |
| Tanque Gamitana | 4000 | 7.00 | 28 | 7.000 | 0.0100 | 450 | 9000 | 60 Gamitanas, 250 g |
| Pecera Goldfish | 300 | 7.20 | 21 | 7.500 | 0.0000 | 40 | 600 | 8 Goldfish, 60 g |
| Pecera Sobrealimentada | 500 | 7.50 | 24 | 6.000 | 0.0500 | 50 | 3000 | 15 Carpas, 250 g |

Los pares actualmente mezclados son Tilapia–Carpa en el estanque mixto y Guppy–Tetra neón en el acuario comunitario. Estos son buenos escenarios comparativos del proyecto, pero no hay multiplicadores ni interacciones cuantificados en la base.

## 6. Alimentos y fichas de especie

Alimentos registrados: Pellet 28%, 32% y 40% de proteína; Hojuelas 35%; Starter 45%. `amoniaco_mg_por_g` tiene valores entre 22 y 36, pero su interpretación y fuente no están verificadas.

Las ocho especies de `especies` son Tilapia, Carpa, Trucha arcoíris, Bagre, Goldfish, Guppy, Tetra neón y Gamitana. En `especie_ficha`, Carpa, Trucha arcoíris, Goldfish, Guppy, Tetra neón y Gamitana tienen nombres científicos cargados como supuestos. Tilapia y Bagre no tienen nombre científico definido en esa tabla. `volumen_min_l` está NULL en las ocho fichas; talla y longevidad también están vacías para Tilapia y Bagre; `es_depredador` de Bagre está NULL. Esos campos describen desconocidos y no deben completarse silenciosamente.

## 7. Funciones SQL y su relación con el futuro simulador

### `simular_tick()`

La función SQL existente modela un tick de una hora para ciertos cambios fisicoquímicos:

- Calcula amoniaco generado como alimento por hora multiplicado por `alimentos.amoniaco_mg_por_g`, y lo compara con `equipos_pecera.filtro_remocion_mg_h`.
- Calcula consumo de oxígeno desde cantidad, peso promedio y `especies.consumo_o2_mg_kg_h`, y lo compara con `equipos_pecera.aireacion_mg_h`.
- Actualiza `estado_pecera`, limita el amoniaco inferiormente a cero y el oxígeno al rango 0–9 mg/L.

No calcula mortalidad, no trata interacción de especies y no lleva historial. Su unidad declarada es una hora por ejecución. Al llamarla, modifica los datos de `estado_pecera`; la aplicación de consulta no la llama. El simulador futuro debe calcular la evolución en memoria para que escenarios repetidos no alteren la base referencial.

### `v_peligro`

Une la especie de cada tanque con sus límites y el estado actual. Una fila significa que al menos una variable está fuera del rango declarado. No incorpora tiempo de exposición, gravedad, mezcla de factores ni letalidad.

## 8. Visión del modelo de alta capacidad

La intención es desarrollar una simulación potente, flexible y probabilística, no limitar el análisis a una lista fija de casos simples. La potencia se logra mediante escenarios numerosos, múltiples factores simultáneos, incertidumbre explícita, interacciones dinámicas, Monte Carlo reproducible y análisis de sensibilidad. El cálculo debe ser transparente y auditable: cada resultado necesita poder relacionarse con los valores iniciales, los supuestos y la versión del modelo.

Un modelo sofisticado no puede deducir tasas biológicas de tablas vacías. Sin datos observados, la incertidumbre se representa con rangos/distribuciones supuestos y el resultado se interpreta como exploración de escenarios. El método concreto, distribuciones y parámetros son decisiones de modelado pendientes, no hechos actualmente implementados.

### Dimensiones que puede integrar

| Dimensión | Variables disponibles | Extensión conceptual |
|---|---|---|
| Población | cantidad y peso promedio por especie y tanque | Cohortes, etapas de vida, distribución de tamaños y cambios poblacionales por paso temporal. |
| Ambiente | pH, temperatura, oxígeno y amoniaco actuales; rangos por especie | Trayectorias horarias/diarias, intensidad y duración del estrés, variación ambiental y otras medidas como nitrito/nitrato si se incorporan. |
| Densidad y recursos | volumen, cantidad, biomasa aproximable, alimento/hora | Competencia por espacio/alimento, consumo, carga del agua y capacidad efectiva del equipo, sujetos a unidades justificadas. |
| Convivencia | pares que comparten tanque y rasgos incompletos de ficha | Efectos direccionales de depredación/agresión, competencia, compatibilidad o transmisión potencial de enfermedad. |
| Enfermedad | ninguna observación cargada | Escenario opcional con introducción, latencia, propagación y recuperación definidos como supuestos separados. |
| Incertidumbre | columnas de rangos en tablas de parámetro/interacción, actualmente vacías | Muestreo de valores por corrida/iteración y presentación de distribución de resultados. |
| Tiempo | estado actual sin fecha histórica | Ticks configurables, duración del escenario, evolución de condiciones y exposición acumulada. |

### Enfoque computacional esperado

El simulador puede representar cada escenario con muchos recorridos Monte Carlo. En cada recorrido, las condiciones iniciales y parámetros inciertos se muestrean; la población y el estado del ambiente evolucionan en pasos temporales; los eventos de muerte se generan de forma probabilística; y los resultados se conservan para comparar escenarios. El cálculo de mortalidad puede partir de una tasa base hipotética y modificar el riesgo por factores ambientales e interacciones, pero la forma matemática y las distribuciones aún deben definirse, probarse y documentarse.

La salida debe incluir tanto la trayectoria de cada iteración como resúmenes entre iteraciones. P5, mediana y P95 describen percentiles del resultado del modelo bajo sus supuestos; no son intervalos de confianza derivados de observaciones reales. Factores dominantes y horas fuera de rango requieren definición operacional explícita.

“Sin reglas fijas” significa que el modelo no debe reducirse a una tabla rígida de `si pasa X, muere Y`. Sigue necesitando una estructura matemática y parámetros: un enfoque probabilístico permite que el resultado emerja de la combinación de incertidumbre, ambiente, población e interacción. Esa estructura todavía no existe en el código.

## 9. Escenarios que el proyecto puede comparar

Estos son ejemplos de preguntas de investigación, no resultados ya calculados:

- Composición monoespecífica frente a mezcla de las especies que ya comparten tanque.
- Densidad actual frente a densidad hipotética mayor o menor.
- Parámetros de agua dentro de rangos frente a cambios graduales o picos de estrés.
- Aireación y filtración declaradas frente a escenarios de equipo reducido o mejorado.
- Variación de alimentación y de su interpretación por grupo/pez.
- Efectos sin interacción, interacción baja, media y alta para analizar sensibilidad.
- Escenarios con y sin una enfermedad hipotética, una vez que su mecánica esté diseñada.
- Duraciones diferentes y análisis de cómo cambia la distribución de mortalidad en el tiempo.

Cada escenario debe mostrar qué variables cambian respecto al escenario base; así se pueden atribuir diferencias y evitar comparaciones ambiguas.

## 10. Resultados y libro Excel

La base de datos no guarda corridas ni resultados. El libro Excel será el artefacto persistente de análisis y debe conservar datos crudos, supuestos y trazabilidad.

Estructura sugerida:

| Hoja | Contenido |
|---|---|
| `Resumen` | Escenario, especie/tanque, peces iniciales, mortalidad final, percentiles, factores principales y advertencia de resultado hipotético. |
| `Resultados_por_pecera_especie` | Una fila por escenario, tanque y especie; resumen de vivos, muertos y porcentajes. |
| `Iteraciones` | Resultados crudos por iteración y paso temporal para análisis independiente. |
| `Trayectoria_ambiental` | Evolución simulada de pH, temperatura, oxígeno, amoniaco y cualquier otra variable incluida. |
| `Supuestos_y_parametros` | Valor/rango, unidad, criterio, fuente, condición de supuesto y dónde se usa. |
| `Escenarios` | Diferencias entre escenario base y escenarios alternativos. |
| `Metadatos` | Fecha, versión del código, semilla aleatoria, iteraciones, duración y configuración del equipo. |

La librería Python `openpyxl` aún no está en `requirements.txt`; puede añadirse cuando se implemente esta exportación.

## 11. Dificultades, vacíos y mejoras prioritarias

### Vacíos biológicos y de mortalidad

- No existe mortalidad base por especie ni por período.
- No hay relación observada entre condiciones, convivencia y mortalidad.
- No hay edad, estado de salud inicial ni variación de tamaños por población.
- El nombre común no identifica siempre una especie taxonómica exacta; faltan aclaraciones para Tilapia y Bagre.
- Temperamento, dieta, depredación y compatibilidad están ausentes o incompletos.
- No hay historial de brotes, transmisión, recuperación ni mortalidad por causa.

### Vacíos ambientales/técnicos

- `estado_pecera` no incluye fecha, por lo que solo sirve como condición inicial puntual.
- No están confirmadas la forma química y las unidades efectivas de algunos coeficientes del alimento y equipo.
- No se conocen picos, variabilidad diaria, temperatura estacional, circulación, filtración biológica real ni fallas de equipo.
- Nitrito/nitrato están previstos en `lectura_agua`, pero no hay registros.
- Los límites en `especies` no declaran población objetivo, etapa ni fuente.

### Consecuencia metodológica

El modelo puede ser computacionalmente potente y útil para explorar relaciones y sensibilidad, pero sin observaciones no puede identificar cuál de varios mecanismos hipotéticos describe mejor la realidad. Muchos parámetros producen comportamientos plausibles distintos. Por eso el análisis debe mostrar rangos/escenarios y explicar la incertidumbre, no reportar una única cifra como si fuera certeza.

## 12. Archivos del proyecto

| Archivo/carpeta | Propósito y estado |
|---|---|
| `consultar_peceras.py` | Aplicación actual de consulta visual; ejecuta un `SELECT`, muestra columnas y registros, pero no implementa simulación. |
| `database.py` | Centraliza conexión y `conectar_bd()`. Actualmente contiene credenciales locales escritas directamente; no se deben incluir en documentos, capturas, commits ni archivos compartidos. Migrarlas a configuración local/variables de entorno es una mejora pendiente. |
| `requirements.txt` | Dependencia actual `psycopg[binary]`; no incluye todavía Excel ni motor Monte Carlo. |
| `esquema_acuicola.sql` | Script inicial de referencia con tablas, ejemplos, `simular_tick()` y `v_peligro`. Incluye `DROP TABLE IF EXISTS`; su ejecución puede borrar datos si se usa contra una base con contenido. |
| `migrations/001_base_simulacion.sql` | Migración aditiva para fichas, interacciones, parámetros, historiales y registro de migración; ya aplicada en la base activa. Cargó ocho fichas marcadas como supuestas. |
| `migrations/001_rollback.sql` | Script histórico para retirar los objetos de 001. Tiene operaciones destructivas sobre esos objetos; no es una consulta ni parte de la ejecución normal. |
| `migrations/002_eliminar_tablas_resultados.sql` | Comprueba que las antiguas tablas de resultados estén vacías, las elimina en el orden FK correcto y registra 002; ya aplicada. |
| `migrations/002_rollback.sql` | Recrea vacías las dos tablas retiradas y registra una versión de rollback. No recupera datos anteriores. |
| `db/base_maestra_postgresql.sql` | Snapshot reproducible del esquema y datos referenciales actuales, sin las tablas de resultados ni credenciales. Está orientado a una base PostgreSQL vacía, no a actualizar la base activa. |
| `backups/` | CSV y estructura previa a los cambios. Preserva el estado anterior; no es entrada del simulador. |

## 13. Ejecución actual

Entorno observado durante el desarrollo: Windows, Python 3.13, PostgreSQL 17.4. La consulta requiere que PostgreSQL esté accesible y que la configuración local de `database.py` sea válida.

```powershell
py -m pip install -r requirements.txt
py consultar_peceras.py
```

La aplicación presenta una ventana con tabla, encabezados y desplazamiento horizontal/vertical. Si la conexión falla, muestra un error. No realiza la simulación.

## 14. Estado de desarrollo deseado

El siguiente bloque de trabajo es pasar de consulta a análisis reproducible: especificar un modelo probabilístico con supuestos trazables, construir escenarios configurables, ejecutar muchas iteraciones, producir métricas interpretables y exportar el conjunto completo a Excel. El motor debería estar separado de la interfaz gráfica y de la conexión, para poder probarse también con datos sintéticos en memoria.

Una IA que continúe el proyecto encontrará decisiones abiertas en vez de especificaciones científicas cerradas. Las principales son: unidad temporal, tasa base hipotética, distribuciones de parámetros, forma de combinar estrés e interacciones, mecanismo probabilístico de muertes, tratamiento de peces restantes, densidad y carga del agua, direccionalidad de interacciones, proceso de enfermedad y cantidad de iteraciones. Las propuestas deben explicarse y marcarse como diseño o supuesto; ninguna está implementada aún.

## 15. Criterios para interpretar un resultado

- El resultado describe lo que produce el modelo bajo una configuración concreta, no una predicción observada.
- La comparación entre escenarios es más informativa que una cifra aislada.
- La variación entre iteraciones refleja las distribuciones y mecanismos que se eligieron; no reemplaza datos reales.
- Los percentiles resumen las corridas simuladas y su significado depende de los supuestos.
- Las diferencias de mortalidad pueden atribuirse solo a factores que el modelo haya representado y registrado.
- Un escenario con más detalle no es automáticamente más correcto: la calidad depende de claridad, coherencia, sensibilidad y trazabilidad.

## 16. Contexto breve para futuras IA

El usuario está desarrollando un trabajo universitario sobre mortalidad y convivencia de peces. Quiere un simulador ambicioso y detallado, capaz de combinar múltiples factores y producir escenarios Monte Carlo, en vez de un conjunto rígido de casos preprogramados. Acepta que los coeficientes sean supuestos didácticos porque no traerá datos reales, siempre que los resultados se entiendan como hipotéticos. PostgreSQL queda como base referencial; Excel es el destino de los resultados. El programa actual solo consulta datos. La función `simular_tick()` sí altera `estado_pecera`, pero no calcula muertes. El modelo, la exportación Excel, los parámetros de riesgo y las interacciones aún están pendientes de diseño e implementación.
