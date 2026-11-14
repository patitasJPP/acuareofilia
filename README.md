# Pisciber BSF

Abre **INICIAR.bat** para ejecutar la aplicación. Dirección: http://127.0.0.1:8000.

## Carpetas principales

- **proycto innovador/**: aplicación vigente. Incluye web, motor, modelos, datos, resultados y documentación.
- **archivo_historico/**: experimentos anteriores, notebooks de Colab e informes de referencia.

Dentro de la aplicación:

- web/: React y API Python.
- simulacion/: motor, modelos entrenados y datos base.
- datos/: corridas y checkpoints guardados.
- resultados/: Excel, capturas y salidas del simulador independiente.
- documentacion/: guía de presentación, estructura y verificaciones.
- herramientas/: utilidades de mantenimiento.

La configuración privada permanece en proycto innovador/.env y no se incluye en Git. Tampoco se versionan dependencias instaladas, cachés, logs ni archivos temporales.

La limpieza se realiza después del commit de organización. Las copias idénticas retiradas se registran en proycto innovador/documentacion/LIMPIEZA.md.
