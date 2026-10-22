param([int]$Port = 5173)
$ErrorActionPreference = 'Stop'
$frontendDir = Join-Path $PSScriptRoot 'naveen\hi-main\hi-main\frontend'
Push-Location $frontendDir
try {
    cmd /c npm run dev -- --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
