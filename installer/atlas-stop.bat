@echo off
cd /d "%~dp0"
title Atlas SEO - Stop

echo.
echo  =========================================
echo   Atlas SEO - Stopping...
echo  =========================================
echo.

docker compose stop
if %ERRORLEVEL% EQU 0 (
    echo [OK] Atlas has been stopped.
) else (
    echo [WARN] Could not stop Atlas (it may not be running).
)
echo.
pause
