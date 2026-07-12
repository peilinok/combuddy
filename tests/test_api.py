from fastapi.testclient import TestClient
from combuddy import api, scan_service

def test_stats_and_scan_flow(tmp_path):
    app = api.create_app(str(tmp_path / "c.sqlite"))
    c = TestClient(app)
    # 配置 roots(空目录也行,重点测通路)
    (tmp_path / "m").mkdir(); (tmp_path / "w").mkdir()
    r = c.post("/api/roots", json={"roots": [
        {"kind": "model", "path": str(tmp_path/"m"), "source": "manual"},
        {"kind": "workflow", "path": str(tmp_path/"w"), "source": "manual"}]})
    assert r.status_code == 200
    assert len(c.get("/api/roots").json()["roots"]) == 2
    s = c.get("/api/stats").json()
    assert s["model_count"] == 0 and "scanning" in s
    assert c.post("/api/scan").json()["started"] is True

def test_scan_conflict_when_running(tmp_path):
    app = api.create_app(str(tmp_path / "c.sqlite")); c = TestClient(app)
    scan_service.STATUS["running"] = True
    try:
        assert c.post("/api/scan").json()["started"] is False
    finally:
        scan_service.STATUS["running"] = False

def test_stats_skips_duplicate_waste_while_scanning(tmp_path):
    app = api.create_app(str(tmp_path / "c.sqlite")); c = TestClient(app)
    assert c.get("/api/stats").json()["duplicate_waste"] == 0
    scan_service.STATUS["running"] = True
    try:
        assert c.get("/api/stats").json()["duplicate_waste"] is None
    finally:
        scan_service.STATUS["running"] = False

def test_stats_uses_consistent_scan_status_snapshot(tmp_path, monkeypatch):
    original_get_stats = api.stats.get_stats
    def finish_scan(conn, skip_duplicates=False):
        result = original_get_stats(conn, skip_duplicates=skip_duplicates)
        if skip_duplicates:
            scan_service.STATUS["running"] = False
        return result
    monkeypatch.setattr(api.stats, "get_stats", finish_scan)
    app = api.create_app(str(tmp_path / "c.sqlite")); c = TestClient(app)
    scan_service.STATUS["running"] = True
    try:
        s = c.get("/api/stats").json()
        assert s["duplicate_waste"] is None
        assert s["scanning"] is True
        assert s["scan"]["running"] is True
    finally:
        scan_service.STATUS["running"] = False

def test_roots_validation_and_delete(tmp_path):
    app = api.create_app(str(tmp_path / "c.sqlite")); c = TestClient(app)
    (tmp_path / "m").mkdir()
    r = c.post("/api/roots", json={"roots": [
        {"kind": "model", "path": str(tmp_path / "nope")},
        {"kind": "model", "path": str(tmp_path / "m")}]}).json()
    assert [x["ok"] for x in r["results"]] == [False, True]
    assert r["results"][0]["reason"] == "not_a_directory"
    r2 = c.post("/api/roots", json={"roots": [{"kind": "model", "path": str(tmp_path / "m")}]}).json()
    assert r2["results"][0]["reason"] == "duplicate"
    roots = c.get("/api/roots").json()["roots"]
    assert len(roots) == 1
    rid = roots[0]["id"]
    assert c.delete(f"/api/roots/{rid}").json()["ok"] is True
    assert c.get("/api/roots").json()["roots"] == []
    assert c.delete(f"/api/roots/{rid}").status_code == 404

def test_remove_root_unbinds_edges(tmp_path):
    from combuddy import db as dbm, config
    conn = dbm.connect(str(tmp_path / "c.sqlite")); dbm.init_schema(conn)
    (tmp_path / "m").mkdir(); (tmp_path / "w").mkdir()
    config.set_roots(conn, [{"kind": "model", "path": str(tmp_path / "m")},
                            {"kind": "workflow", "path": str(tmp_path / "w")}])
    rows = {r["kind"]: r["id"] for r in config.get_roots(conn)}
    conn.execute("""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
        size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(1,?,'/m/a','checkpoints/a','checkpoints','a','a.safetensors','safetensors',9,1,'a','a',1,1)""",
        (rows["model"],))
    conn.execute("""INSERT INTO workflows(id,root_id,path,filename,mtime,ref_count,last_scanned)
        VALUES(1,?,'/w/wf.json','wf.json',1,1,1)""", (rows["workflow"],))
    conn.execute("""INSERT INTO edges(workflow_id,ref_string,ref_key,node_type,model_id,match_kind)
        VALUES(1,'a.safetensors','a.safetensors','CheckpointLoaderSimple',1,'path')""")
    conn.commit()
    assert config.remove_root(conn, rows["model"]) is True
    e = conn.execute("SELECT model_id, match_kind FROM edges").fetchone()
    assert e["model_id"] is None and e["match_kind"] is None
    assert conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"] == 0
