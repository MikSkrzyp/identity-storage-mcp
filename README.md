# identity-storage

Portable, auditable long-term memory for AI agents. Runs as a local MCP
server backed by a single SQLite file. Agents recall memories through MCP
tools; a Stop hook stores session transcripts automatically — no agent
discipline required.

## Why

Agents like Claude Code are stateless between sessions. `identity-storage`
gives them a memory that survives restarts and stays fully inspectable — no
ORM, no migration framework, no hidden state. Point `sqlite3` at the file and
read everything.

## Install

The package is not on PyPI yet. Install directly from GitHub:

```bash
pip install git+https://github.com/MikSkrzyp/identity-storage-mcp.git
```

Or run it without installing:

```bash
uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp.git identity-storage-mcp
```

## Configure Claude Code

### 1. Add the MCP server

```bash
claude mcp add identity-storage -s user -- uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp identity-storage-mcp
```

This makes three memory tools available to the agent in every project.

### 2. Add the Stop hook (auto-store)

Without this, the agent can recall memories but nothing gets stored
automatically. The hook reads the session transcript when a conversation ends
and saves each turn as an episodic memory.

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

That's it. From now on every Claude Code session is remembered.

## Tools

The agent sees three tools, each scoped by `memory_type` (`episodic`,
`semantic`, `procedural`, `personality`, `emotional`):

| Tool           | Purpose                                              |
| -------------- | ---------------------------------------------------- |
| `memory_search`| Full-text search via FTS5 — call at the start of a turn |
| `memory_recall`| Browse by type, tags, and time window (newest first) |
| `memory_store` | Manually persist a memory (rarely needed — the Stop hook handles storage) |

See [docs/usage.md](docs/usage.md) for the full input/output schemas.

## Configuration

| Env var               | Default                        | Purpose                   |
| --------------------- | ------------------------------ | ------------------------- |
| `IDENTITY_STORAGE_DB` | `~/.identity-storage/memory.db`| SQLite database file path |

The parent directory is created on first run. The schema is applied
idempotently on every start, so pointing at a fresh path is safe.

## Audit

The database is a regular SQLite file. Read it while the server runs (WAL mode
allows concurrent reads):

```bash
sqlite3 ~/.identity-storage/memory.db
```

```sql
SELECT id, created_at, content FROM memory
WHERE type='episodic'
ORDER BY created_at DESC;

SELECT * FROM memory
WHERE EXISTS (SELECT 1 FROM json_each(tags) WHERE value='auth');

SELECT m.*
FROM memory m
JOIN memory_fts f ON f.rowid = m.rowid
WHERE f.content MATCH 'auth bug'
ORDER BY rank;
```

The schema lives in [`schemas/schema.sql`](src/identity_storage/schemas/schema.sql)
and is the single source of truth. Run `.schema` in the `sqlite3` CLI to see
exactly what is in the file.

## Other clients

Currently only Claude Code is supported (MCP server + Stop hook ingestor).
Support for Codex, opencode, Cursor, and others is coming soon — the
ingestor interface is already in place
([`adapters/ingest/base.py`](src/identity_storage/adapters/ingest/base.py));
each client just needs a transcript parser.

## Documentation

- [docs/architecture.md](docs/architecture.md) — layers, design decisions,
  how to add a memory type or a backend
- [docs/api.md](docs/api.md) — full API reference
- [docs/usage.md](docs/usage.md) — install snippets, tool schemas, auditing
- [docs/development.md](docs/development.md) — dev setup, commands, conventions

## Status

Alpha. The MCP contract and the SQLite schema are stable for the episodic
case. Semantic memory, procedural memory, consolidation, and embeddings are
planned — see [docs/architecture.md](docs/architecture.md) for the roadmap
shape.

## License

MIT