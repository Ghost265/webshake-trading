@echo off
setlocal
title Webshake-Trading Restart
cd /d "%~dp0"

if exist "%~dp0stop_webshake.bat" (
    call "%~dp0stop_webshake.bat"
)

timeout /t 3 /nobreak >nul

if exist "%~dp0start_webshake.bat" (
    call "%~dp0start_webshake.bat"
    exit /b %ERRORLEVEL%
) else (
    echo FEHLER: start_webshake.bat nicht gefunden.
    pause
    exit /b 1
)
