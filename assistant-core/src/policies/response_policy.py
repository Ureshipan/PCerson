from __future__ import annotations


class ResponsePolicy:
    def __init__(self, assistant_config: dict, routines_config: dict) -> None:
        self.assistant_config = assistant_config
        self.routines_config = routines_config

    def channels(self) -> list[str]:
        preferred = self.routines_config.get("reaction_policy", {}).get("preferred_channels", [])
        if self.assistant_config.get("responses", {}).get("quiet_mode"):
            return ["log_note"]
        return preferred or ["desktop_notification"]

