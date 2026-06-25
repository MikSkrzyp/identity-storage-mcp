"""Pydantic schemas for the MCP tools (input/output + record converter).

Kept separate from the tool functions so the wire shape is readable in one
place. ``MemoryRecordOut`` is the MCP-facing view of ``MemoryRecord`` — an
anti-corruption layer so internal dataclass changes don't leak to clients.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from identity_storage.model.memory_model import MemoryRecord, MemoryType


class MemoryStoreInput(BaseModel):
    memory_type: Annotated[
        MemoryType,
        Field(description="Kind of memory. 'episodic' = an event that happened."),
    ]
    content: Annotated[
        str,
        Field(description="The memory text. Human-readable, self-contained."),
    ]
    tags: Annotated[
        list[str],
        Field(default_factory=list, description="Free-form tags for filtering."),
    ]
    payload: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description=(
                "Type-specific fields as JSON. For 'episodic', allowed keys: "
                "session_id, agent, task, outcome, parent_id, metadata."
            ),
        ),
    ] = None
    confidence: Annotated[
        float,
        Field(default=1.0, ge=0.0, le=1.0, description="How reliable this memory is."),
    ]
    source: Annotated[
        str,
        Field(default="agent", description="Who/what produced this memory."),
    ]


class MemoryStoreOutput(BaseModel):
    id: str
    memory_type: MemoryType
    created_at: datetime


class MemoryRecallInput(BaseModel):
    memory_type: Annotated[MemoryType, Field(description="Which memory type to read.")]
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Only records tagged with ALL of these."),
    ] = None
    since: Annotated[
        datetime | None,
        Field(default=None, description="ISO 8601 lower bound on created_at."),
    ] = None
    until: Annotated[
        datetime | None,
        Field(default=None, description="ISO 8601 upper bound on created_at."),
    ] = None
    limit: Annotated[
        int,
        Field(default=50, ge=1, le=500, description="Max records to return."),
    ]


class MemorySearchInput(BaseModel):
    memory_type: Annotated[MemoryType, Field(description="Which memory type to search.")]
    query: Annotated[
        str,
        Field(description="Full-text query. SQLite FTS5 syntax: terms, 'phrase', AND/OR."),
    ]
    limit: Annotated[
        int,
        Field(default=20, ge=1, le=200, description="Max records to return."),
    ]


class MemoryRecordOut(BaseModel):
    id: str
    memory_type: MemoryType
    content: str
    tags: list[str]
    payload: dict[str, Any]
    confidence: float
    source: str
    created_at: datetime


class MemoryRecallOutput(BaseModel):
    records: list[MemoryRecordOut]


class MemorySearchOutput(BaseModel):
    records: list[MemoryRecordOut]
    unprocessed_count: int = 0


# --------------------------------------------------------------------------- #
# Raw memory consolidation
# --------------------------------------------------------------------------- #


class RawMemoryOut(BaseModel):
    id: str
    content: str
    tags: list[str]
    payload: dict[str, Any]
    source: str
    created_at: datetime


class MemoryGetRawOutput(BaseModel):
    memories: list[RawMemoryOut]


class MemoryMarkProcessedInput(BaseModel):
    ids: Annotated[list[str], Field(description="Raw memory IDs to mark as processed.")]


def to_output(r: MemoryRecord) -> MemoryRecordOut:
    """Convert a domain ``MemoryRecord`` to the MCP-facing Pydantic model."""
    return MemoryRecordOut(
        id=str(r.id),
        memory_type=r.memory_type,
        content=r.content,
        tags=list(r.tags),
        payload=dict(r.payload),
        confidence=float(r.confidence),
        source=r.source,
        created_at=r.created_at,
    )
