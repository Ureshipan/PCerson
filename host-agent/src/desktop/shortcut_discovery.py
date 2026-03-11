from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


DESKTOP_PATHS = (
    Path.home() / "Desktop",
    Path(os.path.expandvars(r"%PUBLIC%\Desktop")),
)
TASKBAR_PATH = Path(
    os.path.expandvars(
        r"%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
    )
)

CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


class WindowsShortcutDiscovery:
    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root
        self.catalog_path = state_root / "runtime" / "shortcut_catalog.json"

    def refresh(self) -> list[dict[str, Any]]:
        shortcuts = self._collect_shortcuts()
        shortcuts.sort(
            key=lambda item: (
                0 if item["source"] == "taskbar" else 1,
                item["display_name"].lower(),
            )
        )
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(
            json.dumps(shortcuts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return shortcuts

    def load(self) -> list[dict[str, Any]]:
        if not self.catalog_path.exists():
            return []
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def _collect_shortcuts(self) -> list[dict[str, Any]]:
        discovered: list[dict[str, Any]] = []
        for path in DESKTOP_PATHS:
            discovered.extend(self._scan_directory(path, source="desktop"))
        discovered.extend(self._scan_directory(TASKBAR_PATH, source="taskbar"))
        deduped: dict[str, dict[str, Any]] = {}
        for entry in discovered:
            deduped.setdefault(entry["id"], entry)
        return list(deduped.values())

    def _scan_directory(self, directory: Path, source: str) -> list[dict[str, Any]]:
        if not directory.exists():
            return []
        shortcuts: list[dict[str, Any]] = []
        for item in directory.glob("*.lnk"):
            resolved = self._resolve_shortcut(item)
            if resolved is None:
                continue
            display_name = item.stem
            target = resolved.get("target", "")
            arguments = resolved.get("arguments", "")
            working_dir = resolved.get("working_dir", "")
            target_type = self._target_type(target)
            exists = self._target_exists(target, target_type)
            search_text = self._build_search_text(
                display_name=display_name,
                target=target,
                arguments=arguments,
                working_dir=working_dir,
            )
            search_tokens = self._tokenize(search_text)
            shortcut_id = f"{source}:{display_name.lower()}:{item.name.lower()}"
            shortcuts.append(
                {
                    "id": shortcut_id,
                    "display_name": display_name,
                    "target_type": target_type,
                    "target": target,
                    "source": source,
                    "launch_hint": "shortcut",
                    "arguments": arguments,
                    "working_dir": working_dir,
                    "exists": exists,
                    "shortcut_path": str(item),
                    "search_text": search_text,
                    "search_tokens": search_tokens,
                }
            )
        return shortcuts

    def _build_search_text(self, display_name: str, target: str, arguments: str, working_dir: str) -> str:
        parts = [
            display_name,
            Path(target).stem if target else "",
            Path(working_dir).name if working_dir else "",
            arguments,
        ]
        tokens: list[str] = []
        for part in parts:
            tokens.extend(self._tokenize(part))
        unique_tokens = list(dict.fromkeys(tokens))
        return " ".join(unique_tokens)

    def _tokenize(self, text: str) -> list[str]:
        raw_tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]+", text.lower())
        normalized: list[str] = []
        for token in raw_tokens:
            token = token.strip()
            if len(token) < 2:
                continue
            normalized.append(token)
            transliterated = self._transliterate_token(token)
            if transliterated and transliterated != token:
                normalized.append(transliterated)
            stem = self._stem_token(token)
            if stem and stem != token:
                normalized.append(stem)
                transliterated_stem = self._transliterate_token(stem)
                if transliterated_stem and transliterated_stem != stem:
                    normalized.append(transliterated_stem)
        return list(dict.fromkeys(normalized))

    def _stem_token(self, token: str) -> str:
        endings = (
            "иями", "ями", "ами", "ями", "ого", "ему", "ому", "ими", "его",
            "ому", "ее", "ие", "ые", "ий", "ый", "ой", "ая", "яя", "ое", "ее",
            "ам", "ям", "ах", "ях", "ов", "ев", "ом", "ем", "ый", "ий", "ой",
            "ую", "юю", "ия", "ья", "ие", "ье", "ка", "ик", "ок", "ия", "ия",
            "ы", "и", "а", "я", "е", "у", "ю", "о",
        )
        if len(token) <= 4:
            return token
        for ending in endings:
            if token.endswith(ending) and len(token) - len(ending) >= 4:
                return token[: -len(ending)]
        return token

    def _transliterate_token(self, token: str) -> str:
        if not token or re.fullmatch(r"[a-z0-9]+", token):
            return token
        return "".join(CYR_TO_LAT.get(char, char) for char in token.lower())

    def _resolve_shortcut(self, shortcut_path: Path) -> dict[str, str] | None:
        escaped = str(shortcut_path).replace("'", "''")
        command = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$shortcut = $shell.CreateShortcut('{escaped}'); "
            "$payload = @{"
            "target = $shortcut.TargetPath; "
            "arguments = $shortcut.Arguments; "
            "working_dir = $shortcut.WorkingDirectory"
            "}; "
            "$payload | ConvertTo-Json -Compress"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
        except Exception:
            return None
        raw = completed.stdout.strip()
        if not raw:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return {
            "target": str(data.get("target", "")).strip(),
            "arguments": str(data.get("arguments", "")).strip(),
            "working_dir": str(data.get("working_dir", "")).strip(),
        }

    def _target_type(self, target: str) -> str:
        lowered = target.lower()
        if lowered.startswith(("http://", "https://", "steam://")):
            return "url"
        return "program"

    def _target_exists(self, target: str, target_type: str) -> bool:
        if target_type == "url":
            return True
        if not target:
            return False
        return Path(target).exists()
