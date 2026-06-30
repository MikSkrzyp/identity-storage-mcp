"""MCP server wiring: FastMCP instance, service factory, entry point."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from identity_storage.adapters.mcp.tools import register_tools
from identity_storage.db.connection import connect, resolve_db_path
from identity_storage.repository.memory_repository import MemoryRepository
from identity_storage.service.memory_service import MemoryService

mcp = FastMCP(
    "identity-storage",
    instructions=(
        "Long-term memory for AI agents, backed by local SQLite.\n"
        "\n"
        "FLOW:\n"
        "\n"
        "1. SEARCH: Call memory_search at the start of every turn with the "
        "user's prompt as query. Returns relevant past memories from FTS5.\n"
        "\n"
        "2. ANSWER: Use the search results as context alongside the user's "
        "prompt.\n"
        "\n"
        "3. STORE: At session end (when the user says exit or the session is "
        "ending), store what happened using memory_store. Classify each "
        "memory:\n"
        "   - episodic: events that happened (actions, fixes, decisions)\n"
        "   - semantic: durable facts (preferences, project info, knowledge)\n"
        "   - procedural: how-tos (steps, commands, procedures)\n"
        "   Store one memory per distinct thing worth remembering. Skip idle "
        "chat and greetings. Set confidence below 1.0 for guesses.\n"
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
    return MemoryService(repo)


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
