$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repoRoot = $PSScriptRoot

Push-Location $repoRoot
try {
  powershell -ExecutionPolicy Bypass -File ".\\attach-model.ps1" @args | Out-Host
}
finally {
  Pop-Location
}
