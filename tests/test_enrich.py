import json, struct, time
from combuddy import db, headers

def _write_st(p, header):
    blob = json.dumps(header).encode(); p.write_bytes(struct.pack("<Q", len(blob)) + blob)

def _insert_model(conn, path, ext):
    conn.execute("INSERT INTO roots(kind,path,source) VALUES('model','/r','manual')")
    conn.execute("""INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,
        ext,size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(1,?,?,?,?,?,?,1,1,?,?,?,?)""",
        (path, "checkpoints/x", "checkpoints", "x", "x."+ext, ext, "x", "x", time.time(), time.time()))
    conn.commit()

def test_enrich_sets_base_and_source(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    p = tmp_path / "x.safetensors"
    _write_st(p, {"double_blocks.0.w": {"dtype":"F16","shape":[1],"data_offsets":[0,2]}})
    _insert_model(conn, str(p), "safetensors")
    n = headers.enrich_bases(conn)
    row = conn.execute("SELECT base_arch, base_source FROM models").fetchone()
    assert n == 1 and row["base_arch"] == "flux" and row["base_source"] == "tensor-heuristic"

def test_enrich_marks_unknown_for_bad_file(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    _insert_model(conn, str(tmp_path/"missing.safetensors"), "safetensors")
    headers.enrich_bases(conn)
    assert conn.execute("SELECT base_arch FROM models").fetchone()["base_arch"] == "unknown"

def test_enrich_second_run_is_noop(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    p = tmp_path / "x.safetensors"
    _write_st(p, {"double_blocks.0.w": {"dtype":"F16","shape":[1],"data_offsets":[0,2]}})
    _insert_model(conn, str(p), "safetensors")
    n1 = headers.enrich_bases(conn)
    assert n1 == 1
    row_before = conn.execute("SELECT base_arch FROM models").fetchone()
    n2 = headers.enrich_bases(conn)
    assert n2 == 0
    row_after = conn.execute("SELECT base_arch FROM models").fetchone()
    assert row_before["base_arch"] == row_after["base_arch"]

def test_enrich_batch_limits(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    # Insert roots first, then two models with different root_ids to avoid UNIQUE constraint violation
    conn.execute("INSERT INTO roots(kind,path,source) VALUES('model','/r1','manual')")
    conn.execute("INSERT INTO roots(kind,path,source) VALUES('model','/r2','manual')")
    conn.commit()
    p1 = tmp_path / "x1.safetensors"
    p2 = tmp_path / "x2.safetensors"
    _write_st(p1, {"double_blocks.0.w": {"dtype":"F16","shape":[1],"data_offsets":[0,2]}})
    _write_st(p2, {"double_blocks.1.w": {"dtype":"F16","shape":[1],"data_offsets":[0,2]}})
    conn.execute("""INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,
        ext,size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(1,?,?,?,?,?,?,1,1,?,?,?,?)""",
        (str(p1), "checkpoints/x", "checkpoints", "x", "x.safetensors", "safetensors", "x", "x", time.time(), time.time()))
    conn.execute("""INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,
        ext,size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(2,?,?,?,?,?,?,1,1,?,?,?,?)""",
        (str(p2), "checkpoints/y", "checkpoints", "y", "y.safetensors", "safetensors", "y", "y", time.time(), time.time()))
    conn.commit()
    # First batch=1 call should process exactly one
    n1 = headers.enrich_bases(conn, batch=1)
    assert n1 == 1
    null_count_1 = conn.execute("SELECT COUNT(*) as c FROM models WHERE base_arch IS NULL").fetchone()["c"]
    assert null_count_1 == 1
    # Second batch=1 call should process the remaining one
    n2 = headers.enrich_bases(conn, batch=1)
    assert n2 == 1
    null_count_2 = conn.execute("SELECT COUNT(*) as c FROM models WHERE base_arch IS NULL").fetchone()["c"]
    assert null_count_2 == 0
