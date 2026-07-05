import hashlib
from combuddy import db, hashes

def _seed(conn, files):
    """files: list[(pathlib.Path, bytes)]. 直接插 models 行(带全部 NOT NULL 列),sha256 留 NULL。"""
    conn.execute("INSERT INTO roots(id,kind,path,enabled) VALUES(1,'model','/r',1)")
    now = 1.0
    for i, (p, data) in enumerate(files, start=1):
        p.write_bytes(data)
        conn.execute(
            """INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
                 size,mtime,match_key,name_key,first_seen,last_scanned)
               VALUES(?,1,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (i, str(p), p.name, "checkpoints", p.name, p.name, "safetensors",
             len(data), now, p.name.lower(), p.name.lower(), now, now))
    conn.commit()

def test_sha256_file_matches_hashlib(tmp_path):
    p = tmp_path / "f.bin"; p.write_bytes(b"hello world")
    assert hashes.sha256_file(str(p)) == hashlib.sha256(b"hello world").hexdigest()

def test_sha256_file_missing_returns_none(tmp_path):
    assert hashes.sha256_file(str(tmp_path / "nope.bin")) is None

def test_compute_hashes_fills_null_rows(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    a = tmp_path / "a.safetensors"; b = tmp_path / "b.safetensors"
    _seed(conn, [(a, b"AAAA"), (b, b"BBBBBB")])
    res = hashes.compute_hashes(conn)
    assert res == {"hashed": 2, "errors": 0, "total": 2, "cancelled": False}
    got = {r["filename"]: r["sha256"] for r in conn.execute("SELECT filename,sha256 FROM models")}
    assert got["a.safetensors"] == hashlib.sha256(b"AAAA").hexdigest()
    assert got["b.safetensors"] == hashlib.sha256(b"BBBBBB").hexdigest()

def test_compute_hashes_parallel_workers_hash_all(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    files = [(tmp_path / f"m{i}.safetensors", bytes([65 + i]) * ((i + 1) * 16)) for i in range(6)]
    _seed(conn, files)
    res = hashes.compute_hashes(conn, workers=3)
    assert res["hashed"] == 6 and res["errors"] == 0
    for p, data in files:
        row = conn.execute("SELECT sha256 FROM models WHERE filename=?", (p.name,)).fetchone()
        assert row["sha256"] == hashlib.sha256(data).hexdigest()

def test_compute_hashes_workers_clamped(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [(tmp_path / "a.safetensors", b"AAAA")])
    res = hashes.compute_hashes(conn, workers=99)   # 不崩,夹取到 8
    assert res["hashed"] == 1

def test_compute_hashes_throttle_does_not_corrupt(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [(tmp_path / "a.safetensors", b"AAAA")])
    hashes.compute_hashes(conn, max_mbps=1)         # 限速不影响正确性
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] == hashlib.sha256(b"AAAA").hexdigest()

def test_compute_hashes_skips_already_hashed(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [(tmp_path / "a.safetensors", b"AAAA")])
    conn.execute("UPDATE models SET sha256='PRESET'"); conn.commit()
    res = hashes.compute_hashes(conn)
    assert res["total"] == 0 and res["hashed"] == 0
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] == "PRESET"

def test_compute_hashes_cancel_stops_before_work(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [(tmp_path / "a.safetensors", b"AAAA")])
    res = hashes.compute_hashes(conn, should_cancel=lambda: True)
    assert res["hashed"] == 0 and res["cancelled"] is True
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] is None

def test_compute_hashes_missing_file_counts_error(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [(tmp_path / "a.safetensors", b"AAAA")])
    (tmp_path / "a.safetensors").unlink()
    res = hashes.compute_hashes(conn)
    assert res["errors"] == 1 and res["hashed"] == 0
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] is None

def test_compute_hashes_reports_progress(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [(tmp_path / "a.safetensors", b"AAAA"), (tmp_path / "b.safetensors", b"BB")])
    seen = []
    hashes.compute_hashes(conn, progress=lambda d, t: seen.append((d, t)))
    assert seen[0] == (0, 2) and seen[-1] == (2, 2)
