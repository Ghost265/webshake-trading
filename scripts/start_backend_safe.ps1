
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backend = Join-Path $root "backend"

Write-Host "Starte Backend im Safe-Mode..."

Set-Location $backend

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}

$py = ".venv\Scripts\python.exe"

Start-Process -FilePath $py `
  -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8765 --workers 1" `
  -WorkingDirectory $backend `
  -WindowStyle Hidden

Write-Host "Backend gestartet."
