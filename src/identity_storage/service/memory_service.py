"""Memory service: application logic. Calls the repository, owns validation.

This is the only entry point for adapters (MCP, CLI). Validation, id
generation, and limit checks live here so every adapter gets the same rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from uuid_utils import uuid7

from identity_storage.model.memory_model import MemoryRecord, MemoryType
from identity_storage.model.raw_memory import RawMemory
from identity_storage.model.store_request import StoreRequest
from identity_storage.repository.memory_repository import MemoryRepository
from identity_storage.repository.raw_memory_repository import RawMemoryRepository
from identity_storage.service.validation import ValidationError, validate_payload

RECALL_LIMIT_MAX = 500
SEARCH_LIMIT_MAX = 200


@dataclass(frozen=True, slots=True)
class Classification:
    """A single classification extracted from a raw memory."""

    memory_type: MemoryType
    content: str
    tags: Sequence[str] = ()
    payload: dict[str, Any] | None = None
    confidence: float = 1.0


class MemoryService:
    """Memory use cases. Adapters call this, never the repository directly —
    so validation and future cross-cutting concerns live in one place."""

    def __init__(
        self,
        repository: MemoryRepository,
        raw_repository: RawMemoryRepository | None = None,
    ) -> None:
        self._repo = repository
        self._raw_repo = raw_repository

    def store(self, request: StoreRequest) -> MemoryRecord:
        payload = dict(request.payload) if request.payload else {}
        validate_payload(request.memory_type, payload)

        record = MemoryRecord(
            id=uuid7(),  # type: ignore[arg-type]
            memory_type=request.memory_type,
            content=request.content,
            tags=list(request.tags),
            payload=payload,
            confidence=request.confidence,
            source=request.source,
        )
        self._repo.store(record)
        return record

    def recall(
        self,
        memory_type: MemoryType,
        *,
        tags: Sequence[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        if limit < 1 or limit > RECALL_LIMIT_MAX:
            raise ValidationError(f"limit must be in [1, {RECALL_LIMIT_MAX}], got {limit}")
        return self._repo.recall(
            memory_type,
            tags=tags,
            since=since,
            until=until,
            limit=limit,
        )

    def search(
        self,
        memory_type: MemoryType,
        query: str,
        *,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        if not query.strip():
            raise ValidationError("query must not be empty")
        if limit < 1 or limit > SEARCH_LIMIT_MAX:
            raise ValidationError(f"limit must be in [1, {SEARCH_LIMIT_MAX}], got {limit}")
        return self._repo.search(memory_type, query, limit=limit)

    def get(self, record_id: UUID) -> MemoryRecord | None:
        return self._repo.get(record_id)

    def delete(self, record_id: UUID) -> bool:
        return self._repo.delete(record_id)

    # ------------------------------------------------------------------ #
    # Raw memory consolidation
    # ------------------------------------------------------------------ #

    def store_raw(self, memory: RawMemory) -> None:
        if self._raw_repo is None:
            raise ValidationError("raw memory repository not configured")
        self._raw_repo.store(memory)

    def get_unprocessed_raw(self, limit: int = 50) -> list[RawMemory]:
        if self._raw_repo is None:
            return []
        if limit < 1 or limit > RECALL_LIMIT_MAX:
            raise ValidationError(f"limit must be in [1, {RECALL_LIMIT_MAX}], got {limit}")
        return self._raw_repo.get_unprocessed(limit=limit)

    def count_unprocessed_raw(self) -> int:
        if self._raw_repo is None:
            return 0
        return self._raw_repo.count_unprocessed()

    def mark_processed(self, memory_ids: Sequence[UUID]) -> int:
        if self._raw_repo is None:
            return 0
        return self._raw_repo.mark_processed(memory_ids)

    def classify_raw(
        self,
        raw_id: UUID,
        classifications: Sequence[Classification],
    ) -> list[MemoryRecord]:
        """Store typed memories from classifications and mark the raw as processed.

        Returns the stored ``MemoryRecord`` objects. Raises ``ValidationError``
        if the raw memory does not exist or is already processed.
        """
        if self._raw_repo is None:
            raise ValidationError("raw memory repository not configured")

        raw = self._raw_repo.get(raw_id)
        if raw is None:
            raise ValidationError(f"raw memory {raw_id} not found")
        if raw.is_processed:
            raise ValidationError(f"raw memory {raw_id} already processed")

        raw_payload = dict(raw.payload) if raw.payload else {}
        raw_session_id = raw_payload.get("session_id", "unknown")
        if not isinstance(raw_session_id, str):
            raw_session_id = "unknown"

        stored: list[MemoryRecord] = []
        for cls in classifications:
            payload = dict(cls.payload) if cls.payload else {}
            payload.setdefault("session_id", raw_session_id)
            payload.setdefault("parent_id", str(raw_id))

            record = self.store(
                StoreRequest(
                    memory_type=cls.memory_type,
                    content=cls.content,
                    tags=list(cls.tags),
                    payload=payload,
                    confidence=cls.confidence,
                    source="consolidation",
                )
            )
            stored.append(record)

        self._raw_repo.mark_processed([raw_id])
        return stored
