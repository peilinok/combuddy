import os, time
from combuddy import db, config, scanner

def _mkfile(p, size=10):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)

def test_scan_filters_noise_and_records_models(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"
    _mkfile(root / "checkpoints" / "SD1.5" / "foo.safetensors", 100)
    _mkfile(root / "loras" / "bar.safetensors", 50)
    _mkfile(root / "checkpoints" / ".DS_Store", 20)
    _mkfile(root / "checkpoints" / "put_checkpoints_here", 0)   # 0 字节占位
    _mkfile(root / "configs" / "x.yaml", 30)
    rid = conn.execute("INSERT INTO roots(kind,path,source) VALUES('model',?,'manual')",
                       (str(root),)).lastrowid
    conn.commit()
    res = scanner.scan_model_root(conn, rid, str(root))
    rows = {r["rel_in_type"]: r for r in conn.execute("SELECT * FROM models")}
    assert res["added"] == 2
    assert "SD1.5/foo.safetensors" in rows
    assert rows["SD1.5/foo.safetensors"]["dir_type"] == "checkpoints"
    assert "bar.safetensors" in rows          # loras 下无子目录
    assert not any(".DS_Store" in k or "put_" in k or ".yaml" in k for k in rows)

def test_scan_incremental_skips_unchanged(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"
    _mkfile(root / "loras" / "a.safetensors", 10)
    rid = conn.execute("INSERT INTO roots(kind,path,source) VALUES('model',?,'manual')",
                       (str(root),)).lastrowid
    conn.commit()
    scanner.scan_model_root(conn, rid, str(root))
    res2 = scanner.scan_model_root(conn, rid, str(root))
    assert res2["skipped"] == 1 and res2["added"] == 0

def test_scan_uncategorized_file_at_root(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"
    _mkfile(root / "loose.safetensors", 100)
    rid = conn.execute("INSERT INTO roots(kind,path,source) VALUES('model',?,'manual')",
                       (str(root),)).lastrowid
    conn.commit()
    res = scanner.scan_model_root(conn, rid, str(root))
    assert res["added"] == 1
    rows = {r["rel_in_type"]: r for r in conn.execute("SELECT * FROM models")}
    assert "loose.safetensors" in rows
    assert rows["loose.safetensors"]["dir_type"] == ""
    assert rows["loose.safetensors"]["rel_in_type"] == "loose.safetensors"

def _mroot(tmp_path):
    mroot = tmp_path / "models" / "checkpoints"; mroot.mkdir(parents=True)
    return tmp_path / "models", mroot

def _rid(conn):
    return config.get_roots(conn, "model")[0]["id"]

def test_changed_file_invalidates_sha256(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    root, mroot = _mroot(tmp_path)
    f = mroot / "a.safetensors"; f.write_bytes(b"AAAA")
    config.set_roots(conn, [{"kind": "model", "path": str(root), "source": "manual"}])
    scanner.scan_model_root(conn, _rid(conn), str(root))
    conn.execute("UPDATE models SET sha256='deadbeef'"); conn.commit()
    f.write_bytes(b"BBBBBB")                     # size 4->6，mtime 也变
    scanner.scan_model_root(conn, _rid(conn), str(root))
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] is None

def test_unchanged_file_keeps_sha256(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    root, mroot = _mroot(tmp_path)
    (mroot / "a.safetensors").write_bytes(b"AAAA")
    config.set_roots(conn, [{"kind": "model", "path": str(root), "source": "manual"}])
    scanner.scan_model_root(conn, _rid(conn), str(root))
    conn.execute("UPDATE models SET sha256='keepme'"); conn.commit()
    scanner.scan_model_root(conn, _rid(conn), str(root))   # 文件没动
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] == "keepme"
