import json, struct, time
from combuddy import db, config, scan_service, stats

def _st(p, header):
    blob = json.dumps(header).encode(); p.write_bytes(struct.pack("<Q", len(blob)) + blob)

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
