@echo off
cd /d "%~dp0"
echo ========================================
echo       pr0-retroconsole Starter          
echo ========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    pause
)
