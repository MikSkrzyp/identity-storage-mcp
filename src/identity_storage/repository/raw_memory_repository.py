"""SQLite repository for raw memories: queries only, no business logic."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from identity_storage.model.raw_memory import RawMemory


def _serialize_tags(tags: Sequence[str]) -> str:
    return json.dumps(list(tags), ensure_ascii=False)


def _serialize_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _parse_tags(raw: str) -> list[str]:
    tags = json.loads(raw)
    if not isinstance(tags, list):
        raise ValueError(f"tags JSON is not a list: {raw!r}")
    return [str(t) for t in tags]


def _parse_payload(raw: str) -> dict[str, object]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"payload JSON is not an object: {raw!r}")
    return payload


def _row_to_raw_memory(row: sqlite3.Row) -> RawMemory:
    processed_at_raw = row["processed_at"]
    return RawMemory(
        id=UUID(row["id"]),
        content=row["content"],
        tags=_parse_tags(row["tags"]),
        payload=_parse_payload(row["payload"]),
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        processed_at=(datetime.fromisoformat(processed_at_raw) if processed_at_raw else None),
    )


class RawMemoryRepository:
    """SQLite persistence for raw, unprocessed memories."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def store(self, memory: RawMemory) -> None:
        self._conn.execute(
            """
            INSERT INTO raw_memories (id, content, tags, payload, source, created_at, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(memory.id),
                memory.content,
                _serialize_tags(memory.tags),
                _serialize_payload(memory.payload),
                memory.source,
                memory.created_at.isoformat(),
                memory.processed_at.isoformat() if memory.processed_at else None,
            ),
        )

    def get_unprocessed(self, limit: int = 50) -> list[RawMemory]:
        rows = self._conn.execute(
            """
            SELECT * FROM raw_memories
            WHERE processed_at IS NULL
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_raw_memory(r) for r in rows]

    def count_unprocessed(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM raw_memories WHERE processed_at IS NULL"
        ).fetchone()
        return int(row[0])

    def mark_processed(self, memory_ids: Sequence[UUID]) -> int:
        if not memory_ids:
            return 0
        now = datetime.utcnow().isoformat()
        placeholders = ", ".join("?" for _ in memory_ids)
        cur = self._conn.execute(
            f"""
            UPDATE raw_memories
            SET processed_at = ?
            WHERE id IN ({placeholders}) AND processed_at IS NULL
            """,
            (now, *(str(mid) for mid in memory_ids)),
        )
        return cur.rowcount

    def get(self, memory_id: UUID) -> RawMemory | None:
        row = self._conn.execute(
            "SELECT * FROM raw_memories WHERE id = ?",
            (str(memory_id),),
        ).fetchone()
        return _row_to_raw_memory(row) if row is not None else None
