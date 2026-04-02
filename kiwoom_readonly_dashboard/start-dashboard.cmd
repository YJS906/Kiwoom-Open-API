@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dashboard.ps1"
start "" "http://127.0.0.1:3000/dashboard"
endlocal
