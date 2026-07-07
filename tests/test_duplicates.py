import os, time, pytest
from combuddy import db as dbm, queries

def _conn(tmp_path):
    c = dbm.connect(str(tmp_path / "t.db")); dbm.init_schema(c)
    c.execute("INSERT INTO roots(id,kind,path,label) VALUES(1,'model',?,?)",
              (str(tmp_path), "shared"))
    return c

def _add(c, mid, real_path, sha, rel, dir_type="checkpoints", first_seen=0.0):
    fn = os.path.basename(real_path)
    c.execute("""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,
                 ext,size,mtime,sha256,match_key,name_key,first_seen,last_scanned)
                 VALUES(?,1,?,?,?,?,?,'safetensors',?,?,?,?,?,?,?)""",
              (mid, real_path, rel, dir_type, rel, fn, os.path.getsize(real_path),
               0.0, sha, rel.casefold(), fn.casefold(), first_seen, 0.0))
    c.commit()

def _ref(c, mid, wf_id=1):
    c.execute("INSERT OR IGNORE INTO workflows(id,root_id,path,filename,mtime,last_scanned) "
              "VALUES(?,1,?,?,0,0)", (wf_id, f"/wf{wf_id}", f"wf{wf_id}.json"))
    c.execute("INSERT INTO edges(workflow_id,ref_string,ref_key,node_type,model_id,match_kind) "
              "VALUES(?,?,?,?,?, 'path')", (wf_id, "x", "x", "Loader", mid))
    c.commit()

def _file(tmp_path, name, content=b"AAAA"):
    p = tmp_path / name; p.write_bytes(content); return str(p)

def test_two_plain_copies_group_and_reclaimable(tmp_path):
    c = _conn(tmp_path)
    a = _file(tmp_path, "a.safetensors"); b = _file(tmp_path, "sub_b.safetensors")
    _add(c, 1, a, "SHA", "a.safetensors", first_seen=1.0)          # 路径层级最浅
    _add(c, 2, b, "SHA", "sub/b.safetensors", first_seen=2.0)
    groups = queries.list_duplicate_groups(c)
    assert len(groups) == 1
    g = groups[0]
    assert g["count"] == 2 and g["sha256"] == "SHA"
    assert g["suggested_keep_id"] == 1          # rel_path 段数少(a 无 '/')
    assert g["reclaimable"] == os.path.getsize(b)   # 删另一份
    assert {m["id"] for m in g["members"] if m["deletable"]} == {2}

def test_referenced_copy_is_kept_and_not_deletable(tmp_path):
    c = _conn(tmp_path)
    a = _file(tmp_path, "a.safetensors"); b = _file(tmp_path, "b.safetensors")
    _add(c, 1, a, "S", "a.safetensors", first_seen=1.0)
    _add(c, 2, b, "S", "b.safetensors", first_seen=2.0); _ref(c, 2)   # 2 被引用
    g = queries.list_duplicate_groups(c)[0]
    assert g["suggested_keep_id"] == 2
    assert all(not m["deletable"] for m in g["members"] if m["id"] == 2)
    assert [m["id"] for m in g["members"] if m["deletable"]] == [1]

def test_hardlink_not_deletable_and_zero_reclaimable(tmp_path):
    c = _conn(tmp_path)
    a = _file(tmp_path, "a.safetensors")
    b = str(tmp_path / "b.safetensors")
    try: os.link(a, b)
    except (OSError, NotImplementedError): pytest.skip("no hardlink support")
    _add(c, 1, a, "S", "a.safetensors", first_seen=1.0)
    _add(c, 2, b, "S", "b.safetensors", first_seen=2.0)
    g = queries.list_duplicate_groups(c)[0]
    assert g["reclaimable"] == 0
    assert all(not m["deletable"] for m in g["members"])   # 同 inode

def test_single_copy_not_in_result(tmp_path):
    c = _conn(tmp_path)
    a = _file(tmp_path, "a.safetensors"); _add(c, 1, a, "UNIQUE", "a.safetensors")
    assert queries.list_duplicate_groups(c) == []

def test_stat_fail_on_keep_skips_whole_group(tmp_path):
    c = _conn(tmp_path)
    a = _file(tmp_path, "a.safetensors"); b = _file(tmp_path, "sub_b.safetensors")
    _add(c, 1, a, "S", "a.safetensors", first_seen=1.0)      # keep 候选(层级最浅)
    _add(c, 2, b, "S", "sub/b.safetensors", first_seen=2.0)
    os.remove(a)                                             # keep 候选 stat 失败
    assert queries.list_duplicate_groups(c) == []
