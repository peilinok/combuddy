import time
from combuddy import db, stats

def _seed(conn):
    conn.execute("INSERT INTO roots(id,kind,path,source) VALUES(1,'model','/r','manual')")
    conn.execute("INSERT INTO roots(id,kind,path,source) VALUES(2,'workflow','/w','manual')")
    for i, (dt, base, size) in enumerate([("checkpoints","sdxl",100),
                                          ("checkpoints",None,50),("loras","sd15",30)]):
        conn.execute("""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,
            filename,ext,size,mtime,base_arch,match_key,name_key,first_seen,last_scanned)
            VALUES(?,1,?,?,?,?,?,'safetensors',?,1,?,?,?,?,?)""",
            (i+1, f"/r/{i}", f"{dt}/f{i}", dt, f"f{i}", f"f{i}", size, base, f"f{i}", f"f{i}", 1, 1))
    conn.execute("INSERT INTO workflows(id,root_id,path,filename,mtime,last_scanned) VALUES(1,2,'/w/a','a',1,1)")
    conn.execute("INSERT INTO edges(workflow_id,ref_string,ref_key,model_id) VALUES(1,'f0','f0',1)")
    conn.commit()

def test_stats_counts_and_coverage(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn); _seed(conn)
    s = stats.get_stats(conn)
    assert s["model_count"] == 3
    assert s["total_size"] == 180
    assert s["workflow_count"] == 1
    assert s["base_coverage"] == {"done": 2, "total": 3}      # 一个 base 为 NULL
    assert s["unreferenced_count"] == 2                        # model 2,3 未被引用
    by = {t["dir_type"]: t for t in s["by_type"]}
    assert by["checkpoints"]["count"] == 2 and by["checkpoints"]["size"] == 150

def test_unreferenced_list(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn); _seed(conn)
    ids = {m["id"] for m in stats.get_unreferenced(conn)}
    assert ids == {2, 3}

def test_hash_coverage(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    conn.execute("INSERT INTO roots(id,kind,path,enabled) VALUES(1,'model','/r',1)")
    for i, sha in ((1, "'abc'"), (2, "NULL")):
        conn.execute(f"""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
            size,mtime,sha256,match_key,name_key,first_seen,last_scanned)
            VALUES({i},1,'/r/{i}','{i}','checkpoints','{i}','{i}.safetensors','safetensors',
                   9,1,{sha},'{i}','{i}',1,1)""")
    conn.commit()
    assert stats.get_stats(conn)["hash_coverage"] == {"hashed": 1, "total": 2}

def test_civitai_coverage(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    conn.execute("INSERT INTO roots(id,kind,path,enabled) VALUES(1,'model','/r',1)")
    for i in (1, 2):
        conn.execute(f"""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
            size,mtime,match_key,name_key,first_seen,last_scanned)
            VALUES({i},1,'/r/{i}','{i}','loras','{i}','{i}.safetensors','safetensors',9,1,'{i}','{i}',1,1)""")
    conn.execute("INSERT INTO civitai(model_id,sha256,found,checked_at) VALUES(1,'x',1,1)")
    conn.execute("INSERT INTO civitai(model_id,sha256,found,checked_at) VALUES(2,'y',0,1)")
    conn.commit()
    assert stats.get_stats(conn)["civitai_coverage"] == {"identified": 1, "total": 2}
