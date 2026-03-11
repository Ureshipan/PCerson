param(
  [switch]$NonInteractive,
  [switch]$RebuildContainers,
  [switch]$SkipDocker
)
$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = Split-Path -Parent $PSScriptRoot
$configUserDir = Join-Path $repoRoot "config\\user"
$modelsUserPath = Join-Path $configUserDir "models.yaml"
$devicesUserPath = Join-Path $configUserDir "devices.yaml"
$providersUserPath = Join-Path $configUserDir "providers.yaml"
$stateDirs = @("state", "state\\logs", "state\\cache", "state\\runtime", "state\\memory")

function Select-Option {
  param(
    [string]$Title,
    [array]$Options,
    [int]$DefaultIndex = 1
  )
  if ($NonInteractive) {
    return $Options[$DefaultIndex - 1].value
  }
  Write-Host $Title
  for ($i = 0; $i -lt $Options.Count; $i++) {
    Write-Host ("[{0}] {1}" -f ($i + 1), $Options[$i].label)
  }
  $inputValue = Read-Host ("Выбери вариант [1-{0}] (по умолчанию {1})" -f $Options.Count, $DefaultIndex)
  if ([string]::IsNullOrWhiteSpace($inputValue)) {
    return $Options[$DefaultIndex - 1].value
  }
  $parsed = 0
  if ([int]::TryParse($inputValue, [ref]$parsed) -and $parsed -ge 1 -and $parsed -le $Options.Count) {
    return $Options[$parsed - 1].value
  }
  return $Options[$DefaultIndex - 1].value
}

function Ensure-JsonConfig {
  param(
    [string]$Path,
    [string]$FallbackJson = "{}"
  )
  if (-not (Test-Path $Path)) {
    return ($FallbackJson | ConvertFrom-Json)
  }
  $raw = Get-Content $Path -Raw
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return ($FallbackJson | ConvertFrom-Json)
  }
  return ($raw | ConvertFrom-Json)
}

function Save-JsonConfig {
  param(
    [string]$Path,
    [object]$Data
  )
  $json = $Data | ConvertTo-Json -Depth 30
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $json, $utf8NoBom)
}

function Set-ObjectProperty {
  param(
    [object]$Object,
    [string]$Name,
    [object]$Value
  )
  if ($Object.PSObject.Properties[$Name]) {
    $Object.$Name = $Value
  }
  else {
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
  }
}

function Remove-ObjectProperty {
  param(
    [object]$Object,
    [string]$Name
  )
  if ($Object.PSObject.Properties[$Name]) {
    $Object.PSObject.Properties.Remove($Name)
  }
}

function Remove-MojibakeAliasKeys {
  param(
    [object]$Object
  )
  $toDelete = @()
  foreach ($prop in $Object.PSObject.Properties) {
    $name = [string]$prop.Name
    if ($name -match "^[Р].*[В]") {
      $toDelete += $name
    }
  }
  foreach ($name in $toDelete) {
    $Object.PSObject.Properties.Remove($name)
  }
}

Push-Location $repoRoot
try {
  Write-Host "Checking Python..."
  $python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $python) {
    throw "Python 3.11+ is required."
  }

  foreach ($dir in $stateDirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot $dir) | Out-Null
  }
  New-Item -ItemType Directory -Force -Path $configUserDir | Out-Null

  $env:PYTHONPATH = "$repoRoot\\assistant-core\\src;$repoRoot\\host-agent\\src"
  python -c "from pathlib import Path; from config.loader import ConfigLoader; print(len(ConfigLoader(Path('config')).ensure_user_configs()))" | Out-Host

  $backend = Select-Option -Title "LLM backend:" -Options @(
    @{ label = "Ollama (Docker, рекомендовано)"; value = "ollama" },
    @{ label = "Mock (без локальной модели)"; value = "mock" }
  ) -DefaultIndex 1

  $model = Select-Option -Title "Модель:" -Options @(
    @{ label = "qwen2.5"; value = "qwen2.5" },
    @{ label = "llama3.2:3b"; value = "llama3.2:3b" },
    @{ label = "mistral:7b"; value = "mistral:7b" }
  ) -DefaultIndex 1

  $modelsCfg = Ensure-JsonConfig -Path $modelsUserPath -FallbackJson '{"llm":{},"stt":{"enabled":false,"backend":"none"},"vision":{"enabled":false,"backend":"none"}}'
  $existingBackend = ""
  $existingModel = ""
  if ($modelsCfg.llm) {
    $existingBackend = [string]$modelsCfg.llm.backend
    $existingModel = [string]$modelsCfg.llm.model
  }
  if ($NonInteractive -and -not [string]::IsNullOrWhiteSpace($existingBackend)) {
    $backend = $existingBackend
  }
  if ($NonInteractive -and -not [string]::IsNullOrWhiteSpace($existingModel)) {
    $model = $existingModel
  }

  if (-not $modelsCfg.llm) {
    $modelsCfg | Add-Member -NotePropertyName llm -NotePropertyValue (@{}) -Force
  }
  $modelsCfg.llm.backend = $backend
  $modelsCfg.llm.model = $model
  $modelsCfg.llm.endpoint = "http://127.0.0.1:11434"
  Save-JsonConfig -Path $modelsUserPath -Data $modelsCfg

  $devicesCfg = Ensure-JsonConfig -Path $devicesUserPath -FallbackJson '{"desktop_aliases":{},"registered_commands":{},"allowed_paths":[]}'
  if (-not $devicesCfg.desktop_aliases) {
    $devicesCfg | Add-Member -NotePropertyName desktop_aliases -NotePropertyValue (@{}) -Force
  }
  if (-not $devicesCfg.registered_commands) {
    $devicesCfg | Add-Member -NotePropertyName registered_commands -NotePropertyValue (@{}) -Force
  }
  Remove-MojibakeAliasKeys -Object $devicesCfg.desktop_aliases
  Set-ObjectProperty -Object $devicesCfg.desktop_aliases -Name "steam" -Value @{
    type = "url"
    target = "steam://open/main"
  }
  Set-ObjectProperty -Object $devicesCfg.desktop_aliases -Name "browser" -Value @{
    type = "url"
    target = "https://www.google.com"
  }
  Remove-ObjectProperty -Object $devicesCfg.desktop_aliases -Name "браузер"
  Set-ObjectProperty -Object $devicesCfg.registered_commands -Name "open_steam" -Value @{
    type = "url"
    target = "steam://open/main"
    args = @()
  }
  Set-ObjectProperty -Object $devicesCfg.registered_commands -Name "open_browser" -Value @{
    type = "url"
    target = "https://www.google.com"
    args = @()
  }
  Save-JsonConfig -Path $devicesUserPath -Data $devicesCfg

  $providersCfg = Ensure-JsonConfig -Path $providersUserPath -FallbackJson '{"weather":{},"news":{},"timeouts":{"connect_seconds":5,"read_seconds":10},"cache":{"ttl_seconds":900}}'
  if (-not $providersCfg.weather) {
    $providersCfg | Add-Member -NotePropertyName weather -NotePropertyValue (@{}) -Force
  }
  if (-not $providersCfg.news) {
    $providersCfg | Add-Member -NotePropertyName news -NotePropertyValue (@{}) -Force
  }
  $providersCfg.weather.enabled = $true
  $providersCfg.weather.providers = @("open-meteo")
  if (-not $providersCfg.weather.PSObject.Properties["language"]) {
    $providersCfg.weather | Add-Member -NotePropertyName language -NotePropertyValue "ru" -Force
  }
  if (-not $providersCfg.weather.PSObject.Properties["geocode_endpoint"]) {
    $providersCfg.weather | Add-Member -NotePropertyName geocode_endpoint -NotePropertyValue "https://geocoding-api.open-meteo.com/v1/search" -Force
  }
  if (-not $providersCfg.weather.PSObject.Properties["forecast_endpoint"]) {
    $providersCfg.weather | Add-Member -NotePropertyName forecast_endpoint -NotePropertyValue "https://api.open-meteo.com/v1/forecast" -Force
  }
  if (-not $providersCfg.weather.PSObject.Properties["default_location"]) {
    $providersCfg.weather | Add-Member -NotePropertyName default_location -NotePropertyValue "" -Force
  }

  $providersCfg.news.enabled = $true
  $providersCfg.news.providers = @("google-news-rss")
  if (-not $providersCfg.news.PSObject.Properties["language"]) {
    $providersCfg.news | Add-Member -NotePropertyName language -NotePropertyValue "ru" -Force
  }
  if (-not $providersCfg.news.PSObject.Properties["region"]) {
    $providersCfg.news | Add-Member -NotePropertyName region -NotePropertyValue "RU" -Force
  }
  if (-not $providersCfg.news.PSObject.Properties["default_topics"]) {
    $providersCfg.news | Add-Member -NotePropertyName default_topics -NotePropertyValue @("gaming", "technology") -Force
  }
  if (-not $providersCfg.news.PSObject.Properties["top_rss_url"]) {
    $providersCfg.news | Add-Member -NotePropertyName top_rss_url -NotePropertyValue "https://news.google.com/rss" -Force
  }
  if (-not $providersCfg.news.PSObject.Properties["search_rss_url"]) {
    $providersCfg.news | Add-Member -NotePropertyName search_rss_url -NotePropertyValue "https://news.google.com/rss/search" -Force
  }
  Save-JsonConfig -Path $providersUserPath -Data $providersCfg

  if ($backend -eq "ollama" -and -not $SkipDocker) {
    Write-Host "Checking Docker..."
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
      Write-Warning "Docker not found. Switching llm backend to mock."
      $modelsCfg.llm.backend = "mock"
      Save-JsonConfig -Path $modelsUserPath -Data $modelsCfg
    }
    else {
      if ($RebuildContainers) {
        Write-Host "Recreating model containers..."
        docker compose -f .\compose\docker-compose.yml up -d --force-recreate ollama qdrant | Out-Host
      }
      else {
        Write-Host "Ensuring model containers are running..."
        docker compose -f .\compose\docker-compose.yml up -d ollama qdrant | Out-Host
      }
      if ($LASTEXITCODE -ne 0) {
        Write-Warning "Cannot start Ollama container. Switching llm backend to mock."
        $modelsCfg.llm.backend = "mock"
        Save-JsonConfig -Path $modelsUserPath -Data $modelsCfg
      }
      else {
        $modelList = (docker compose -f .\compose\docker-compose.yml exec -T ollama ollama list) 2>$null
        if ($modelList -match [regex]::Escape($model)) {
          Write-Host "Model already present: $model"
        }
        else {
          Write-Host "Pulling model $model ..."
          docker compose -f .\compose\docker-compose.yml exec -T ollama ollama pull $model | Out-Host
          if ($LASTEXITCODE -ne 0) {
            Write-Warning "Model pull failed. Keeping configured backend; doctor will show availability."
          }
        }
        $embeddingModel = "nomic-embed-text"
        $memoryConfig = $modelsCfg.memory
        if ($memoryConfig -and -not [string]::IsNullOrWhiteSpace([string]$memoryConfig.embedding_model)) {
          $embeddingModel = [string]$memoryConfig.embedding_model
        }
        if ($modelList -match [regex]::Escape($embeddingModel)) {
          Write-Host "Embedding model already present: $embeddingModel"
        }
        else {
          Write-Host "Pulling embedding model $embeddingModel ..."
          docker compose -f .\compose\docker-compose.yml exec -T ollama ollama pull $embeddingModel | Out-Host
          if ($LASTEXITCODE -ne 0) {
            Write-Warning "Embedding model pull failed. Semantic memory may be unavailable until retry."
          }
        }
      }
    }
  }

  Write-Host "Bootstrap complete."
}
finally {
  Pop-Location
}
