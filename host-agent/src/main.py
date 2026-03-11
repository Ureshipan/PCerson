from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path
from typing import Any

from config.loader import ConfigLoader
from desktop.shortcut_discovery import WindowsShortcutDiscovery
from hotkeys.windows_hotkey import WindowsHotkeyActivation
from orchestration.app import AssistantApp
from bridge.local_bridge import LocalHostBridge
from ui.overlay import HotkeyOverlayApp


def build_bridge(devices_config: dict[str, Any], assistant_config: dict[str, Any]) -> LocalHostBridge:
    return LocalHostBridge(repo_root=Path.cwd(), devices_config=devices_config, assistant_config=assistant_config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCerson host-agent")
    parser.add_argument("--config-root", default="config")
    parser.add_argument("--state-root", default="state")
    parser.add_argument("--hotkey", action="store_true", help="Run global hotkey listener")
    parser.add_argument("--hotkey-console", action="store_true", help="Run global hotkey listener with console input")
    parser.add_argument("--refresh-shortcuts", action="store_true", help="Refresh Windows shortcut catalog")
    return parser


def run_hotkey_loop(config_root: Path, state_root: Path) -> int:
    loaded = ConfigLoader(config_root).load_all()
    hotkey_cfg = loaded["assistant"].get("activation", {}).get("hotkey", {})
    if not hotkey_cfg.get("enabled", False):
        print("Hotkey disabled in config.")
        return 0
    combo = hotkey_cfg.get("combo", "ctrl+alt+space")
    app = AssistantApp(config_root=config_root, state_root=state_root)
    activation = WindowsHotkeyActivation(combo=combo, enabled=True)
    print(f"Hotkey listener active: {combo}. Press Ctrl+C to stop.")

    def on_event(_event: dict[str, Any]) -> None:
        text = input("PCerson command> ").strip()
        if not text:
            return
        result = app.handle_text(text)
        print(result.get("message", "No response"))

    try:
        activation.start(on_event)
    except KeyboardInterrupt:
        pass
    finally:
        activation.stop()
    return 0


def run_hotkey_overlay(config_root: Path, state_root: Path) -> int:
    loaded = ConfigLoader(config_root).load_all()
    hotkey_cfg = loaded["assistant"].get("activation", {}).get("hotkey", {})
    if not hotkey_cfg.get("enabled", False):
        print("Hotkey disabled in config.")
        return 0

    combo = hotkey_cfg.get("combo", "ctrl+alt+space")
    app = AssistantApp(config_root=config_root, state_root=state_root)
    activation = WindowsHotkeyActivation(combo=combo, enabled=True)
    overlay = HotkeyOverlayApp(
        title="PCerson",
        submit_handler=app.handle_text,
        status_supplier=app.runtime_snapshot,
        hotkey_label=combo,
    )

    def hotkey_worker() -> None:
        try:
            activation.start(lambda _event: overlay.root.after(0, overlay.show))
        finally:
            activation.stop()

    thread = threading.Thread(target=hotkey_worker, daemon=True)
    thread.start()
    try:
        return overlay.run()
    finally:
        activation.stop()


def refresh_shortcuts(state_root: Path, as_json: bool = False) -> int:
    discovery = WindowsShortcutDiscovery(state_root=state_root)
    catalog = discovery.refresh()
    if as_json:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
    else:
        print(f"Refreshed shortcut catalog: {len(catalog)} entries")
    return 0


if __name__ == "__main__":
    args = build_parser().parse_args()
    config_root = Path(args.config_root)
    state_root = Path(args.state_root)
    if args.refresh_shortcuts:
        raise SystemExit(refresh_shortcuts(state_root=state_root))
    loaded = ConfigLoader(config_root).load_all()
    bridge = build_bridge(devices_config=loaded["devices"], assistant_config=loaded["assistant"])
    print(bridge.healthcheck())
    if args.hotkey_console:
        raise SystemExit(run_hotkey_loop(config_root=config_root, state_root=state_root))
    if args.hotkey:
        raise SystemExit(run_hotkey_overlay(config_root=config_root, state_root=state_root))
