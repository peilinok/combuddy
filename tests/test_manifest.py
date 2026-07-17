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
    ("https://evil.tld\\@civitai.com/", False),   # 反斜杠权威混淆:浏览器导航到 evil.tld [Critical]
    ("https://civitai.com\tx", False),             # 含 tab 等控制字符一律拒(解析分歧输入面)
    ("https://civitai.com\n", False),              # 含换行一律拒
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


def test_candidates_empty_dir_type_does_not_cross_match(tmp_path):
    # 攻击者写 "dir_type": "" 想绕过类型约束,不能被当作"未指定"去跨类型兜底 [H1]
    c = _conn(tmp_path)
    _model(c, _root(c, "/m"), "loras", "foo.safetensors", sha256="b" * 64)
    c.commit()
    assert manifest._candidates(
        c, {"ref_string": "foo.safetensors", "filename": "foo.safetensors", "dir_type": ""}) == []


def test_candidates_deterministic_when_all_sort_keys_tie(tmp_path):
    # 全打平时 _candidates 返回全部候选且顺序稳定。注意:因 models.id≡rowid≡自然扫描序,
    # 本测试无法区分 _ORDER 末列有无 m.id ASC(删掉仍绿)——该兜底列的回归改由下面两个
    # 测试共同锁定:first_seen 层由 test_candidates_first_seen_breaks_tie_before_rowid,
    # 最末 m.id 层由 test_order_ends_with_id_tiebreak(结构断言) [H2]
    c = _conn(tmp_path)
    a = _model(c, _root(c, "/m1"), "checkpoints", "SD1.5/foo.safetensors", sha256="y" * 64)
    b = _model(c, _root(c, "/m2"), "checkpoints", "SD1.5/foo.safetensors", sha256="z" * 64)
    c.execute("UPDATE models SET first_seen=100.0")     # 全部排序维度打平
    c.commit()
    ids = [r["id"] for r in manifest._candidates(
        c, {"ref_string": "SD1.5/foo.safetensors", "filename": "foo.safetensors",
            "dir_type": "checkpoints"})]
    assert ids == sorted([a, b])


def test_candidates_first_seen_breaks_tie_before_rowid(tmp_path):
    # 行为锁定 [H2] 的 first_seen ASC 层:构造 id 序与 first_seen 序故意相反(先插的 a
    # id 更小但 first_seen 更晚),断言按 first_seen 升序返回 [b, a] 而非 rowid 序 [a, b]。
    # 删掉 _ORDER 的 first_seen ASC 会退化成自然 rowid 序 → 断言变红,守住这一层兜底。
    c = _conn(tmp_path)
    a = _model(c, _root(c, "/m1"), "checkpoints", "SD1.5/foo.safetensors", sha256="y" * 64)
    b = _model(c, _root(c, "/m2"), "checkpoints", "SD1.5/foo.safetensors", sha256="z" * 64)
    c.execute("UPDATE models SET first_seen=200.0 WHERE id=?", (a,))   # 先插,但更晚见到
    c.execute("UPDATE models SET first_seen=100.0 WHERE id=?", (b,))   # 后插,但更早见到
    c.commit()
    ids = [r["id"] for r in manifest._candidates(
        c, {"ref_string": "SD1.5/foo.safetensors", "filename": "foo.safetensors",
            "dir_type": "checkpoints"})]
    assert ids == [b, a]


def test_order_ends_with_id_tiebreak():
    # 最末的 m.id ASC 是 first_seen 也打平时的唯一仲裁,但因 id≡rowid≡自然扫描序,输出
    # 断言无法区分它在不在(见上面测试的注释)。故用结构断言钉死:_ORDER 必须以 m.id ASC
    # 收尾。注意 `"m.id" in _ORDER` 无效——开头 ref_count 子查询已含 m.id,恒真 [H2]
    assert manifest._ORDER.rstrip().endswith("m.id ASC")


def test_candidates_non_str_filename_does_not_crash(tmp_path):
    # filename 是攻击者可控字段,_read_manifest 只校验 ref_string 是 str。非 str 的
    # filename 不能让 match_key 崩溃(会对非 str 调 .replace),应退回 ref 的 basename
    c = _conn(tmp_path)
    m = _model(c, _root(c, "/m"), "loras", "foo.safetensors", sha256="a" * 64)
    c.commit()
    rows = manifest._candidates(
        c, {"ref_string": "foo.safetensors", "filename": 123, "dir_type": "loras"})
    assert [r["id"] for r in rows] == [m]     # 退到 basename("foo.safetensors") → 命中


def test_candidates_backslash_ref_missing_filename_matches_by_name(tmp_path):
    # name_key 兜底取 basename 前必须先归一化反斜杠(与 _entry 第 56 行一致)。外来 manifest
    # 用 Windows 风格 ref 且缺 filename 时,POSIX 的 os.path.basename 不切 `\`;若不先归一化
    # 就把整串当 basename → 漏掉本地同名模型、把 present 误报成 missing [审查]
    c = _conn(tmp_path)
    m = _model(c, _root(c, "/m"), "loras", "foo.safetensors", sha256="a" * 64)
    c.commit()
    rows = manifest._candidates(
        c, {"ref_string": "SD1.5\\foo.safetensors", "dir_type": "loras"})   # 无 filename 字段
    assert [r["id"] for r in rows] == [m]     # 归一化后 basename=foo.safetensors → 命中


def test_unhashed_local_never_mismatches(tmp_path):
    # 导入方 auto_hash 关闭或 hashing 未跑完时本地 sha 全 NULL。若只查「同名存在」
    # 就报 mismatch,一个字节完全一致的库会整片报「版本不符」——这是 Blocker [B2]
    c = _conn(tmp_path)
    _model(c, _root(c, "/m"), "checkpoints", "a.safetensors", sha256=None)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "a.safetensors", "filename": "a.safetensors",
        "dir_type": "checkpoints", "lock": "exact", "sha256": "a" * 64}]))
    assert rep["mismatch"] == []
    assert rep["summary"]["present_unverified"] == 1
    assert rep["present"][0]["needs_hash"] is True


def test_mismatch_only_when_local_is_hashed_and_differs(tmp_path):
    c = _conn(tmp_path)
    m = _model(c, _root(c, "/m"), "checkpoints", "a.safetensors", sha256="b" * 64)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "a.safetensors", "filename": "a.safetensors",
        "dir_type": "checkpoints", "lock": "exact", "sha256": "a" * 64,
        "civitai": {"url": "https://civitai.com/models/9"}}]))
    assert rep["summary"]["mismatch"] == 1
    assert rep["mismatch"][0]["model_id"] == m
    assert rep["mismatch"][0]["civitai_url"] == "https://civitai.com/models/9"


def test_sha_hit_wins_over_same_name_different_sha(tmp_path):
    # 本地既有 sha 一致的副本(异路径)、又有同名不同 sha 的 → present(exact),绝不 mismatch
    c = _conn(tmp_path)
    mr = _root(c, "/m")
    hit = _model(c, mr, "checkpoints", "other/a.safetensors", sha256="a" * 64)
    _model(c, mr, "checkpoints", "a.safetensors", sha256="b" * 64)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "a.safetensors", "filename": "a.safetensors",
        "dir_type": "checkpoints", "lock": "exact", "sha256": "a" * 64}]))
    assert rep["summary"] == {"present_exact": 1, "present_unverified": 0, "mismatch": 0,
                              "ambiguous": 0, "missing": 0, "total": 1}
    assert rep["present"][0]["model_id"] == hit


def test_weak_never_mismatches(tmp_path):
    # lock != exact 的 sha 可能 pin 的是源侧误命中的模型,不得驱动 mismatch [H3][L3]
    c = _conn(tmp_path)
    _model(c, _root(c, "/m"), "loras", "c.safetensors", sha256="d" * 64)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "c.safetensors", "filename": "c.safetensors", "dir_type": "loras",
        "lock": "weak", "match_kind": "basename", "sha256": "c" * 64}]))
    assert rep["mismatch"] == []
    assert rep["present"][0]["confidence"] == "unverified"
    assert "needs_hash" not in rep["present"][0]


def test_multiple_candidates_yield_ambiguous_without_model_id(tmp_path):
    # 多 root / 同名多副本是 combuddy 常态;契约是「多命中永不绑定」[H2]
    c = _conn(tmp_path)
    _model(c, _root(c, "/m1"), "checkpoints", "SD1.5/foo.safetensors", sha256="y" * 64)
    _model(c, _root(c, "/m2"), "checkpoints", "SD1.5/foo.safetensors", sha256="z" * 64)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "SD1.5/foo.safetensors", "filename": "foo.safetensors",
        "dir_type": "checkpoints", "lock": "weak"}]))
    assert rep["summary"]["ambiguous"] == 1
    item = rep["ambiguous"][0]
    assert "model_id" not in item
    assert len(item["candidates"]) == 2
    assert {x["sha256"] for x in item["candidates"]} == {"y" * 64, "z" * 64}


def test_missing_and_cross_dir_type_is_missing(tmp_path):
    # 本地只有 loras/foo,manifest 要 checkpoints/foo → MISSING,不是 mismatch/present [H1]
    c = _conn(tmp_path)
    _model(c, _root(c, "/m"), "loras", "foo.safetensors", sha256="b" * 64)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "foo.safetensors", "filename": "foo.safetensors",
        "dir_type": "checkpoints", "lock": "exact", "sha256": "a" * 64}]))
    assert rep["summary"]["missing"] == 1
    assert rep["missing"][0]["filename"] == "foo.safetensors"


def test_verify_drops_unsafe_civitai_url(tmp_path):
    c = _conn(tmp_path)
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "z.safetensors", "filename": "z.safetensors", "dir_type": "loras",
        "lock": "expected", "civitai": {"url": "javascript:alert(1)"}}]))
    assert rep["missing"][0]["civitai_url"] is None       # [B1]


def test_invalid_sha_degrades_to_name_path(tmp_path):
    # 非 64-hex 的 sha 不进 SQL,降级为无-sha 路径 [L2]
    c = _conn(tmp_path)
    _model(c, _root(c, "/m"), "loras", "a.safetensors", sha256="a" * 64)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "a.safetensors", "filename": "a.safetensors", "dir_type": "loras",
        "lock": "exact", "sha256": "'; DROP TABLE models; --"}]))
    assert rep["summary"]["present_unverified"] == 1
    assert c.execute("SELECT COUNT(*) c FROM models").fetchone()["c"] == 1


def test_roundtrip_fully_hashed_workflow_is_all_exact(tmp_path):
    # 只有「全 hash + 全 path 解析」的 workflow 才可断言全 present(exact) [L7]
    c = _conn(tmp_path)
    mr, wr = _root(c, "/m"), _root(c, "/w", "workflow")
    m1 = _model(c, mr, "checkpoints", "a.safetensors", sha256="a" * 64)
    m2 = _model(c, mr, "loras", "sub/b.safetensors", sha256="b" * 64)
    p = tmp_path / "rt.json"
    p.write_bytes(b'{"nodes": []}')
    wf = _workflow(c, wr, str(p), "rt.json", 2)
    _edge(c, wf, "a.safetensors", "CheckpointLoaderSimple", "checkpoints", m1, "path")
    _edge(c, wf, "sub/b.safetensors", "LoraLoader", "loras", m2, "path")
    c.commit()

    body, _ = manifest.build_bundle(c, wf)
    rep = manifest.verify_bundle(c, body)
    assert rep["summary"] == {"present_exact": 2, "present_unverified": 0, "mismatch": 0,
                              "ambiguous": 0, "missing": 0, "total": 2}
    assert rep["workflow"]["filename"] == "rt.json"


def test_sha_comparison_is_case_insensitive(tmp_path):
    # 本地 sha 恒小写(hexdigest);别的工具生成的 manifest 可能用大写 hex(合规 64-hex 格式)。
    # 字节相同就是同一文件 → present(exact),绝不能因大小写判 mismatch [B2 同一类别]
    c = _conn(tmp_path)
    m = _model(c, _root(c, "/m"), "loras", "a.safetensors", sha256="a" * 64)   # 本地小写
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "a.safetensors", "filename": "a.safetensors", "dir_type": "loras",
        "lock": "exact", "sha256": "A" * 64}]))                                  # manifest 大写
    assert rep["summary"]["present_exact"] == 1
    assert rep["summary"]["mismatch"] == 0
    assert rep["present"][0]["model_id"] == m


def test_verify_endpoint_roundtrip(tmp_path):
    c = _conn(tmp_path)
    mr, wr = _root(c, "/m"), _root(c, "/w", "workflow")
    m1 = _model(c, mr, "checkpoints", "a.safetensors", sha256="a" * 64)
    p = tmp_path / "rt.json"
    p.write_bytes(b'{"nodes": []}')
    wf = _workflow(c, wr, str(p), "rt.json", 1)
    _edge(c, wf, "a.safetensors", "CheckpointLoaderSimple", "checkpoints", m1, "path")
    c.commit()
    c.close()

    client = _app(tmp_path)
    body = client.get(f"/api/workflows/{wf}/bundle").content
    r = client.post("/api/manifest/verify", content=body)
    assert r.status_code == 200
    assert r.json()["summary"]["present_exact"] == 1


def test_verify_endpoint_rejects_oversized_body_before_buffering(tmp_path):
    # request.body() 会先把整个体缓冲进内存再判大小 → 超大 body 先 OOM。
    # 必须流式累加、读满前拒绝 [H5]
    _conn(tmp_path).close()
    r = _app(tmp_path).post("/api/manifest/verify", content=b"x" * (manifest.BODY_MAX + 1))
    assert r.status_code == 413 and r.json()["reason"] == "too_large"


def test_verify_endpoint_maps_errors_to_reason_codes(tmp_path):
    _conn(tmp_path).close()
    client = _app(tmp_path)
    r = client.post("/api/manifest/verify", content=b"not a zip")
    assert r.status_code == 400 and r.json()["reason"] == "bad_zip"
    r = client.post("/api/manifest/verify",
                    content=_zip_of(json.dumps({"combuddy_manifest": 99, "models": []}).encode()))
    assert r.status_code == 400 and r.json()["reason"] == "unsupported_version"


def test_verify_endpoint_streams_body_and_never_buffers(tmp_path, monkeypatch):
    # H5 的机制回归防护:上面的终态测试对被禁止的 `await request.body()` 写法会产生
    # 逐字节相同的结果,抓不住退化。这里把 Request.body 打成地雷 —— 端点一旦从
    # request.stream() 退化成先缓冲后判,这个测试立刻变红。
    import starlette.requests

    async def _boom(self):
        raise AssertionError("endpoint must use request.stream(), not request.body() [H5]")

    monkeypatch.setattr(starlette.requests.Request, "body", _boom)
    c = _conn(tmp_path)
    mr, wr = _root(c, "/m"), _root(c, "/w", "workflow")
    m1 = _model(c, mr, "checkpoints", "a.safetensors", sha256="a" * 64)
    p = tmp_path / "rt.json"
    p.write_bytes(b'{"nodes": []}')
    wf = _workflow(c, wr, str(p), "rt.json", 1)
    _edge(c, wf, "a.safetensors", "CheckpointLoaderSimple", "checkpoints", m1, "path")
    c.commit()
    c.close()

    client = _app(tmp_path)
    body = client.get(f"/api/workflows/{wf}/bundle").content
    r = client.post("/api/manifest/verify", content=body)
    assert r.status_code == 200                      # 走 stream 成功;若走 body() 则地雷会炸
    assert r.json()["summary"]["present_exact"] == 1


def test_verify_non_dict_civitai_does_not_crash(tmp_path):
    # civitai 是攻击者可控字段,_read_manifest 不校验其类型。非 dict(如字符串)不能让
    # verify_bundle 崩溃——isinstance(civ, dict) 守卫应吞掉它,civitai_url 归 None [B1]
    c = _conn(tmp_path)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "a.safetensors", "dir_type": "checkpoints",
        "lock": "expected", "civitai": "pwned"}]))
    assert rep["summary"]["missing"] == 1
    assert rep["missing"][0]["civitai_url"] is None


def test_verify_non_str_dir_type_does_not_cross_match(tmp_path):
    # dir_type 攻击者可控且不校验类型。非 str/非 None(如 int)不能崩溃,也绝不当作「未指定」
    # 去跨类型裸 name_key 匹配——_candidates 对这类值走 return [] → 归 missing [H1]
    c = _conn(tmp_path)
    _model(c, _root(c, "/m"), "loras", "foo.safetensors", sha256="a" * 64)
    c.commit()
    rep = manifest.verify_bundle(c, _bundle_of([{
        "ref_string": "foo.safetensors", "dir_type": 123, "lock": "expected"}]))
    assert rep["summary"]["missing"] == 1     # 无候选,绝不跨类型命中 loras/foo


def test_verify_missing_and_mismatch_echo_sha(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite")); db.init_schema(c)
    mr = _root(c, "/m")
    # 本地有一个 loras/have.safetensors,sha=本地值 → 与 bundle 的 exact 条目 sha 不同 → mismatch
    _model(c, mr, "loras", "have.safetensors", sha256="b" * 64)
    body = _bundle_of([                                                  # 条目列表直接进 _bundle_of [B1]
        {"ref_string": "have.safetensors", "dir_type": "loras", "filename": "have.safetensors",
         "sha256": "a" * 64, "lock": "exact"},                          # 同名不同 sha → mismatch
        {"ref_string": "gone.safetensors", "dir_type": "loras", "filename": "gone.safetensors",
         "sha256": "c" * 64, "lock": "exact"},                          # 本地无 → missing,带 sha
        {"ref_string": "nohash.safetensors", "dir_type": "loras", "filename": "nohash.safetensors",
         "lock": "expected"}])                                           # 打包方也没有 → missing,无 sha
    rep = manifest.verify_bundle(c, body)
    mm = {m["ref_string"]: m for m in rep["mismatch"]}
    ms = {m["ref_string"]: m for m in rep["missing"]}
    assert mm["have.safetensors"]["sha256"] == "a" * 64                 # mismatch 必带 bundle 条目 sha(正确版本)
    assert ms["gone.safetensors"]["sha256"] == "c" * 64                 # missing(lock=exact) 带 sha
    assert "sha256" not in ms["nohash.safetensors"]                     # missing(lock=expected) 无 sha
