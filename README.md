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

This installs one console script:

- `identity-storage-mcp` — the MCP server (agent calls tools through it)

## Configure Claude Code

### 1. Add the MCP server

```bash
claude mcp add identity-storage -s user -- uvx --from git+https://github.com/MikSkrzyp/identity-storage-mcp identity-storage-mcp
```

### 2. Add memory instructions to CLAUDE.md

Add this to `~/.claude/CLAUDE.md` (global, all projects) or your project's
`CLAUDE.md`:

```markdown
# Memory — MANDATORY

identity-storage MCP is connected. Follow these rules EVERY session:

1. SEARCH: Call memory_search when the user references past work or you need
   context from previous sessions. Pass the user's prompt as query.

2. STORE: Call memory_store after every non-trivial turn:
   - episodic: events/actions (fixed bug, refactored module, user asked for X)
   - semantic: durable facts (user preferences, project info, tech stack)
   - procedural: how-tos (commands, steps, procedures)
   One memory per distinct thing. Skip idle chat.

3. SESSION END: When the user says exit/quit, store anything not yet saved.

Forgetting to store = permanent loss of the session.
Forgetting to search = working blind.
```

## Configure opencode

### 1. Add the MCP server

Add to `~/.config/opencode/opencode.jsonc`:

```json
{
  "$schema": "https://opencode.ai/config.json",
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

### 2. Add memory instructions to AGENTS.md

Add the same memory instructions (from the Claude Code section above) to
`~/.config/opencode/AGENTS.md` (global) or your project's `AGENTS.md`.

## Tools

The agent sees three tools, each scoped by `memory_type` (`episodic`,
`semantic`, `procedural`, `personality`, `emotional`):

| Tool             | Purpose                                                       |
| ---------------- | ------------------------------------------------------------- |
| `memory_search`  | Full-text search via FTS5 — when the user references past work |
| `memory_store`   | Store a memory with type classification (episodic/semantic/procedural) |
| `memory_recall`  | Browse by type, tags, and time window (newest first)          |

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

Claude Code and opencode are supported. Both use the same MCP server and
the same memory database. For other MCP-compatible clients (Codex, Cursor,
etc.), add the MCP server per their docs and add the memory instructions to
their equivalent of CLAUDE.md (e.g. `.cursorrules` for Cursor).

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