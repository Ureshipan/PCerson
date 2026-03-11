from __future__ import annotations

import difflib
import os
import shlex
import subprocess
import webbrowser
from pathlib import Path
from typing import Any


class WindowsPlatformAdapter:
    def __init__(self, devices_config: dict[str, Any]) -> None:
        self.devices_config = devices_config
        self.aliases = devices_config.get("desktop_aliases", {})
        self.shortcut_catalog = devices_config.get("shortcut_catalog", [])
        self.registered_commands = devices_config.get("registered_commands", {})
        self.builtin_program_aliases = {
            "блокнот": "notepad.exe",
            "проводник": "explorer.exe",
            "калькулятор": "calc.exe",
            "терминал": "wt.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "steam": "steam://open/main",
            "стим": "steam://open/main",
            "browser": "https://www.google.com",
            "браузер": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "ютуб": "https://www.youtube.com",
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

    def _open_shortcut(self, payload: dict[str, Any]) -> dict[str, Any]:
        shortcut_id = str(payload.get("shortcut_id", "")).strip()
        shortcut = self._find_shortcut(shortcut_id)
        if shortcut is None:
            return {"ok": False, "message": f"Unknown shortcut: {shortcut_id}"}
        shortcut_path = str(shortcut.get("shortcut_path", "")).strip()
        if shortcut_path:
            try:
                os.startfile(shortcut_path)
                return {"ok": True, "message": f"Opened shortcut '{shortcut.get('display_name', shortcut_id)}'"}
            except OSError:
                pass

        target = str(shortcut.get("target", "")).strip()
        target_type = str(shortcut.get("target_type", "")).strip().lower()
        arguments = str(shortcut.get("arguments", "")).strip()
        if target_type == "url" and target:
            webbrowser.open(target)
            return {"ok": True, "message": f"Opened shortcut URL '{shortcut.get('display_name', shortcut_id)}'"}
        if target:
            try:
                self._launch_target(target=target, arguments=arguments)
                return {"ok": True, "message": f"Opened shortcut target '{shortcut.get('display_name', shortcut_id)}'"}
            except OSError as exc:
                return {"ok": False, "message": f"Shortcut launch failed: {exc}"}

        return {"ok": False, "message": f"Shortcut has no runnable target: {shortcut_id}"}

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
        alias_name = self._best_alias_name(target)
        if alias_name is not None:
            return self._open_alias({"alias": alias_name})

        normalized = target.lower()
        builtin_target = self.builtin_program_aliases.get(normalized)
        if builtin_target is None:
            builtin_target = self._fuzzy_builtin_target(normalized)
        if builtin_target:
            os.startfile(builtin_target)
            return {"ok": True, "message": f"Started program alias: {target}"}

        shortcut_match = self._best_shortcut_match(target)
        if shortcut_match is not None:
            return self._open_shortcut({"shortcut_id": str(shortcut_match.get("id", ""))})

        self._launch_target(target=target, arguments=str(payload.get("arguments", "")).strip())
        return {"ok": True, "message": f"Started program: {target}"}

    def _open_recent(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.devices_config.get("recent", {}).get("enabled", True):
            return {"ok": False, "message": "Recent feature disabled by config"}
        target_type = payload.get("target_type", "file")
        recent_item = self._select_recent_item(target_type=target_type)
        if recent_item is None:
            return {"ok": False, "message": f"No recent {target_type} found in allowed paths"}
        os.startfile(str(recent_item))
        return {"ok": True, "message": f"Opened recent {target_type}: {recent_item}"}

    def _run_registered(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", ""))
        spec = self.registered_commands.get(name)
        if not spec:
            return {"ok": False, "message": f"Unknown registered command: {name}"}
        command_type = str(spec.get("type", "program")).lower()
        target = os.path.expandvars(str(spec.get("target", "")))
        args = [os.path.expandvars(str(value)) for value in spec.get("args", [])]
        if command_type == "program":
            subprocess.Popen([target, *args], shell=False)
            return {"ok": True, "message": f"Started registered command: {name}"}
        if command_type == "url":
            webbrowser.open(target)
            return {"ok": True, "message": f"Opened registered URL command: {name}"}
        return {"ok": False, "message": f"Unsupported registered command type: {command_type}"}

    def _find_alias(self, alias: str) -> dict[str, Any] | None:
        if alias in self.aliases:
            return self.aliases[alias]
        normalized = alias.lower()
        for key, spec in self.aliases.items():
            if str(key).lower() == normalized:
                return spec
        return None

    def _find_shortcut(self, shortcut_id: str) -> dict[str, Any] | None:
        normalized = shortcut_id.strip().lower()
        for shortcut in self.shortcut_catalog:
            if str(shortcut.get("id", "")).strip() == shortcut_id:
                return shortcut
            if str(shortcut.get("id", "")).strip().lower() == normalized:
                return shortcut
            if str(shortcut.get("display_name", "")).strip().lower() == normalized:
                return shortcut
        best = self._best_shortcut_match(shortcut_id)
        if best is not None:
            return best
        return None

    def _best_shortcut_match(self, target: str) -> dict[str, Any] | None:
        normalized = target.lower().strip()
        candidates: list[tuple[float, dict[str, Any]]] = []
        for shortcut in self.shortcut_catalog:
            display_name = str(shortcut.get("display_name", "")).lower()
            search_text = str(shortcut.get("search_text", display_name)).lower()
            score = difflib.SequenceMatcher(a=normalized, b=display_name).ratio()
            if display_name and display_name in normalized:
                score += 1.0
            if normalized and normalized in search_text:
                score += 0.75
            candidates.append((score, shortcut))
        if not candidates:
            return None
        best_score, best_shortcut = max(candidates, key=lambda item: item[0])
        if best_score < 0.72:
            return None
        return best_shortcut

    def _best_alias_name(self, target: str) -> str | None:
        if target in self.aliases:
            return target
        normalized = target.lower()
        lowered_aliases = {str(alias).lower(): str(alias) for alias in self.aliases}
        if normalized in lowered_aliases:
            return lowered_aliases[normalized]
        if not lowered_aliases:
            return None
        best = difflib.get_close_matches(normalized, list(lowered_aliases.keys()), n=1, cutoff=0.72)
        if best:
            return lowered_aliases[best[0]]
        return None

    def _fuzzy_builtin_target(self, normalized_target: str) -> str | None:
        best = difflib.get_close_matches(normalized_target, list(self.builtin_program_aliases.keys()), n=1, cutoff=0.72)
        if not best:
            return None
        return self.builtin_program_aliases[best[0]]

    def _launch_target(self, target: str, arguments: str = "") -> None:
        expanded_target = os.path.expandvars(target)
        if arguments:
            parsed_args = shlex.split(arguments, posix=False)
            subprocess.Popen([expanded_target, *parsed_args], shell=False)
            return
        subprocess.Popen([expanded_target], shell=False)

    def _is_allowed_path(self, path: Path) -> bool:
        if not self.allowed_paths:
            return True
        normalized = str(path).lower()
        return any(normalized.startswith(str(root).lower()) for root in self.allowed_paths)

    def _select_recent_item(self, target_type: str) -> Path | None:
        candidates: list[Path] = []
        roots = self.allowed_paths or [Path.home() / "Desktop", Path.home() / "Documents"]
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for item in root.iterdir():
                if target_type == "folder" and item.is_dir():
                    candidates.append(item)
                if target_type == "file" and item.is_file():
                    candidates.append(item)
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.stat().st_mtime)
