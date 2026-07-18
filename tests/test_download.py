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
