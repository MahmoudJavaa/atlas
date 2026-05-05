@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Atlas SEO

echo.
echo  =========================================
echo   Atlas SEO - Starting...
echo  =========================================
echo.

REM ── Check Docker is installed ────────────────────────────────────────────────
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed or not on PATH.
    echo.
    echo Please install Docker Desktop for Windows first:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    start "" "https://www.docker.com/products/docker-desktop/"
    pause
    exit /b 1
)

REM ── Check Docker daemon is running ───────────────────────────────────────────
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Docker Desktop is not running. Attempting to start it...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker to start (up to 60 seconds)...
    set /a count=0
    :wait_docker
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if %ERRORLEVEL% EQU 0 goto docker_ready
    set /a count+=1
    if !count! LSS 20 goto wait_docker
    echo [ERROR] Docker did not start in time. Please start Docker Desktop manually.
    pause
    exit /b 1
)

:docker_ready
echo [OK] Docker is running.

REM ── Create .env from default if missing ─────────────────────────────────────
if not exist ".env" (
    if exist "default.env" (
        copy "default.env" ".env" >nul
        echo [OK] Created .env from default configuration.
    )
)

REM ── First-run detection ──────────────────────────────────────────────────────
if not exist ".atlas-built" (
    echo.
    echo [FIRST RUN] Building Atlas containers (5-15 minutes depending on your connection)
    echo This only happens once. Please wait...
    echo.
    docker compose pull 2>nul
    docker compose up --build -d
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to build/start Atlas.
        echo Check that Docker Desktop is running and try again.
        pause
        exit /b 1
    )
    echo built > .atlas-built
) else (
    REM Normal start
    docker compose up -d
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to start Atlas containers.
        pause
        exit /b 1
    )
)

echo.
echo [OK] Atlas is starting up...
echo Waiting for services to be ready...
timeout /t 6 /nobreak >nul

REM ── Open browser ─────────────────────────────────────────────────────────────
echo Opening Atlas in your browser...
start "" "http://localhost:3000"

echo.
echo  =========================================
echo   Atlas SEO is running at:
echo   http://localhost:3000
echo.
echo   Dashboard login:
echo   Email:    admin@atlas.local
echo   Password: atlas
echo  =========================================
echo.
echo (You can close this window. Atlas continues running in the background.)
timeout /t 8 /nobreak >nul
