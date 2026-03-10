from __future__ import annotations

from typing import Any


class NotificationService:
    def __init__(self, assistant_config: dict[str, Any]) -> None:
        self.assistant_config = assistant_config

    def healthcheck(self) -> dict[str, Any]:
        return {"enabled": self.assistant_config.get("responses", {}).get("desktop_notification", True)}

    def notify(self, message: str) -> None:
        if not self.assistant_config.get("responses", {}).get("desktop_notification", True):
            return
        print(f"[notification] {message}")

