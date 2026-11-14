param([int]$Puerto=8000)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonProyecto=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProyecto)) {
    py -m venv --system-site-packages .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno Python.' }
    & $pythonProyecto -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Python.' }
}
if (-not (Test-Path -LiteralPath 'web\frontend\dist\index.html')) {
    Push-Location web/frontend
    npm.cmd install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias de React.' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo construir React.' }
    Pop-Location
}
Write-Host "Pisciber disponible en http://127.0.0.1:$Puerto"
& $pythonProyecto -m uvicorn backend.main:app --app-dir web --host 127.0.0.1 --port $Puerto
