$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root "private/runtime"
if (!(Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker Desktop не найден. Установите и запустите Docker Desktop для PostgreSQL-проверки." }
if (!(Test-Path -LiteralPath (Join-Path $runtime "pg-password.txt"))) { throw "Не найден private/runtime/pg-password.txt. Сначала подготовьте локальный runtime." }
if (!(Test-Path -LiteralPath (Join-Path $root ".venv/Scripts/python.exe"))) { throw "Не найден .venv. Подготовьте Python-зависимости проекта перед PostgreSQL-проверкой." }
$pgPassword = (Get-Content -LiteralPath (Join-Path $runtime "pg-password.txt") -Raw).Trim()
$encodedPassword = [uri]::EscapeDataString($pgPassword)
$env:ELTON_TEST_DATABASE_URL = "postgresql+psycopg://elton_demo:$encodedPassword@127.0.0.1:5432/elton_test"

$exists = & docker compose -f (Join-Path $root "compose.local.yaml") exec -T pg psql -U elton_demo -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='elton_test'"
if ($LASTEXITCODE -ne 0) { throw "Не удалось проверить тестовую PostgreSQL базу." }
if ($exists.Trim() -ne "1") {
  & docker compose -f (Join-Path $root "compose.local.yaml") exec -T pg createdb -U elton_demo elton_test
  if ($LASTEXITCODE -ne 0) { throw "Не удалось создать отдельную тестовую базу." }
}

$python = Join-Path $root ".venv/Scripts/python.exe"
& $python -m pytest packages/database/tests apps/api/tests -q
exit $LASTEXITCODE
