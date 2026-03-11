$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

Push-Location $repoRoot
try {
  powershell -ExecutionPolicy Bypass -File ".\\start-model.ps1" | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "start-model failed with exit code $LASTEXITCODE"
  }
  $env:PYTHONPATH = "$repoRoot\\assistant-core\\src;$repoRoot\\host-agent\\src"
  python -m main --hotkey @args
}
finally {
  Pop-Location
}
