from __future__ import annotations

from pathlib import Path
import json
import subprocess

from config.loader import ConfigLoader
from integrations.llm import LLMClient
from integrations.shortcut_catalog import ShortcutCatalog
from integrations.vector_memory import VectorMemoryStore
from memory.service import MemoryService

try:
    from audio.service import build_stt_service
except ModuleNotFoundError:  # pragma: no cover
    build_stt_service = None


def _read_runtime_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _detect_ollama_processor(repo_root: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(repo_root / "compose" / "docker-compose.yml"),
                "exec",
                "-T",
                "ollama",
                "ollama",
                "ps",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}

    if result.returncode != 0:
        return {}

    lines = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return {"ollama_processor": "idle"}

    header = [part.strip() for part in lines[0].split("    ") if part.strip()]
    row = [part.strip() for part in lines[1].split("    ") if part.strip()]
    if "PROCESSOR" not in header or len(row) < len(header):
        return {}

    processor_index = header.index("PROCESSOR")
    return {
        "ollama_processor": row[processor_index],
        "ollama_ps": lines[1],
    }


def run_doctor(config_root: Path, state_root: Path) -> dict:
    config = ConfigLoader(config_root).load_all()
    memory = MemoryService(state_root / "memory" / "assistant.sqlite3")
    semantic_memory = VectorMemoryStore(config["models"])
    shortcuts = ShortcutCatalog(state_root).load()
    capabilities = config["assistant"].get("capabilities", {})
    activation = config["assistant"].get("activation", {})
    runtime_state_path = state_root / "runtime" / "model_runtime.json"
    runtime_state = _read_runtime_state(runtime_state_path)
    repo_root = config_root.parent
    if config["models"].get("llm", {}).get("backend") == "ollama":
        runtime_state.update(_detect_ollama_processor(repo_root))
    stt_info = config["models"].get("stt", {})
    if build_stt_service is not None:
        try:
            stt_info = build_stt_service(config["models"].get("stt", {})).healthcheck()
        except Exception:
            stt_info = config["models"].get("stt", {})
    return {
        "config_files": list(config.keys()),
        "memory_entries": len(memory.recent(limit=100)),
        "platform": config["assistant"].get("platform"),
        "llm": LLMClient(config["models"]).healthcheck(),
        "stt": stt_info,
        "semantic_memory": semantic_memory.healthcheck(),
        "model_runtime_state": runtime_state,
        "activation": {
            "hotkey": activation.get("hotkey", {}).get("enabled", False),
            "wake_word": activation.get("wake_word", {}).get("enabled", False),
            "manual": activation.get("manual", {}).get("enabled", True),
        },
        "capabilities": {
            "desktop": capabilities.get("desktop", False),
            "camera": capabilities.get("camera", False),
            "microphone": capabilities.get("microphone", False),
            "printer": capabilities.get("printer", False),
            "home_assistant": capabilities.get("home_assistant", False),
        },
        "shortcut_catalog_entries": len(shortcuts),
        "desktop_aliases": sorted(config["devices"].get("desktop_aliases", {}).keys()),
        "registered_commands": sorted(config["devices"].get("registered_commands", {}).keys()),
    }
