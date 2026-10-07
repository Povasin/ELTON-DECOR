[CmdletBinding()]
param([switch]$BootstrapOwner)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$runtime = Join-Path $root "private/runtime"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
if (!(Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker Desktop was not found. Start Docker Desktop before running the local PostgreSQL service." }
if (!(Test-Path -LiteralPath (Join-Path $root ".venv/Scripts/python.exe"))) { throw "Python environment .venv was not found. Install the project Python dependencies first." }
$python = Join-Path $root ".venv/Scripts/python.exe"
$workspacePythonPaths = @(
  (Join-Path $root "packages/database/src"),
  (Join-Path $root "apps/api/src")
)
if ($env:PYTHONPATH) { $workspacePythonPaths += $env:PYTHONPATH }
$env:PYTHONPATH = $workspacePythonPaths -join [System.IO.Path]::PathSeparator
& (Join-Path $PSScriptRoot "prepare-cache.ps1")

function New-LocalSecret {
  $bytes = New-Object byte[] 48
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Ensure-Secret([string]$name) {
  $path = Join-Path $runtime $name
  if (!(Test-Path -LiteralPath $path)) {
    $secret = New-LocalSecret
    [System.IO.File]::WriteAllText($path, "$secret$([Environment]::NewLine)", [System.Text.UTF8Encoding]::new($false))
  }
  return $path
}

function Get-Secret([string]$name) {
  $path = Ensure-Secret $name
  return (Get-Content -LiteralPath $path -Raw).Trim()
}

function Assert-PortFree([int]$port) {
  if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
    throw "Port $port is already in use. The script does not stop processes it did not start."
  }
}

function Start-LocalProcess([string]$name, [string]$file, [string[]]$arguments, [string]$workingDirectory = $root) {
  $stdout = Join-Path $runtime "$name.out.log"
  $stderr = Join-Path $runtime "$name.err.log"
  $process = Start-Process -FilePath $file -ArgumentList $arguments -WorkingDirectory $workingDirectory -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  [pscustomobject]@{ id = $process.Id; name = $name; command_marker = ($arguments -join " "); started_at = (Get-Date).ToUniversalTime().ToString("o") } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime "$name.pid.json") -Encoding utf8
}

$pgPassword = Get-Secret "pg-password.txt"
$env:ELTON_DATABASE_URL = "postgresql+psycopg://elton_demo:$([uri]::EscapeDataString($pgPassword))@127.0.0.1:5432/elton_demo"
$env:ELTON_SESSION_CSRF_KEY = Get-Secret "session-csrf.txt"
$env:ELTON_GUEST_ORIGINS = '["http://localhost:3000"]'
$env:ELTON_ADMIN_ORIGINS = '["http://localhost:3001"]'
$env:ELTON_MEDIA_STORAGE_ROOT = Join-Path $root "var/media"
$env:ELTON_API_URL = "http://127.0.0.1:8000"
$env:ELTON_PG_PASSWORD_FILE = Join-Path $runtime "pg-password.txt"

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
$ffmpegFallback = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_*\ffmpeg-*\bin\ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
$ffprobeFallback = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_*\ffmpeg-*\bin\ffprobe.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ffmpeg) { $env:ELTON_FFMPEG_BINARY = $ffmpeg.Source } elseif ($ffmpegFallback) { $env:ELTON_FFMPEG_BINARY = $ffmpegFallback.FullName }
if ($ffprobe) { $env:ELTON_FFPROBE_BINARY = $ffprobe.Source } elseif ($ffprobeFallback) { $env:ELTON_FFPROBE_BINARY = $ffprobeFallback.FullName }

& docker compose -f (Join-Path $root "compose.local.yaml") up -d pg
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL did not start." }
for ($attempt = 0; $attempt -lt 30; $attempt++) {
  & docker compose -f (Join-Path $root "compose.local.yaml") exec -T pg pg_isready -U elton_demo -d elton_demo *> $null
  if ($LASTEXITCODE -eq 0) { break }
  Start-Sleep -Seconds 1
  if ($attempt -eq 29) { throw "PostgreSQL did not become ready." }
}

& $python -m alembic -c (Join-Path $root "packages/database/alembic.ini") upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migrations could not be applied." }
& $python (Join-Path $root "scripts/seed_demo.py")
if ($LASTEXITCODE -ne 0) { throw "The demonstration catalog could not be loaded." }
if ($BootstrapOwner) { & $python (Join-Path $root "scripts/bootstrap_admin.py"); if ($LASTEXITCODE -ne 0) { throw "The admin owner account could not be created." } }

Assert-PortFree 8000
Assert-PortFree 3000
Assert-PortFree 3001
Start-LocalProcess "api" $python @("-m", "uvicorn", "elton_api.main:app_factory", "--factory", "--app-dir", "apps/api/src", "--host", "127.0.0.1", "--port", "8000")
Start-LocalProcess "storefront" "node.exe" @("node_modules/next/dist/bin/next", "dev", "-p", "3000") (Join-Path $root "apps/storefront")
Start-LocalProcess "admin" "node.exe" @("node_modules/next/dist/bin/next", "dev", "-p", "3001") (Join-Path $root "apps/admin")

for ($attempt = 0; $attempt -lt 30; $attempt++) {
  try {
    $apiReady = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/health/ready" -TimeoutSec 2).StatusCode -eq 200
    $storeReady = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:3000/catalog" -TimeoutSec 2).StatusCode -eq 200
    $adminReady = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:3001/login" -TimeoutSec 2).StatusCode -eq 200
    if ($apiReady -and $storeReady -and $adminReady) { break }
  } catch { }
  Start-Sleep -Seconds 1
  if ($attempt -eq 29) { throw "A local service did not become ready. Logs are available in $runtime." }
}

Write-Output "Storefront: http://localhost:3000"
Write-Output "Admin:      http://localhost:3001/login"
Write-Output "API:        http://localhost:8000/health/ready"
