from __future__ import annotations

from typing import Any


class CommandRouter:
    def __init__(self, devices_config: dict[str, Any]) -> None:
        self.devices_config = devices_config

    def route(self, text: str) -> dict[str, Any]:
        command = text.strip()
        lowered = command.lower()

        if lowered in {"status", "health", "diag"}:
            return {"intent": "status", "payload": {}}
        if any(token in lowered for token in ("погод", "weather", "температур", "дожд", "снег")):
            return {"intent": "info.weather", "payload": {"text": command}}
        if any(token in lowered for token in ("новост", "news", "сводк", "дайджест", "заголов")):
            return {"intent": "info.news", "payload": {"text": command}}
        return {"intent": "chat.fallback", "payload": {"text": command}}
