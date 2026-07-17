import io, json, urllib.error
import pytest
from combuddy import civitai

# 真实 Civitai /api/v1/models 结构（PROD 2026-07-17 抓包精简）：item.type + item.modelVersions[].files[]
def _item(model_id, ver_id, model_name, ver_name, base, files, mtype="LORA"):
    return {"id": model_id, "name": model_name, "type": mtype,
            "modelVersions": [{"id": ver_id, "name": ver_name, "baseModel": base, "files": files}]}

def _file(name, size_kb=223286.08, ftype="Model", primary=True):
    return {"name": name, "sizeKB": size_kb, "type": ftype, "primary": primary}

class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False

def _capture(payload, box):
    def f(req, timeout=None):
        box.append(req.full_url)
        return _Resp(json.dumps(payload).encode())
    return f

def test_normalize_basic_shape():
    items = [_item(5, 9, "Cool Model", "v1", "SDXL", [_file("cool_v1.safetensors")])]
    out = civitai.normalize_search(items, "cool_v1.safetensors")
    assert len(out) == 1
    c = out[0]
    assert c["model_name"] == "Cool Model" and c["version_name"] == "v1"
    assert c["model_type"] == "LORA" and c["base_model"] == "SDXL"
    assert c["civitai_url"] == "https://civitai.com/models/5?modelVersionId=9"
    assert c["file"] == {"name": "cool_v1.safetensors", "size_kb": 223286.08}
    assert c["file_match"] is True

def test_normalize_file_match_uses_norm_key_nfd():
    # Civitai file.name 为 NFD 分解形，ref 为 NFC；裸 casefold 会漏，norm.match_key 命中
    import unicodedata
    nfc = "Pastél.safetensors"; nfd = unicodedata.normalize("NFD", nfc)
    items = [_item(1, 2, "M", "v", "SDXL", [_file(nfd)])]
    out = civitai.normalize_search(items, nfc)
    assert out[0]["file_match"] is True

def test_normalize_file_match_sorts_first():
    a = _item(1, 1, "A", "v", "SDXL", [_file("other.safetensors")])       # 不匹配
    b = _item(2, 2, "B", "v", "SDXL", [_file("target.safetensors")])      # 匹配
    out = civitai.normalize_search([a, b], "target.safetensors")
    assert out[0]["model_name"] == "B" and out[0]["file_match"] is True

def test_normalize_prefers_version_with_matching_file():
    item = {"id": 3, "name": "M", "type": "LORA", "modelVersions": [
        {"id": 30, "name": "new", "baseModel": "SDXL", "files": [_file("new.safetensors")]},
        {"id": 20, "name": "old", "baseModel": "SDXL", "files": [_file("wanted.safetensors")]}]}
    out = civitai.normalize_search([item], "wanted.safetensors")
    assert out[0]["version_name"] == "old"                                # 深链到含匹配文件的版本
    assert out[0]["civitai_url"].endswith("modelVersionId=20")

def test_normalize_skips_empty_modelversions():
    items = [{"id": 1, "name": "M", "type": "LORA", "modelVersions": []},
             _item(2, 2, "Good", "v", "SDXL", [_file("g.safetensors")])]
    out = civitai.normalize_search(items, "g.safetensors")
    assert [c["model_name"] for c in out] == ["Good"]                     # 空版本被跳过，不 500

def test_normalize_picks_primary_model_file():
    files = [_file("cfg.yaml", size_kb=4.0, ftype="Config", primary=False),
             _file("model.safetensors", size_kb=6775434.0, ftype="Model", primary=True)]
    out = civitai.normalize_search([_item(1, 1, "M", "v", "SDXL", files)], "model.safetensors")
    assert out[0]["file"]["name"] == "model.safetensors" and out[0]["file"]["size_kb"] == 6775434.0

def test_normalize_drops_non_int_id():
    ver = {"id": 9, "baseModel": "SDXL", "files": [_file("x.safetensors")]}
    bad_str = {"id": "5", "name": "M", "type": "LORA", "modelVersions": [ver]}
    bad_bool = {"id": True, "name": "M", "type": "LORA", "modelVersions": [ver]}   # bool 是 int 子类,须排除 [L4]
    assert civitai.normalize_search([bad_str], "x.safetensors") == []
    assert civitai.normalize_search([bad_bool], "x.safetensors") == []

def test_normalize_no_ref_disables_file_match():
    out = civitai.normalize_search([_item(1, 1, "M", "v", "SDXL", [_file("x.safetensors")])], None)
    assert out[0]["file_match"] is False

def test_normalize_truncates_to_limit():
    items = [_item(i, i, f"M{i}", "v", "SDXL", [_file(f"m{i}.safetensors")]) for i in range(1, 9)]
    assert len(civitai.normalize_search(items, "none.safetensors", limit=5)) == 5

def test_fetch_search_encodes_query_and_types(monkeypatch):
    box = []
    payload = {"items": [_item(1, 1, "M", "v", "SDXL", [_file("m.safetensors")])]}
    monkeypatch.setattr(civitai.urllib.request, "urlopen", _capture(payload, box))
    kind, items = civitai.fetch_search("龙 & <lora>\n", types=["LORA", "LoCon"])
    assert kind == "ok" and len(items) == 1
    url = box[0]
    assert "query=%E9%BE%99+%26+%3Clora%3E%0A" in url          # CJK/空格/&/</换行被 percent-encode [L3]
    assert "types=LORA" in url and "types=LoCon" in url        # doseq 多值 [L3]

def test_fetch_search_no_types_omits_param(monkeypatch):
    box = []
    monkeypatch.setattr(civitai.urllib.request, "urlopen", _capture({"items": []}, box))
    civitai.fetch_search("x", types=None)
    assert "types=" not in box[0]

def test_fetch_search_rate_limited(monkeypatch):
    def f(req, timeout=None): raise urllib.error.HTTPError("u", 429, "rate", {}, None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f)
    assert civitai.fetch_search("x") == ("rate_limited", None)

def test_fetch_search_error_on_5xx_and_urlerror(monkeypatch):
    def f5(req, timeout=None): raise urllib.error.HTTPError("u", 500, "err", {}, None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f5)
    assert civitai.fetch_search("x") == ("error", None)
    def fe(req, timeout=None): raise urllib.error.URLError("boom")
    monkeypatch.setattr(civitai.urllib.request, "urlopen", fe)
    assert civitai.fetch_search("x") == ("error", None)

def test_fetch_search_error_on_unexpected_shape(monkeypatch):
    # HTTP 200 但结构意外(items 非 list / 顶层非 dict)→ error,不冒泡 500 [M2③]
    monkeypatch.setattr(civitai.urllib.request, "urlopen", lambda req, timeout=None: _Resp(b'{"items": null}'))
    assert civitai.fetch_search("x") == ("error", None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", lambda req, timeout=None: _Resp(b'[]'))
    assert civitai.fetch_search("x") == ("error", None)

def test_types_map_values():
    assert civitai._TYPES["checkpoints"] == ["Checkpoint"]
    assert civitai._TYPES["loras"] == ["LORA", "LoCon", "DoRA"]
    assert civitai._TYPES["vae"] == ["VAE"]
    assert civitai._TYPES["controlnet"] == ["Controlnet"]      # 小写 n(Civitai 枚举)
    assert civitai._TYPES["upscale_models"] == ["Upscaler"]
    assert civitai._TYPES["diffusion_models"] == ["Checkpoint"]
    assert civitai._TYPES.get("text_encoders") is None         # 故意不映射
    assert civitai._TYPES.get("clip_vision") is None

_HASH_PAYLOAD = {"id": 9, "modelId": 5, "name": "v1.0", "baseModel": "SDXL",
                 "model": {"name": "Cool Model", "type": "LORA"},
                 "trainedWords": ["trig"], "images": [{"url": "https://img/x/width=1024/a.jpeg"}]}

def test_lookup_by_hash_found(monkeypatch):
    monkeypatch.setattr(civitai.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp(json.dumps(_HASH_PAYLOAD).encode()))
    kind, ident = civitai.lookup_by_hash("a" * 64)
    assert kind == "found"
    assert ident["name"] == "Cool Model" and ident["civitai_url"] == "https://civitai.com/models/5?modelVersionId=9"

def test_lookup_by_hash_notfound(monkeypatch):
    def f(req, timeout=None): raise urllib.error.HTTPError("u", 404, "nf", {}, None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f)
    assert civitai.lookup_by_hash("a" * 64) == ("notfound", None)

def test_lookup_by_hash_rate_limited(monkeypatch):
    def f(req, timeout=None): raise urllib.error.HTTPError("u", 429, "rate", {}, None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f)
    assert civitai.lookup_by_hash("a" * 64) == ("rate_limited", None)

def test_lookup_by_hash_error(monkeypatch):
    def f(req, timeout=None): raise urllib.error.URLError("boom")
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f)
    assert civitai.lookup_by_hash("a" * 64) == ("error", None)

def test_fetch_by_hash_unchanged_still_folds_429_to_skip(monkeypatch):
    # 回归护栏:fetch_by_hash 的 skip 语义不能被本功能改动 [M1]
    def f(req, timeout=None): raise urllib.error.HTTPError("u", 429, "rate", {}, None)
    monkeypatch.setattr(civitai.urllib.request, "urlopen", f)
    assert civitai.fetch_by_hash("a" * 64) == ("skip", None)
