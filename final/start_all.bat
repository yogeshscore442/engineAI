@echo off
title AI Health Copilot - Full Stack Launcher
echo ====================================================
echo  Starting AI Health Copilot (Backend + AI + Frontend)
echo ====================================================

set "PATH=C:\Users\YOGESH\nodejs\node-v22.23.3-win-x64;%PATH%"
echo Starting Backend API (Port 8001)...
start "Health Copilot Backend" powershell -ExecutionPolicy Bypass -NoExit -File "%~dp0start_backend.ps1" -Port 8001

timeout /t 2 /nobreak >nul

echo Starting Frontend UI (Port 5173)...
cd /d "%~dp0naveen\hi-main\hi-main\frontend"
cmd /c npm run dev -- --host 127.0.0.1 --port 5173
pause
