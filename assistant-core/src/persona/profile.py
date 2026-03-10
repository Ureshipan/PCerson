from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PersonaProfile:
    name: str
    style: str
    tone: str
    system_prompt: str

    @classmethod
    def from_config(cls, payload: dict) -> "PersonaProfile":
        return cls(
            name=payload.get("name", "PCerson"),
            style=payload.get("style", "neutral"),
            tone=payload.get("tone", "direct"),
            system_prompt=payload.get("system_prompt", ""),
        )

