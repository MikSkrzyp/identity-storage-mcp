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
        "Call memory_search at the start of every turn with the user's prompt "
        "as query. This retrieves relevant memories from past sessions. If "
        "nothing matches, that's fine — not every turn needs memory.\n"
        "\n"
        "Storing new memories is handled automatically by your client (e.g. "
        "Claude Code Stop hook). You do not need to call memory_store manually "
        "unless the user explicitly asks you to remember something.\n"
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
