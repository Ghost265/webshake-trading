@echo off
setlocal
title Webshake-Trading Start
cd /d "%~dp0"

if exist "%~dp0desktop\node_modules\.vite" (
    rmdir /s /q "%~dp0desktop\node_modules\.vite"
)

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start_webshake.ps1"
set EXITCODE=%ERRORLEVEL%

if "%EXITCODE%"=="0" (
    exit /b 0
) else (
    echo.
    echo Start mit Fehler beendet. Fehlercode: %EXITCODE%
    echo Fehlerfenster bleibt sichtbar.
    pause
    exit /b %EXITCODE%
)
