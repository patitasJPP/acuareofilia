# Limpieza posterior al commit

Commit de respaldo: 3010c3ff30eb9daf5fce0dc8b342df174a9660e4

Se retiraron 114.22 MiB de archivos redundantes o regenerables del árbol de trabajo. La versión anterior permanece en Git; esta cifra no equivale al espacio neto libre del disco, porque Git conserva el histórico comprimido.

Se conservaron la aplicación, sus dependencias activas, la configuración privada, todos sus modelos y corridas, los notebooks y los informes anteriores. Los datos de entrenamiento vigentes permanecen en simulacion/datos_base. Los resultados Colab originales permanecen comprimidos en archivo_historico/colab_resultados.

Las copias idénticas retiradas se identifican con su ubicación canónica en LIMPIEZA.json. Para volver a ejecutar un script histórico que esperaba esas copias, se pueden copiar desde esa ubicación o recuperar el archivo del commit previo.

El node_modules que estaba en la raíz era un enlace a herramientas compartidas. Solo se retiró el enlace; no se borró su destino. Las dependencias React de la aplicación se mantienen.
