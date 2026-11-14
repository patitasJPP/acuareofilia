$ErrorActionPreference='Stop'
$raizProyecto=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
Set-Location -LiteralPath $raizProyecto
if(Test-Path -LiteralPath (Join-Path $raizProyecto 'web\backend')){Write-Output 'La estructura ya está organizada.'; exit 0}
New-Item -ItemType Directory -Force -Path web,simulacion,simulacion\motor,datos,resultados,logs,documentacion,herramientas | Out-Null
$cambios=@(
 @('backend','web\backend'),@('frontend','web\frontend'),@('ml','simulacion\ml'),
 @('models','simulacion\modelos'),@('seed','simulacion\datos_base'),@('data','datos\corridas'),
 @('exports','resultados\exportaciones'),@('actualizar_ui_vivo.py','herramientas\actualizar_ui_vivo.py')
)
foreach($cambio in $cambios){
 $origen=[IO.Path]::GetFullPath((Join-Path $raizProyecto $cambio[0]))
 $destino=[IO.Path]::GetFullPath((Join-Path $raizProyecto $cambio[1]))
 if(-not $origen.StartsWith($raizProyecto+[IO.Path]::DirectorySeparatorChar) -or -not $destino.StartsWith($raizProyecto+[IO.Path]::DirectorySeparatorChar)){throw 'Ruta fuera del proyecto'}
 if(Test-Path -LiteralPath $origen){
  if(Test-Path -LiteralPath $destino){throw "El destino ya existe: $destino"}
  Move-Item -LiteralPath $origen -Destination $destino
 }
}
$origenMotor=[IO.Path]::GetFullPath((Join-Path $raizProyecto 'web\backend\live_engine.py'))
$destinoMotor=[IO.Path]::GetFullPath((Join-Path $raizProyecto 'simulacion\motor\live_engine.py'))
if(Test-Path -LiteralPath $origenMotor){Move-Item -LiteralPath $origenMotor -Destination $destinoMotor}
foreach($nombreLog in @('servidor.log','servidor-error.log')){
 $origenLog=Join-Path $raizProyecto $nombreLog
 if(Test-Path -LiteralPath $origenLog){Move-Item -LiteralPath $origenLog -Destination (Join-Path $raizProyecto ('logs\anterior-'+$nombreLog))}
}
Write-Output 'Web, simulación, datos y resultados organizados.'
