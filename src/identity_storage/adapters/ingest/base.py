"""Ingestor interface: extract memories from a client's session transcript.

Each AI client (Claude Code, Codex, Cursor, ...) stores session transcripts
in a different format. An ``Ingestor`` knows how to read one client's format
and turn it into ``StoreRequest`` objects. The service layer persists them;
the ingestor only parses.

New clients = new file in ``adapters/ingest/`` implementing ``Ingestor``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from identity_storage.model.store_request import StoreRequest


class Ingestor(Protocol):
    """Read a client's session transcript and produce memory store requests.

    Implementations are registered in ``INGESTORS`` (see ``cli.py``) and
    selected by name via ``--agent <name>``.
    """

    def ingest(self, payload: dict[str, str]) -> Sequence[StoreRequest]:
        """Parse the hook payload and return memories to store.

        ``payload`` is the JSON the client sends on its Stop hook (read from
        stdin by the CLI). At minimum it contains a path to the transcript;
        the exact key depends on the client.
        """
        ...
