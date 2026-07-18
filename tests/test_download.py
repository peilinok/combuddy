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

from combuddy import download_service, config, db, scanner
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

def test_start_download_resets_cancel_at_start(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, _ = _mroot(conn, tmp_path)
    download_service.DOWNLOAD_STATUS["cancel"] = True                 # 上次遗留
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: ("ok", "a" * 64))
    download_service.start_download(conn, _spec(rid))
    assert download_service.DOWNLOAD_STATUS["cancel"] is False        # 起点复位 [H9]

def test_start_download_rejects_malformed_types(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    rid, _ = _mroot(conn, tmp_path)
    monkeypatch.setattr(download_service.civitai, "download_file", lambda *a, **k: ("ok", "a" * 64))
    for bad in [{"ref_string": None}, {"dir_type": ["loras"]}, {"size_kb": "big"}]:
        r = download_service.start_download(conn, _spec(rid, **bad))
        assert r["error"] == "bad_request" and download_service.DOWNLOAD_STATUS["error"] == "bad_request"
