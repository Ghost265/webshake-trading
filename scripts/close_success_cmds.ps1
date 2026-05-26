$ErrorActionPreference = "SilentlyContinue"
# Schließt nur erfolgreiche Webshake-Start/Update-CMDs. Fehlerfenster mit sichtbarer Pause bleiben offen.
Get-CimInstance Win32_Process -Filter "name = 'cmd.exe'" | Where-Object {
  ($_.CommandLine -like "*Webshake Start*") -or
  ($_.CommandLine -like "*start_webshake.bat*") -or
  ($_.CommandLine -like "*update_webshake.bat*")
} | ForEach-Object {
  try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
}
