from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


CONFIG_NAMES = (
    "assistant",
    "devices",
    "persona",
    "models",
    "providers",
    "routines",
)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class ConfigLoader:
    def __init__(self, config_root: Path) -> None:
        self.config_root = config_root
        self.defaults_dir = config_root / "defaults"
        self.user_dir = config_root / "user"

    def ensure_user_configs(self) -> list[Path]:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        for name in CONFIG_NAMES:
            target = self.user_dir / f"{name}.yaml"
            if target.exists():
                continue
            source = self.defaults_dir / f"{name}.default.yaml"
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            created.append(target)
        return created

    def load_all(self) -> dict[str, dict[str, Any]]:
        self.ensure_user_configs()
        loaded: dict[str, dict[str, Any]] = {}
        for name in CONFIG_NAMES:
            defaults = self._read_yaml(self.defaults_dir / f"{name}.default.yaml")
            user = self._read_yaml(self.user_dir / f"{name}.yaml")
            loaded[name] = self._expand_env(deep_merge(defaults, user))
        return loaded

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        if yaml is not None:
            data = yaml.safe_load(raw) or {}
        else:
            data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Config {path} must be a mapping")
        return data

    def _expand_env(self, value: Any) -> Any:
        if isinstance(value, str):
            return os.path.expandvars(value)
        if isinstance(value, list):
            return [self._expand_env(item) for item in value]
        if isinstance(value, dict):
            return {key: self._expand_env(item) for key, item in value.items()}
        return value
