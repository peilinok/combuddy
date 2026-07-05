import sqlite3

SCHEMA_VERSION = 3

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

        CREATE TABLE IF NOT EXISTS roots (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,           -- 'model' | 'workflow'
            path TEXT NOT NULL UNIQUE,
            label TEXT,
            source TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL REFERENCES roots(id),
            path TEXT NOT NULL UNIQUE,
            rel_path TEXT NOT NULL,
            dir_type TEXT NOT NULL,
            rel_in_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            ext TEXT NOT NULL,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            base_arch TEXT,
            base_source TEXT,
            header_meta TEXT,             -- reserved for future enrichment, unpopulated in v1 (same as sha256)
            sha256 TEXT,
            precision TEXT,
            param_count INTEGER,
            display_name TEXT,
            match_key TEXT NOT NULL,
            name_key TEXT NOT NULL,
            first_seen REAL NOT NULL,
            last_scanned REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_models_match ON models(dir_type, match_key);
        CREATE INDEX IF NOT EXISTS ix_models_name ON models(name_key);

        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL REFERENCES roots(id),
            path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            mtime REAL NOT NULL,
            ref_count INTEGER NOT NULL DEFAULT 0,
            parse_error TEXT,
            last_scanned REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY,
            workflow_id INTEGER NOT NULL REFERENCES workflows(id),
            ref_string TEXT NOT NULL,
            ref_key TEXT NOT NULL,
            ref_dir_type TEXT,
            node_type TEXT,
            model_id INTEGER REFERENCES models(id),
            match_kind TEXT,
            UNIQUE(workflow_id, ref_string, node_type)
        );
        CREATE INDEX IF NOT EXISTS ix_edges_model ON edges(model_id);

        CREATE TABLE IF NOT EXISTS trash (
            id INTEGER PRIMARY KEY,
            model_path TEXT NOT NULL,
            rel_path TEXT,
            dir_type TEXT,
            size INTEGER,
            trashed_at REAL NOT NULL,
            trash_path TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS civitai (
            model_id     INTEGER PRIMARY KEY REFERENCES models(id) ON DELETE CASCADE,
            sha256       TEXT NOT NULL,
            found        INTEGER NOT NULL,
            name         TEXT,
            version_name TEXT,
            base_model   TEXT,
            model_type   TEXT,
            trigger_words TEXT,
            nsfw_level   INTEGER,
            civitai_url  TEXT,
            image_path   TEXT,
            checked_at   REAL NOT NULL
        );
        """
    )
    # migrate existing (pre-v2) dbs: add columns the CREATE-IF-NOT-EXISTS above can't add
    have = {r["name"] for r in conn.execute("PRAGMA table_info(models)")}
    for col, decl in (("precision", "TEXT"), ("param_count", "INTEGER"), ("display_name", "TEXT")):
        if col not in have:
            conn.execute(f"ALTER TABLE models ADD COLUMN {col} {decl}")
    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
