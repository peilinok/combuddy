from combuddy import db

def test_init_schema_creates_tables(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite"))
    db.init_schema(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"roots", "models", "workflows", "edges", "meta"} <= names
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    ver = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    assert int(ver) == db.SCHEMA_VERSION
