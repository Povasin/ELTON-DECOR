[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$cacheRoot = Join-Path $root ".cache"
New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null

# Next.js treats Windows paths with different letter casing as separate modules.
# Store the canonical workspace path and discard only generated compiler caches
# when the project is later opened through a differently-cased path.
$workspacePathMarker = Join-Path $cacheRoot ".workspace-path"
if (Test-Path -LiteralPath $workspacePathMarker) {
  $previousRoot = (Get-Content -LiteralPath $workspacePathMarker -Raw).Trim()
  if ($previousRoot -cne $root) {
    foreach ($generatedCache in @("next", "typescript")) {
      $generatedCachePath = Join-Path $cacheRoot $generatedCache
      if (Test-Path -LiteralPath $generatedCachePath) {
        Remove-Item -LiteralPath $generatedCachePath -Recurse -Force
      }
    }
  }
} else {
  # The marker was introduced after caches had already been generated.  Start
  # once from a clean compiler state so old path metadata cannot be reused.
  foreach ($generatedCache in @("next", "typescript")) {
    $generatedCachePath = Join-Path $cacheRoot $generatedCache
    if (Test-Path -LiteralPath $generatedCachePath) {
      Remove-Item -LiteralPath $generatedCachePath -Recurse -Force
    }
  }
}
Set-Content -LiteralPath $workspacePathMarker -Value $root -Encoding utf8

function Set-Junction([string]$target, [string]$destination) {
  $parent = Split-Path -Parent $target
  New-Item -ItemType Directory -Force -Path $parent | Out-Null

  if (Test-Path -LiteralPath $target) {
    $item = Get-Item -LiteralPath $target -Force
    if ($item.LinkType -eq "Junction" -and $item.Target -eq $destination) { return }
    Remove-Item -LiteralPath $target -Recurse -Force
  }

  New-Item -ItemType Junction -Path $target -Target $destination | Out-Null
}

function Set-CacheJunction([string]$relativeTarget, [string]$relativeCache) {
  $target = Join-Path $root $relativeTarget
  $cache = Join-Path $cacheRoot $relativeCache
  New-Item -ItemType Directory -Force -Path $cache | Out-Null
  Set-Junction $target $cache
}

Set-CacheJunction "apps/admin/.next" "next/admin"
Set-CacheJunction "apps/storefront/.next" "next/storefront"

$rootNodeModules = Join-Path $root "node_modules"
if (Test-Path -LiteralPath $rootNodeModules) {
  Get-ChildItem -LiteralPath (Join-Path $root "packages") -Directory | ForEach-Object {
    $manifestPath = Join-Path $_.FullName "package.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) { return }

    $packageName = (Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json).name
    if ($packageName -notmatch '^@elton/(.+)$') { return }

    $packageLink = Join-Path $rootNodeModules $packageName
    Set-Junction $packageLink $_.FullName
  }

  Set-Junction (Join-Path $root "apps/admin/node_modules") $rootNodeModules
  Set-Junction (Join-Path $root "apps/storefront/node_modules") $rootNodeModules
}

Write-Output "Cache and dependencies are ready in $cacheRoot and $rootNodeModules"
