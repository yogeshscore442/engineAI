param([switch]$AuditDependencies)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
foreach ($project in @('praveen/backend', 'yogesh/healthcare_copilot_AI-Engine-main')) {
    Push-Location (Join-Path $projectRoot $project)
    try {
        & $python -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed: $project" }
    } finally { Pop-Location }
}
Push-Location (Join-Path $projectRoot 'naveen/hi-main/hi-main/frontend')
try {
    foreach ($check in @('test', 'lint', 'build')) {
        & npm.cmd run $check
        if ($LASTEXITCODE -ne 0) { throw "Frontend check failed: $check" }
    }
    if ($AuditDependencies) {
        & npm.cmd audit
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Frontend dependency audit has findings; see QA_REPORT.md.' }
    }
} finally { Pop-Location }
if ($AuditDependencies) {
    & $python -m pip_audit
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Python dependency audit has findings; see QA_REPORT.md.' }
}
