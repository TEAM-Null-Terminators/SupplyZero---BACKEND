$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'frontend')
Write-Host 'SupplyZero dashboard: http://127.0.0.1:5173' -ForegroundColor Green
npm run dev -- --host 127.0.0.1
