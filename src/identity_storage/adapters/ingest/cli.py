"""CLI entry point for the ingest command.

Reads a Stop hook payload from stdin, dispatches to the right ingestor by
``--agent``, and stores the extracted memories via ``MemoryService``.

Usage (from a Claude Code Stop hook):

    identity-storage-ingest --agent claude-code < stdin_payload.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from identity_storage.adapters.ingest.base import Ingestor
from identity_storage.adapters.ingest.claude_code import ClaudeCodeIngestor
from identity_storage.db.connection import connect, resolve_db_path
from identity_storage.model.store_request import StoreRequest
from identity_storage.repository.memory_repository import MemoryRepository
from identity_storage.service.memory_service import MemoryService

INGESTORS: dict[str, type[Ingestor]] = {
    "claude-code": ClaudeCodeIngestor,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="identity-storage-ingest",
        description="Ingest a session transcript into long-term memory.",
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=sorted(INGESTORS.keys()),
        help="Which client's transcript format to parse.",
    )
    args = parser.parse_args()

    payload_raw = sys.stdin.read()
    if not payload_raw.strip():
        print("ingest: empty stdin, nothing to do", file=sys.stderr)
        return

    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as e:
        print(f"ingest: invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(payload, dict):
        print("ingest: payload is not a JSON object", file=sys.stderr)
        sys.exit(1)

    ingestor_cls = INGESTORS[args.agent]
    ingestor = ingestor_cls()

    requests: Sequence[StoreRequest] = ingestor.ingest(payload)
    if not requests:
        print("ingest: no memories extracted", file=sys.stderr)
        return

    db_path = resolve_db_path(os.environ.get("IDENTITY_STORAGE_DB"))
    conn = connect(db_path)
    repo = MemoryRepository(conn)
    service = MemoryService(repo)

    stored = 0
    for request in requests:
        try:
            service.store(request)
            stored += 1
        except Exception as e:
            print(f"ingest: failed to store memory: {e}", file=sys.stderr)

    print(f"ingest: stored {stored} memor{'y' if stored == 1 else 'ies'}")


if __name__ == "__main__":
    main()
