$ErrorActionPreference='Stop'
$raiz=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$archivo=Join-Path $raiz 'archivo_historico'
$commit=(git -C $raiz rev-parse HEAD).Trim()
if((git -C $raiz log -1 --format=%s) -ne 'Organiza aplicacion, simulador e historicos de Pisciber'){throw 'Se requiere el commit previo de organización'}
$registro=[Collections.Generic.List[object]]::new()
function Validar-Ruta([string]$ruta){
 $absoluta=[IO.Path]::GetFullPath($ruta)
 if(-not $absoluta.StartsWith($raiz+[IO.Path]::DirectorySeparatorChar)){throw "Ruta fuera del proyecto: $absoluta"}
 return $absoluta
}
function Retirar([string]$ruta,[string]$motivo,[string]$canonico=''){
 $ruta=Validar-Ruta $ruta
 if(-not(Test-Path -LiteralPath $ruta)){return}
 $item=Get-Item -LiteralPath $ruta -Force
 if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'No eliminar enlaces recursivamente'}
 if($item.PSIsContainer){
  $enlaces=Get-ChildItem -LiteralPath $ruta -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }
  if($enlaces){throw 'Carpeta con enlaces: requiere revisión individual'}
  $bytes=(Get-ChildItem -LiteralPath $ruta -Recurse -File -Force | Measure-Object Length -Sum).Sum
  Remove-Item -LiteralPath $ruta -Recurse -Force
 }else{$bytes=$item.Length;Remove-Item -LiteralPath $ruta -Force}
 $registro.Add([PSCustomObject]@{ruta=$ruta.Substring($raiz.Length+1);bytes=[long]$bytes;motivo=$motivo;conservado_en=$canonico})
}
# Solo duplicados exactos, comprobados con SHA-256 contra el archivo vigente.
foreach($sub in @('datos_base','modelos')){
 $fuente=Join-Path $raiz ('proycto innovador\simulacion\'+$sub)
 foreach($actual in Get-ChildItem -LiteralPath $fuente -File){
  $viejo=Join-Path $archivo ('experimento_v3\'+$actual.Name)
  if((Test-Path -LiteralPath $viejo) -and ((Get-FileHash -LiteralPath $viejo).Hash -eq (Get-FileHash -LiteralPath $actual.FullName).Hash)){
   Retirar $viejo 'Copia idéntica SHA-256; se conserva el archivo vigente' $actual.FullName.Substring($raiz.Length+1)
  }
 }
}
# Paquetes generados a partir de código y datos que permanecen guardados.
Get-ChildItem -LiteralPath $archivo -File -Filter '*.zip' | ForEach-Object { Retirar $_.FullName 'Paquete regenerable; snapshot previo conservado en Git' }
# Copia de trabajo de los resultados Colab, conservados en el ZIP de origen.
$zipColab=Join-Path $archivo 'colab_resultados\Resultados_Colab_v3.zip'
if(Test-Path -LiteralPath $zipColab){Retirar (Join-Path $archivo 'outputs') 'Extracción temporal redundante' 'archivo_historico/colab_resultados/Resultados_Colab_v3.zip'}
foreach($nombre in @('build','dist')){
 $ruta=Join-Path $archivo $nombre
 if((Test-Path -LiteralPath $ruta) -and -not (Get-ChildItem -LiteralPath $ruta -Force)){Retirar $ruta 'Carpeta vacía de compilación antigua'}
}
Retirar (Join-Path $raiz '__pycache__') 'Caché Python regenerable'
$app=Join-Path $raiz 'proycto innovador'
$caches=Get-ChildItem -LiteralPath $app -Directory -Recurse -Force | Where-Object {$_.Name -eq '__pycache__' -and $_.FullName -notlike '*\.venv\*' -and $_.FullName -notlike '*\node_modules\*'}
foreach($cache in $caches){Retirar $cache.FullName 'Caché Python regenerable'}
# El enlace de herramientas apunta a un runtime compartido. Se elimina SOLO el enlace.
$enlace=Join-Path $raiz 'node_modules'
if(Test-Path -LiteralPath $enlace){
 $item=Get-Item -LiteralPath $enlace -Force
 if($item.LinkType -ne 'Junction'){throw 'node_modules raíz no es el enlace esperado'}
 [IO.Directory]::Delete((Validar-Ruta $enlace))
 $registro.Add([PSCustomObject]@{ruta='node_modules';bytes=0;motivo='Enlace local de herramientas eliminado sin tocar su destino compartido';conservado_en='Runtime de herramientas externo al proyecto'})
}
$salida=Join-Path $app 'documentacion\LIMPIEZA.json'
@{commit_previo=$commit;archivos_retirados=$registro;bytes_retirados=($registro|Measure-Object bytes -Sum).Sum} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $salida -Encoding utf8
$mb=[math]::Round(($registro|Measure-Object bytes -Sum).Sum/1MB,2)
@"
# Limpieza posterior al commit

Commit de respaldo: $commit

Se retiraron $mb MiB de archivos redundantes o regenerables del árbol de trabajo. La versión anterior permanece en Git; esta cifra no equivale al espacio neto libre del disco, porque Git conserva el histórico comprimido.

Se conservaron la aplicación, sus dependencias activas, la configuración privada, todos sus modelos y corridas, los notebooks y los informes anteriores. Los datos de entrenamiento vigentes permanecen en simulacion/datos_base. Los resultados Colab originales permanecen comprimidos en archivo_historico/colab_resultados.

Las copias idénticas retiradas se identifican con su ubicación canónica en LIMPIEZA.json. Para volver a ejecutar un script histórico que esperaba esas copias, se pueden copiar desde esa ubicación o recuperar el archivo del commit previo.

El node_modules que estaba en la raíz era un enlace a herramientas compartidas. Solo se retiró el enlace; no se borró su destino. Las dependencias React de la aplicación se mantienen.
"@ | Set-Content -LiteralPath (Join-Path $app 'documentacion\LIMPIEZA.md') -Encoding utf8
Write-Output "Limpieza terminada: $mb MiB retirados del árbol de trabajo."
