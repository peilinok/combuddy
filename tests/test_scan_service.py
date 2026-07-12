import json, struct, time
from combuddy import db, config, scan_service, stats

def _st(p, header):
    blob = json.dumps(header).encode(); p.write_bytes(struct.pack("<Q", len(blob)) + blob)

def test_run_scan_increments_revision(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    assert scan_service.STATUS["revision"] == 0
    scan_service.run_scan(conn)
    assert scan_service.STATUS["revision"] == 1

def test_run_scan_populates_everything(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    mroot = tmp_path / "models"; (mroot/"checkpoints"/"SD1.5").mkdir(parents=True)
    _st(mroot/"checkpoints"/"SD1.5"/"foo.safetensors",
        {"double_blocks.0.w": {"dtype":"F16","shape":[1],"data_offsets":[0,2]}})
    wroot = tmp_path / "wf"; wroot.mkdir()
    (wroot/"a.json").write_text(json.dumps({"nodes": [
        {"type": "CheckpointLoaderSimple", "widgets_values": ["SD1.5/foo.safetensors"]}]}))
    config.set_roots(conn, [
        {"kind":"model","path":str(mroot),"source":"manual"},
        {"kind":"workflow","path":str(wroot),"source":"manual"}])
    summary = scan_service.run_scan(conn)
    s = stats.get_stats(conn)
    assert s["model_count"] == 1
    assert s["base_coverage"] == {"done": 1, "total": 1}
    assert s["unreferenced_count"] == 0            # foo 被 a.json 引用
    assert scan_service.STATUS["running"] is False

def test_single_flight(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    scan_service.STATUS["running"] = True
    try:
        assert scan_service.run_scan(conn) == {"skipped": "already running"}
        assert scan_service.STATUS["revision"] == 0
    finally:
        scan_service.STATUS["running"] = False

def test_run_scan_skips_bad_workflow_root_and_continues(tmp_path):
    conn = db.connect(str(tmp_path/"c.sqlite")); db.init_schema(conn)
    mroot = tmp_path / "models"; (mroot/"checkpoints"/"SD1.5").mkdir(parents=True)
    _st(mroot/"checkpoints"/"SD1.5"/"foo.safetensors",
        {"double_blocks.0.w": {"dtype":"F16","shape":[1],"data_offsets":[0,2]}})
    good_wroot = tmp_path / "wf"; good_wroot.mkdir()
    (good_wroot/"a.json").write_text(json.dumps({"nodes": [
        {"type": "CheckpointLoaderSimple", "widgets_values": ["SD1.5/foo.safetensors"]}]}))
    bad_wroot = tmp_path / "gone"          # 不存在于磁盘上
    config.set_roots(conn, [
        {"kind":"model","path":str(mroot),"source":"manual"},
        {"kind":"workflow","path":str(good_wroot),"source":"manual"},
        {"kind":"workflow","path":str(bad_wroot),"source":"manual"}])
    scan_service.run_scan(conn)
    assert scan_service.STATUS["running"] is False
    s = stats.get_stats(conn)
    assert s["workflow_count"] == 1                 # 好 root 的 workflow 被处理
    assert s["unreferenced_count"] == 0              # foo 被 a.json 引用,ref 已解析
    assert scan_service.STATUS["errors"] >= 1        # 坏 root 记了错误,而不是中断整个扫描

def _one_model_root(conn, tmp_path):
    mroot = tmp_path / "models" / "checkpoints" / "SD1.5"; mroot.mkdir(parents=True)
    _st(mroot / "foo.safetensors",
        {"double_blocks.0.w": {"dtype": "F16", "shape": [1], "data_offsets": [0, 2]}})
    config.set_roots(conn, [{"kind": "model", "path": str(tmp_path / "models"), "source": "manual"}])

def test_run_scan_hashes_when_auto_on(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _one_model_root(conn, tmp_path)                 # auto_hash 默认开
    scan_service.run_scan(conn)
    sha = conn.execute("SELECT sha256 FROM models").fetchone()["sha256"]
    assert sha is not None and len(sha) == 64
    assert scan_service.STATUS["running"] is False

def test_run_scan_skips_hashing_when_auto_off(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _one_model_root(conn, tmp_path)
    config.set_settings(conn, {"auto_hash": False})
    scan_service.run_scan(conn)
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] is None

def test_run_scan_hashing_respects_cancel(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _one_model_root(conn, tmp_path)
    # 模拟扫描途中点取消:在 bases(enrich)阶段结束、hashing 门控之前置 cancel
    orig = scan_service.headers.enrich_models
    def _enrich_then_cancel(c, *a, **k):
        r = orig(c, *a, **k)
        scan_service.STATUS["cancel"] = True
        return r
    monkeypatch.setattr(scan_service.headers, "enrich_models", _enrich_then_cancel)
    scan_service.run_scan(conn)
    assert conn.execute("SELECT sha256 FROM models").fetchone()["sha256"] is None
    assert scan_service.STATUS["running"] is False

def test_run_scan_enriches_when_online_on(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _one_model_root(conn, tmp_path)                          # online_enrich 默认开
    calls = []
    monkeypatch.setattr(scan_service.civitai, "enrich_models",
                        lambda c, **k: calls.append(True) or {"found": 0, "checked": 0, "total": 0})
    scan_service.run_scan(conn)
    assert calls == [True] and scan_service.STATUS["running"] is False

def test_run_scan_skips_enrich_when_online_off(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _one_model_root(conn, tmp_path)
    config.set_settings(conn, {"online_enrich": False})
    calls = []
    monkeypatch.setattr(scan_service.civitai, "enrich_models", lambda c, **k: calls.append(True))
    scan_service.run_scan(conn)
    assert calls == []

def test_run_scan_enrich_respects_cancel(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    _one_model_root(conn, tmp_path)
    calls = []
    monkeypatch.setattr(scan_service.civitai, "enrich_models", lambda c, **k: calls.append(True))
    orig = scan_service.hashes.compute_hashes
    def _hash_then_cancel(c, **k):
        r = orig(c, **k); scan_service.STATUS["cancel"] = True; return r
    monkeypatch.setattr(scan_service.hashes, "compute_hashes", _hash_then_cancel)
    scan_service.run_scan(conn)
    assert calls == []                                      # hashing 后置 cancel → enrich 门控跳过
