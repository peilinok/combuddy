import time
from combuddy import db, queries, norm

def _seed(conn):
    conn.execute("INSERT INTO roots(id,kind,path,source) VALUES(1,'model','/r','manual')")
    conn.execute("INSERT INTO roots(id,kind,path,source) VALUES(2,'workflow','/w','manual')")
    def m(i, dt, fn, base, size):
        conn.execute("""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
            size,mtime,base_arch,match_key,name_key,first_seen,last_scanned)
            VALUES(?,1,?,?,?,?,?,'safetensors',?,1,?,?,?,?,?)""",
            (i, f"/r/{fn}", f"{dt}/{fn}", dt, fn, fn, size, base, fn, fn, 1, 1))
    m(1, "checkpoints", "a.safetensors", "sdxl", 100)
    m(2, "text_encoders", "t5.safetensors", None, 50)     # role label, unreferenced
    conn.execute("INSERT INTO workflows(id,root_id,path,filename,mtime,ref_count,last_scanned) VALUES(1,2,'/w/wf.json','wf.json',1,2,1)")
    conn.execute("INSERT INTO edges(workflow_id,ref_string,ref_key,node_type,model_id,match_kind) VALUES(1,'a.safetensors','a.safetensors','CheckpointLoaderSimple',1,'path')")
    conn.execute("INSERT INTO edges(workflow_id,ref_string,ref_key,node_type,model_id,match_kind) VALUES(1,'gone.safetensors','gone.safetensors','LoraLoader',NULL,NULL)")
    conn.commit()

def test_list_models_labels_and_refcount(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn); _seed(conn)
    by = {m["filename"]: m for m in queries.list_models(conn)}
    assert by["a.safetensors"]["label"] == "sdxl" and by["a.safetensors"]["ref_count"] == 1
    assert by["t5.safetensors"]["label"] == "文本编码器" and by["t5.safetensors"]["ref_count"] == 0

def test_list_models_flag_unreferenced(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn); _seed(conn)
    names = {m["filename"] for m in queries.list_models(conn, flag="unreferenced")}
    assert names == {"t5.safetensors"}

def test_model_detail_reverse_deps(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn); _seed(conn)
    d = queries.get_model_detail(conn, 1)
    assert d["filename"] == "a.safetensors"
    assert [w["filename"] for w in d["workflows"]] == ["wf.json"]

def test_workflow_resolution_status(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn); _seed(conn)
    r = queries.get_workflow_resolution(conn, 1)
    st = {e["ref_string"]: e["status"] for e in r["edges"]}
    assert st["a.safetensors"] == "path" and st["gone.safetensors"] == "missing"

def test_workflow_resolution_ambiguous(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn); _seed(conn)
    conn.execute("""INSERT INTO edges(workflow_id,ref_string,ref_key,node_type,model_id,match_kind)
        VALUES(1,'dup.safetensors','dup.safetensors','CheckpointLoaderSimple',NULL,'ambiguous')""")
    conn.commit()
    r = queries.get_workflow_resolution(conn, 1)
    st = {e["ref_string"]: e["status"] for e in r["edges"]}
    assert st["dup.safetensors"] == "ambiguous"
