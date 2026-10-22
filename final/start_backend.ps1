param([switch]$MockAI, [switch]$RealAI, [int]$Port = 8001)
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $projectPython)) {
    $projectPython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (!$projectPython) { throw 'Python not found in system or .venv' }
}
$env:AI_ENGINE_ROOT = Join-Path $PSScriptRoot 'yogesh\healthcare_copilot_AI-Engine-main'
$env:USE_MOCK_AI = if ($MockAI -and !$RealAI) { 'true' } else { 'false' }
$env:DISABLE_CACHE = 'true'
Push-Location (Join-Path $PSScriptRoot 'praveen\backend')
try { & $projectPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port }
finally { Pop-Location }
