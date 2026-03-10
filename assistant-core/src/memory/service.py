from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

