# Usage

## Install

The package is not on PyPI yet. Install directly from GitHub:

```bash
pip install git+https://github.com/MikSkrzyp/identity-storage-mcp.git
```

Or run it without installing:

```bash
uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp.git identity-storage-mcp
```

The package installs two console scripts:

- `identity-storage-mcp` — the MCP server (stdio transport)
- `identity-storage-ingest` — the transcript ingestor (called by client hooks)

## Configure Claude Code

### 1. Add the MCP server

One command — adds identity-storage as a user-scoped MCP server (available in
all your projects):

```bash
claude mcp add identity-storage -s user -- uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp identity-storage-mcp
```

Or manually, in `~/.claude.json`:

```json
{
  "mcpServers": {
    "identity-storage": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/MikSkrzyp/identity-storage-mcp",
        "identity-storage-mcp"
      ]
    }
  }
}
```

### 2. Add the Stop hook (auto-store)

Without this, the agent can recall memories but nothing gets stored
automatically. The hook runs when a conversation ends, reads the session
transcript, and saves each turn as an episodic memory.

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "command": "uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp identity-storage-ingest --agent claude-code"
      }
    ]
  }
}
```

If you installed with `pip` instead, use `"command": "identity-storage-ingest"`
with `--agent claude-code` as an arg.

## Other clients

Currently only Claude Code is supported. The ingestor interface
([`adapters/ingest/base.py`](../src/identity_storage/adapters/ingest/base.py))
defines the contract; each client needs a transcript parser implementing it.
Support for Codex, opencode, Cursor, and others is coming soon.

## Configuration

| Env var               | Default                        | Purpose                   |
| --------------------- | ------------------------------ | ------------------------- |
| `IDENTITY_STORAGE_DB` | `~/.identity-storage/memory.db`| SQLite database file path |

The parent directory is created on first run. The schema is applied
idempotently on every start, so pointing at a fresh path is safe.

## Tools

The agent sees three tools, each scoped by `memory_type` from the enum
(`episodic`, `semantic`, `procedural`, `personality`, `emotional`).

### `memory_search`

Search past memories by content. Call this at the start of every turn with
the user's prompt as query. Returns ranked results from FTS5. If empty, no
memory is needed for this turn.

Inputs:

| Field         | Type         | Default | Notes                                            |
| ------------- | ------------ | ------- | ------------------------------------------------ |
| `memory_type` | `MemoryType` | —       | Which memory type to search                      |
| `query`       | `str`        | —       | FTS5 query: terms, `'phrase'`, `AND`/`OR`        |
| `limit`       | `int`        | `20`    | Max records to return, in `[1, 200]`             |

Returns `{ records: [MemoryRecordOut, ...] }`.

### `memory_recall`

Browse memories of one type, newest first. Filter by tags and time window.
Use for "what did I do recently" or "what happened in this session". Not for
per-turn recall — use `memory_search` for that.

Inputs:

| Field         | Type             | Default | Notes                                          |
| ------------- | ---------------- | ------- | ---------------------------------------------- |
| `memory_type` | `MemoryType`     | —       | Which memory type to read                      |
| `tags`        | `list[str] \| None` | `None` | Only records tagged with ALL of these (AND)   |
| `since`       | `datetime \| None`  | `None` | ISO 8601 lower bound on `created_at`          |
| `until`       | `datetime \| None`  | `None` | ISO 8601 upper bound on `created_at`          |
| `limit`       | `int`            | `50`    | Max records to return, in `[1, 500]`           |

Returns `{ records: [MemoryRecordOut, ...] }`.

### `memory_store`

Manually persist a memory. Only use when the user explicitly asks you to
remember something. Regular turn storage is handled automatically by the
client's Stop hook.

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