$ErrorActionPreference = "Stop"
$destDir = "C:\Users\YOGESH\nodejs"
if (!(Test-Path $destDir)) { 
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null 
}
$zipPath = Join-Path $destDir "node-v22.zip"
Write-Host "Downloading Node.js v22.23.3 (35 MB)..."
curl.exe -L -o $zipPath https://nodejs.org/dist/v22.23.3/node-v22.23.3-win-x64.zip

Write-Host "Extracting Node.js v22..."
Expand-Archive -Path $zipPath -DestinationPath $destDir -Force
if (Test-Path $zipPath) {
    Remove-Item -Path $zipPath -Force
}

$nodeDir = Join-Path $destDir "node-v22.23.3-win-x64"
Write-Host "Configuring User PATH..."
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
# Remove older node-v20 path if present
$cleanPath = ($userPath -split ';' | Where-Object { $_ -notlike "*node-v20*" -and $_ -notlike "*node-v22*" }) -join ';'
[Environment]::SetEnvironmentVariable("Path", "$nodeDir;$cleanPath", "User")

Write-Host "Verifying Node.js and npm:"
$env:Path = "$nodeDir;" + $env:Path
& "$nodeDir\node.exe" -v
& "$nodeDir\npm.cmd" -v
Write-Host "Node.js v22 successfully installed and ready!"
