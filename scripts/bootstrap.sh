#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
mkdir -p "$repo_root/state/logs" "$repo_root/state/cache" "$repo_root/state/runtime" "$repo_root/state/memory" "$repo_root/config/user"
export PYTHONPATH="$repo_root/assistant-core/src:$repo_root/host-agent/src"
python -c "from pathlib import Path; from config.loader import ConfigLoader; print(len(ConfigLoader(Path('config')).ensure_user_configs()))"
echo "Bootstrap complete."
