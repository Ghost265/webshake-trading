
$ErrorActionPreference = "SilentlyContinue"

Write-Host "Stoppe Webshake Python-Prozesse..."

Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and
  ($_.CommandLine -like '*webshake*' -or $_.CommandLine -like '*uvicorn*')
} | ForEach-Object {
  try {
    Stop-Process -Id $_.ProcessId -Force
    Write-Host "Beendet:" $_.ProcessId
  } catch {}
}

try {
  Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
  ForEach-Object {
    if($_.OwningProcess){
      Stop-Process -Id $_.OwningProcess -Force
    }
  }
} catch {}

Write-Host "Backend-Prozesse gestoppt."
