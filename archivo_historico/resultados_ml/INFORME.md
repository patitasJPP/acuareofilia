# Revision y entrenamiento de mortalidad

Entrada: 55,223 filas y 51 columnas.
Peces unicos observados: 14,465; el prompt indicaba 14,516. Muertos desde la primera observacion: 1,903.
Quedan 40,758 ejemplos de peces vivos con hora siguiente observada, 12,347 positivos (30.29%).
Se proponen 29 predictores; el ajuste final conserva 25 antes de one-hot. Cada fold selecciona independientemente.

## Lo que estaba bien
IDs nuevos al reponer peces, registros horarios y motor estocastico separado del entrenamiento. Agrupar por pez es necesario. Los lags permiten conservar historia previa sin usar el estado de muerte.

## Errores encontrados y decisiones
- El script anterior hacia shift sin comprobar una hora exacta y preprocesaba antes de validar.
- La comparacion con pecera nunca se ejecutaba porque ya habia retirado su ID.
- Elegia XGBoost como mejor de antemano y reutilizaba un split de evaluacion.
- El generador asignaba el total de vivos del tanque a CADA especie, inflando biomasa y consumo de oxigeno.
- El generador limpio acumulaba las mismas muertes cada hora y etiquetaba el final desconocido como supervivencia.
- causa_riesgo_principal se obtiene de desvios ambientales, no de la muerte confirmada. Se excluye por redundancia.
- dano_total y estres no son necesariamente fuga futura segun su formula; se excluyen siguiendo la politica conservadora solicitada.
- Una proporcion 74/26 NO es balance perfecto. La prevalencia que importa es la del objetivo futuro reconstruido.
- No se altera el Excel original. Corregir el generador no corrige retroactivamente su biomasa exportada.

## Comparacion de modelos
Metricas fuera de muestra agrupadas. Umbral 0.5; precision/recall/F1 para muerte. PR-AUC se informa como average precision (AP), no integracion trapezoidal. TN/FP/FN/TP forman la matriz [[TN, FP], [FN, TP]].

- pecera_fuera / Logistica: precision=0.343, recall=0.533, F1=0.417, ROC-AUC=0.617, AP=0.524, accuracy=0.549; matriz=[[15776, 12635], [5762, 6585]].
- pecera_fuera / RandomForest: precision=0.673, recall=0.764, F1=0.715, ROC-AUC=0.898, AP=0.836, accuracy=0.816; matriz=[[23832, 4579], [2919, 9428]].
- pecera_fuera / XGBoost: precision=0.781, recall=0.799, F1=0.790, ROC-AUC=0.936, AP=0.887, accuracy=0.871; matriz=[[25645, 2766], [2483, 9864]].
- por_pez_con_pecera / Logistica: precision=0.708, recall=0.849, F1=0.772, ROC-AUC=0.932, AP=0.876, accuracy=0.848; matriz=[[24081, 4330], [1863, 10484]].
- por_pez_con_pecera / RandomForest: precision=0.773, recall=0.834, F1=0.803, ROC-AUC=0.944, AP=0.899, accuracy=0.876; matriz=[[25393, 3018], [2048, 10299]].
- por_pez_con_pecera / XGBoost: precision=0.772, recall=0.841, F1=0.805, ROC-AUC=0.947, AP=0.906, accuracy=0.877; matriz=[[25347, 3064], [1966, 10381]].
- por_pez_sin_pecera / Logistica: precision=0.708, recall=0.849, F1=0.772, ROC-AUC=0.932, AP=0.876, accuracy=0.848; matriz=[[24085, 4326], [1859, 10488]].
- por_pez_sin_pecera / RandomForest: precision=0.774, recall=0.835, F1=0.803, ROC-AUC=0.944, AP=0.900, accuracy=0.876; matriz=[[25398, 3013], [2034, 10313]].
- por_pez_sin_pecera / XGBoost: precision=0.771, recall=0.842, F1=0.805, ROC-AUC=0.947, AP=0.907, accuracy=0.876; matriz=[[25318, 3093], [1955, 10392]].

## Efecto de identificar la pecera
- Logistica: cambio ROC-AUC=+0.000, AP=-0.000, F1=-0.000.
- RandomForest: cambio ROC-AUC=-0.000, AP=-0.001, F1=-0.001.
- XGBoost: cambio ROC-AUC=-0.000, AP=-0.000, F1=+0.000.

Una diferencia pequena no descarta memorizacion: volumen, equipos y limites de especie tambien identifican ambientes.

## Variables importantes
Importancia por permutacion en validacion, medida como caida de AP. Las correlaciones pueden repartir u ocultar importancia.
- Logistica: ph (0.4264), salud_lag1 (0.2016), num_especies_pecera (0.1141), danos_acumulados_lag1 (0.0945), dano_ph (0.0745)
- RandomForest: salud_lag1 (0.1400), danos_acumulados_lag1 (0.0936), amoniaco (0.0859), ph (0.0136), ph_max (-0.0021)
- XGBoost: amoniaco (0.3360), salud_lag1 (0.2975), danos_acumulados_lag1 (0.0326), ph (0.0078), temperatura (0.0051)

## Alertas
Sin resultados >0.98 ni dominancia >50%; esto no demuestra ausencia de fuga.

## Columnas eliminadas y motivo
- vivo: Inverso de murio; solo se usa murio para elegibilidad.
- salud: Estado contemporaneo excluido por el prompt; se conserva solo salud_lag1.
- riesgo_muerte: Derivado de salud y forzado a 1 en registros de muerte.
- punto_critico: El generador fuerza 1 en filas de muerte.
- danos_acumulados: Estado contemporaneo excluido; se conserva solo danos_acumulados_lag1.
- nivel_estres: Resumen ambiental derivado; exclusion conservadora solicitada, no fuga futura demostrada.
- nivel_estres_cat: Categoria del dano ambiental; exclusion conservadora solicitada.
- dano_total: Suma de desvios ambientales; exclusion conservadora solicitada.
- ox_desvio: Exclusion solicitada; su constancia se informa en auditoria.
- dano_oxigeno: Exclusion solicitada; su constancia se informa en auditoria.
- ox_critico: Exclusion solicitada; su constancia se informa en auditoria.
- sobrepoblacion: Exclusion solicitada; su constancia se informa en auditoria.
- tiene_filtro: Exclusion solicitada; su constancia se informa en auditoria.
- tiene_aireacion: Exclusion solicitada; su constancia se informa en auditoria.
- ph_desvio: Redundante con dano_ph.
- temp_desvio: Redundante con dano_temp.
- nh3_desvio: Redundante con dano_amoniaco.
- pez_id: Identificador/metadato, no predictor.
- pecera_id: Identificador/metadato, no predictor.
- pecera_nombre: Identificador/metadato, no predictor.
- especie_id: Identificador/metadato, no predictor.
- hora_sim: Identificador/metadato, no predictor.
- murio: Se usa para elegibilidad y etiqueta futura, no como predictor.
- causa_riesgo_principal: Resumen ambiental redundante; no fuga directa segun generador.
- temp_max: Correlacion > 0.95 con temp_min en entrenamiento (ajuste final).
- dano_amoniaco: Correlacion > 0.95 con amoniaco en entrenamiento (ajuste final).
- filtro_mg_h: Correlacion > 0.95 con volumen_l en entrenamiento (ajuste final).
- aireacion_mg_h: Correlacion > 0.95 con volumen_l en entrenamiento (ajuste final).

## Conclusiones y limites
Modelo exploratorio seleccionado por AP agrupada: XGBoost. Se guarda para reproducir, no como modelo validado en granja.
El modelo aprende este simulador. Hay solo siete ambientes, una trayectoria compartida por pecera y parametros biologicos supuestos. Separar peces deja condiciones de agua compartidas entre train/test; dejar peceras fuera es la prueba mas exigente de estas salidas.
La seleccion del modelo usa la misma validacion comparativa: no es una estimacion final independiente ni prospectiva. Para eso hacen falta corridas nuevas con semillas, ambientes y equipos variados y una prueba temporal independiente.
Los peces que mueren antes de su primera observacion quedan fuera: el resultado es condicional a estar vivo y observado. No deducir muerte de una fila ausente. No usar datos del final como supervivencia sin observar t+1.
Los pesos de clase mejoran sensibilidad pero las probabilidades no estan calibradas. Se necesita calibracion y elegir el umbral en validacion interna segun el costo de falsas alarmas y muertes omitidas.
Las probabilidades, unidades de amoniaco, filtro, alimento y mecanismos biologicos requieren validacion externa. No se cambiaron coeficientes para obtener mejores metricas. Los resultados no se trasladan automaticamente a una granja real.
