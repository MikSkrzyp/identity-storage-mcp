"""Tests for the repository layer using an in-memory SQLite database.

Exercises the full SQL + FTS5 path. No validation logic here — that belongs
to the service tests.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from uuid_utils import uuid7

from identity_storage.db.connection import _apply_schema
from identity_storage.model.memory_model import MemoryRecord, MemoryType
from identity_storage.repository.memory_repository import MemoryRepository


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    _apply_schema(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn: sqlite3.Connection) -> MemoryRepository:
    return MemoryRepository(conn)


def _make_record(
    *,
    content: str = "fixed the auth bug",
    memory_type: MemoryType = MemoryType.EPISODIC,
    tags: list[str] | None = None,
    created_at: datetime | None = None,
    payload: dict[str, object] | None = None,
) -> MemoryRecord:
    return MemoryRecord(
        id=uuid7(),  # type: ignore[arg-type]
        memory_type=memory_type,
        content=content,
        tags=tags or [],
        payload=payload or {},
        created_at=created_at or datetime.utcnow(),
    )


def test_store_and_get_roundtrip(repo: MemoryRepository) -> None:
    record = _make_record(content="hello world", tags=["greeting"])
    repo.store(record)
    fetched = repo.get(record.id)
    assert fetched is not None
    assert fetched.content == "hello world"
    assert fetched.tags == ["greeting"]


def test_get_missing_returns_none(repo: MemoryRepository) -> None:
    assert repo.get(UUID("00000000-0000-7000-8000-000000000000")) is None


def test_recall_orders_by_created_at_desc(repo: MemoryRepository) -> None:
    base = datetime(2024, 1, 1, 12, 0, 0)
    older = _make_record(content="older", created_at=base)
    newer = _make_record(content="newer", created_at=base + timedelta(hours=1))
    repo.store(older)
    repo.store(newer)

    results = repo.recall(MemoryType.EPISODIC)
    assert [r.content for r in results] == ["newer", "older"]


def test_recall_filters_by_tags(repo: MemoryRepository) -> None:
    repo.store(_make_record(content="with-tag", tags=["auth", "bug"]))
    repo.store(_make_record(content="no-tag", tags=["auth"]))
    results = repo.recall(MemoryType.EPISODIC, tags=["auth", "bug"])
    assert len(results) == 1
    assert results[0].content == "with-tag"


def test_recall_filters_by_time_window(repo: MemoryRepository) -> None:
    base = datetime(2024, 1, 1, 12, 0, 0)
    repo.store(_make_record(content="before", created_at=base - timedelta(hours=2)))
    repo.store(_make_record(content="during", created_at=base))
    repo.store(_make_record(content="after", created_at=base + timedelta(hours=2)))

    results = repo.recall(
        MemoryType.EPISODIC,
        since=base - timedelta(minutes=1),
        until=base + timedelta(minutes=1),
    )
    assert [r.content for r in results] == ["during"]


def test_recall_is_scoped_to_memory_type(repo: MemoryRepository) -> None:
    repo.store(_make_record(content="episodic", memory_type=MemoryType.EPISODIC))
    repo.store(_make_record(content="semantic", memory_type=MemoryType.SEMANTIC))
    results = repo.recall(MemoryType.EPISODIC)
    assert all(r.memory_type == MemoryType.EPISODIC for r in results)
    assert len(results) == 1


def test_search_uses_fts5(repo: MemoryRepository) -> None:
    repo.store(_make_record(content="the authentication module was broken"))
    repo.store(_make_record(content="unrelated note about cookies"))
    results = repo.search(MemoryType.EPISODIC, "authentication")
    assert len(results) == 1
    assert "authentication" in results[0].content


def test_search_is_scoped_to_memory_type(repo: MemoryRepository) -> None:
    repo.store(_make_record(content="shared keyword", memory_type=MemoryType.EPISODIC))
    repo.store(_make_record(content="shared keyword", memory_type=MemoryType.SEMANTIC))
    results = repo.search(MemoryType.EPISODIC, "shared")
    assert all(r.memory_type == MemoryType.EPISODIC for r in results)
    assert len(results) == 1


def test_delete(repo: MemoryRepository) -> None:
    record = _make_record(content="to be deleted")
    repo.store(record)
    assert repo.delete(record.id) is True
    assert repo.delete(record.id) is False
    assert repo.get(record.id) is None


def test_delete_keeps_fts_index_consistent(repo: MemoryRepository) -> None:
    record = _make_record(content="unique searchable phrase")
    repo.store(record)
    assert len(repo.search(MemoryType.EPISODIC, "unique")) == 1
    repo.delete(record.id)
    assert len(repo.search(MemoryType.EPISODIC, "unique")) == 0
