from __future__ import annotations

from typing import Any

from capabilities.base import CapabilityAdapter
from integrations.host_bridge import HostBridge


class DesktopCapability(CapabilityAdapter):
    name = "desktop"

    def __init__(self, enabled: bool, host_bridge: HostBridge) -> None:
        self._enabled = enabled
        self.host_bridge = host_bridge

    @property
    def enabled(self) -> bool:
        return self._enabled

    def healthcheck(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "host": self.host_bridge.healthcheck(),
        }

    def capabilities(self) -> list[str]:
        return [
            "open_program",
            "open_file",
            "open_folder",
            "open_url",
            "open_alias",
            "open_recent",
        ]

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "message": "Desktop capability disabled"}
        return self.host_bridge.execute(action, payload)

