$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backend = Join-Path $root "backend"
$desktop = Join-Path $root "desktop"
$logDir = Join-Path $root "logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$backendLog = Join-Path $logDir "backend_start.log"
$backendErr = Join-Path $logDir "backend_error.log"
$frontendLog = Join-Path $logDir "frontend_start.log"
$frontendErr = Join-Path $logDir "frontend_error.log"
$electronLog = Join-Path $logDir "electron_start.log"

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Webshake-Trading Start v0.1.3-beta" | Out-File -FilePath $backendLog -Encoding UTF8 -Append

function Test-Url($url, $tries, $sleepMs) {
  for($i=0; $i -lt $tries; $i++) {
    try {
      $r = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1
      if($r.StatusCode -ge 200) { return $true }
    } catch {}
    Start-Sleep -Milliseconds $sleepMs
  }
  return $false
}

function Stop-Port($port) {
  try {
    Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    ForEach-Object {
      if($_.OwningProcess) {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
      }
    }
  } catch {}
}

Stop-Port 8765
Stop-Port 5173
Start-Sleep -Seconds 1

if (-not (Test-Path $backend)) {
  "FEHLER: Backend-Ordner fehlt: $backend" | Out-File -FilePath $backendLog -Encoding UTF8 -Append
  exit 2
}

Set-Location $backend

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  "Erstelle Python venv..." | Out-File -FilePath $backendLog -Encoding UTF8 -Append
  python -m venv .venv *>> $backendLog
}

if (Test-Path "requirements.txt") {
  "Pruefe Backend-Abhaengigkeiten..." | Out-File -FilePath $backendLog -Encoding UTF8 -Append
  .venv\Scripts\pip.exe install -r requirements.txt *>> $backendLog
}

"Starte Backend..." | Out-File -FilePath $backendLog -Encoding UTF8 -Append

# Wichtig:
# RedirectStandardOutput und RedirectStandardError duerfen NICHT dieselbe Datei sein.
# Deshalb getrennte Dateien: backend_start.log und backend_error.log
Start-Process `
  -FilePath ".venv\Scripts\python.exe" `
  -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8765" `
  -WorkingDirectory $backend `
  -WindowStyle Hidden `
  -RedirectStandardOutput $backendLog `
  -RedirectStandardError $backendErr

if (-not (Test-Url "http://127.0.0.1:8765/api/status" 40 500)) {
  "FEHLER: Backend nicht erreichbar." | Out-File -FilePath $backendLog -Encoding UTF8 -Append
  if (Test-Path $backendErr) {
    "---- backend_error.log ----" | Out-File -FilePath $backendLog -Encoding UTF8 -Append
    Get-Content $backendErr -ErrorAction SilentlyContinue | Out-File -FilePath $backendLog -Encoding UTF8 -Append
  }
  exit 3
}

"Backend erreichbar." | Out-File -FilePath $backendLog -Encoding UTF8 -Append

if (-not (Test-Path $desktop)) {
  "FEHLER: Desktop-Ordner fehlt: $desktop" | Out-File -FilePath $frontendLog -Encoding UTF8 -Append
  exit 4
}

Set-Location $desktop

if (Test-Path "node_modules\.vite") {
  Remove-Item "node_modules\.vite" -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path "node_modules")) {
  "Installiere Frontend-Abhaengigkeiten..." | Out-File -FilePath $frontendLog -Encoding UTF8 -Append
  npm install *>> $frontendLog
}

"Starte Frontend..." | Out-File -FilePath $frontendLog -Encoding UTF8 -Append
Start-Process `
  -FilePath "cmd.exe" `
  -ArgumentList "/c npm run dev -- --host 127.0.0.1 --port 5173 > `"$frontendLog`" 2> `"$frontendErr`"" `
  -WorkingDirectory $desktop `
  -WindowStyle Hidden

if (-not (Test-Url "http://127.0.0.1:5173" 40 500)) {
  "FEHLER: Frontend nicht erreichbar." | Out-File -FilePath $frontendLog -Encoding UTF8 -Append
  exit 5
}

"Frontend erreichbar." | Out-File -FilePath $frontendLog -Encoding UTF8 -Append

"Starte Electron..." | Out-File -FilePath $electronLog -Encoding UTF8 -Append
Start-Process `
  -FilePath "cmd.exe" `
  -ArgumentList "/c npm start > `"$electronLog`" 2>&1" `
  -WorkingDirectory $desktop `
  -WindowStyle Hidden

exit 0
