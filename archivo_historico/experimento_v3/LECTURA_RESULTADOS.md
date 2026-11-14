# Como interpretar los resultados mejorados

Filas nuevas: 311,433; corridas: 96.
Horizonte preferido antes de test: 12 h.
Los resultados con historia y sin historia a 1 h usan las mismas corridas de test. La version con historia incorpora tambien seleccion de configuracion; la diferencia no aisla solo el efecto de historia.
Comparar recall entre 1 y 12 h cambia la pregunta. Se presentan todas las filas, no solo la mejor.

## Muertes distintas anticipadas (al menos un aviso dentro del horizonte)
- 1 h: 71 de 274 muertes distintas (25.9%). Falsas alarmas por observacion: 589.
- 6 h: 231 de 274 muertes distintas (84.3%). Falsas alarmas por observacion: 7422.
- 12 h: 247 de 274 muertes distintas (90.1%). Falsas alarmas por observacion: 8240.

Un aviso puede repetirse para un mismo pez en distintas horas. No sumar las muertes anticipadas de distintos horizontes ni confundir TP de observaciones con peces distintos.
Una falsa alarma significa que no murio dentro del horizonte evaluado, no que nunca murio.
El rendimiento es el obtenido; no se garantiza alcanzar una precision o recall deseados.
Si se modifican modelos tras observar este test, debe reservarse otro conjunto de semillas nuevas.

## Revision de exactitud elevada
La exactitud a 1 h supera 0,98, pero siempre predecir supervivencia alcanza 99.3244%. No se considera por ello un resultado casi perfecto: se revisaron variables permitidas, causalidad de la historia, eventos, censura, corridas disjuntas y reproduccion de predicciones guardadas. El ROC-AUC no supera 0,98. Estos controles no prueban ausencia absoluta de fuga.