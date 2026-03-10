from __future__ import annotations

from pathlib import Path
from typing import Any

from host_platform.windows.adapter import WindowsPlatformAdapter
from notifications.service import NotificationService


class LocalHostBridge:
    def __init__(self, repo_root: Path, devices_config: dict[str, Any], assistant_config: dict[str, Any]) -> None:
        self.platform = WindowsPlatformAdapter(devices_config=devices_config)
        self.notifications = NotificationService(assistant_config=assistant_config)

    def healthcheck(self) -> dict[str, Any]:
        return {
            "platform": self.platform.healthcheck(),
            "notifications": self.notifications.healthcheck(),
        }

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.platform.execute(action, payload)
        if result.get("ok"):
            self.notifications.notify(result["message"])
        return result
