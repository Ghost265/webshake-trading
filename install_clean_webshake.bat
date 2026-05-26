@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Webshake Trading Clean Install

echo ============================================================
echo  Webshake Trading - Clean Install v1.0 Beta
echo ============================================================
echo.
echo Diese Installation setzt Webshake Trading komplett frisch auf.
echo Datenbank, Logs, Backups und Config in DIESEM Ordner sind leer/neu.
echo.

if not exist "backend" (
  echo FEHLER: backend-Ordner fehlt.
  pause
  exit /b 1
)
if not exist "desktop" (
  echo FEHLER: desktop-Ordner fehlt.
  pause
  exit /b 1
)

mkdir database 2>nul
mkdir logs 2>nul
mkdir backups 2>nul
mkdir config 2>nul
mkdir userdata 2>nul
mkdir temp 2>nul
mkdir updates 2>nul

echo [1/5] Pruefe Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo FEHLER: Python wurde nicht gefunden. Bitte Python 3.12 installieren und "Add Python to PATH" aktivieren.
  pause
  exit /b 1
)

echo [2/5] Pruefe Node.js...
node -v >nul 2>&1
if errorlevel 1 (
  echo FEHLER: Node.js wurde nicht gefunden. Bitte Node.js LTS installieren.
  pause
  exit /b 1
)

echo [3/5] Erstelle Python-Umgebung und installiere Backend-Pakete...
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo FEHLER: Python-Umgebung konnte nicht erstellt werden.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo FEHLER: Backend-Pakete konnten nicht installiert werden.
  pause
  exit /b 1
)

echo [4/5] Installiere Desktop-Pakete...
cd /d "%~dp0desktop"
npm install
if errorlevel 1 (
  echo FEHLER: Node-Pakete konnten nicht installiert werden.
  pause
  exit /b 1
)

echo [5/5] Initialisiere frische Ordnerstruktur...
cd /d "%~dp0"
if not exist "backend\.env" copy "backend\.env.example" "backend\.env" >nul

echo.
echo ============================================================
echo  Clean Install abgeschlossen.
echo ============================================================
echo.
choice /C JN /N /M "Webshake Trading jetzt starten? [J/N] "
if errorlevel 2 goto end
call "%~dp0start_webshake.bat"

:end
echo.
echo Fertig. Zum Starten spaeter: start_webshake.bat
pause
exit /b 0
