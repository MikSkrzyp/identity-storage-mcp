-- identity-storage schema
-- Single source of truth for the SQLite layout. Auditable: anyone can run
-- `sqlite3 ~/.identity-storage/memory.db ".schema"` and see the truth.
--
-- Versioning: a `schema_version` row is inserted on init. Future migrations
-- bump the version and apply diffs in code (not here).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One table for all memory types. Type-specific payload validation happens in
-- the application layer; the DB stores it as JSON for portability and audit.
CREATE TABLE IF NOT EXISTS memory (
    id          TEXT PRIMARY KEY,           -- UUID v7 (text for auditability)
    type        TEXT NOT NULL,              -- MemoryType enum value
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',  -- JSON array
    payload     TEXT NOT NULL DEFAULT '{}',  -- JSON object, type-specific
    confidence  REAL NOT NULL DEFAULT 1.0,
    source      TEXT NOT NULL DEFAULT 'agent',
    created_at  TEXT NOT NULL,              -- ISO 8601 UTC
    CHECK (confidence BETWEEN 0.0 AND 1.0)
);

CREATE INDEX IF NOT EXISTS ix_memory_type_created ON memory (type, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_memory_created ON memory (created_at DESC);

-- FTS5 virtual table for full-text search across content + tags.
-- Use the "external content" pattern: FTS5 stores indexed tokens, the base
-- table stores the rows. We keep it simple (contentless not used) so the FTS
-- table itself is auditable by humans running `SELECT * FROM memory_fts`.
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content,
    tags,
    content='memory',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers keep the FTS index in sync with the base table.
CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
    INSERT INTO memory_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO memory_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;