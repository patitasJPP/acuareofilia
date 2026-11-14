# Evaluacion operativa

El modelo se entrega como experimento, no como sistema de alerta confiable.
En prueba: 85 muertes detectadas, 205 omitidas, 1168 falsas alarmas.
La exactitud de siempre predecir supervivencia es mayor que la del modelo: los eventos son raros, por eso accuracy no sirve como criterio principal.
La calibracion no garantizo mejora: Brier antes 0.007278, despues 0.007314. Se informa sin elegir con test.
No se modificaron coeficientes ni umbral tras observar test. Para investigar otro horizonte o politica de alertas se debe fijar el nuevo protocolo y reservar semillas finales nuevas.
La incertidumbre individual y la falta de validacion biologica no quedan resueltas por generar mas filas.
