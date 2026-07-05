from combuddy import db


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_fresh_db_is_v3(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite"))
    db.init_schema(conn)
    assert db.SCHEMA_VERSION == 3
    assert {"precision", "param_count", "display_name"} <= _cols(conn, "models")
    assert "trash" in {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]) == 3


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
    assert int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]) == 3


def test_fresh_db_is_v3_with_civitai(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    assert db.SCHEMA_VERSION == 3
    cols = _cols(conn, "civitai")
    assert {"model_id", "sha256", "found", "name", "base_model", "model_type",
            "trigger_words", "nsfw_level", "civitai_url", "image_path", "checked_at"} <= cols

def test_init_schema_idempotent_to_v3(tmp_path):
    p = str(tmp_path / "c.sqlite")
    conn = db.connect(p); db.init_schema(conn); db.init_schema(conn)   # 二次不炸
    assert conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()["value"] == "3"

def test_civitai_cascades_on_model_delete(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    conn.execute("INSERT INTO roots(id,kind,path,enabled) VALUES(1,'model','/r',1)")
    conn.execute("""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
        size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(1,1,'/r/a','a','checkpoints','a','a.safetensors','safetensors',9,1,'a','a',1,1)""")
    conn.execute("""INSERT INTO civitai(model_id,sha256,found,checked_at) VALUES(1,'deadbeef',1,1)""")
    conn.commit()
    conn.execute("DELETE FROM models WHERE id=1"); conn.commit()   # FK ON DELETE CASCADE
    assert conn.execute("SELECT COUNT(*) c FROM civitai").fetchone()["c"] == 0
