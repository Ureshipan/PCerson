$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repoRoot = $PSScriptRoot

Push-Location $repoRoot
try {
  Write-Host "First run setup started."
  Write-Host "Step 1/3: interactive bootstrap and model setup."
  powershell -ExecutionPolicy Bypass -File ".\\scripts\\bootstrap.ps1" -RebuildContainers | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Bootstrap failed with exit code $LASTEXITCODE"
  }

  Write-Host "Step 2/3: diagnostics."
  powershell -ExecutionPolicy Bypass -File ".\\scripts\\doctor.ps1" | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Doctor failed with exit code $LASTEXITCODE"
  }

  Write-Host "Step 3/3: chat mode."
  Write-Host "Try: Дарова, хочу чо нибудь поиграть"
  powershell -ExecutionPolicy Bypass -File ".\\attach-model.ps1" | Out-Host
}
finally {
  Pop-Location
}
