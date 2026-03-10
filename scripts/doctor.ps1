$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
  $env:PYTHONPATH = "$repoRoot\\assistant-core\\src;$repoRoot\\host-agent\\src"
  python -c "import json; from pathlib import Path; from diagnostics.doctor import run_doctor; print(json.dumps(run_doctor(Path('config'), Path('state')), ensure_ascii=False, indent=2))"
}
finally {
  Pop-Location
}
