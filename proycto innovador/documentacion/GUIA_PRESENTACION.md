# Módulo de mortalidad de Pisciber BSF

## Relación con el avance del curso

El avance propone predicción de riesgo en tanques, alertas tempranas, recomendaciones de mantenimiento y estadísticas. Este módulo implementa esas funciones con datos simulados. Demanda y chatbot quedan en los módulos que el equipo trabaja por separado.

## Qué demostrar

1. Abrir **Simulaciones**, elegir ambiente y semilla y seleccionar ejecución en vivo. El servidor calcula una nueva hora por paso y la página la consulta.
2. En **Vista general**, explicar los peces vivos, alertas y muertes esperadas. Estas últimas son la suma de probabilidades individuales en una misma hora.
3. En **Predicciones por pez**, abrir un pez y mostrar su riesgo, mediciones e historial disponible. El simulador genera los acontecimientos; XGBoost estima el riesgo con los datos hasta ese momento.
4. En **Estadísticas de corrida**, explicar la población inicial, las muertes ya ocurridas y la mortalidad acumulada por pecera o especie. Estas estadísticas describen lo observado, mientras la probabilidad mira hacia adelante.
5. En **Seguimiento de alertas**, revisar un aviso: hora emitida, plazo, probabilidad y resultado. Antes de completar el plazo aparece pendiente; después puede resultar aviso correcto o falsa alarma. Al consultar todas las predicciones aparecen también muertes sin aviso y supervivencias correctas.
6. Registrar una atención y mostrar el cambio persistente. La demora se mide en horas simuladas desde la emisión. Registrar atención no altera el motor, no cambia el resultado de la evaluación y no demuestra que se evitó una muerte.
7. En **Simulaciones**, comparar ambientes. El resumen utiliza corridas completas de 96 horas, separa motores y elimina duplicados de semilla/ambiente/motor. Las pruebas en curso se mantienen fuera de ese resumen.
8. Descargar el Excel. Incluye detalle e historial, mortalidad por grupo, seguimiento al corte, atención y sugerencias de revisión, además de las métricas del modelo reservado.

## Cómo leer los indicadores

- Mortalidad acumulada = peces muertos hasta el corte / peces iniciales. Cada pez se cuenta una vez.
- Precisión de alertas = avisos correctos / avisos evaluados. Una falsa alarma significa que el pez no murió dentro de ese plazo; podría morir más tarde.
- Recall = observaciones positivas detectadas / observaciones positivas. En plazos largos una muerte puede producir varias observaciones positivas.
- Las muertes distintas anticipadas se cuentan por pez, por separado de las observaciones pez/hora.
- Demora de atención = hora simulada de registro de la atención − hora de emisión del aviso. No se presenta como un tiempo de respuesta empresarial real.
- «Sin casos» indica denominador vacío. No equivale a cero rendimiento.

## Reglas de revisión

Las sugerencias comparan mediciones con los rangos de las fichas simuladas y con el estado del filtro/aireación. Recomiendan confirmar lecturas y revisar equipos o fichas. No son diagnósticos biológicos ni recomendaciones de dosificación. No atribuyen una causa de muerte al modelo.

## Alcance de las conclusiones

Se puede demostrar el funcionamiento del flujo de datos, las predicciones y su evaluación en escenarios simulados. No se ha medido una reducción real de mortalidad o costos de Pisciber BSF ni realizado pruebas de campo con su personal. Las afirmaciones del avance sobre datos empresariales o visitas deben ajustarse a las evidencias que el equipo realmente tenga.

La comparación de escenarios es descriptiva. Para evaluar el modelo en simulaciones nuevas se conservan los pesos y umbrales; no se reentrena usando el resultado de la prueba.
