"""MCP tool functions: one per memory operation.

Each tool is a thin adapter — translate Pydantic input → ``StoreRequest`` /
service call → Pydantic output. No business logic here; that lives in
``service.memory_service``.
"""

from __future__ import annotations

from uuid import UUID

from mcp.server.fastmcp import FastMCP

from identity_storage.adapters.mcp.schemas import (
    MemoryClassifyInput,
    MemoryClassifyOutput,
    MemoryGetRawOutput,
    MemoryMarkProcessedInput,
    MemoryRecallInput,
    MemoryRecallOutput,
    MemorySearchInput,
    MemorySearchOutput,
    MemoryStoreInput,
    MemoryStoreOutput,
    RawMemoryOut,
    to_output,
)
from identity_storage.model.store_request import StoreRequest
from identity_storage.service.memory_service import Classification
from identity_storage.service.validation import ValidationError


def register_tools(mcp: FastMCP, service_factory: object) -> None:
    """Register the three memory tools on ``mcp``.

    ``service_factory`` is a zero-arg callable returning a ``MemoryService``.
    Passed in rather than imported, so this module has no DB/service wiring.
    """

    @mcp.tool(
        name="memory_store",
        description=(
            "Persist a memory manually. Only use when the user explicitly "
            "asks you to remember something. Regular turn storage is handled "
            "automatically by the client's Stop hook. Episodic payload keys: "
            "session_id, agent, task, outcome, parent_id, metadata. Returns "
            "the new record id."
        ),
    )
    def memory_store(input: MemoryStoreInput) -> MemoryStoreOutput:
        service = service_factory()  # type: ignore[operator]
        try:
            record = service.store(
                StoreRequest(
                    memory_type=input.memory_type,
                    content=input.content,
                    tags=input.tags,
                    payload=input.payload or {},
                    confidence=input.confidence,
                    source=input.source,
                )
            )
        except ValidationError as e:
            raise ValueError(str(e)) from e
        return MemoryStoreOutput(
            id=str(record.id),
            memory_type=record.memory_type,
            created_at=record.created_at,
        )

    @mcp.tool(
        name="memory_recall",
        description=(
            "Browse memories of one type, newest first. Filter by tags and time "
            "window. Use for 'what did I do recently' or 'what happened in this "
            "session'. Not for per-turn recall — use memory_search for that."
        ),
    )
    def memory_recall(input: MemoryRecallInput) -> MemoryRecallOutput:
        service = service_factory()  # type: ignore[operator]
        records = service.recall(
            input.memory_type,
            tags=input.tags,
            since=input.since,
            until=input.until,
            limit=input.limit,
        )
        return MemoryRecallOutput(records=[to_output(r) for r in records])

    @mcp.tool(
        name="memory_search",
        description=(
            "Search past memories by content. Call this at the START of every "
            "turn with the user's prompt as query. Returns ranked results from "
            "FTS5 plus the count of unprocessed raw memories from the previous "
            "session. If unprocessed_count > 0, call memory_get_raw to see them, "
            "classify them into typed memories with memory_store, then call "
            "memory_mark_processed. If empty, no memory is needed for this turn."
        ),
    )
    def memory_search(input: MemorySearchInput) -> MemorySearchOutput:
        service = service_factory()  # type: ignore[operator]
        try:
            records = service.search(input.memory_type, input.query, limit=input.limit)
        except ValidationError as e:
            raise ValueError(str(e)) from e
        return MemorySearchOutput(
            records=[to_output(r) for r in records],
            unprocessed_count=service.count_unprocessed_raw(),
        )

    @mcp.tool(
        name="memory_get_raw",
        description=(
            "Retrieve unprocessed raw memories from previous sessions. Call "
            "this when memory_search reports unprocessed_count > 0. Read each "
            "raw memory, classify it with memory_classify (facts → semantic, "
            "procedures → procedural, events → episodic). If a raw memory "
            "contains nothing worth keeping, dismiss it with "
            "memory_mark_processed."
        ),
    )
    def memory_get_raw() -> MemoryGetRawOutput:
        service = service_factory()  # type: ignore[operator]
        raw_memories = service.get_unprocessed_raw()
        return MemoryGetRawOutput(
            memories=[
                RawMemoryOut(
                    id=str(m.id),
                    content=m.content,
                    tags=list(m.tags),
                    payload=dict(m.payload),
                    source=m.source,
                    created_at=m.created_at,
                )
                for m in raw_memories
            ]
        )

    @mcp.tool(
        name="memory_classify",
        description=(
            "Classify a raw memory into typed memories and mark it processed "
            "in one step. Pass the raw_id and the typed memories you extracted "
            "(facts → semantic, procedures → procedural, events → episodic). "
            "session_id and parent_id are filled in automatically. The raw "
            "memory is marked as processed after the typed memories are stored."
        ),
    )
    def memory_classify(input: MemoryClassifyInput) -> MemoryClassifyOutput:
        service = service_factory()  # type: ignore[operator]
        classifications = [
            Classification(
                memory_type=c.memory_type,
                content=c.content,
                tags=list(c.tags),
                confidence=c.confidence,
            )
            for c in input.classifications
        ]
        try:
            stored = service.classify_raw(UUID(input.raw_id), classifications)
        except ValidationError as e:
            raise ValueError(str(e)) from e
        return MemoryClassifyOutput(stored_ids=[str(r.id) for r in stored])

    @mcp.tool(
        name="memory_mark_processed",
        description=(
            "Dismiss raw memories without classifying them. Use when a raw "
            "memory contains nothing worth keeping (idle chat, greetings, "
            "trivial responses). Pass the raw IDs to mark as processed. For "
            "useful raw memories, use memory_classify instead."
        ),
    )
    def memory_mark_processed(input: MemoryMarkProcessedInput) -> str:
        service = service_factory()  # type: ignore[operator]
        ids = [UUID(raw_id) for raw_id in input.ids]
        count = service.mark_processed(ids)
        return f"Marked {count} raw memor{'y' if count == 1 else 'ies'} as processed"
