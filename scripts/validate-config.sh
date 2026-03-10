#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export PYTHONPATH="$repo_root/assistant-core/src:$repo_root/host-agent/src"
python -c "from pathlib import Path; from config.loader import ConfigLoader; cfg = ConfigLoader(Path('config')).load_all(); print('OK:', ', '.join(sorted(cfg.keys())))"
