from __future__ import annotations

from pathlib import Path
from typing import Any

from bridge.local_bridge import LocalHostBridge as HostAgentLocalBridge


class HostBridge:
    def healthcheck(self) -> dict[str, Any]:
        raise NotImplementedError

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class LocalHostBridge(HostBridge):
    def __init__(self, repo_root: Path, devices_config: dict[str, Any], assistant_config: dict[str, Any]) -> None:
        self._bridge = LocalHostBridgeAdapter(repo_root, devices_config, assistant_config)

    def healthcheck(self) -> dict[str, Any]:
        return self._bridge.healthcheck()

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._bridge.execute(action, payload)


class LocalHostBridgeAdapter:
    def __init__(self, repo_root: Path, devices_config: dict[str, Any], assistant_config: dict[str, Any]) -> None:
        self.adapter = HostAgentLocalBridge(
            repo_root=repo_root,
            devices_config=devices_config,
            assistant_config=assistant_config,
        )

    def healthcheck(self) -> dict[str, Any]:
        return self.adapter.healthcheck()

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.adapter.execute(action, payload)
