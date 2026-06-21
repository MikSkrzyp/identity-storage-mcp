"""SQLite repository: queries only, no business logic.

Takes a ``sqlite3.Connection``, returns ``MemoryRecord`` objects. The service
layer owns validation and id generation; this layer only queries and
deserializes. When embeddings arrive, ``search`` grows here (FTS5 +
sqlite-vec) without touching the service.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from identity_storage.model.memory_model import MemoryRecord, MemoryType
from identity_storage.repository.helpers import row_to_record, serialize_payload, serialize_tags


class MemoryRepository:
    """SQLite persistence for ``MemoryRecord``.

    Concrete class, not a Protocol — we have exactly one backend. If a second
    ever appears, extract an interface then, not now.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def store(self, record: MemoryRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO memory (id, type, content, tags, payload, confidence, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record.id),
                record.memory_type.value,
                record.content,
                serialize_tags(record.tags),
                serialize_payload(record.payload),
                record.confidence,
                record.source,
                record.created_at.isoformat(),
            ),
        )

    def recall(
        self,
        memory_type: MemoryType,
        *,
        tags: Sequence[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        sql = "SELECT * FROM memory WHERE type = ?"
        params: list[object] = [memory_type.value]

        if since is not None:
            sql += " AND created_at >= ?"
            params.append(since.isoformat())
        if until is not None:
            sql += " AND created_at <= ?"
            params.append(until.isoformat())
        if tags:
            for tag in tags:
                sql += " AND EXISTS (SELECT 1 FROM json_each(memory.tags) WHERE value = ?)"
                params.append(tag)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        return [row_to_record(r) for r in rows]

    def search(
        self,
        memory_type: MemoryType,
        query: str,
        *,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        rows = self._conn.execute(
            """
            SELECT m.*
            FROM memory m
            JOIN memory_fts f ON f.rowid = m.rowid
            WHERE f.content MATCH ? AND m.type = ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, memory_type.value, limit),
        ).fetchall()
        return [row_to_record(r) for r in rows]

    def get(self, record_id: UUID) -> MemoryRecord | None:
        row = self._conn.execute(
            "SELECT * FROM memory WHERE id = ?",
            (str(record_id),),
        ).fetchone()
        return row_to_record(row) if row is not None else None

    def delete(self, record_id: UUID) -> bool:
        cur = self._conn.execute(
            "DELETE FROM memory WHERE id = ?",
            (str(record_id),),
        )
        return cur.rowcount > 0
