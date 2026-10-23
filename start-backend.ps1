$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Write-Host 'SupplyZero API: http://127.0.0.1:8000 (docs: /docs)' -ForegroundColor Green
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
