import struct
from combuddy import headers

def _write_gguf(p, arch: str):
    # 最小 GGUF:magic, version=3, tensor_count=0, kv_count=1, 一条 general.architecture=string
    out = b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0) + struct.pack("<Q", 1)
    key = b"general.architecture"
    out += struct.pack("<Q", len(key)) + key
    out += struct.pack("<I", 8)                       # value type 8 = STRING
    out += struct.pack("<Q", len(arch)) + arch.encode()
    p.write_bytes(out)

def test_gguf_architecture(tmp_path):
    p = tmp_path / "m.gguf"; _write_gguf(p, "flux")
    assert headers.read_gguf_architecture(str(p)) == "flux"
    assert headers.infer_base(str(p), "gguf") == ("flux", "gguf-arch")

def test_gguf_bad_magic_is_unknown_not_crash(tmp_path):
    p = tmp_path / "x.gguf"; p.write_bytes(b"NOPE" + b"\x00" * 32)
    assert headers.infer_base(str(p), "gguf") == ("unknown", "")

def test_gguf_truncated_kv_is_none_not_crash(tmp_path):
    p = tmp_path / "trunc.gguf"
    # Valid header: magic + version + tensor_count=0 + kv_count=1, but NO following KV bytes
    out = b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0) + struct.pack("<Q", 1)
    p.write_bytes(out)
    assert headers.read_gguf_architecture(str(p)) is None
    assert headers.infer_base(str(p), "gguf") == ("unknown", "")
