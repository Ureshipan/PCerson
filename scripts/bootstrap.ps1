$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$configUser = Join-Path $repoRoot "config\\user"
$stateDirs = @("state", "state\\logs", "state\\cache", "state\\runtime", "state\\memory")

Push-Location $repoRoot
try {
  Write-Host "Checking Python..."
  $python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $python) {
    throw "Python 3.11+ is required."
  }

  Write-Host "Checking Docker..."
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    Write-Warning "Docker not found. Service layer will stay optional."
  }

  foreach ($dir in $stateDirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot $dir) | Out-Null
  }

  New-Item -ItemType Directory -Force -Path $configUser | Out-Null

  $env:PYTHONPATH = "$repoRoot\\assistant-core\\src;$repoRoot\\host-agent\\src"
  python -c "from pathlib import Path; from config.loader import ConfigLoader; print(len(ConfigLoader(Path('config')).ensure_user_configs()))" | Out-Host

  Write-Host "Bootstrap complete."
}
finally {
  Pop-Location
}
