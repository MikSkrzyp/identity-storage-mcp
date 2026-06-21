"""Domain model for long-term memory.

Pure Python, no I/O, no framework imports. Safe to import from anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class MemoryType(StrEnum):
    """Kind of memory. Drives payload validation and storage strategy.

    New memory kinds are added here; existing tools stay compatible.
    """

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PERSONALITY = "personality"
    EMOTIONAL = "emotional"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A single memory entry, type-agnostic.

    ``payload`` holds type-specific fields validated by the service layer
    based on ``memory_type``. The domain only guarantees structure, not
    type-specific semantics.
    """

    id: UUID
    memory_type: MemoryType
    content: str
    tags: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "agent"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if not self.content.strip():
            raise ValueError("content must not be empty or whitespace-only")
