"""MCP server wiring: FastMCP instance, service factory, entry point."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from identity_storage.adapters.mcp.tools import register_tools
from identity_storage.db.connection import connect, resolve_db_path
from identity_storage.repository.memory_repository import MemoryRepository
from identity_storage.repository.raw_memory_repository import RawMemoryRepository
from identity_storage.service.memory_service import MemoryService

mcp = FastMCP(
    "identity-storage",
    instructions=(
        "Long-term memory for AI agents, backed by local SQLite.\n"
        "\n"
        "FLOW — follow every turn:\n"
        "\n"
        "1. SEARCH: Call memory_search at the start of every turn with the "
        "user's prompt as query. This returns relevant past memories AND the "
        "count of unprocessed raw memories from the previous session.\n"
        "\n"
        "2. CONSOLIDATE: If unprocessed_count > 0, call memory_get_raw to "
        "retrieve the raw memories. For each raw memory:\n"
        "   - If it contains useful information, classify it with "
        "memory_classify: extract facts as semantic, procedures as "
        "procedural, events as episodic.\n"
        "   - If it is trivial (idle chat, greetings), dismiss it with "
        "memory_mark_processed.\n"
        "\n"
        "3. ANSWER: Use the search results (and any memories you just "
        "classified) as context alongside the user's prompt.\n"
        "\n"
        "Storing new raw memories is handled automatically by the client's "
        "Stop hook. You do not need to call memory_store for regular turns.\n"
        "\n"
        "Set IDENTITY_STORAGE_DB to override the default database path "
        "(~/.identity-storage/memory.db)."
    ),
)

_service: MemoryService | None = None


def _build_service() -> MemoryService:
    db_path = resolve_db_path(os.environ.get("IDENTITY_STORAGE_DB"))
    conn = connect(db_path)
    repo = MemoryRepository(conn)
    raw_repo = RawMemoryRepository(conn)
    return MemoryService(repo, raw_repo)


def _service_singleton() -> MemoryService:
    global _service  # noqa: PLW0603
    if _service is None:
        _service = _build_service()
    return _service


register_tools(mcp, _service_singleton)


def main() -> None:
    """Entry point for the ``identity-storage-mcp`` console script."""
    _service_singleton()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
