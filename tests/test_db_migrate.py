from combuddy import db


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_fresh_db_is_v2(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite"))
    db.init_schema(conn)
    assert db.SCHEMA_VERSION == 2
    assert {"precision", "param_count", "display_name"} <= _cols(conn, "models")
    assert "trash" in {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]) == 2


def test_migrates_old_v1_db(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite"))
    # simulate a v1 models table (no new columns, no trash table)
    conn.executescript("""
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
      CREATE TABLE roots(id INTEGER PRIMARY KEY, kind TEXT, path TEXT UNIQUE, label TEXT, source TEXT, enabled INTEGER DEFAULT 1);
      CREATE TABLE models(id INTEGER PRIMARY KEY, root_id INTEGER, path TEXT UNIQUE, rel_path TEXT,
        dir_type TEXT, rel_in_type TEXT, filename TEXT, ext TEXT, size INTEGER, mtime REAL,
        base_arch TEXT, base_source TEXT, header_meta TEXT, sha256 TEXT, match_key TEXT, name_key TEXT,
        first_seen REAL, last_scanned REAL);
      INSERT INTO meta VALUES('schema_version','1');
    """)
    conn.commit()
    db.init_schema(conn)   # must migrate in place, not crash
    assert {"precision", "param_count", "display_name"} <= _cols(conn, "models")
    assert "trash" in {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]) == 2
