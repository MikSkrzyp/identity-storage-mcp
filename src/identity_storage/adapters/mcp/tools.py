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
    MemoryRecallInput,
    MemoryRecallOutput,
    MemorySearchInput,
    MemorySearchOutput,
    MemoryStoreInput,
    MemoryStoreOutput,
    to_output,
)
from identity_storage.model.store_request import StoreRequest
from identity_storage.service.memory_service import Classification
from identity_storage.service.validation import ValidationError


def register_tools(mcp: FastMCP, service_factory: object) -> None:
    """Register the four memory tools on ``mcp``.

    ``service_factory`` is a zero-arg callable returning a ``MemoryService``.
    Passed in rather than imported, so this module has no DB/service wiring.
    """

    @mcp.tool(
        name="memory_search",
        description=(
            "Search past memories by content. Call this at the start of every "
            "turn with the user's prompt as query. Returns ranked results from "
            "FTS5. If empty, no memory is needed for this turn. For browsing "
            "by tags or time window, use memory_recall."
        ),
    )
    def memory_search(input: MemorySearchInput) -> MemorySearchOutput:
        service = service_factory()  # type: ignore[operator]
        try:
            records = service.search(input.memory_type, input.query, limit=input.limit)
        except ValidationError as e:
            raise ValueError(str(e)) from e
        return MemorySearchOutput(records=[to_output(r) for r in records])

    @mcp.tool(
        name="memory_classify",
        description=(
            "Classify a raw memory into typed memories and mark it processed. "
            "Pass the raw_id and the typed memories you extracted (facts → "
            "semantic, procedures → procedural, events → episodic). session_id "
            "and parent_id are filled in automatically. Pass an empty "
            "classifications list to dismiss a trivial raw memory (idle chat, "
            "greetings) without storing anything."
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
