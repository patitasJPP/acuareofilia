# Verificación del módulo

Fecha: 14 de noviembre de 2026.

Se verificaron 19 pruebas distintas: contratos de la API y exportación, causalidad temporal, reproducibilidad, checkpoints, reloj sin navegador, estadísticas al corte, atención idempotente, resultados pendientes y comparación con tasas desde conteos. Se recompiló React correctamente.

Verificaciones funcionales en la página:

- Las corridas previas y el checkpoint en vivo se abren después de separar carpetas.
- Las estadísticas concilian población inicial = vivos + muertos, con desglose por pecera y especie.
- El seguimiento permite consultar avisos correctos, falsas alarmas y pendientes.
- Se registró una atención de demostración con nota explícita; quedó guardada en PostgreSQL.
- La comparación por ambiente separa motores y permite cambiar horizonte. Corridas incompletas y semillas repetidas quedan fuera del agregado.
- El Excel incluye las hojas de mortalidad, evolución, seguimiento y sugerencias, además de los datos y métricas previos. Las observaciones de seguimiento no superan el corte solicitado.
- El motor se ejecutó por separado mediante `python -m simulacion.ejecutar` y produjo mediciones, eventos, agua y metadatos dentro de resultados/simulaciones.

Los experimentos históricos externos a esta aplicación, la base original de especies y los documentos del curso se conservaron. La reorganización afecta la aplicación dentro de `proycto innovador`.
