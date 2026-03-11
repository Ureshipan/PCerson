from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(slots=True)
class MemoryEntry:
    kind: str
    content: str
    metadata: str = "{}"


class MemoryService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def add(self, entry: MemoryEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memory_entries(kind, content, metadata) VALUES (?, ?, ?)",
                (entry.kind, entry.content, entry.metadata),
            )

    def recent(self, limit: int = 10, kind: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT kind, content, metadata, created_at FROM memory_entries"
        params: list[Any] = []
        if kind:
            query += " WHERE kind = ?"
            params.append(kind)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "kind": row[0],
                "content": row[1],
                "metadata": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    def recent_by_kinds(self, kinds: list[str], limit: int = 10) -> list[dict[str, Any]]:
        if not kinds:
            return []
        placeholders = ", ".join(["?"] * len(kinds))
        query = (
            "SELECT kind, content, metadata, created_at FROM memory_entries "
            f"WHERE kind IN ({placeholders}) ORDER BY id DESC LIMIT ?"
        )
        params: list[Any] = [*kinds, limit]
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "kind": row[0],
                "content": row[1],
                "metadata": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    def recent_dialogue(self, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.recent_by_kinds(["user_message", "assistant_message"], limit=limit)
        dialogue = []
        for row in reversed(rows):
            role = "user" if row["kind"] == "user_message" else "assistant"
            dialogue.append(
                {
                    "role": role,
                    "text": row["content"],
                    "created_at": row["created_at"],
                }
            )
        return dialogue

    def add_structured(self, kind: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.add(MemoryEntry(kind=kind, content=content, metadata=json.dumps(metadata or {}, ensure_ascii=False)))

    def contains(self, kind: str, content: str) -> bool:
        normalized = content.strip().lower()
        if not normalized:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM memory_entries WHERE kind = ? AND lower(trim(content)) = ? LIMIT 1",
                (kind, normalized),
            ).fetchone()
        return row is not None
