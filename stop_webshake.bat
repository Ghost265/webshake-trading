@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop_webshake.ps1"
echo Webshake Hintergrundprozesse wurden beendet.
exit /b 0
