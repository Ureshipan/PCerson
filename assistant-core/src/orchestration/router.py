from __future__ import annotations

from typing import Any


class CommandRouter:
    def __init__(self, devices_config: dict[str, Any]) -> None:
        self.devices_config = devices_config
        self.aliases = devices_config.get("desktop_aliases", {})

    def route(self, text: str) -> dict[str, Any]:
        command = text.strip()
        lowered = command.lower()
        if lowered in {"status", "health", "diag"}:
            return {"intent": "status", "payload": {}}
        if lowered.startswith("open "):
            target = command[5:].strip()
            if self._is_alias(target):
                return {"intent": "desktop.open_alias", "payload": {"alias": target}}
            return self._route_target(target)
        if lowered.startswith("открой "):
            target = command[7:].strip()
            if self._is_alias(target):
                return {"intent": "desktop.open_alias", "payload": {"alias": target}}
            return self._route_target(target)
        return {"intent": "chat.fallback", "payload": {"text": command}}

    def _route_target(self, target: str) -> dict[str, Any]:
        lowered = target.lower()
        if lowered.startswith(("http://", "https://")):
            return {"intent": "desktop.open_url", "payload": {"target": target}}
        if "\\" in target or "/" in target:
            return {
                "intent": "desktop.open_path",
                "payload": {"target": target},
            }
        return {
            "intent": "desktop.open_alias_or_program",
            "payload": {"target": target},
        }

    def _is_alias(self, candidate: str) -> bool:
        if candidate in self.aliases:
            return True
        normalized = candidate.lower()
        return any(str(alias).lower() == normalized for alias in self.aliases)
