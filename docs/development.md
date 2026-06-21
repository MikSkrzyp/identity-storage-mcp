# Development

## Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for environment and
dependency management. To get a working dev environment:

```bash
git clone https://github.com/mikskrzyp/identity-storage.git
cd identity-storage
uv sync
```

This creates a virtual environment in `.venv/` and installs the project
together with the dev dependencies (`ruff`, `mypy`, `pytest`).

## Commands

Run all of these before pushing. They are what CI will run (once CI exists).

```bash
uv run ruff check          # lint
uv run ruff format --check # format check (run `uv run ruff format` to fix)
uv run mypy                # strict type check
uv run pytest              # tests
```

To run just the tests:

```bash
uv run pytest -q
```

To smoke-test the MCP server against a throwaway database:

```bash
IDENTITY_STORAGE_DB=/tmp/identity-storage-smoke.db uv run identity-storage-mcp &
sleep 1
kill %1
sqlite3 /tmp/identity-storage-smoke.db ".schema"
rm /tmp/identity-storage-smoke.db*
```

## Project layout

```
src/identity_storage/
├── __init__.py             # public re-exports
├── model/
│   ├── memory_model.py     # MemoryRecord, MemoryType (dataclasses, pure)
│   └── store_request.py    # StoreRequest (input DTO, dataclass)
├── repository/
│   ├── memory_repository.py # MemoryRepository (SQLite queries)
│   └── helpers.py          # serialize/parse/row_to_record
├── service/
│   ├── memory_service.py   # MemoryService (validation + orchestration)
│   └── validation.py       # ValidationError, validate_payload
├── db/
│   └── connection.py       # connect(), resolve_db_path(), schema init
├── schemas/schema.sql      # DDL (single source of truth for the DB layout)
└── adapters/mcp/
    ├── schemas.py          # Pydantic input/output + to_output converter
    ├── tools.py            # register_tools(mcp, service_factory)
    └── server.py           # FastMCP wiring, _service_singleton, main

tests/unit/
├── test_repository.py      # in-memory SQLite, full SQL + FTS5 path
└── test_service.py         # FakeRepository, validation + orchestration
```

The dependency direction is inward: `model/` → `repository/` → `service/` →
`adapters/`. Nothing imports from a layer to its right. `model/` imports only
the standard library.

## Conventions

- **No inline comments.** Docstrings on public APIs are welcome and expected;
  inline `#` comments are not. Explain *why* in a docstring or in this `docs/`
  directory, not in a code comment.
- **Docstrings on public APIs.** `MemoryService`, `MemoryRepository`,
  `MemoryRecord`, `StoreRequest`, `MemoryType`, `ValidationError`, and the
  MCP tool `description` arguments are the public surface. Keep their
  docstrings accurate; they show up in `help()` and IDE hover.
- **`__init__.py` re-exports only.** No implementation lives in an
  `__init__.py`. Code lives in named modules (`memory_model.py`,
  `memory_repository.py`, etc.); the package `__init__.py` re-exports the
  public surface.
- **Pydantic on the edge only.** `adapters/mcp/schemas.py` is the only place
  Pydantic models live. `model/`, `service/`, and `repository/` never import
  Pydantic. This keeps the core stdlib-only and testable without a framework.
- **SQLite is the only backend.** `repository/memory_repository.py` speaks
  `sqlite3` directly. If a second backend ever appears, extract a `Protocol`
  at that point — not preemptively.

## Adding a new memory type

1. Add a member to `MemoryType` in `model/memory_model.py`.
2. (Optional) Add a payload validator in `service/validation.py` and register
   it in `_PAYLOAD_VALIDATORS`. Without a validator, the type passes through
   unvalidated — useful while experimenting.
3. No adapter, schema, or repository change is needed. The MCP tools and the
   `memory` table are type-agnostic; the `memory_type` value is stored as a
   string column and surfaced as the enum on read.

## Adding a new backend

Not done yet. When it happens:

1. Extract a `MemoryRepository` Protocol (in `repository/` or `model/` if the
   domain needs to reference it).
2. Rename the current `MemoryRepository` to `SqliteMemoryRepository` and have
   it implement the Protocol.
3. Add the new backend as a second implementation.
4. Only the wiring in `adapters/mcp/server.py` changes; `MemoryService` already
   takes a repository.

## Releasing

Single source of truth is `pyproject.toml`. Bump `version` there following
[SemVer](https://semver.org/):

- **patch** (`0.1.0` → `0.1.1`): bug fixes, no new tools, no schema changes.
- **minor** (`0.1.0` → `0.2.0`): new memory types, new tool, new payload keys —
  backwards-compatible.
- **major** (`0.1.0` → `1.0.0`): breaking change to the MCP tool schema or the
  SQLite layout.

The schema version in `db/connection.py` (`SCHEMA_VERSION`) is independent
of the package version. Bump it only when `schemas/schema.sql` changes in a
way that is not backwards-compatible, and write a migration in code at the
same time.