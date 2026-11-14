$ErrorActionPreference='Stop'
$raiz=[IO.Path]::GetFullPath($PSScriptRoot)
$archivo=Join-Path $raiz 'archivo_historico'
New-Item -ItemType Directory -Force -Path $archivo | Out-Null
$carpetas=@('backups','db','migrations','experimento_v2','experimento_v3','exportaciones','resultados_ml','outputs','build','dist')
$archivos=@('consultar_peceras.py','database.py','esquema_acuicola.sql','requirements.txt','entrenar_mortalidad.py','estadisticas_colab_v3.py','estadisticas_verificacion.log','experimento_mortalidad.py','experimento_v3_ejecucion.log','exportar_resumen_experimento.mjs','generar_datos_limpios.py','generar_datos_ml.py','mejorar_predicciones.py','ml_prediccion_mortalidad.py','mostrar_resultados_v3.py','Pisciber_BSF_Colab.ipynb','Pisciber_Colab.zip','Pisciber_Entrenamiento_v3.ipynb','Pisciber_Entrenamiento_v3.zip','Pisciber_Resultados_v3.ipynb','PrediccionMortalidad.spec','preparar_colab_v3.py','preparar_colab.py','preparar_entrenamiento_colab_v3.py','recuperar_estadisticas_colab.py','Recuperar_Estadisticas_Colab.zip','requirements-ml.txt','Resultados_Pisciber_v3.zip','revisar_experimento.py','revisar_mejora.py','simulacion_estanque_visual.py','simulacion_todas_peceras_visual.py','simulacion_todas_peceras.py','simulacion_visual.py','simulacion.py','SUPUESTOS_SIMULACION.md','test_experimento.py','test_mejora.py','test_mortalidad.py','unir_mega_excel.py','validar_datos_limpios.py','verificar_resultados_ml.py')
foreach($nombre in ($carpetas+$archivos)){
 $origen=[IO.Path]::GetFullPath((Join-Path $raiz $nombre))
 $destino=[IO.Path]::GetFullPath((Join-Path $archivo $nombre))
 if(-not $origen.StartsWith($raiz+[IO.Path]::DirectorySeparatorChar) -or -not $destino.StartsWith($archivo+[IO.Path]::DirectorySeparatorChar)){throw 'Ruta fuera del proyecto'}
 if(Test-Path -LiteralPath $origen){
  if(Test-Path -LiteralPath $destino){throw "Ya existe $destino"}
  Move-Item -LiteralPath $origen -Destination $destino
 }
}
Write-Output 'Experimentos y utilidades anteriores agrupados en archivo_historico.'
