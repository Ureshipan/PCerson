$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repoRoot = $PSScriptRoot
$runtimeStatePath = Join-Path $repoRoot "state\\runtime\\model_runtime.json"
$modelsConfigPath = Join-Path $repoRoot "config\\user\\models.yaml"
$composePath = Join-Path $repoRoot "compose\\docker-compose.yml"

function Get-OllamaProcessor {
  param(
    [string]$ComposePath
  )
  $output = (docker compose -f $ComposePath exec -T ollama ollama ps) 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($output)) {
    return $null
  }
  $lines = $output -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  if ($lines.Count -lt 2) {
    return "idle"
  }
  $header = ($lines[0] -split "\s{2,}") | Where-Object { $_ -ne "" }
  $row = ($lines[1] -split "\s{2,}") | Where-Object { $_ -ne "" }
  $processorIndex = [Array]::IndexOf($header, "PROCESSOR")
  if ($processorIndex -lt 0 -or $row.Count -le $processorIndex) {
    return $null
  }
  return $row[$processorIndex]
}

Push-Location $repoRoot
try {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($docker -and (Test-Path $modelsConfigPath)) {
    $modelsConfig = Get-Content $modelsConfigPath -Raw | ConvertFrom-Json
    if ($modelsConfig.llm.backend -eq "mock" -and -not [string]::IsNullOrWhiteSpace([string]$modelsConfig.llm.model)) {
      $modelsConfig.llm.backend = "ollama"
      $modelsConfig.llm.endpoint = "http://127.0.0.1:11434"
      $json = $modelsConfig | ConvertTo-Json -Depth 30
      $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
      [System.IO.File]::WriteAllText($modelsConfigPath, $json, $utf8NoBom)
    }
  }
  powershell -ExecutionPolicy Bypass -File ".\\scripts\\bootstrap.ps1" -NonInteractive | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Bootstrap failed with exit code $LASTEXITCODE"
  }
  $env:PYTHONPATH = "$repoRoot\\assistant-core\\src;$repoRoot\\host-agent\\src"
  python -m main --refresh-shortcuts | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Shortcut refresh failed with exit code $LASTEXITCODE"
  }
  $runtimeName = "unknown"
  $running = $false
  $processor = $null
  if (Test-Path $modelsConfigPath) {
    $modelsConfig = Get-Content $modelsConfigPath -Raw | ConvertFrom-Json
    $runtimeName = [string]$modelsConfig.llm.backend
    if ($runtimeName -eq "ollama") {
      $running = $true
      $processor = Get-OllamaProcessor -ComposePath $composePath
    }
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $runtimeStatePath) | Out-Null
  $runtimeJson = @(
    "{",
    ('  "model_runtime": "{0}",' -f $runtimeName),
    ('  "running": {0},' -f $running.ToString().ToLower()),
    ('  "processor": {0}' -f $(if ($null -eq $processor) { "null" } else { '"' + $processor + '"' })),
    "}"
  ) -join "`n"
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($runtimeStatePath, $runtimeJson, $utf8NoBom)
}
finally {
  Pop-Location
}
