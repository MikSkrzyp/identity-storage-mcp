# identity-storage

Portable, auditable long-term memory for AI agents. Runs as a local MCP
server backed by a single SQLite file. Agents store and recall memories
through three abstract tools; you audit the database with plain SQL.

## Why

Agents like Claude Code, Codex, and opencode are stateless between sessions.
`identity-storage` gives them a memory that survives restarts, works across
clients, and stays fully inspectable — no ORM, no migration framework, no
hidden state. Point `sqlite3` at the file and read everything.

## Install

The package is not on PyPI yet. Install directly from GitHub:

```bash
pip install git+https://github.com/MikSkrzyp/identity-storage-mcp.git
```

Or run it without installing (downloads, builds, and executes on each call):

```bash
uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp.git identity-storage-mcp
```

## Configure your client

### Claude Code

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

### opencode

`opencode.json`:

```json
{
  "mcp": {
    "identity-storage": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "git+https://github.com/MikSkrzyp/identity-storage-mcp",
        "identity-storage-mcp"
      ]
    }
  }
}
```

### Codex / other MCP clients

Point the client at `identity-storage-mcp` over stdio. The server advertises
three tools via `tools/list`; any MCP-compatible client picks them up.

## Tools

The agent sees three tools, each scoped by `memory_type` (`episodic`,
`semantic`, `procedural`, `personality`, `emotional`):

| Tool           | Purpose                                              |
| -------------- | ---------------------------------------------------- |
| `memory_store` | Persist a memory for future sessions                 |
| `memory_recall`| Browse by type, tags, and time window (newest first) |
| `memory_search`| Full-text search via SQLite FTS5 (ranked by relevance)|

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