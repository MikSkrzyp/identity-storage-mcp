# Usage

## Install

```bash
pip install identity-storage
```

Or with `uv`:

```bash
uvx identity-storage-mcp
```

The package installs a single console script, `identity-storage-mcp`, which
runs the MCP server on the stdio transport.

## Configure your client

### Claude Code

Add to `~/.config/claude/claude_desktop_config.json` (or the equivalent path
on your platform):

```json
{
  "mcpServers": {
    "identity-storage": {
      "command": "uvx",
      "args": ["identity-storage-mcp"]
    }
  }
}
```

If you installed with `pip` instead, use `"command": "identity-storage-mcp"`
with no args.

### opencode

Add to `opencode.json`:

```json
{
  "mcp": {
    "identity-storage": {
      "type": "local",
      "command": ["uvx", "identity-storage-mcp"]
    }
  }
}
```

### Codex / other MCP clients

Point the client at `identity-storage-mcp` over stdio. The server advertises
three tools via `tools/list`; any MCP-compatible client should pick them up.

## Configuration

| Env var               | Default                            | Purpose                    |
| --------------------- | ---------------------------------- | -------------------------- |
| `IDENTITY_STORAGE_DB` | `~/.identity-storage/memory.db`     | SQLite database file path  |

The parent directory is created on first run. The schema is applied
idempotently on every start, so pointing at a fresh path is safe.

## Tools

The agent sees three tools. Each takes a `memory_type` from the enum
(`episodic`, `semantic`, `procedural`, `personality`, `emotional`) so the
same tools work for every kind of memory we add.

### `memory_store`

Persist a memory for future sessions. Use whenever the user says "remember
this", when you learn a durable fact, fix a bug, or take a non-trivial action
you may need to recall later.

Inputs:

| Field         | Type             | Default | Notes                                                  |
| ------------- | ---------------- | ------- | ------------------------------------------------------ |
| `memory_type`| `MemoryType`    | —       | Kind of memory                                         |
| `content`     | `str`           | —       | The memory text, human-readable and self-contained     |
| `tags`        | `list[str]`      | `[]`    | Free-form tags for filtering                            |
| `payload`     | `dict \| None`   | `None`  | Type-specific JSON. Episodic allowed keys: `session_id`, `agent`, `task`, `outcome`, `parent_id`, `metadata` |
| `confidence`  | `float`          | `1.0`   | How reliable this memory is, in `[0.0, 1.0]`           |
| `source`      | `str`            | `"agent"` | Who/what produced this memory                         |

Returns `{ id, memory_type, created_at }`. The `id` is a UUID v7
(time-sortable).

### `memory_recall`

Browse memories of one type, newest first. Filter by tags and time window. Use
this for "what did I do recently" or "what happened in this session". For
free-text lookup use `memory_search` instead.

Inputs:

| Field         | Type             | Default | Notes                                          |
| ------------- | ---------------- | ------- | ---------------------------------------------- |
| `memory_type` | `MemoryType`     | —       | Which memory type to read                      |
| `tags`        | `list[str] \| None` | `None` | Only records tagged with ALL of these (AND)   |
| `since`       | `datetime \| None`  | `None` | ISO 8601 lower bound on `created_at`          |
| `until`       | `datetime \| None`  | `None` | ISO 8601 upper bound on `created_at`          |
| `limit`       | `int`            | `50`    | Max records to return, in `[1, 500]`           |

Returns `{ records: [MemoryRecordOut, ...] }`.

### `memory_search`

Full-text search within one memory type. Use this when you don't know the
exact tag or time — e.g. "show me memories about the auth bug". Returns ranked
by relevance. For chronological browsing use `memory_recall`.

Inputs:

| Field         | Type         | Default | Notes                                            |
| ------------- | ------------ | ------- | ------------------------------------------------ |
| `memory_type` | `MemoryType` | —       | Which memory type to search                      |
| `query`       | `str`        | —       | FTS5 query: terms, `'phrase'`, `AND`/`OR`        |
| `limit`       | `int`        | `20`    | Max records to return, in `[1, 200]`             |

Returns `{ records: [MemoryRecordOut, ...] }`.

### `MemoryRecordOut`

Every record returned by `memory_recall` and `memory_search` has this shape:

| Field         | Type         |
| ------------- | ------------ |
| `id`          | `str` (UUID)|
| `memory_type` | `MemoryType` |
| `content`     | `str`        |
| `tags`        | `list[str]`  |
| `payload`     | `dict`       |
| `confidence`  | `float`      |
| `source`      | `str`        |
| `created_at`  | `datetime`   |

## Auditing the database

The database is a regular SQLite file. Any SQL client works while the server
is running (WAL mode allows concurrent reads):

```bash
sqlite3 ~/.identity-storage/memory.db
```

Useful queries:

```sql
-- newest episodic memories
SELECT id, created_at, content FROM memory
WHERE type='episodic'
ORDER BY created_at DESC;

-- memories tagged 'auth'
SELECT * FROM memory
WHERE EXISTS (SELECT 1 FROM json_each(tags) WHERE value='auth');

-- pull a field out of the payload
SELECT payload->>'task', payload->>'outcome'
FROM memory WHERE type='episodic';

-- full-text search the same way the agent does
SELECT m.*
FROM memory m
JOIN memory_fts f ON f.rowid = m.rowid
WHERE f.content MATCH 'auth bug'
ORDER BY rank;

-- counts per type
SELECT type, COUNT(*), MIN(created_at), MAX(created_at)
FROM memory GROUP BY type;
```

The schema is in `schemas/schema.sql` and is the single source of truth. Run
`.schema` in the `sqlite3` CLI to see exactly what is in the file.