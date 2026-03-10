#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export PYTHONPATH="$repo_root/assistant-core/src:$repo_root/host-agent/src"
python -c "import json; from pathlib import Path; from diagnostics.doctor import run_doctor; print(json.dumps(run_doctor(Path('config'), Path('state')), ensure_ascii=False, indent=2))"
