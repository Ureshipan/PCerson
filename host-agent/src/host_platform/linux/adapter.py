from __future__ import annotations


class LinuxPlatformAdapter:
    def healthcheck(self) -> dict:
        return {"platform": "linux", "ready": False}
