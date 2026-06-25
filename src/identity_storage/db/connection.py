"""SQLite connection management.

Keeps a single connection per process (MCP servers are long-lived). WAL mode
gives concurrent reads while a tool call writes; `sqlite3` CLI users see
committed rows immediately. The schema is idempotent: re-running it is safe.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final

DEFAULT_DB_PATH: Final[Path] = Path.home() / ".identity-storage" / "memory.db"

SCHEMA_VERSION: Final[int] = 2

_SCHEMA_SQL_PATH = Path(__file__).parent.parent / "schemas" / "schema.sql"


def resolve_db_path(env_value: str | None) -> Path:
    """Pick the DB path from an env value, falling back to the default."""
    if env_value and env_value.strip():
        path = Path(env_value).expanduser()
        if path.is_dir():
            raise ValueError(f"IDENTITY_STORAGE_DB points to a directory: {path}")
        return path
    return DEFAULT_DB_PATH


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection and ensure the schema is present.

    Idempotent: safe to call on every server start. Creates the parent
    directory if missing so first-run is seamless.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        isolation_level=None,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")

    _apply_schema(conn)
    _record_schema_version(conn)
    return conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    schema_sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)


def _record_schema_version(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    elif row["version"] > SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema_version {row['version']} is newer than "
            f"supported {SCHEMA_VERSION}; refusing to downgrade"
        )
