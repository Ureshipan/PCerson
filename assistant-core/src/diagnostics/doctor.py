from __future__ import annotations

from pathlib import Path

from config.loader import ConfigLoader
from memory.service import MemoryService


def run_doctor(config_root: Path, state_root: Path) -> dict:
    config = ConfigLoader(config_root).load_all()
    memory = MemoryService(state_root / "memory" / "assistant.sqlite3")
    return {
        "config_files": list(config.keys()),
        "memory_entries": len(memory.recent(limit=100)),
        "platform": config["assistant"].get("platform"),
        "desktop_enabled": config["assistant"].get("capabilities", {}).get("desktop", False),
    }

