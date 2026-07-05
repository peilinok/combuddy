import json, struct, time
from combuddy import db, headers

def _st(p, tensors: dict, meta: dict | None = None):
    hdr = dict(tensors)
    if meta is not None:
        hdr["__metadata__"] = meta
    blob = json.dumps(hdr).encode()
    p.write_bytes(struct.pack("<Q", len(blob)) + blob)

def test_extract_precision_and_params(tmp_path):
    p = tmp_path / "m.safetensors"
    _st(p, {"a.weight": {"dtype": "BF16", "shape": [2, 3], "data_offsets": [0, 12]},
            "b.weight": {"dtype": "BF16", "shape": [4], "data_offsets": [12, 20]}},
        {"modelspec.title": "My Model"})
    f = headers.extract_facts(str(p), "safetensors")
    assert f["precision"] == "bf16"
    assert f["param_count"] == 2 * 3 + 4        # 10
    assert f["display_name"] == "My Model"
    assert "modelspec.title" in (f["header_meta"] or "")

def test_extract_bad_file_all_none(tmp_path):
    f = headers.extract_facts(str(tmp_path / "nope.safetensors"), "safetensors")
    assert f == {"precision": None, "param_count": None, "display_name": None, "header_meta": None}

def test_enrich_models_fills_new_columns(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    p = tmp_path / "x.safetensors"
    _st(p, {"double_blocks.0.w": {"dtype": "F16", "shape": [2], "data_offsets": [0, 4]}}, {})
    conn.execute("INSERT INTO roots(id,kind,path,source) VALUES(1,'model','/r','manual')")
    conn.execute("""INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
        size,mtime,match_key,name_key,first_seen,last_scanned)
        VALUES(1,?,?,?,?,?,'safetensors',1,1,?,?,?,?)""",
        (str(p), "unet/x", "unet", "x", "x", "x", "x", time.time(), time.time()))
    conn.commit()
    n = headers.enrich_models(conn)
    row = conn.execute("SELECT base_arch, precision FROM models").fetchone()
    assert n == 1 and row["base_arch"] == "flux" and row["precision"] == "fp16"
