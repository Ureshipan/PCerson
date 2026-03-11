from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PersonaProfile:
    name: str
    style: str
    tone: str
    system_prompt: str
    planner_system_prompt: str
    recovery_system_prompt: str
    memory_extraction_system_prompt: str
    memory_context_system_prompt: str
    tool_result_system_prompt: str

    @classmethod
    def from_config(cls, payload: dict) -> "PersonaProfile":
        return cls(
            name=payload.get("name", "PCerson"),
            style=payload.get("style", "neutral"),
            tone=payload.get("tone", "direct"),
            system_prompt=payload.get("system_prompt", ""),
            planner_system_prompt=payload.get("planner_system_prompt", ""),
            recovery_system_prompt=payload.get("recovery_system_prompt", ""),
            memory_extraction_system_prompt=payload.get("memory_extraction_system_prompt", ""),
            memory_context_system_prompt=payload.get("memory_context_system_prompt", ""),
            tool_result_system_prompt=payload.get("tool_result_system_prompt", ""),
        )
