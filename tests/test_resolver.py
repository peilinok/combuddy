import time
from combuddy import db, resolver, norm

def _model(conn, dir_type, rel_in_type, filename):
    conn.execute("""INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,
        ext,size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(1,?,?,?,?,?,'safetensors',1,1,?,?,?,?)""",
        (f"/r/{dir_type}/{rel_in_type}", f"{dir_type}/{rel_in_type}", dir_type, rel_in_type,
         filename, norm.match_key(rel_in_type), filename.casefold(), time.time(), time.time()))

def _setup(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    conn.execute("INSERT INTO roots(id,kind,path,source) VALUES(1,'model','/r','manual')")
    conn.execute("INSERT INTO roots(id,kind,path,source) VALUES(2,'workflow','/w','manual')")
    conn.execute("INSERT INTO workflows(id,root_id,path,filename,mtime,last_scanned) VALUES(1,2,'/w/a.json','a.json',1,1)")
    return conn

def test_resolve_path_match_with_subdir_and_case(tmp_path):
    conn = _setup(tmp_path)
    _model(conn, "checkpoints", "SD1.5/foo.safetensors", "foo.safetensors"); conn.commit()
    resolver.resolve_workflow(conn, 1, [
        {"ref_string": "sd1.5/foo.safetensors", "node_type": "CheckpointLoaderSimple"}])  # 大小写不同
    e = conn.execute("SELECT * FROM edges").fetchone()
    assert e["match_kind"] == "path" and e["model_id"] == 1

def test_resolve_missing_is_null(tmp_path):
    conn = _setup(tmp_path)
    resolver.resolve_workflow(conn, 1, [
        {"ref_string": "nope.safetensors", "node_type": "LoraLoader"}])
    e = conn.execute("SELECT * FROM edges").fetchone()
    assert e["model_id"] is None and e["match_kind"] is None and e["ref_dir_type"] == "loras"

def test_resolve_ambiguous_not_bound(tmp_path):
    conn = _setup(tmp_path)
    _model(conn, "checkpoints", "A/dup.safetensors", "dup.safetensors")
    _model(conn, "checkpoints", "B/dup.safetensors", "dup.safetensors"); conn.commit()
    resolver.resolve_workflow(conn, 1, [
        {"ref_string": "dup.safetensors", "node_type": "CheckpointLoaderSimple"}])  # 仅 basename,两个候选
    e = conn.execute("SELECT * FROM edges").fetchone()
    assert e["match_kind"] == "ambiguous" and e["model_id"] is None

def test_reparse_deletes_old_edges(tmp_path):
    conn = _setup(tmp_path)
    resolver.resolve_workflow(conn, 1, [{"ref_string": "a.safetensors", "node_type": None}])
    resolver.resolve_workflow(conn, 1, [{"ref_string": "b.safetensors", "node_type": None}])
    rows = conn.execute("SELECT ref_string FROM edges").fetchall()
    assert len(rows) == 1 and rows[0]["ref_string"] == "b.safetensors"
