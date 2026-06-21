# Architecture

## Overview

identity-storage is a portable, auditable long-term memory for AI agents.
It runs as a local MCP server backed by a single SQLite file. Agents (Claude
Code, Codex, opencode, Claude Desktop) call three abstract tools to store and
recall memories; humans audit the database directly with `sqlite3` or any
SQL client.

The design follows one rule: **pure domain in the middle, frameworks on the
edges.** Pydantic and the MCP SDK never leak past the adapter layer; SQLite
never leaks past the repository; the model knows nothing about either.

## Layers

```
adapters/mcp/  →  service/  →  repository/  →  SQLite file
     │              │             │
     │              │             └── queries + serialization (SQL, JSON columns, FTS5)
     │              └── validation, id generation, limit checks (pure Python)
     └── Pydantic schemas, FastMCP wiring (frameworks live here only)
                      ▲
                      │
              model/  ── pure dataclasses, no I/O, no framework imports
              db/     ── connection + schema init (sqlite3 stdlib only)
              schemas/schema.sql ── DDL, the single source of truth for the layout
```

Dependencies point inward. `model/` depends on nothing. `repository/` depends
on `model/`. `service/` depends on `model/` and `repository/`. `adapters/`
depends on everything. Nothing depends on `adapters/`.

## Why this shape (and not alternatives we considered)

### Why not full hexagonal / ports & adapters

We started with `MemoryRepository` and `Embedder` Protocols in the model and a
separate application layer. With exactly one backend (SQLite) and one driver
(MCP), this was YAGNI — two abstractions with one implementation each. We
collapsed to a pragmatic monolith, then split back into `repository/` +
`service/` when the single `service.py` file grew past 200 lines and started
mixing validation logic with SQL. The current split is by responsibility
(querying vs. orchestration), not by speculative backends.

When a second backend actually arrives (Postgres, a vector store, an
embedder), the right move is to extract a `Protocol` then — not before. The
seam is already implicit: `MemoryService.__init__` takes a
`MemoryRepository`; swapping the concrete class for a Protocol is a local
change.

### Why not event-driven / CQRS

Considered for the consolidation stage. Rejected for now: the agent calls
`memory_store` synchronously and wants a confirmation, so eventual
consistency would add cost without benefit. When consolidation, embedding,
and decay arrive, an outbox event log in the same SQLite file is the plan —
same database, still auditable, no external broker. That stage will introduce
the first real consumer of events; until then, YAGNI.

### Why dataclasses in `model/` and Pydantic only in `adapters/`

`MemoryRecord` and `StoreRequest` are plain dataclasses. Pydantic is a
runtime dependency with field validators, serialization config, and lifecycle
hooks that are useful on the wire boundary and unnecessary inside the
process. Keeping `model/` stdlib-only means `service/`, `repository/`, and
tests never import Pydantic. The MCP adapter translates between the canonical
dataclass and a Pydantic `MemoryRecordOut` at the edge — an anti-corruption
layer so internal changes don't leak to clients.

## Adding a new memory type

Memory types are open-ended. The flow:

1. Add a member to `MemoryType` in `model/memory_model.py`.
2. Optionally add a payload validator in `service/validation.py` and register
   it in `_PAYLOAD_VALIDATORS`. Unknown types pass through unvalidated, so
   experimental types work without any code change.
3. No adapter, schema, or repository change is needed — the MCP tools and the
   `memory` table are type-agnostic. The `memory_type` enum value is stored
   as a string column and surfaced as the enum on read.

## Adding a new backend

Not done yet. When it happens:

1. Extract a `MemoryRepository` Protocol in `repository/` (or `model/` if the
   domain needs to reference it).
2. Rename the current `MemoryRepository` to `SqliteMemoryRepository` and have
   it implement the Protocol.
3. Add the new backend as a second implementation.
4. `MemoryService.__init__` already takes a repository — only the wiring in
   `adapters/mcp/server.py` changes.

## Auditing

The database is a single file (default `~/.identity-storage/memory.db`,
overridable via `IDENTITY_STORAGE_DB`). It uses WAL mode so concurrent reads
from `sqlite3` CLI see committed rows immediately while the MCP server is
running. The schema is in `schemas/schema.sql` and is applied idempotently on
every connection.

Any SQL client works:

```sql
SELECT id, created_at, content FROM memory WHERE type='episodic' ORDER BY created_at DESC;
SELECT * FROM memory WHERE EXISTS (SELECT 1 FROM json_each(tags) WHERE value='auth');
SELECT payload->>'task' FROM memory WHERE type='episodic';
SELECT m.* FROM memory m JOIN memory_fts f ON f.rowid=m.rowid WHERE f.content MATCH 'auth bug';
```

There is no ORM, no migration framework, no hidden state. What you see in
`schema.sql` is exactly what is in the file.