"""CLI entry point for the consolidate command (SessionStart hook).

Reads unprocessed raw memories from the database and prints them to stdout.
Claude Code's SessionStart hook injects stdout as additionalContext into the
agent's first turn, so the agent sees the raw memories and classifies them
via memory_classify before answering the user.

Usage (from a Claude Code SessionStart hook):

    identity-storage-consolidate

Output format (plain text, injected as context):

    You have N unprocessed raw memories from previous sessions.
    Classify each one with memory_classify before answering the user.
    Pass an empty classifications list to dismiss trivial memories.

    --- raw_id: 019efbba-... ---
    User: fix the login bug
    Assistant: Fixed auth check in login.py
    ---
    ...
"""

from __future__ import annotations

import os
import sys

from identity_storage.db.connection import connect, resolve_db_path
from identity_storage.repository.memory_repository import MemoryRepository
from identity_storage.repository.raw_memory_repository import RawMemoryRepository
from identity_storage.service.memory_service import MemoryService

RAW_PREVIEW_MAX_CHARS = 500


def main() -> None:
    db_path = resolve_db_path(os.environ.get("IDENTITY_STORAGE_DB"))
    conn = connect(db_path)
    repo = MemoryRepository(conn)
    raw_repo = RawMemoryRepository(conn)
    service = MemoryService(repo, raw_repo)

    raw_memories = service.get_unprocessed_raw()

    if not raw_memories:
        return

    lines: list[str] = [
        f"You have {len(raw_memories)} unprocessed raw memor"
        f"{'y' if len(raw_memories) == 1 else 'ies'} from previous sessions.",
        "Classify each one with memory_classify before answering the user.",
        "Pass an empty classifications list to dismiss trivial memories.",
        "",
    ]

    for m in raw_memories:
        preview = m.content[:RAW_PREVIEW_MAX_CHARS]
        if len(m.content) > RAW_PREVIEW_MAX_CHARS:
            preview += "..."
        lines.append(f"--- raw_id: {m.id} ---")
        lines.append(preview)
        lines.append("---")
        lines.append("")

    sys.stdout.write("\n".join(lines))


if __name__ == "__main__":
    main()
