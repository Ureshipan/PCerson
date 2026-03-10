$ErrorActionPreference = "Stop"
param(
  [Parameter(Mandatory = $true)]
  [string]$Archive
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Expand-Archive -Path $Archive -DestinationPath $repoRoot -Force
Write-Host "Restore complete."
