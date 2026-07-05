import io, json, os, urllib.error
from combuddy import db, civitai

class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False

def _ok(payload):
    def f(req, timeout=None): return _Resp(json.dumps(payload).encode())
    return f

_PAYLOAD = {"id": 9, "modelId": 5, "name": "v1.0", "baseModel": "SDXL",
            "model": {"name": "Cool Model", "type": "LORA"},
            "trainedWords": ["trigger"],
            "images": [{"url": "https://img.civitai.com/x/width=1024/a.jpeg", "nsfwLevel": 4}]}

def test_fetch_found(monkeypatch):
    monkeypatch.setattr(civitai.urllib.request, "urlopen", _ok(_PAYLOAD))
    kind, ident = civitai.fetch_by_hash("abc")
    assert kind == "found"
    assert ident["name"] == "Cool Model" and ident["base_model"] == "SDXL"
    assert ident["model_type"] == "LORA" and ident["nsfw_level"] == 4
    assert json.loads(ident["trigger_words"]) == ["trigger"]
    assert ident["civitai_url"] == "https://civitai.com/models/5?modelVersionId=9"
    assert ident["image_url"].endswith("a.jpeg")

def test_fetch_notfound(monkeypatch):
    def f(req, timeout=None): raise urllib.error.HTTPError("u", 404, "nf", {}, None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f)
    assert civitai.fetch_by_hash("abc") == ("notfound", None)

def test_fetch_skip_on_429_and_error(monkeypatch):
    def f429(req, timeout=None): raise urllib.error.HTTPError("u", 429, "rate", {}, None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f429)
    assert civitai.fetch_by_hash("abc") == ("skip", None)
    def ferr(req, timeout=None): raise urllib.error.URLError("boom")
    monkeypatch.setattr(civitai.urllib.request, "urlopen", ferr)
    assert civitai.fetch_by_hash("abc") == ("skip", None)

def _seed(conn, items):  # items: list[(sha256, filename)]
    conn.execute("INSERT INTO roots(id,kind,path,enabled) VALUES(1,'model','/r',1)")
    for i, (sha, fn) in enumerate(items, 1):
        conn.execute("""INSERT INTO models(id,root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
            size,mtime,sha256,match_key,name_key,first_seen,last_scanned)
            VALUES(?,1,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (i, f"/r/{fn}", fn, "loras", fn, fn, "safetensors", 9, 1, sha, fn, fn, 1, 1))
    conn.commit()

def test_enrich_found_notfound_skip(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [("aaa", "m1"), ("bbb", "m2"), ("ccc", "m3")])
    ident = {"name": "N", "version_name": "v", "base_model": "SDXL", "model_type": "LORA",
             "trigger_words": '["t"]', "nsfw_level": 2, "civitai_url": "u",
             "image_url": "https://img/width=9/x.jpg"}
    fetch = lambda sha: {"aaa": ("found", ident), "bbb": ("notfound", None),
                         "ccc": ("skip", None)}[sha]
    got = []
    def dl(url, dest): got.append(dest); open(dest, "wb").write(b"IMG"); return True
    res = civitai.enrich_models(conn, fetch=fetch, download=dl)
    assert res["found"] == 1 and res["total"] == 3
    rows = {r["model_id"]: dict(r) for r in conn.execute("SELECT * FROM civitai")}
    assert rows[1]["found"] == 1 and rows[1]["name"] == "N" and rows[1]["image_path"] == "aaa.jpg"
    assert rows[2]["found"] == 0 and rows[2]["name"] is None
    assert 3 not in rows                                   # skip → 不写
    assert len(got) == 1                                   # 只 found 的下图

def test_enrich_skips_already_checked(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [("aaa", "m1")])
    conn.execute("INSERT INTO civitai(model_id,sha256,found,checked_at) VALUES(1,'aaa',0,1)")
    conn.commit()
    called = []
    civitai.enrich_models(conn, fetch=lambda s: called.append(s) or ("skip", None),
                          download=lambda u, d: False)
    assert called == []                                   # 已查过(sha256 未变)→ 不再查

def test_enrich_rechecks_when_sha_changed(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [("newsha", "m1")])
    conn.execute("INSERT INTO civitai(model_id,sha256,found,checked_at) VALUES(1,'oldsha',0,1)")
    conn.commit()
    called = []
    civitai.enrich_models(conn, fetch=lambda s: called.append(s) or ("notfound", None),
                          download=lambda u, d: False)
    assert called == ["newsha"]                            # sha256 变了 → 重查

def test_enrich_cancel_stops(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _seed(conn, [("aaa", "m1")])
    res = civitai.enrich_models(conn, should_cancel=lambda: True,
                                fetch=lambda s: ("found", {}), download=lambda u, d: False)
    assert res["found"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM civitai").fetchone()["c"] == 0
