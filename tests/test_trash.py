import os, time
from combuddy import db, trash

def _model(conn, path, root_path):
    conn.execute("INSERT OR IGNORE INTO roots(id,kind,path,source) VALUES(1,'model',?,'manual')", (root_path,))
    cur = conn.execute("""INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
        size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(1,?,?,?,?,?,'safetensors',10,1,?,?,?,?) RETURNING id""",
        (path, os.path.relpath(path, root_path), "loras", os.path.basename(path),
         os.path.basename(path), "k", "k", time.time(), time.time()))
    return cur.fetchone()["id"]

def test_move_and_restore(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"; (root/"loras").mkdir(parents=True)
    f = root/"loras"/"x.safetensors"; f.write_bytes(b"x"*10)
    mid = _model(conn, str(f), str(root)); conn.commit()
    res = trash.move_to_trash(conn, [mid])
    assert mid in res["moved"] and not f.exists()          # file moved out
    assert conn.execute("SELECT COUNT(*) c FROM models WHERE id=?", (mid,)).fetchone()["c"] == 0
    tid = trash.list_trash(conn)[0]["id"]
    trash.restore(conn, [tid])
    assert f.exists()                                       # restored

def test_guard_refuses_referenced(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"; (root/"loras").mkdir(parents=True)
    f = root/"loras"/"used.safetensors"; f.write_bytes(b"x"*10)
    mid = _model(conn, str(f), str(root))
    conn.execute("INSERT INTO workflows(id,root_id,path,filename,mtime,last_scanned) VALUES(1,1,'/w','w',1,1)")
    conn.execute("INSERT INTO edges(workflow_id,ref_string,ref_key,model_id) VALUES(1,'used.safetensors','used.safetensors',?)", (mid,))
    conn.commit()
    res = trash.move_to_trash(conn, [mid])
    assert mid in res["skipped"] and f.exists()             # referenced → not moved

def test_move_same_basename_no_overwrite(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"
    (root/"checkpoints").mkdir(parents=True); (root/"loras").mkdir(parents=True)
    f1 = root/"checkpoints"/"x.safetensors"; f1.write_bytes(b"A"*10)
    f2 = root/"loras"/"x.safetensors"; f2.write_bytes(b"B"*20)
    mid1 = _model(conn, str(f1), str(root))
    mid2 = _model(conn, str(f2), str(root))
    conn.commit()
    res = trash.move_to_trash(conn, [mid1, mid2])
    assert mid1 in res["moved"] and mid2 in res["moved"]
    assert not f1.exists() and not f2.exists()
    tids = {r["model_path"]: r["id"] for r in trash.list_trash(conn)}
    trash.restore(conn, [tids[str(f1)], tids[str(f2)]])
    assert f1.exists() and f1.read_bytes() == b"A"*10        # own bytes, no overwrite
    assert f2.exists() and f2.read_bytes() == b"B"*20

def test_move_dedup_ids(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"; (root/"loras").mkdir(parents=True)
    f = root/"loras"/"x.safetensors"; f.write_bytes(b"x"*10)
    mid = _model(conn, str(f), str(root)); conn.commit()
    res = trash.move_to_trash(conn, [mid, mid])
    assert res["moved"].count(mid) == 1
    assert mid not in res["skipped"]

def test_restore_missing_trash_file_no_crash(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    root = tmp_path / "models"; (root/"loras").mkdir(parents=True)
    f = root/"loras"/"x.safetensors"; f.write_bytes(b"x"*10)
    mid = _model(conn, str(f), str(root)); conn.commit()
    trash.move_to_trash(conn, [mid])
    row = trash.list_trash(conn)[0]
    os.remove(row["trash_path"])                             # simulate lost trash file
    res = trash.restore(conn, [row["id"]])
    assert row["id"] in res["error"]
    assert row["id"] not in res["restored"]
