import json, struct
from combuddy import headers

def _write_st(p, header: dict):
    blob = json.dumps(header).encode("utf-8")
    p.write_bytes(struct.pack("<Q", len(blob)) + blob + b"\x00" * 8)

def test_base_from_modelspec_metadata(tmp_path):
    p = tmp_path / "m.safetensors"
    _write_st(p, {"__metadata__": {"modelspec.architecture": "stable-diffusion-xl-v1-base"},
                  "some.weight": {"dtype": "F16", "shape": [4], "data_offsets": [0, 8]}})
    assert headers.infer_base(str(p), "safetensors") == ("sdxl", "modelspec-metadata")

def test_base_from_flux_tensor_keys(tmp_path):
    p = tmp_path / "f.safetensors"
    _write_st(p, {"double_blocks.0.img_attn.qkv.weight": {"dtype": "F16", "shape": [1], "data_offsets": [0, 2]}})
    arch, src = headers.infer_base(str(p), "safetensors")
    assert arch == "flux" and src == "tensor-heuristic"

def test_oversized_header_is_unknown_not_crash(tmp_path):
    p = tmp_path / "big.safetensors"
    p.write_bytes(struct.pack("<Q", headers.HEADER_CAP + 1) + b"{}")
    assert headers.infer_base(str(p), "safetensors") == ("unknown", "")

def test_missing_file_is_unknown(tmp_path):
    assert headers.infer_base(str(tmp_path / "nope.safetensors"), "safetensors") == ("unknown", "")

def test_base_source_is_kohya_metadata_for_ss_base_model_version(tmp_path):
    p = tmp_path / "k.safetensors"
    _write_st(p, {"__metadata__": {"ss_base_model_version": "stable-diffusion-v1"}})
    arch, src = headers.infer_base(str(p), "safetensors")
    assert arch == "sd15" and src == "kohya-metadata"

def test_base_source_is_modelspec_metadata_for_modelspec_architecture(tmp_path):
    p = tmp_path / "s.safetensors"
    _write_st(p, {"__metadata__": {"modelspec.architecture": "stable-diffusion-v1"}})
    arch, src = headers.infer_base(str(p), "safetensors")
    assert arch == "sd15" and src == "modelspec-metadata"

def test_embedders_10_does_not_false_positive_as_sdxl(tmp_path):
    p = tmp_path / "trap.safetensors"
    _write_st(p, {"conditioner.embedders.10.x": {"dtype": "F16", "shape": [1], "data_offsets": [0, 2]}})
    assert headers.infer_base(str(p), "safetensors") == ("unknown", "")
