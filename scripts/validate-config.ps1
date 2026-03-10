$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
  $env:PYTHONPATH = "$repoRoot\\assistant-core\\src;$repoRoot\\host-agent\\src"
  python -c "from pathlib import Path; from config.loader import ConfigLoader; cfg = ConfigLoader(Path('config')).load_all(); print('OK:', ', '.join(sorted(cfg.keys())))"
}
finally {
  Pop-Location
}
