param([switch]$RealAI)
$ErrorActionPreference = 'Stop'

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " Starting AI Health Copilot (All 3 Integrated Modules)" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Start Backend in separate process
$backendArgs = if ($RealAI) { "-ExecutionPolicy Bypass -File .\start_backend.ps1 -RealAI" } else { "-ExecutionPolicy Bypass -File .\start_backend.ps1" }
Start-Process powershell -ArgumentList $backendArgs -WorkingDirectory $PSScriptRoot

Write-Host "✓ Backend server starting on http://127.0.0.1:8000 (API & Docs)" -ForegroundColor Green
Start-Sleep -Seconds 2

# 2. Start Frontend in current window or separate window
Write-Host "✓ Frontend UI starting on http://127.0.0.1:5173" -ForegroundColor Green
$frontendDir = Join-Path $PSScriptRoot 'naveen\hi-main\hi-main\frontend'
Push-Location $frontendDir
try {
    cmd /c npm run dev -- --host 127.0.0.1 --port 5173
}
finally {
    Pop-Location
}
