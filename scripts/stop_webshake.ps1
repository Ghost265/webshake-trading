$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
try { Invoke-RestMethod -Method POST "http://127.0.0.1:8765/api/system/shutdown-log?reason=manual-stop" | Out-Null } catch {}
foreach($port in @(8765,5173)){
  try { Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object { if($_.OwningProcess){ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } } catch {}
}
try {
  Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -in @('python.exe','pythonw.exe','node.exe','electron.exe')) -and
    (($_.CommandLine -like "*$root*") -or ($_.CommandLine -like "*uvicorn*") -or ($_.CommandLine -like "*Webshake*") -or ($_.CommandLine -like "*webshake*"))
  } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
} catch {}
Start-Sleep -Seconds 2
