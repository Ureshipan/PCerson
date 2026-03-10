from __future__ import annotations

from pathlib import Path

from bridge.local_bridge import LocalHostBridge


def build_bridge() -> LocalHostBridge:
    return LocalHostBridge(repo_root=Path.cwd(), devices_config={}, assistant_config={"responses": {"desktop_notification": True}})


if __name__ == "__main__":
    bridge = build_bridge()
    print(bridge.healthcheck())

