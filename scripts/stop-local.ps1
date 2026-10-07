$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$runtime = Join-Path $root "private/runtime"

foreach ($name in "api", "storefront", "admin") {
  $pidFile = Join-Path $runtime "$name.pid.json"
  if (!(Test-Path -LiteralPath $pidFile)) { continue }
  $removePidFile = $false
  try {
    $saved = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($saved.id)" -ErrorAction Stop
    if ($process.CommandLine -and $saved.command_marker -and $process.CommandLine.Contains($saved.command_marker)) {
      Stop-Process -Id $saved.id -ErrorAction Stop
      $removePidFile = $true
    } else {
      Write-Warning "The $name process with PID $($saved.id) does not match its saved command and was not stopped."
    }
  } catch {
    # A missing process leaves behind only stale metadata and can be forgotten safely.
    $removePidFile = $true
  }
  if ($removePidFile) { Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue }
}

Write-Output "The local API, storefront, and admin app were stopped. PostgreSQL is still running."
