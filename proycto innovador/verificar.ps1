$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONPATH=Join-Path $PSScriptRoot 'web'
& '.\.venv\Scripts\python.exe' -m unittest backend.test_analysis backend.test_live backend.test_realistic backend.test_app -v
if($LASTEXITCODE -ne 0){throw 'Fallaron las pruebas Python'}
Push-Location web/frontend
npm.cmd run build
if($LASTEXITCODE -ne 0){throw 'Falló la compilación React'}
Pop-Location
