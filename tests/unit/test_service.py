"""Tests for MemoryService — uses a fake repository, no SQL.

Exercises validation, id generation, limit checks, and delegation to the
repository. The repository contract is verified separately (see
``test_repository.py``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import pytest

from identity_storage.model.memory_model import MemoryRecord, MemoryType
from identity_storage.model.store_request import StoreRequest
from identity_storage.service.memory_service import MemoryService
from identity_storage.service.validation import ValidationError

UUID_VERSION_V7 = 7
EXPECTED_RECALL_COUNT = 2


class FakeRepository:
    """In-memory stand-in for ``MemoryRepository``. Structural typing — no
    inheritance, just the same methods. Cheap and fast for service tests."""

    def __init__(self) -> None:
        self.records: list[MemoryRecord] = []

    def store(self, record: MemoryRecord) -> None:
        if any(r.id == record.id for r in self.records):
            raise ValueError(f"duplicate id {record.id}")
        self.records.append(record)

    def recall(
        self,
        memory_type: MemoryType,
        *,
        tags: Sequence[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        out = [r for r in self.records if r.memory_type == memory_type]
        if tags:
            out = [r for r in out if all(t in r.tags for t in tags)]
        if since:
            out = [r for r in out if r.created_at >= since]
        if until:
            out = [r for r in out if r.created_at <= until]
        out.sort(key=lambda r: r.created_at, reverse=True)
        return out[:limit]

    def search(
        self,
        memory_type: MemoryType,
        query: str,
        *,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        q = query.lower()
        out = [r for r in self.records if r.memory_type == memory_type and q in r.content.lower()]
        return out[:limit]

    def get(self, record_id: UUID) -> MemoryRecord | None:
        return next((r for r in self.records if r.id == record_id), None)

    def delete(self, record_id: UUID) -> bool:
        before = len(self.records)
        self.records = [r for r in self.records if r.id != record_id]
        return len(self.records) < before


@pytest.fixture
def service() -> MemoryService:
    return MemoryService(FakeRepository())  # type: ignore[arg-type]


def test_store_returns_record_with_uuid_v7(service: MemoryService) -> None:
    record = service.store(
        StoreRequest(
            memory_type=MemoryType.EPISODIC,
            content="refactored the login flow",
            tags=["auth"],
        )
    )
    assert record.id.version == UUID_VERSION_V7
    assert record.memory_type == MemoryType.EPISODIC
    assert record.tags == ["auth"]


def test_store_rejects_episodic_payload_with_unknown_keys(service: MemoryService) -> None:
    with pytest.raises(ValidationError, match="unexpected keys"):
        service.store(
            StoreRequest(
                memory_type=MemoryType.EPISODIC,
                content="x",
                payload={"bogus_field": 1},
            )
        )


def test_store_accepts_episodic_payload_with_allowed_keys(service: MemoryService) -> None:
    record = service.store(
        StoreRequest(
            memory_type=MemoryType.EPISODIC,
            content="fixed login bug",
            payload={"task": "login", "outcome": "success"},
        )
    )
    assert record.payload == {"task": "login", "outcome": "success"}


def test_store_allows_unknown_type_without_payload_validation(
    service: MemoryService,
) -> None:
    record = service.store(
        StoreRequest(
            memory_type=MemoryType.PERSONALITY,
            content="user prefers concise answers",
            payload={"anything": "goes"},
        )
    )
    assert record.memory_type == MemoryType.PERSONALITY


def test_store_and_get_roundtrip(service: MemoryService) -> None:
    record = service.store(
        StoreRequest(MemoryType.EPISODIC, content="hello world", tags=["greeting"])
    )
    fetched = service.get(record.id)
    assert fetched is not None
    assert fetched.content == "hello world"
    assert fetched.tags == ["greeting"]


def test_get_missing_returns_none(service: MemoryService) -> None:
    assert service.get(UUID("00000000-0000-7000-8000-000000000000")) is None


def test_recall_rejects_invalid_limit(service: MemoryService) -> None:
    with pytest.raises(ValidationError, match="limit"):
        service.recall(MemoryType.EPISODIC, limit=0)
    with pytest.raises(ValidationError, match="limit"):
        service.recall(MemoryType.EPISODIC, limit=501)


def test_recall_orders_by_created_at_desc(service: MemoryService) -> None:
    service.store(StoreRequest(MemoryType.EPISODIC, content="a"))
    service.store(StoreRequest(MemoryType.EPISODIC, content="b"))
    results = service.recall(MemoryType.EPISODIC)
    assert len(results) == EXPECTED_RECALL_COUNT
    assert results[0].created_at >= results[1].created_at


def test_recall_filters_by_tags(service: MemoryService) -> None:
    service.store(StoreRequest(MemoryType.EPISODIC, content="a", tags=["auth", "bug"]))
    service.store(StoreRequest(MemoryType.EPISODIC, content="b", tags=["auth"]))
    results = service.recall(MemoryType.EPISODIC, tags=["auth", "bug"])
    assert len(results) == 1
    assert results[0].content == "a"


def test_recall_is_scoped_to_memory_type(service: MemoryService) -> None:
    service.store(StoreRequest(MemoryType.EPISODIC, content="episodic"))
    service.store(StoreRequest(MemoryType.SEMANTIC, content="semantic"))
    results = service.recall(MemoryType.EPISODIC)
    assert all(r.memory_type == MemoryType.EPISODIC for r in results)
    assert len(results) == 1


def test_search_rejects_empty_query(service: MemoryService) -> None:
    with pytest.raises(ValidationError, match="query"):
        service.search(MemoryType.EPISODIC, "   ")


def test_search_uses_query_to_match_content(service: MemoryService) -> None:
    service.store(StoreRequest(MemoryType.EPISODIC, content="the authentication module was broken"))
    service.store(StoreRequest(MemoryType.EPISODIC, content="unrelated note about cookies"))
    results = service.search(MemoryType.EPISODIC, "authentication")
    assert len(results) == 1
    assert "authentication" in results[0].content


def test_search_is_scoped_to_memory_type(service: MemoryService) -> None:
    service.store(StoreRequest(MemoryType.EPISODIC, content="shared keyword"))
    service.store(StoreRequest(MemoryType.SEMANTIC, content="shared keyword"))
    results = service.search(MemoryType.EPISODIC, "shared")
    assert all(r.memory_type == MemoryType.EPISODIC for r in results)
    assert len(results) == 1


def test_delete(service: MemoryService) -> None:
    record = service.store(StoreRequest(MemoryType.EPISODIC, content="x"))
    assert service.delete(record.id) is True
    assert service.delete(record.id) is False
    assert service.get(record.id) is None


def test_delete_keeps_search_results_consistent(service: MemoryService) -> None:
    record = service.store(StoreRequest(MemoryType.EPISODIC, content="unique phrase"))
    assert len(service.search(MemoryType.EPISODIC, "unique")) == 1
    service.delete(record.id)
    assert len(service.search(MemoryType.EPISODIC, "unique")) == 0
