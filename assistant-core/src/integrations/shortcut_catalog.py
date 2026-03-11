from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ShortcutCatalog:
    def __init__(self, state_root: Path) -> None:
        self.catalog_path = state_root / "runtime" / "shortcut_catalog.json"

    def load(self) -> list[dict[str, Any]]:
        if not self.catalog_path.exists():
            return []
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

