# Comparacion de horizontes y mejora de XGBoost

Horizonte elegido en validacion antes de abrir test: 12 horas. Politica principal F2.
96 corridas nuevas (72 entrenamiento, 6 calibracion, 6 validacion, 12 test). Semillas distintas al experimento anterior. El mecanismo de mortalidad no se modifico.
La historia usa solo mediciones disponibles hasta t, incluidas medias de 6, 12 y 24 h, maximos y exposicion acumulada.
Se compararon profundidad, numero de arboles y peso de muertes con validacion cruzada agrupada por corrida.
Los objetivos 1, 6 y 12 h tienen distintas prevalencias y muestras por censura. Una mejor metrica a 12 h no demuestra mejora para predecir muertes a 1 h.
Para horizontes largos una misma muerte puede producir varias filas positivas previas. TP no equivale al numero de peces muertos distintos. Las metricas son por observacion pez/hora.
La politica recall80 exige 80% en validacion; no garantiza ese recall en test.

## Test
- historia_24h 1h F2: precision=8.25%, recall=36.50%, F1=0.1346, AP=0.0767, referencia AP=0.0068; TP=100, FP=1112, FN=174.
- historia_24h 1h recall80_validacion: precision=2.43%, recall=83.58%, F1=0.0472, AP=0.0767, referencia AP=0.0068; TP=229, FP=9194, FN=45.
- sin_historia_nueva 1h F2: precision=8.96%, recall=31.02%, F1=0.1390, AP=0.0784, referencia AP=0.0068; TP=85, FP=864, FN=189.
- historia_24h 6h F2: precision=15.28%, recall=80.60%, F1=0.2569, AP=0.3520, referencia AP=0.0416; TP=1309, FP=7256, FN=315.
- historia_24h 6h recall80_validacion: precision=13.23%, recall=86.15%, F1=0.2293, AP=0.3520, referencia AP=0.0416; TP=1399, FP=9178, FN=225.
- historia_24h 12h F2: precision=23.55%, recall=84.51%, F1=0.3683, AP=0.5055, referencia AP=0.0852; TP=2678, FP=8694, FN=491.
- historia_24h 12h recall80_validacion: precision=23.67%, recall=84.22%, F1=0.3696, AP=0.5055, referencia AP=0.0852; TP=2669, FP=8606, FN=500.

Los supuestos biologicos y la aleatoriedad siguen limitando las predicciones. No se reclama un resultado excelente por haber cambiado horizonte o aumentado alertas. No reajustar modelos con estos test; nuevos cambios requieren semillas finales nuevas.