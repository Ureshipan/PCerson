from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capabilities.desktop import DesktopCapability
from config.loader import ConfigLoader
from integrations.host_bridge import LocalHostBridge
from memory.service import MemoryEntry, MemoryService
from orchestration.router import CommandRouter
from persona.profile import PersonaProfile
from policies.response_policy import ResponsePolicy


class AssistantApp:
    def __init__(self, config_root: Path, state_root: Path) -> None:
        self.repo_root = config_root.parent
        self.config = ConfigLoader(config_root).load_all()
        self.persona = PersonaProfile.from_config(self.config["persona"])
        self.memory = MemoryService(state_root / "memory" / "assistant.sqlite3")
        self.router = CommandRouter(self.config["devices"])
        self.response_policy = ResponsePolicy(self.config["assistant"], self.config["routines"])
        self.desktop = DesktopCapability(
            enabled=self.config["assistant"]["capabilities"].get("desktop", True),
            host_bridge=LocalHostBridge(
                repo_root=self.repo_root,
                devices_config=self.config["devices"],
                assistant_config=self.config["assistant"],
            ),
        )

    def handle_text(self, text: str) -> dict[str, Any]:
        route = self.router.route(text)
        intent = route["intent"]
        payload = route["payload"]

        self.memory.add(MemoryEntry(kind="session", content=text or "status"))

        if intent == "status":
            result = self._build_status()
        elif intent.startswith("desktop."):
            result = self._handle_desktop(intent, payload)
        else:
            result = {
                "ok": True,
                "message": "Команда не сопоставлена с capability. Доступен базовый desktop flow.",
                "channels": self.response_policy.channels(),
            }

        self.memory.add(MemoryEntry(kind="episodic", content=result["message"], metadata=json.dumps(result, ensure_ascii=False)))
        return result

    def _handle_desktop(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "desktop.open_alias":
            execution = self.desktop.execute("open_alias", payload)
        elif intent == "desktop.open_url":
            execution = self.desktop.execute("open_url", payload)
        elif intent == "desktop.open_path":
            execution = self.desktop.execute("open_path", payload)
        elif intent == "desktop.open_alias_or_program":
            execution = self.desktop.execute("open_alias_or_program", payload)
        else:
            execution = {"ok": False, "message": f"Unsupported desktop intent: {intent}"}
        execution["channels"] = self.response_policy.channels()
        return execution

    def _build_status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "message": "assistant-core active",
            "channels": self.response_policy.channels(),
            "persona": self.persona.name,
            "desktop": self.desktop.healthcheck(),
            "recent_memory": self.memory.recent(limit=5),
        }

