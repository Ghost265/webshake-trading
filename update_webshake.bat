@echo off
setlocal
title Webshake-Trading Update
cd /d "%~dp0"

echo.
echo Webshake-Trading Update
echo -----------------------

python scripts\update_engine.py
set EXITCODE=%ERRORLEVEL%

echo.
if "%EXITCODE%"=="0" (
    echo Update erfolgreich installiert.
    echo Webshake-Trading wird automatisch gestartet...
    timeout /t 3 /nobreak >nul
    if exist "%~dp0start_webshake.bat" (
        start "" cmd /c ""%~dp0start_webshake.bat""
        exit /b 0
    ) else (
        echo FEHLER: start_webshake.bat nicht gefunden.
        pause
        exit /b 1
    )
) else (
    echo Update mit Fehler beendet. Fehlercode: %EXITCODE%
    pause
    exit /b %EXITCODE%
)
