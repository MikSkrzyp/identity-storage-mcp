# API reference

## Public API

Importable from the top-level package:

```python
from identity_storage import (
    MemoryRecord,
    MemoryType,
    StoreRequest,
    MemoryService,
    MemoryRepository,
    ValidationError,
)
```

## `model/`

### `MemoryType` (StrEnum)

```python
class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PERSONALITY = "personality"
    EMOTIONAL = "emotional"
```

Kind of memory. Drives payload validation and storage strategy. Members are
strings, so they serialize to JSON and store in SQLite as plain text. New
kinds are added here; existing tools and the `memory` table stay compatible.

### `MemoryRecord` (frozen dataclass)

```python
@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: UUID
    memory_type: MemoryType
    content: str
    tags: list[str] = []
    payload: dict[str, Any] = {}
    confidence: float = 1.0
    source: str = "agent"
    created_at: datetime = datetime.utcnow()
```

A single memory entry, type-agnostic. `payload` holds type-specific fields
validated by the service layer based on `memory_type`; the model only
guarantees structure.

Invariants enforced in `__post_init__`:

- `confidence` must be in `[0.0, 1.0]`.
- `content` must not be empty or whitespace-only.

### `StoreRequest` (frozen dataclass)

```python
@dataclass(frozen=True, slots=True)
class StoreRequest:
    memory_type: MemoryType
    content: str
    tags: Sequence[str] = ()
    payload: dict[str, Any] | None = None
    confidence: float = 1.0
    source: str = "agent"
```

Input DTO for `MemoryService.store`. Callers supply this; the service fills in
`id` and `created_at` when building the `MemoryRecord`.

## `repository/`

### `MemoryRepository`

```python
class MemoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def store(self, record: MemoryRecord) -> None: ...
    def recall(
        self,
        memory_type: MemoryType,
        *,
        tags: Sequence[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...
    def search(
        self,
        memory_type: MemoryType,
        query: str,
        *,
        limit: int = 20,
    ) -> list[MemoryRecord]: ...
    def get(self, record_id: UUID) -> MemoryRecord | None: ...
    def delete(self, record_id: UUID) -> bool: ...
```

SQLite persistence for `MemoryRecord`. Concrete class, not a Protocol — there
is one backend. `recall` returns records ordered by `created_at` descending.
`search` uses FTS5 over the `content` column and ranks by relevance. Tag
filtering uses AND semantics: a record matches only if it contains every
requested tag. `delete` returns `True` if a row was removed.

### `helpers.py`

- `serialize_tags(tags) -> str` — JSON-encode a tag list.
- `serialize_payload(payload) -> str` — JSON-encode the payload dict.
- `parse_tags(raw) -> list[str]` — inverse of `serialize_tags`.
- `parse_payload(raw) -> dict[str, object]` — inverse of `serialize_payload`.
- `row_to_record(row: sqlite3.Row) -> MemoryRecord` — map a SQLite row to a
  `MemoryRecord`.

## `service/`

### `MemoryService`

```python
class MemoryService:
    def __init__(self, repository: MemoryRepository) -> None: ...
    def store(self, request: StoreRequest) -> MemoryRecord: ...
    def recall(
        self,
        memory_type: MemoryType,
        *,
        tags: Sequence[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...
    def search(
        self,
        memory_type: MemoryType,
        query: str,
        *,
        limit: int = 20,
    ) -> list[MemoryRecord]: ...
    def get(self, record_id: UUID) -> MemoryRecord | None: ...
    def delete(self, record_id: UUID) -> bool: ...
```

The only entry point for adapters. Adapters call this, never the repository
directly, so validation and future cross-cutting concerns (logging,
consolidation triggers) live in one place.

`store` generates a UUID v7 (time-sortable) and `created_at`, validates the
payload against the type-specific rules, persists, and returns the record.

Limits: `recall` accepts `[1, 500]`; `search` accepts `[1, 200]`. Out-of-range
limits raise `ValidationError`. Empty/whitespace search queries raise
`ValidationError`.

### `ValidationError`

```python
class ValidationError(ValueError): ...
```

Raised when a memory record fails semantic validation (bad payload keys,
out-of-range limit, empty query). Adapters translate this into a client error
string.

### Payload validation

Per-type validators live in `validation.py`. Register a new type's validator
in `_PAYLOAD_VALIDATORS`. The current registered set:

| `MemoryType`   | Allowed `payload` keys                                            |
| -------------- | ----------------------------------------------------------------- |
| `EPISODIC`     | `session_id`, `agent`, `task`, `outcome`, `parent_id`, `metadata` |
| others         | (none — pass through unvalidated, experimentation allowed)       |

## `db/`

### `connect(db_path: Path) -> sqlite3.Connection`

Open a connection, apply the schema idempotently, record the schema version,
and return the connection. Creates the parent directory if missing. WAL mode
is enabled; `foreign_keys` is on; `synchronous` is `NORMAL`.

### `resolve_db_path(env_value: str | None) -> Path`

Resolve a database path from an env value, falling back to
`~/.identity-storage/memory.db`. Raises `ValueError` if the value points to a
directory.

### Constants

- `DEFAULT_DB_PATH` — `~/.identity-storage/memory.db`.
- `SCHEMA_VERSION` — current schema version, written to the `schema_version`
  table on init. Refuses to downgrade.

## `adapters/mcp/`

### MCP tools

Three tools are registered on the FastMCP server:

| Tool           | Input class          | Output class          | Purpose                              |
| -------------- | -------------------- | --------------------- | ------------------------------------ |
| `memory_store` | `MemoryStoreInput`   | `MemoryStoreOutput`   | Persist a memory for future sessions |
| `memory_recall`| `MemoryRecallInput`  | `MemoryRecallOutput`  | Browse by type, tags, time window    |
| `memory_search`| `MemorySearchInput`  | `MemorySearchOutput`  | Full-text search via FTS5            |

Schemas (Pydantic `BaseModel`) and the `to_output(record)` converter live in
`adapters/mcp/schemas.py`. The tool functions are thin adapters — they
translate Pydantic input into a `StoreRequest` or a service call, then map the
result to Pydantic output. No business logic lives here.

### `main()`

Entry point for the `identity-storage-mcp` console script. Eagerly builds the
service so DB/schema problems surface at startup, then runs the FastMCP server
on the stdio transport.

## Console script

```
identity-storage-mcp
```

Installed by `pyproject.toml` as `[project.scripts]`. Reads
`IDENTITY_STORAGE_DB` from the environment to override the database path.