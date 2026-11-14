# Comparacion de horizontes y mejora de XGBoost

Horizonte elegido en validacion antes de abrir test: 12 horas. Politica principal F2.
96 corridas nuevas (72 entrenamiento, 6 calibracion, 6 validacion, 12 test). Semillas distintas al experimento anterior. El mecanismo de mortalidad no se modifico.
La historia usa solo mediciones disponibles hasta t, incluidas medias de 6, 12 y 24 h, maximos y exposicion acumulada.
Se compararon profundidad, numero de arboles y peso de muertes con validacion cruzada agrupada por corrida.
Los objetivos 1, 6 y 12 h tienen distintas prevalencias y muestras por censura. Una mejor metrica a 12 h no demuestra mejora para predecir muertes a 1 h.
Para horizontes largos una misma muerte puede producir varias filas positivas previas. TP no equivale al numero de peces muertos distintos. Las metricas son por observacion pez/hora.
La politica recall80 exige 80% en validacion; no garantiza ese recall en test.

## Test
- historia_24h 1h F2: precision=10.76%, recall=25.91%, F1=0.1520, AP=0.0774, referencia AP=0.0068; TP=71, FP=589, FN=203.
- historia_24h 1h recall80_validacion: precision=2.38%, recall=84.31%, F1=0.0462, AP=0.0774, referencia AP=0.0068; TP=231, FP=9487, FN=43.
- sin_historia_nueva 1h F2: precision=7.90%, recall=33.21%, F1=0.1276, AP=0.0754, referencia AP=0.0068; TP=91, FP=1061, FN=183.
- historia_24h 6h F2: precision=14.98%, recall=80.54%, F1=0.2527, AP=0.3500, referencia AP=0.0416; TP=1308, FP=7422, FN=316.
- historia_24h 6h recall80_validacion: precision=13.33%, recall=85.10%, F1=0.2305, AP=0.3500, referencia AP=0.0416; TP=1382, FP=8986, FN=242.
- historia_24h 12h F2: precision=24.23%, recall=83.15%, F1=0.3752, AP=0.5081, referencia AP=0.0852; TP=2635, FP=8240, FN=534.
- historia_24h 12h recall80_validacion: precision=23.27%, recall=84.38%, F1=0.3648, AP=0.5081, referencia AP=0.0852; TP=2674, FP=8816, FN=495.

Los supuestos biologicos y la aleatoriedad siguen limitando las predicciones. No se reclama un resultado excelente por haber cambiado horizonte o aumentado alertas. No reajustar modelos con estos test; nuevos cambios requieren semillas finales nuevas.