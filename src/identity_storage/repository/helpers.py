"""Serialization helpers for the SQLite repository.

Tags and payload are stored as JSON columns. These functions convert between
Python types and the JSON strings in the database. Row → ``MemoryRecord``
mapping lives here so the repository class stays focused on queries.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from identity_storage.model.memory_model import MemoryRecord, MemoryType


def serialize_tags(tags: Sequence[str]) -> str:
    return json.dumps(list(tags), ensure_ascii=False)


def serialize_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def parse_tags(raw: str) -> list[str]:
    tags = json.loads(raw)
    if not isinstance(tags, list):
        raise ValueError(f"tags JSON is not a list: {raw!r}")
    return [str(t) for t in tags]


def parse_payload(raw: str) -> dict[str, object]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"payload JSON is not an object: {raw!r}")
    return payload


def row_to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=UUID(row["id"]),
        memory_type=MemoryType(row["type"]),
        content=row["content"],
        tags=parse_tags(row["tags"]),
        payload=parse_payload(row["payload"]),
        confidence=float(row["confidence"]),
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
