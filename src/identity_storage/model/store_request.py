"""Input DTO for ``MemoryService.store``.

Kept alongside the persisted ``MemoryRecord`` because both are plain data
contracts shared across layers. The service owns record creation (ids,
timestamps); ``StoreRequest`` is what callers supply.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from identity_storage.model.memory_model import MemoryType


@dataclass(frozen=True, slots=True)
class StoreRequest:
    """What a caller passes to store a memory. The service fills in id and
    created_at — callers never set those."""

    memory_type: MemoryType
    content: str
    tags: Sequence[str] = ()
    payload: dict[str, Any] | None = None
    confidence: float = 1.0
    source: str = "agent"
