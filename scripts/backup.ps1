$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $repoRoot "artifacts\\backup-$stamp.zip"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
Compress-Archive -Path (Join-Path $repoRoot "config\\user"), (Join-Path $repoRoot "state") -DestinationPath $target -Force
Write-Host $target

