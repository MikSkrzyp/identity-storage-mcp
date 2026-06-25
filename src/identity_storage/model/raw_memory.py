"""Raw memory model: unprocessed session transcripts awaiting consolidation.

Raw memories are written by the Stop hook ingestor and read by the agent
at the start of the next session. The agent classifies them into typed
memories (episodic, semantic, procedural, ...) via ``memory_store``, then
marks them processed via ``memory_mark_processed``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RawMemory:
    """A raw, unprocessed memory from a session transcript."""

    id: UUID
    content: str
    tags: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "stop-hook"
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: datetime | None = None

    @property
    def is_processed(self) -> bool:
        return self.processed_at is not None
