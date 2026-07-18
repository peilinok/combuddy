import io, urllib.error, urllib.request
from combuddy import civitai

class _Resp(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(data); self.headers = headers or {}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def getheader(self, k, default=None): return self.headers.get(k, default)

class _FakeOpener:
    """download_file 走 _build_opener().open(req),不是 module 级 urlopen——monkeypatch urlopen
    拦不到 opener.open(BE-SEC 本地实验坐实会真联网)[B1]。测试必须替换 _build_opener 本身。"""
    def __init__(self, resp): self.resp = resp; self.req = None
    def open(self, req, timeout=None):
        self.req = req
        if isinstance(self.resp, Exception): raise self.resp
        return self.resp

def test_download_ok_streams_and_hashes_lowercase(monkeypatch, tmp_path):
    body = b"MODELBYTES" * 1000
    import hashlib; want = hashlib.sha256(body).hexdigest()
    opener = _FakeOpener(_Resp(body, {"Content-Length": str(len(body))}))
    monkeypatch.setattr(civitai, "_build_opener", lambda: opener)     # 替换 opener,不是 urlopen [B1]
    prog = []
    dest = tmp_path / "m.safetensors.part"
    kind, sha = civitai.download_file("https://civitai.com/api/download/models/9", str(dest),
                                      "sk-token", progress=lambda d, t: prog.append((d, t)))
    assert kind == "ok" and sha == want and sha == sha.lower()
    assert opener.req.get_header("Authorization") == "Bearer sk-token"
    assert "sk-token" not in opener.req.full_url                      # 不进 URL [L10]
    assert dest.read_bytes() == body and prog[-1][0] == len(body)

def test_download_anonymous_no_auth_header(monkeypatch, tmp_path):    # 空 token → 匿名,无 Authorization [M1]
    opener = _FakeOpener(_Resp(b"X", {"Content-Length": "1"}))
    monkeypatch.setattr(civitai, "_build_opener", lambda: opener)
    civitai.download_file("https://civitai.com/x", str(tmp_path / "p.part"), "")
    assert opener.req.get_header("Authorization") is None

def test_redirect_handler_strips_authorization_cross_host():
    # 直接单测 redirect_request 方法(比模拟整个 opener/error 链路可靠)——跨域剥、同域留 [B1 安全关键]
    h = civitai._NoAuthCrossHostRedirect()
    req = urllib.request.Request("https://civitai.com/api/download/models/9")
    req.add_header("Authorization", "Bearer sk-secret")
    cross = h.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "https://b2.civitai.com/blob/x")
    assert cross is not None and not cross.has_header("Authorization")   # 跨域 → 剥 [B1]
    req2 = urllib.request.Request("https://civitai.com/a")
    req2.add_header("Authorization", "Bearer sk-secret")
    same = h.redirect_request(req2, io.BytesIO(b""), 302, "Found", {}, "https://civitai.com/b")
    assert same.has_header("Authorization")                             # 同域 → 留

def test_download_auth_forbidden_error(monkeypatch, tmp_path):
    for code, want in [(401, "auth"), (403, "forbidden"), (500, "error")]:
        err = urllib.error.HTTPError("https://civitai.com/x", code, "x", {}, None)
        monkeypatch.setattr(civitai, "_build_opener", lambda e=err: _FakeOpener(e))
        assert civitai.download_file("https://civitai.com/x", str(tmp_path / "p.part"), "t") == (want, None)

def test_download_urlerror_is_error(monkeypatch, tmp_path):           # URLError(连接失败)→ error [M1]
    monkeypatch.setattr(civitai, "_build_opener", lambda: _FakeOpener(urllib.error.URLError("boom")))
    assert civitai.download_file("https://civitai.com/x", str(tmp_path / "p.part"), "t") == ("error", None)

def test_download_cancelled(monkeypatch, tmp_path):
    monkeypatch.setattr(civitai, "_build_opener",
                        lambda: _FakeOpener(_Resp(b"X" * 10000, {"Content-Length": "10000"})))
    kind, _ = civitai.download_file("https://civitai.com/x", str(tmp_path / "p.part"), "t",
                                    should_cancel=lambda: True)
    assert kind == "cancelled"

def test_download_max_bytes_guard(monkeypatch, tmp_path):
    monkeypatch.setattr(civitai, "_build_opener",
                        lambda: _FakeOpener(_Resp(b"X" * 5000, {"Content-Length": "100"})))
    assert civitai.download_file("https://civitai.com/x", str(tmp_path / "p.part"), "t",
                                 max_bytes=1000)[0] == "error"

from combuddy import download_service, config, db, scanner, scan_service
import struct, json as _json

def _mroot(conn, tmp_path):
    root = tmp_path / "models"; (root / "loras").mkdir(parents=True)
    rid = config.set_roots(conn, [{"kind": "model", "path": str(root)}]);
    return conn.execute("SELECT id FROM roots WHERE kind='model'").fetchone()["id"], root

def _spec(root_id, **kw):
    base = {"url": "https://civitai.com/api/download/models/9", "sha256": "a" * 64,
            "size_kb": 1.0, "dir_type": "loras", "ref_string": "foo.safetensors", "root_id": root_id}
    base.update(kw); return base

def test_start_download_rejects_path_traversal(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, _ = _mroot(conn, tmp_path)
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: ("ok", "a" * 64))
    r = download_service.start_download(conn, _spec(rid, ref_string="../../etc/passwd"))
    assert r["error"] == "path_unsafe" and download_service.DOWNLOAD_STATUS["error"] == "path_unsafe"

def test_start_download_rejects_prefix_collision(tmp_path, monkeypatch):
    # root=/x/models,ref 让 dest 落到 /x/models-evil → startswith 会漏,commonpath 挡住 [H4]
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    (tmp_path / "models").mkdir(); (tmp_path / "models" / "loras").mkdir()
    (tmp_path / "models-evil").mkdir()
    config.set_roots(conn, [{"kind": "model", "path": str(tmp_path / "models")}])
    rid = conn.execute("SELECT id FROM roots").fetchone()["id"]
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: ("ok", "a" * 64))
    r = download_service.start_download(conn, _spec(rid, dir_type="loras", ref_string="../../models-evil/x.safetensors"))
    assert r["error"] == "path_unsafe"

def test_start_download_rejects_bad_url_and_dir_type(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, _ = _mroot(conn, tmp_path)
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: ("ok", "a" * 64))
    assert download_service.start_download(conn, _spec(rid, url="https://evil.tld/x"))["error"] == "bad_url"
    assert download_service.start_download(conn, _spec(rid, dir_type="../evil"))["error"] == "path_unsafe"

def test_start_download_root_not_found_and_exists_and_disk(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, root = _mroot(conn, tmp_path)
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: ("ok", "a" * 64))
    assert download_service.start_download(conn, _spec(9999))["error"] == "root_not_found"
    (root / "loras" / "foo.safetensors").write_bytes(b"x")           # 已存在
    assert download_service.start_download(conn, _spec(rid))["error"] == "exists"
    (root / "loras" / "foo.safetensors").unlink()
    monkeypatch.setattr(download_service.shutil, "disk_usage",
                        lambda p: type("U", (), {"free": 0})())        # free=0
    assert download_service.start_download(conn, _spec(rid, size_kb=1000.0))["error"] == "disk_full"

def test_start_download_rejects_bad_sha(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, _ = _mroot(conn, tmp_path)
    assert download_service.start_download(conn, _spec(rid, sha256="xyz"))["error"] == "bad_request"

def test_start_download_rejects_when_online_enrich_disabled(tmp_path, monkeypatch):
    # 总闸:关掉 online_enrich 后下载必须整条链路零网络,同 /api/locate 的门控 [review Important I-1]
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, _ = _mroot(conn, tmp_path)
    config.set_settings(conn, {"online_enrich": False})
    calls = []
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: calls.append(1))
    r = download_service.start_download(conn, _spec(rid))
    assert r == {"error": "online_disabled"} and calls == []           # download_file 从未被调用
    assert download_service.DOWNLOAD_STATUS["error"] == "online_disabled"

def test_start_download_resets_cancel_at_start(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    config.set_settings(conn, {"auto_hash": False, "online_enrich": False})   # 关断,避免真联网
    rid, _ = _mroot(conn, tmp_path)
    download_service.DOWNLOAD_STATUS["cancel"] = True                 # 上次遗留
    def _dl(url, dest_part, token, **k): open(dest_part, "wb").write(b"x"); return ("ok", "a" * 64)
    monkeypatch.setattr(download_service.civitai, "download_file", _dl)
    download_service.start_download(conn, _spec(rid))
    assert download_service.DOWNLOAD_STATUS["cancel"] is False        # 起点复位 [H9]

def test_start_download_rejects_malformed_types(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, _ = _mroot(conn, tmp_path)
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: ("ok", "a" * 64))
    for bad in [{"ref_string": None}, {"dir_type": ["loras"]}, {"size_kb": "big"}]:
        r = download_service.start_download(conn, _spec(rid, **bad))
        assert r["error"] == "bad_request" and download_service.DOWNLOAD_STATUS["error"] == "bad_request"

def _st_bytes(header):   # 造 safetensors 字节(sha 可算)
    blob = _json.dumps(header).encode(); return struct.pack("<Q", len(blob)) + blob

def test_download_success_imports_and_flips_edge(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    config.set_settings(conn, {"auto_hash": False, "online_enrich": True})   # 门控要求 True [I-1];真联网靠 monkeypatch download_file 挡住
    root = tmp_path / "models"; (root / "loras").mkdir(parents=True)
    wf = tmp_path / "wf"; wf.mkdir()
    (wf / "w.json").write_text(_json.dumps({"nodes": [
        {"type": "LoraLoader", "widgets_values": ["foo.safetensors", 1.0, 1.0]}]}))
    config.set_roots(conn, [{"kind": "model", "path": str(root)},
                            {"kind": "workflow", "path": str(wf)}])
    rid = conn.execute("SELECT id FROM roots WHERE kind='model'").fetchone()["id"]
    scan_service.run_scan(conn)
    body = _st_bytes({"w": {"dtype": "F16", "shape": [1], "data_offsets": [0, 2]}})
    import hashlib; real_sha = hashlib.sha256(body).hexdigest()
    def fake_dl(url, dest_part, token, progress=None, should_cancel=None, max_bytes=None):
        open(dest_part, "wb").write(body); return ("ok", real_sha)     # 桩写字节 [test_enrich.py:58 先例]
    monkeypatch.setattr(download_service.civitai, "download_file", fake_dl)
    r = download_service.start_download(conn, _spec(rid, sha256=real_sha))
    assert r == {"ok": True}
    assert (root / "loras" / "foo.safetensors").read_bytes() == body   # rename 到位
    assert not (root / "loras" / "foo.safetensors.part").exists()      # .part 已消
    from combuddy import queries
    assert queries.get_workflow_resolution(conn, 1)["edges"][0]["status"] == "path"   # 入库+绑定 [闭环]
    assert conn.execute("SELECT sha256 FROM models WHERE filename='foo.safetensors'").fetchone()["sha256"] == real_sha   # sha 写回 [M2]

def test_download_sha_mismatch_deletes_part(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, root = _mroot(conn, tmp_path)
    def fake_dl(url, dest_part, token, **k): open(dest_part, "wb").write(b"WRONG"); return ("ok", "b" * 64)
    monkeypatch.setattr(download_service.civitai, "download_file", fake_dl)
    r = download_service.start_download(conn, _spec(rid, sha256="a" * 64))
    assert r["error"] == "sha_mismatch"
    assert not (root / "loras" / "foo.safetensors").exists()
    assert not (root / "loras" / "foo.safetensors.part").exists()      # 删 .part、不入库 [成功标准4]

def test_download_failure_paths_delete_part(tmp_path, monkeypatch):
    for res, want in [(("auth", None), "auth"), (("forbidden", None), "forbidden"),
                      (("error", None), "network"), (("cancelled", None), "cancelled")]:
        conn = db.connect(str(tmp_path / f"c{want}.sqlite")); db.init_schema(conn)
        rid, root = _mroot(conn, tmp_path / want)
        def fake_dl(url, dest_part, token, r=res, **k):
            open(dest_part, "wb").write(b"partial"); return r
        monkeypatch.setattr(download_service.civitai, "download_file", fake_dl)
        out = download_service.start_download(conn, _spec(rid))
        assert out["error"] == want                                    # 四失败路径分档 [M2]
        assert not (root / "loras" / "foo.safetensors.part").exists()  # 都删 .part

def test_download_unexpected_exception_cleans_part_and_reports_network(tmp_path, monkeypatch):
    # os.replace 等未预期异常不得向外传播、必须清 .part、写 DOWNLOAD_STATUS.error [review Important I-2]
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, root = _mroot(conn, tmp_path)
    def fake_dl(url, dest_part, token, **k):
        open(dest_part, "wb").write(b"x"); return ("ok", "a" * 64)
    monkeypatch.setattr(download_service.civitai, "download_file", fake_dl)
    monkeypatch.setattr(download_service.os, "replace",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk gone")))
    r = download_service.start_download(conn, _spec(rid))
    assert r == {"error": "network"}                                   # 不传播,机器码 [I-2]
    assert download_service.DOWNLOAD_STATUS["error"] == "network"
    assert not (root / "loras" / "foo.safetensors.part").exists()      # .part 已清
    assert not (root / "loras" / "foo.safetensors").exists()           # 未入库(rename 从未成功)

def test_download_import_pending_when_scan_stays_busy(tmp_path, monkeypatch):
    """文件已下但 scan 持续忙、入库耗尽则返 import_pending、文件保留"""
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    config.set_settings(conn, {"auto_hash": False, "online_enrich": True})   # 门控要求 True [I-1]
    rid, root = _mroot(conn, tmp_path)
    def fake_dl(url, dest_part, token, **k):
        open(dest_part, "wb").write(b"x"); return ("ok", "a" * 64)
    monkeypatch.setattr(download_service.civitai, "download_file", fake_dl)
    monkeypatch.setattr(download_service.scan_service, "run_scan",
                        lambda conn: {"skipped": "busy"})              # run_scan 恒返回 skipped
    download_service.scan_service.STATUS["running"] = False            # 轮询快速耗尽
    r = download_service.start_download(conn, _spec(rid))
    assert r == {"error": "import_pending"}                            # 报可区分状态
    assert (root / "loras" / "foo.safetensors").exists()               # 文件保留、未被删 [闭环重要]
    assert not (root / "loras" / "foo.safetensors.part").exists()      # .part 消

from fastapi.testclient import TestClient
from combuddy.api import create_app

def _client(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.sqlite"), static_dir=None))

def test_settings_never_returns_key_plaintext(tmp_path):
    cl = _client(tmp_path)
    post = cl.post("/api/settings", json={"civitai_api_key": "sk-secret"})
    assert "civitai_api_key" not in post.json() and post.json()["civitai_api_key_set"] is True   # POST 不回明文 [B2]
    get = cl.get("/api/settings")
    assert "civitai_api_key" not in get.json() and get.json()["civitai_api_key_set"] is True      # GET 不回明文 [B2]

def test_download_cross_origin_guard(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("combuddy.download_service.start_download", lambda *a, **k: calls.append(1))
    r = _client(tmp_path).post("/api/download", json=_spec(1), headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403 and calls == []                       # 跨源守卫 [B4]

def test_download_demo_noop_zero_network(tmp_path, monkeypatch):
    p = str(tmp_path / "d.sqlite"); c = db.connect(p); db.init_schema(c)
    config.set_settings(c, {"civitai_api_key": "sk-fake"}); c.close()   # 即便配了 key
    calls = []
    monkeypatch.setattr("combuddy.civitai.download_file", lambda *a, **k: calls.append(1))
    r = TestClient(create_app(p, demo=True)).post("/api/download", json=_spec(1))
    assert r.json() == {"started": False, "demo": True} and calls == []   # demo no-op 零网络 [L4]

def test_stats_exposes_download_and_key_set(tmp_path):
    s = _client(tmp_path).get("/api/stats").json()
    assert "download" in s and s["civitai_api_key_set"] is False

def test_hash_candidate_carries_download():
    from combuddy.api import _hash_candidate
    ident = {"name": "M", "version_name": "v", "model_type": "LORA", "base_model": "SDXL",
             "civitai_url": "https://civitai.com/models/5",
             "download": {"url": "https://civitai.com/api/download/models/9", "filename": "m.safetensors",
                          "size_kb": 1.0, "sha256": "a" * 64}}
    assert _hash_candidate(ident)["download"]["filename"] == "m.safetensors"   # download 透传

def test_download_already_running_409(tmp_path):
    download_service.DOWNLOAD_STATUS["running"] = True                 # 实现有分支、须有测试驱动 [M1]
    try:
        r = _client(tmp_path).post("/api/download", json=_spec(1))
        assert r.status_code == 409 and r.json()["reason"] == "already_running"
    finally:
        download_service.DOWNLOAD_STATUS["running"] = False

def test_settings_post_cross_origin_guard(tmp_path):                   # 凭证写入口防 CSRF [H1]
    r = _client(tmp_path).post("/api/settings", json={"civitai_api_key": "x"},
                               headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403
