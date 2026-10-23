# Keep native Python/pip stderr from becoming a terminating PowerShell error.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

Write-Host 'Preparing SupplyZero...' -ForegroundColor Cyan
if (-not (Test-Path $python)) {
    Write-Host 'Creating Python virtual environment (first run only)...' -ForegroundColor Yellow
    py -3 -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3 was not found. Install Python 3.11+ and enable the Python Launcher (py), then run this script again.' }
}

& $python -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing backend dependencies (first run only)...' -ForegroundColor Yellow
    # The app sandbox may deny pip access to the Windows profile temp directory.
    $pipTemp = Join-Path $root '.supplyzero-tmp'
    New-Item -ItemType Directory -Path $pipTemp -Force | Out-Null
    $env:TEMP = $pipTemp
    $env:TMP = $pipTemp
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Could not update pip in the local virtual environment.' }
    & $python -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}

if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    Write-Host 'Installing frontend dependencies (first run only)...' -ForegroundColor Yellow
    Push-Location (Join-Path $root 'frontend')
    npm install
    $installExit = $LASTEXITCODE
    Pop-Location
    if ($installExit -ne 0) { throw 'Frontend dependency installation failed.' }
}

if (-not (Test-Path (Join-Path $root '.env'))) {
    Copy-Item (Join-Path $root '.env.example') (Join-Path $root '.env')
}

Write-Host 'Adding any missing demo shipments and telemetry...' -ForegroundColor Yellow
Push-Location $root
& $python -m app.seed
$seedExit = $LASTEXITCODE
Pop-Location
if ($seedExit -ne 0) { throw 'Demo data setup failed. Check the backend setup output above.' }

$backendScript = Join-Path $root 'start-backend.ps1'
$frontendScript = Join-Path $root 'start-frontend.ps1'
Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "`"$backendScript`"")
Start-Process powershell.exe -WorkingDirectory (Join-Path $root 'frontend') -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "`"$frontendScript`"")
Start-Sleep -Seconds 2
Write-Host ''
Write-Host 'SupplyZero is starting in two PowerShell windows:' -ForegroundColor Green
Write-Host '  Dashboard: http://127.0.0.1:5173'
Write-Host '  API docs:  http://127.0.0.1:8000/docs'
Write-Host 'Keep both windows open while using the app. Close them to stop the services.'
