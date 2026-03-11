$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repoRoot = $PSScriptRoot
$runtimeStatePath = Join-Path $repoRoot "state\\runtime\\model_runtime.json"
$modelsConfigPath = Join-Path $repoRoot "config\\user\\models.yaml"

Push-Location $repoRoot
try {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($docker) {
    docker compose -f .\compose\docker-compose.yml stop ollama qdrant | Out-Host
  }
  $runtimeName = "unknown"
  if (Test-Path $modelsConfigPath) {
    $modelsConfig = Get-Content $modelsConfigPath -Raw | ConvertFrom-Json
    $runtimeName = [string]$modelsConfig.llm.backend
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $runtimeStatePath) | Out-Null
  $runtimeJson = @(
    "{",
    ('  "model_runtime": "{0}",' -f $runtimeName),
    '  "running": false,',
    '  "processor": null',
    "}"
  ) -join "`n"
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($runtimeStatePath, $runtimeJson, $utf8NoBom)
}
finally {
  Pop-Location
}
