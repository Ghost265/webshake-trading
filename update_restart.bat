@echo off
setlocal
title Webshake-Trading Update Restart
cd /d "%~dp0"

if exist "%~dp0update_webshake.bat" (
    call "%~dp0update_webshake.bat"
    exit /b %ERRORLEVEL%
) else (
    echo FEHLER: update_webshake.bat nicht gefunden.
    pause
    exit /b 1
)
