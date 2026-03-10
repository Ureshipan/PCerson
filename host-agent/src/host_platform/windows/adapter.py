from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any


class WindowsPlatformAdapter:
    def __init__(self, devices_config: dict[str, Any]) -> None:
        self.devices_config = devices_config
        self.aliases = devices_config.get("desktop_aliases", {})
        self.builtin_program_aliases = {
            "блокнот": "notepad.exe",
            "проводник": "explorer.exe",
            "калькулятор": "calc.exe",
            "терминал": "wt.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
        }
        self.allowed_paths = [Path(os.path.expandvars(path)) for path in devices_config.get("allowed_paths", [])]

    def healthcheck(self) -> dict[str, Any]:
        return {"platform": "windows", "aliases": sorted(self.aliases.keys())}

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = getattr(self, f"_{action}", None)
        if not handler:
            return {"ok": False, "message": f"Unsupported action: {action}"}
        try:
            return handler(payload)
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "message": f"{action} failed: {exc}"}

    def _open_alias(self, payload: dict[str, Any]) -> dict[str, Any]:
        alias = payload["alias"]
        spec = self._find_alias(alias)
        if not spec:
            return {"ok": False, "message": f"Unknown alias: {alias}"}
        target = spec["target"]
        entry_type = spec.get("type", "program")
        if entry_type == "url":
            webbrowser.open(target)
        else:
            os.startfile(target)
        return {"ok": True, "message": f"Opened alias '{alias}'"}

    def _open_url(self, payload: dict[str, Any]) -> dict[str, Any]:
        target = payload["target"]
        webbrowser.open(target)
        return {"ok": True, "message": f"Opened URL: {target}"}

    def _open_path(self, payload: dict[str, Any]) -> dict[str, Any]:
        target = Path(os.path.expandvars(payload["target"])).expanduser().resolve()
        if not self._is_allowed_path(target):
            return {"ok": False, "message": f"Path denied by policy: {target}"}
        os.startfile(str(target))
        return {"ok": True, "message": f"Opened path: {target}"}

    def _open_alias_or_program(self, payload: dict[str, Any]) -> dict[str, Any]:
        target = payload["target"].strip()
        if self._find_alias(target):
            return self._open_alias({"alias": target})

        normalized = target.lower()
        builtin_target = self.builtin_program_aliases.get(normalized)
        if builtin_target:
            os.startfile(builtin_target)
            return {"ok": True, "message": f"Started program alias: {target}"}

        subprocess.Popen([target], shell=False)
        return {"ok": True, "message": f"Started program: {target}"}

    def _find_alias(self, alias: str) -> dict[str, Any] | None:
        if alias in self.aliases:
            return self.aliases[alias]
        normalized = alias.lower()
        for key, spec in self.aliases.items():
            if str(key).lower() == normalized:
                return spec
        return None

    def _is_allowed_path(self, path: Path) -> bool:
        if not self.allowed_paths:
            return True
        normalized = str(path).lower()
        return any(normalized.startswith(str(root).lower()) for root in self.allowed_paths)
