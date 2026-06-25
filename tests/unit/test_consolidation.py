"""Tests for the consolidation flow: raw → classify → typed memories."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import pytest
from uuid_utils import uuid7

from identity_storage.model.memory_model import MemoryType
from identity_storage.model.raw_memory import RawMemory
from identity_storage.service.memory_service import Classification, MemoryService
from identity_storage.service.validation import ValidationError

EXPECTED_CLASSIFICATION_COUNT = 2
EXPECTED_RAW_COUNT = 2


class FakeRepository:
    def __init__(self) -> None:
        self.records: list[object] = []

    def store(self, record: object) -> None:
        self.records.append(record)

    def recall(self, *_args: object, **_kwargs: object) -> list[object]:
        return []

    def search(self, *_args: object, **_kwargs: object) -> list[object]:
        return []

    def get(self, record_id: object) -> object | None:
        return next((r for r in self.records if getattr(r, "id", None) == record_id), None)

    def delete(self, record_id: object) -> bool:
        before = len(self.records)
        self.records = [r for r in self.records if getattr(r, "id", None) != record_id]
        return len(self.records) < before


class FakeRawRepository:
    def __init__(self) -> None:
        self.raw: list[RawMemory] = []

    def store(self, memory: RawMemory) -> None:
        self.raw.append(memory)

    def get_unprocessed(self, limit: int = 50) -> list[RawMemory]:
        return [m for m in self.raw if not m.is_processed][:limit]

    def count_unprocessed(self) -> int:
        return sum(1 for m in self.raw if not m.is_processed)

    def mark_processed(self, memory_ids: Sequence[UUID]) -> int:
        count = 0
        now = datetime.utcnow().isoformat()
        for m in self.raw:
            if m.id in memory_ids and not m.is_processed:
                object.__setattr__(m, "processed_at", datetime.fromisoformat(now))
                count += 1
        return count

    def get(self, memory_id: UUID) -> RawMemory | None:
        return next((m for m in self.raw if m.id == memory_id), None)


@pytest.fixture
def service() -> MemoryService:
    return MemoryService(
        FakeRepository(),  # type: ignore[arg-type]
        FakeRawRepository(),  # type: ignore[arg-type]
    )


def _make_raw(**overrides: object) -> RawMemory:
    defaults: dict[str, object] = {
        "id": uuid7(),
        "content": "User: what is 2+2\nAssistant: 4",
        "tags": ["session:test"],
        "payload": {"session_id": "test-session", "agent": "claude-code"},
        "source": "stop-hook",
    }
    defaults.update(overrides)
    return RawMemory(**defaults)  # type: ignore[arg-type]


def test_classify_raw_stores_typed_and_marks_processed(service: MemoryService) -> None:
    raw = _make_raw()
    service.store_raw(raw)

    classifications = [
        Classification(
            memory_type=MemoryType.SEMANTIC,
            content="User asked about basic arithmetic",
            tags=["math"],
        ),
    ]

    stored = service.classify_raw(raw.id, classifications)

    assert len(stored) == 1
    assert stored[0].memory_type == MemoryType.SEMANTIC
    assert stored[0].source == "consolidation"
    assert service.count_unprocessed_raw() == 0


def test_classify_raw_fills_session_id_and_parent_id(service: MemoryService) -> None:
    raw = _make_raw(payload={"session_id": "abc-123", "agent": "claude-code"})
    service.store_raw(raw)

    stored = service.classify_raw(
        raw.id,
        [Classification(memory_type=MemoryType.EPISODIC, content="event")],
    )

    assert stored[0].payload["session_id"] == "abc-123"
    assert stored[0].payload["parent_id"] == str(raw.id)


def test_classify_raw_rejects_nonexistent_raw(service: MemoryService) -> None:
    with pytest.raises(ValidationError, match="not found"):
        service.classify_raw(
            UUID("00000000-0000-7000-8000-000000000000"),
            [],
        )


def test_classify_raw_rejects_already_processed(service: MemoryService) -> None:
    raw = _make_raw()
    service.store_raw(raw)
    service.mark_processed([raw.id])

    with pytest.raises(ValidationError, match="already processed"):
        service.classify_raw(
            raw.id,
            [Classification(memory_type=MemoryType.EPISODIC, content="x")],
        )


def test_classify_raw_multiple_classifications(service: MemoryService) -> None:
    raw = _make_raw(content="User: how do I run tests?\nAssistant: Use pytest -x")
    service.store_raw(raw)

    stored = service.classify_raw(
        raw.id,
        [
            Classification(
                memory_type=MemoryType.PROCEDURAL,
                content="Run tests with: pytest -x",
                tags=["testing"],
            ),
            Classification(
                memory_type=MemoryType.EPISODIC,
                content="User asked about running tests",
                tags=["testing"],
            ),
        ],
    )

    assert len(stored) == EXPECTED_CLASSIFICATION_COUNT
    assert service.count_unprocessed_raw() == 0


def test_count_unprocessed(service: MemoryService) -> None:
    assert service.count_unprocessed_raw() == 0
    service.store_raw(_make_raw())
    service.store_raw(_make_raw())
    assert service.count_unprocessed_raw() == EXPECTED_RAW_COUNT


def test_get_unprocessed_returns_oldest_first(service: MemoryService) -> None:
    old = _make_raw()
    new = _make_raw()
    service.store_raw(old)
    service.store_raw(new)

    result = service.get_unprocessed_raw()
    assert result[0].id == old.id
    assert result[1].id == new.id


def test_mark_processed_dismisses_without_classifying(service: MemoryService) -> None:
    raw = _make_raw(content="User: hi\nAssistant: hello")
    service.store_raw(raw)

    count = service.mark_processed([raw.id])
    assert count == 1
    assert service.count_unprocessed_raw() == 0
