# Experimento universitario de alerta de mortalidad

Objetivo: riesgo de muerte en la siguiente hora, condicionado a estar vivo y observado en t.
Seis escenarios; multiples semillas, peceras nuevas, volumen, peso, ambiente, equipos y parametros inciertos. Ningun dato real de mortalidad fue utilizado ni se accedio a cuentas externas.

## Correcciones aplicadas
- Identidad compuesta corrida/pez; eventos explicitos de muerte y censura; seguimiento desde hora cero.
- Sin reposicion: cada pez aporta como maximo una muerte. La diversidad procede de corridas independientes.
- TAN y NH3-N separados, ambos mg N/L; dependencia de pH y temperatura segun fuente EPA.
- Biomasa calculada a partir del peso de los peces vivos; probabilidad 1-exp(-tasa), siempre acotada.
- Ruido de medicion e historia ambiental; variabilidad individual latente no observable. Peces con observaciones iguales pueden tener igual riesgo, aunque su desenlace difiera.
- Lista explicita de predictores: se excluyen salud, carga interna, tasa generadora, muerte, causa, IDs, escenario, semilla, particion y parametros ocultos.
- Corridas completas disjuntas para entrenamiento, calibracion, seleccion/umbral y prueba final.
- Seleccion y one-hot ajustados solo en train; calibracion sigmoid en corridas reservadas; umbral que maximiza F2 en validacion (prioriza recall).
- Importancias en validacion, control negativo e intervalos Monte Carlo por corrida. Las correlaciones no permiten inferir causalidad.

## Resultados de prueba independiente
Modelo elegido antes de test: XGBoost; umbral=0.0428.
- accuracy: 0.9647
- precision: 0.0678
- recall: 0.2931
- f1: 0.1102
- roc_auc: 0.8542
- pr_auc_ap: 0.0543
- brier: 0.0073
Matriz [[TN, FP], [FN, TP]]: [[37441, 1168], [205, 85]].
Brier antes de calibrar: 0.00728; despues: 0.00731; baseline: 0.00740.
Prevalencia test / AP de referencia: 0.7455%.
Control negativo AP=0.0116, prevalencia validacion=0.0093.

## Lo que sigue siendo un supuesto
Las tasas base, respuesta al estres, recuperacion, sensibilidad por individuo, escenarios, excrecion, intercambio gaseoso y filtracion son supuestos exploratorios, registrados por corrida. Los limites por especie proceden de las fichas locales, sin validacion externa. El rango .02-.06 mg NH3-N/L es una escala de sensibilidad del simulador, no un umbral seguro universal.
Los escenarios estables, averias, deterioro y recuperacion se muestrean deliberadamente; su proporcion no estima la frecuencia de incidentes de una empresa. Las probabilidades solo estan calibradas para esta mezcla sintetica.
No se simulan nitritos, salinidad, enfermedad transmisible ni depredacion sin fichas fiables. No se presentan como mecanismos resueltos. La formula quimica no valida la tasa de mortalidad.
No es posible afirmar que el simulador es realista en sentido predictivo sin contrastarlo con observaciones. Se ha mejorado coherencia, trazabilidad y evaluacion, no demostrado validez biologica.
El test permanece como prueba cerrada. No ajustar parametros tras ver su rendimiento. Las alertas agregadas indican numero esperado de muertes, no certeza de muerte ni probabilidad de al menos una.

## Reproduccion
`py experimento_mortalidad.py`
El archivo datos.csv es la fuente completa. El Excel del experimento se genera aparte para consulta. Los resultados anteriores corresponden al motor historico y no describen este experimento.

## Fuentes
- [amoniaco](https://www.epa.gov/wqc/aquatic-life-criteria-ammonia)
- [especiacion](https://www.epa.gov/sites/default/files/2019-02/documents/update-wqc-ammonia-1998.pdf)
- [calibracion](https://scikit-learn.org/stable/modules/calibration.html)
