import json
from combuddy import workflows

def _wf(p, nodes):
    p.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")

def test_parse_known_loader_and_subdir(tmp_path):
    p = tmp_path / "a.json"
    _wf(p, [{"type": "CheckpointLoaderSimple", "widgets_values": ["SD1.5/动漫 primemix_v21.safetensors"]}])
    refs, err = workflows.parse_workflow(str(p))
    assert err is None
    assert {"ref_string": "SD1.5/动漫 primemix_v21.safetensors", "node_type": "CheckpointLoaderSimple"} in refs

def test_parse_backslash_and_multi_position(tmp_path):
    p = tmp_path / "b.json"
    _wf(p, [{"type": "DWPreprocessor", "widgets_values": [512, "x", 0.5, "y", "yolox_l.onnx", "dw\\ll.pt"]}])
    refs, err = workflows.parse_workflow(str(p))
    got = {r["ref_string"] for r in refs}
    assert "yolox_l.onnx" in got and "dw/ll.pt" in got     # 反斜杠归一化

def test_parse_bad_json_records_error(tmp_path):
    p = tmp_path / "c.json"; p.write_text("{not json", encoding="utf-8")
    refs, err = workflows.parse_workflow(str(p))
    assert refs == [] and err is not None

def test_skip_note_nodes(tmp_path):
    import json
    p = tmp_path / "n.json"
    p.write_text(json.dumps({"nodes": [
        {"type": "MarkdownNote", "widgets_values": ["用 taesd.safetensors 做预览。可选。"]},
        {"type": "CheckpointLoaderSimple", "widgets_values": ["real.safetensors"]}]}), encoding="utf-8")
    refs, err = workflows.parse_workflow(str(p))
    got = {r["ref_string"] for r in refs}
    assert "real.safetensors" in got
    assert not any("taesd" in g for g in got)   # note prose not extracted

def test_reject_prose_value(tmp_path):
    import json
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"nodes": [
        {"type": "SomeLoader", "widgets_values": ["see notes.\nload big.safetensors first"]}]}), encoding="utf-8")
    refs, _ = workflows.parse_workflow(str(p))
    assert refs == []   # value with newline/prose rejected
