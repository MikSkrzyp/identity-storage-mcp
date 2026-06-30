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
        "You MUST follow this flow every session:\n"
        "\n"
        "1. SEARCH: Call memory_search when the user references past work "
        "('do you remember', 'last time', 'previously') or when you need "
        "context from a previous session. Pass the user's prompt as query. "
        "Skip for new standalone tasks with no history.\n"
        "\n"
        "2. ANSWER: Use the search results as context alongside the user's "
        "prompt.\n"
        "\n"
        "3. STORE: You MUST call memory_store after every non-trivial turn "
        "where you took an action, learned a fact, or made a decision. "
        "Classify each memory:\n"
        "   - episodic: events that happened ('fixed login bug', 'refactored "
        "auth module', 'user asked for a game')\n"
        "   - semantic: durable facts ('user prefers Python 3.12', 'project "
        "uses pytest', 'auth uses JWT')\n"
        "   - procedural: how-tos ('run tests: pytest -x', 'deploy: npm run "
        "build')\n"
        "   One memory per distinct thing. Skip idle chat and greetings.\n"
        "\n"
        "4. SESSION END: When the user says exit/quit, store anything not "
        "yet saved. Forgetting to store = permanent loss of the session.\n"
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
