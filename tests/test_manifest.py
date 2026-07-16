import io
import json
import os
import struct
import time
import zipfile

import pytest

from combuddy import db, manifest, norm


def _conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


def _root(c, path, kind="model"):
    return c.execute(
        "INSERT INTO roots(kind,path,label,source) VALUES(?,?,?,'test')", (kind, path, "R")
    ).lastrowid


def _model(c, root_id, dir_type, rel_in_type, sha256=None, base_arch=None, size=100):
    filename = os.path.basename(rel_in_type)
    now = time.time()
    return c.execute(
        """INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,ext,size,mtime,
           base_arch,sha256,match_key,name_key,first_seen,last_scanned)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (root_id, f"/m{root_id}/{dir_type}/{rel_in_type}", f"{dir_type}/{rel_in_type}", dir_type,
         rel_in_type, filename, "safetensors", size, now, base_arch, sha256,
         norm.match_key(rel_in_type), norm.match_key(filename), now, now),
    ).lastrowid


def _civitai(c, model_id, sha256, found=1, name="Foo", version_name="v1",
             url="https://civitai.com/models/1?modelVersionId=2"):
    c.execute(
        """INSERT INTO civitai(model_id,sha256,found,name,version_name,base_model,model_type,
           trigger_words,nsfw_level,civitai_url,image_path,checked_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (model_id, sha256, found, name, version_name, "SDXL", "LORA", "[]", 1, url, None, time.time()),
    )


def _workflow(c, root_id, path, filename, ref_count=0):
    now = time.time()
    return c.execute(
        "INSERT INTO workflows(root_id,path,filename,mtime,ref_count,last_scanned) VALUES(?,?,?,?,?,?)",
        (root_id, path, filename, now, ref_count, now),
    ).lastrowid


def _edge(c, wf_id, ref_string, node_type, ref_dir_type, model_id=None, match_kind=None):
    c.execute(
        """INSERT INTO edges(workflow_id,ref_string,ref_key,ref_dir_type,node_type,model_id,match_kind)
           VALUES(?,?,?,?,?,?,?)""",
        (wf_id, ref_string, norm.match_key(ref_string), ref_dir_type, node_type, model_id, match_kind),
    )


def _wf_row(c, wf_id):
    return c.execute("SELECT * FROM workflows WHERE id=?", (wf_id,)).fetchone()


def test_lock_four_states(tmp_path):
    c = _conn(tmp_path)
    mr, wr = _root(c, "/m"), _root(c, "/w", "workflow")
    m1 = _model(c, mr, "checkpoints", "a.safetensors", sha256="a" * 64, base_arch="SDXL")
    m2 = _model(c, mr, "loras", "b.safetensors", sha256=None)          # 已绑定但未 hash
    m3 = _model(c, mr, "loras", "c.safetensors", sha256="c" * 64)      # basename 兜底命中
    wf = _workflow(c, wr, "/w/x.json", "x.json", 5)
    _edge(c, wf, "a.safetensors", "CheckpointLoaderSimple", "checkpoints", m1, "path")
    _edge(c, wf, "b.safetensors", "LoraLoader", "loras", m2, "path")
    _edge(c, wf, "c.safetensors", "LoraLoader", "loras", m3, "basename")
    _edge(c, wf, "amb.safetensors", "LoraLoader", "loras", None, "ambiguous")
    _edge(c, wf, "SD1.5/gone.safetensors", "LoraLoader", "loras", None, None)
    c.commit()

    m = manifest.build_manifest(c, _wf_row(c, wf))
    by_ref = {e["ref_string"]: e for e in m["models"]}
    assert by_ref["a.safetensors"]["lock"] == "exact"
    assert by_ref["b.safetensors"]["lock"] == "weak"        # 未 hash
    assert by_ref["c.safetensors"]["lock"] == "weak"        # basename 永不 exact [H3]
    assert by_ref["c.safetensors"]["sha256"] == "c" * 64    # 带 sha 但仍 weak
    assert by_ref["c.safetensors"]["match_kind"] == "basename"
    assert by_ref["amb.safetensors"]["lock"] == "ambiguous"  # 不塌缩进 expected [M5]
    assert by_ref["SD1.5/gone.safetensors"]["lock"] == "expected"
    # filename 总是有:未绑定条目取 basename(ref_string),供接收方按名核对
    assert by_ref["SD1.5/gone.safetensors"]["filename"] == "gone.safetensors"
    assert "sha256" not in by_ref["b.safetensors"]
    assert "civitai" not in by_ref["a.safetensors"]      # 没有 civitai 行 → 不吐 civitai 键 [L8]
    assert m["combuddy_manifest"] == manifest.MANIFEST_VERSION
    assert m["workflow"] == {"filename": "x.json", "ref_count": 5}


def test_civitai_block_only_when_found(tmp_path):
    c = _conn(tmp_path)
    mr, wr = _root(c, "/m"), _root(c, "/w", "workflow")
    m1 = _model(c, mr, "loras", "a.safetensors", sha256="a" * 64)
    m2 = _model(c, mr, "loras", "b.safetensors", sha256="b" * 64)
    _civitai(c, m1, "a" * 64, found=1)
    # 404 负缓存行:found=0 且各列为 NULL,不得吐出 {name:null,url:null} 空块 [L1]
    _civitai(c, m2, "b" * 64, found=0, name=None, version_name=None, url=None)
    wf = _workflow(c, wr, "/w/x.json", "x.json", 2)
    _edge(c, wf, "a.safetensors", "LoraLoader", "loras", m1, "path")
    _edge(c, wf, "b.safetensors", "LoraLoader", "loras", m2, "path")
    c.commit()

    by_ref = {e["ref_string"]: e for e in manifest.build_manifest(c, _wf_row(c, wf))["models"]}
    assert by_ref["a.safetensors"]["civitai"]["url"] == "https://civitai.com/models/1?modelVersionId=2"
    assert "civitai" not in by_ref["b.safetensors"]


def test_empty_workflow_yields_empty_models(tmp_path):
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    wf = _workflow(c, wr, "/w/e.json", "e.json", 0)
    c.commit()
    m = manifest.build_manifest(c, _wf_row(c, wf))
    assert m["models"] == []
    assert m["generated_by"].startswith("combuddy ")


def test_unbound_filename_falls_back_to_normalized_basename(tmp_path):
    # 未绑定条目的 filename 取自 ref_string 的 basename;ref 里的反斜杠必须先归一化,
    # 否则 POSIX 上 basename 会把整串 "SD1.5\\x.safetensors" 当成文件名
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    wf = _workflow(c, wr, "/w/x.json", "x.json", 1)
    _edge(c, wf, "SD1.5\\gone.safetensors", "LoraLoader", "loras", None, None)
    c.commit()
    e = manifest.build_manifest(c, _wf_row(c, wf))["models"][0]
    assert e["filename"] == "gone.safetensors"


def test_bundle_has_both_files_and_verbatim_workflow(tmp_path):
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    p = tmp_path / "x.json"
    raw = '{"nodes": [], "note": "保留原字节"}'.encode("utf-8")
    p.write_bytes(raw)
    wf = _workflow(c, wr, str(p), "x.json", 0)
    c.commit()

    data, stem = manifest.build_bundle(c, wf)
    z = zipfile.ZipFile(io.BytesIO(data))
    assert set(z.namelist()) == {"manifest.json", "workflow.json"}
    assert z.read("workflow.json") == raw          # 逐字节复制,不重建
    assert stem == "x"
    assert json.loads(z.read("manifest.json"))["workflow"]["filename"] == "x.json"


def test_bundle_not_found(tmp_path):
    c = _conn(tmp_path)
    with pytest.raises(manifest.ManifestError) as ei:
        manifest.build_bundle(c, 999)
    assert (ei.value.reason, ei.value.status) == ("not_found", 404)


def test_bundle_source_missing(tmp_path):
    # 扫描后原文件被删/移:必须 409 明确拒绝,不得静默产出残缺 bundle [M7]
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    wf = _workflow(c, wr, str(tmp_path / "gone.json"), "gone.json", 0)
    c.commit()
    with pytest.raises(manifest.ManifestError) as ei:
        manifest.build_bundle(c, wf)
    assert (ei.value.reason, ei.value.status) == ("source_missing", 409)


def _zip_of(manifest_bytes, workflow_bytes=b"{}"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if manifest_bytes is not None:
            z.writestr("manifest.json", manifest_bytes)
        z.writestr("workflow.json", workflow_bytes)
    return buf.getvalue()


def _manifest_bytes(models, version=1):
    return json.dumps({
        "combuddy_manifest": version,
        "generated_by": "combuddy test",
        "generated_at": "2026-07-16T00:00:00Z",
        "workflow": {"filename": "x.json", "ref_count": len(models)},
        "models": models,
    }).encode()


def _bundle_of(models, version=1):
    return _zip_of(_manifest_bytes(models, version))


def _app(tmp_path):
    from fastapi.testclient import TestClient
    from combuddy.api import create_app
    return TestClient(create_app(str(tmp_path / "t.sqlite"), static_dir=None))


def test_export_endpoint_returns_zip(tmp_path):
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    p = tmp_path / "my flow.json"
    p.write_bytes(b'{"nodes": []}')
    wf = _workflow(c, wr, str(p), "my flow.json", 0)
    c.commit()
    c.close()

    r = _app(tmp_path).get(f"/api/workflows/{wf}/bundle")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "my flow.combuddy.zip" in r.headers["content-disposition"]
    assert set(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == {"manifest.json", "workflow.json"}


def test_export_endpoint_errors(tmp_path):
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    wf = _workflow(c, wr, str(tmp_path / "gone.json"), "gone.json", 0)
    c.commit()
    c.close()
    client = _app(tmp_path)

    assert client.get("/api/workflows/999/bundle").status_code == 404
    assert client.get("/api/workflows/999/bundle").json()["reason"] == "not_found"
    r = client.get(f"/api/workflows/{wf}/bundle")
    assert r.status_code == 409 and r.json()["reason"] == "source_missing"


def test_export_filename_header_is_sanitized(tmp_path):
    # 文件名里的引号/控制字符会注入响应头 [L12]
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    p = tmp_path / "evil.json"
    p.write_bytes(b"{}")
    wf = _workflow(c, wr, str(p), 'ev"il\r\n.json', 0)
    c.commit()
    c.close()

    cd = _app(tmp_path).get(f"/api/workflows/{wf}/bundle").headers["content-disposition"]
    assert '"' not in cd.replace('filename="', "").replace('.combuddy.zip"', "")
    assert "\r" not in cd and "\n" not in cd


def test_export_filename_header_handles_cjk(tmp_path):
    # Starlette 用 latin-1 编码响应头:CJK 文件名若原样进 filename= 会 UnicodeEncodeError → 500。
    # CLAUDE.md 把 CJK 文件名列为一等公民场景,必须导得出来。
    c = _conn(tmp_path)
    wr = _root(c, "/w", "workflow")
    p = tmp_path / "cjk.json"
    p.write_bytes(b"{}")
    wf = _workflow(c, wr, str(p), "我的工作流.json", 0)
    c.commit()
    c.close()

    r = _app(tmp_path).get(f"/api/workflows/{wf}/bundle")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert "filename*=UTF-8''" in cd        # RFC 5987 保留原名
    assert "%E6%88%91" in cd                # "我" 的 percent-encoding
    assert set(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == {"manifest.json", "workflow.json"}


def test_read_manifest_ok():
    data = manifest._read_manifest(_bundle_of([{"ref_string": "a.safetensors"}]))
    assert data["models"][0]["ref_string"] == "a.safetensors"


@pytest.mark.parametrize("body,reason", [
    (b"not a zip at all", "bad_zip"),
    (_zip_of(None), "missing_manifest"),
    (_zip_of(b"{not json"), "bad_json"),
    (_zip_of(b'"a string, not an object"'), "bad_json"),
    (_zip_of(json.dumps({"combuddy_manifest": 1, "models": "nope"}).encode()), "bad_json"),
    (_zip_of(json.dumps({"combuddy_manifest": 1, "models": [{"no_ref": 1}]}).encode()), "bad_json"),
    (_zip_of(json.dumps({"combuddy_manifest": 99, "models": []}).encode()), "unsupported_version"),
    (_zip_of(json.dumps({"combuddy_manifest": "1", "models": []}).encode()), "unsupported_version"),
    (_zip_of(json.dumps({"combuddy_manifest": True, "models": []}).encode()), "unsupported_version"),
    (_zip_of(json.dumps({"models": []}).encode()), "unsupported_version"),
])
def test_read_manifest_rejects_malformed(body, reason):
    with pytest.raises(manifest.ManifestError) as ei:
        manifest._read_manifest(body)
    assert ei.value.reason == reason
    assert ei.value.status == 400


def test_read_manifest_rejects_zip_bomb():
    # 压缩后极小、解压后超限:压缩体积上限根本拦不住 zipfile.read() 的无界解压 [H4]
    body = _zip_of(b"A" * (manifest.MANIFEST_MAX + 1024))
    assert len(body) < 100_000
    with pytest.raises(manifest.ManifestError) as ei:
        manifest._read_manifest(body)
    assert ei.value.reason == "too_large"


def _zip_with_broken_local_header():
    # 合法中央目录 + 损坏的 local file header:ZipFile() 构造只读末尾的中央目录,
    # 要到 open() 才碰 local header,故这类包骗得过构造函数校验
    body = bytearray(_zip_of(b'{"combuddy_manifest": 1, "models": []}'))
    i = body.find(b"PK\x03\x04")
    body[i:i + 4] = b"PK\x03\x05"
    return bytes(body)


def _zip_lying_about_size():
    # 中央目录谎报 uncompressed size = 10,真实负载远大于它:骗过 file_size 的
    # cheap 预检,逼代码必须靠有界读这个权威判据兜底
    body = bytearray(_zip_of(b"A" * (manifest.MANIFEST_MAX + 1024)))
    i = body.find(b"PK\x01\x02")                  # 中央目录第一条 = manifest.json
    struct.pack_into("<I", body, i + 24, 10)      # 偏移 24 = uncompressed size
    return bytes(body)


def _zip_with_corrupt_deflate_stream():
    # 合法容器 + 合法 local header + 中段被翻转的 DEFLATE 流。DEFLATE 是 zip 默认压缩,
    # 损坏时 zlib 抛 zlib.error —— 它不是 OSError/BadZipFile 的子类,白名单接不住
    payload = json.dumps({"combuddy_manifest": 1,
                          "models": [{"ref_string": f"m{i}.safetensors"} for i in range(300)]}).encode()
    body = bytearray(_zip_of(payload))
    i = body.find(b"PK\x03\x04")
    start = i + 30 + len("manifest.json")      # local header 固定 30 字节 + 文件名(extra 为空)
    for k in range(start + 30, start + 60):    # 翻转压缩流中段
        body[k] ^= 0xFF
    return bytes(body)


def _zip_with_bad_utf8_filename():
    # 中央目录条目设了 UTF-8 文件名标志(0x0800)但文件名字节非法 →
    # ZipFile() 构造时 filename.decode('utf-8') 抛 UnicodeDecodeError
    body = bytearray(_zip_of(b'{"combuddy_manifest": 1, "models": []}'))
    i = body.find(b"PK\x01\x02")                  # 中央目录首条
    struct.pack_into("<H", body, i + 8, 0x0800)   # 偏移 8 = general purpose flag
    body[i + 46] = 0xFF                            # 偏移 46 = 文件名首字节
    return bytes(body)


def _zip_with_unsupported_version():
    # 中央目录条目的 "version needed to extract" = 99(> MAX_EXTRACT_VERSION=63)
    # → ZipFile() 构造时抛 NotImplementedError
    body = bytearray(_zip_of(b'{"combuddy_manifest": 1, "models": []}'))
    i = body.find(b"PK\x01\x02")
    struct.pack_into("<H", body, i + 6, 99)       # 偏移 6 = version needed
    return bytes(body)


@pytest.mark.parametrize("factory", [_zip_with_broken_local_header, _zip_lying_about_size,
                                     _zip_with_corrupt_deflate_stream, _zip_with_bad_utf8_filename,
                                     _zip_with_unsupported_version])
def test_read_manifest_rejects_valid_container_with_malicious_member(factory):
    # 容器合法、成员恶意:必须以 ManifestError 干净拒绝,绝不冒泡成未捕获异常(→500)
    with pytest.raises(manifest.ManifestError) as ei:
        manifest._read_manifest(factory())
    assert ei.value.reason in ("bad_zip", "too_large")   # 两者都是合规拒绝
    assert ei.value.status == 400


def test_read_manifest_rejects_too_many_models():
    body = _bundle_of([{"ref_string": f"m{i}.safetensors"} for i in range(manifest.MODELS_MAX + 1)])
    with pytest.raises(manifest.ManifestError) as ei:
        manifest._read_manifest(body)
    assert ei.value.reason == "too_large"


def test_read_manifest_rejects_deeply_nested_json():
    # 超深嵌套必须以 400 拒绝且不崩/不 OOM。本项目 .venv(CPython 3.12)上走的是
    # json.loads 抛 RecursionError → 被 except (ValueError, RecursionError) 接住;
    # 某些更新的解释器能解析完深层 list,则由顶层 isinstance(data, dict) 校验拦下。
    # 两条路径都归 bad_json —— 这里锁定的是「不冒泡成 500」这个结果。
    body = _zip_of(b"[" * 100_000 + b"]" * 100_000)
    with pytest.raises(manifest.ManifestError) as ei:
        manifest._read_manifest(body)
    assert ei.value.reason == "bad_json"


@pytest.mark.parametrize("url,ok", [
    ("https://civitai.com/models/1?modelVersionId=2", True),
    ("https://civitai.com/", True),
    ("http://civitai.com/models/1", False),            # 非 https
    ("https://civitai.com.evil.tld/x", False),         # 仿冒域
    ("https://civitai-com.evil.tld/x", False),
    ("https://evil.tld/civitai.com", False),
    ("javascript:fetch('http://evil/'+document.cookie)", False),   # 会在本地 origin 执行
    ("JavaScript:alert(1)", False),
    ("data:text/html,<script>alert(1)</script>", False),
    ("", False), (None, False), (123, False), ({"u": "x"}, False),
])
def test_safe_civitai_url(url, ok):
    # bundle 来自他人,civitai.url 完全可控;前端会把它渲染成用户被诱导点击的链接 [B1]
    assert (manifest._safe_civitai_url(url) is not None) is ok


def test_candidates_name_fallback_is_scoped_by_dir_type(tmp_path):
    # manifest 要 checkpoints/foo,本地只有毫不相干的 loras/foo → 必须无候选 [H1]
    c = _conn(tmp_path)
    mr = _root(c, "/m")
    _model(c, mr, "loras", "foo.safetensors", sha256="b" * 64)
    c.commit()
    assert manifest._candidates(
        c, {"ref_string": "foo.safetensors", "filename": "foo.safetensors",
            "dir_type": "checkpoints"}) == []
    # dir_type 为 null(未知 loader)时才允许裸 name_key 兜底 [L11]
    assert len(manifest._candidates(
        c, {"ref_string": "foo.safetensors", "filename": "foo.safetensors",
            "dir_type": None})) == 1


def test_candidates_prefers_path_over_name_and_is_deterministic(tmp_path):
    c = _conn(tmp_path)
    mr = _root(c, "/m")
    exact_path = _model(c, mr, "loras", "sub/foo.safetensors", sha256="a" * 64)
    _model(c, mr, "loras", "foo.safetensors", sha256="b" * 64)
    c.commit()
    # match_key 命中即不再退 name_key(与 resolver._match 同优先级)
    rows = manifest._candidates(
        c, {"ref_string": "sub/foo.safetensors", "filename": "foo.safetensors", "dir_type": "loras"})
    assert [r["id"] for r in rows] == [exact_path]


def test_candidates_multi_root_same_relpath_returns_all_in_stable_order(tmp_path):
    c = _conn(tmp_path)
    m2 = _model(c, _root(c, "/m2"), "checkpoints", "SD1.5/foo.safetensors", sha256="z" * 64)
    m1 = _model(c, _root(c, "/m1"), "checkpoints", "SD1.5/foo.safetensors", sha256="y" * 64)
    c.commit()
    entry = {"ref_string": "SD1.5/foo.safetensors", "filename": "foo.safetensors",
             "dir_type": "checkpoints"}
    ids = [r["id"] for r in manifest._candidates(c, entry)]
    assert sorted(ids) == sorted([m1, m2])
    assert ids == [r["id"] for r in manifest._candidates(c, entry)]   # 确定性:两次同序 [H2]
