from fastapi.testclient import TestClient
from combuddy import api, db, queries, scan_service

def _app(tmp_path):
    dbp = str(tmp_path / "c.sqlite")
    c = db.connect(dbp); db.init_schema(c)
    c.execute("INSERT INTO roots(id,kind,path,source) VALUES(1,'model','/r','manual')")
    c.execute("""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,size,mtime,
        base_arch,match_key,name_key,first_seen,last_scanned)
        VALUES(1,1,'/r/a','checkpoints/a','checkpoints','a','a.safetensors','safetensors',9,1,'sdxl','a','a',1,1)""")
    c.commit(); c.close()
    return TestClient(api.create_app(dbp))

def _bare_app(tmp_path):
    dbp = str(tmp_path / "c.sqlite")
    c = db.connect(dbp); db.init_schema(c); c.close()
    return TestClient(api.create_app(dbp))

def test_models_and_detail(tmp_path):
    cl = _app(tmp_path)
    r = cl.get("/api/models"); assert r.status_code == 200
    assert r.json()["models"][0]["label"] == "sdxl"
    d = cl.get("/api/models/1").json()
    assert d["filename"] == "a.safetensors" and "workflows" in d
    assert cl.get("/api/models/999").status_code == 404

def test_workflows_and_cleanup_trash_empty(tmp_path):
    cl = _app(tmp_path)
    assert cl.get("/api/workflows").json()["workflows"] == []
    assert cl.get("/api/cleanup/trash").json()["trash"] == []
    # model 1 is unreferenced → trashable path returns shape (file missing, so skipped)
    r = cl.post("/api/cleanup/trash", json={"model_ids": [1]})
    assert r.status_code == 200 and "moved" in r.json() and "skipped" in r.json()

def test_settings_default_and_update(tmp_path):
    cl = _bare_app(tmp_path)
    assert cl.get("/api/settings").json() == {
        "auto_hash": True, "hash_workers": 1, "hash_max_mbps": 0,
        "online_enrich": True, "nsfw_blur_threshold": 1}
    r = cl.post("/api/settings", json={"auto_hash": False, "online_enrich": False}).json()
    assert r["auto_hash"] is False and r["online_enrich"] is False
    assert cl.get("/api/settings").json()["online_enrich"] is False

def test_scan_cancel_sets_flag(tmp_path):
    cl = _bare_app(tmp_path)
    assert cl.post("/api/scan/cancel").json() == {"ok": True}
    assert scan_service.STATUS["cancel"] is True

def test_preview_endpoint(tmp_path):
    dbp = str(tmp_path / "c.sqlite")
    c = db.connect(dbp); db.init_schema(c); c.close()
    pv = tmp_path / "previews"; pv.mkdir()
    (pv / ("a" * 64 + ".jpg")).write_bytes(b"\xff\xd8\xff\xe0IMGDATA")       # JPEG 魔数
    (pv / ("a" * 64 + "_hd.jpg")).write_bytes(b"\x89PNG\r\n\x1a\nHDDATA")    # PNG 魔数
    cl = TestClient(api.create_app(dbp))
    r = cl.get(f"/api/preview/{'a'*64}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"   # 嗅探为 jpeg
    hd = cl.get(f"/api/preview/{'a'*64}?hd=1")
    assert hd.status_code == 200 and hd.content.endswith(b"HDDATA")             # HD 走 _hd.jpg
    assert hd.headers["content-type"] == "image/png"                           # 嗅探为 png
    assert cl.get(f"/api/preview/{'b'*64}").status_code == 404                  # 不存在
    assert cl.get("/api/preview/..%2f..%2fetc").status_code == 404              # 非 hex → 拒绝
