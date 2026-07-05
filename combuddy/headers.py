import json, struct, os, re

HEADER_CAP = 16 * 1024 * 1024
_GGUF_ARCH_MAP = {"flux": "flux", "sdxl": "sdxl", "sd1": "sd15", "sd3": "sd3"}
_GGUF_READ_CAP = 4 * 1024 * 1024  # 只读文件开头一段找 general.architecture

def read_safetensors_header(path: str) -> dict:
    with open(path, "rb") as f:
        n_bytes = f.read(8)
        if len(n_bytes) < 8:
            raise ValueError("truncated")
        n = struct.unpack("<Q", n_bytes)[0]
        if n <= 0 or n > HEADER_CAP:
            raise ValueError("header too large")
        blob = f.read(n)
        if len(blob) < n:
            raise ValueError("truncated header")
        return json.loads(blob)

_MODELSPEC = {
    "stable-diffusion-xl": "sdxl",
    "stable-diffusion-v1": "sd15",
    "flux": "flux",
    "stable-diffusion-3": "sd3",
}

_METADATA_SOURCE = {
    "modelspec.architecture": "modelspec-metadata",
    "modelspec.sai_model_spec": "modelspec-metadata",
    "ss_base_model_version": "kohya-metadata",
}

def _from_metadata(meta: dict) -> tuple[str, str] | None:
    for key in ("modelspec.architecture", "ss_base_model_version", "modelspec.sai_model_spec"):
        v = str(meta.get(key, "")).lower()
        for needle, arch in _MODELSPEC.items():
            if needle in v:
                return arch, _METADATA_SOURCE[key]
    return None

def _from_tensor_keys(header: dict) -> str | None:
    keys = [k for k in header.keys() if k != "__metadata__"]
    joined = "\n".join(keys)
    if "double_blocks." in joined or "single_blocks." in joined:
        return "flux"
    if "conditioner.embedders.1." in joined:  # 双 text encoder → SDXL
        return "sdxl"
    if "model.diffusion_model.input_blocks.0.0.weight" in joined:
        return "sd15"
    return None

def _gguf_read_string(buf, off):
    (n,) = struct.unpack_from("<Q", buf, off); off += 8
    s = buf[off:off + n].decode("utf-8", "replace"); off += n
    return s, off

# GGUF value type sizes for skipping non-string scalar values
_GGUF_SCALAR = {0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1,10:8,11:8,12:8}

def read_gguf_architecture(path: str) -> str | None:
    with open(path, "rb") as f:
        buf = f.read(_GGUF_READ_CAP)
    if buf[:4] != b"GGUF":
        return None
    try:
        off = 4
        (_ver,) = struct.unpack_from("<I", buf, off); off += 4
        off += 8                                    # tensor_count
        (kv_count,) = struct.unpack_from("<Q", buf, off); off += 8
        for _ in range(kv_count):
            key, off = _gguf_read_string(buf, off)
            (vtype,) = struct.unpack_from("<I", buf, off); off += 4
            if vtype == 8:                          # STRING
                val, off = _gguf_read_string(buf, off)
                if key == "general.architecture":
                    return val
            elif vtype in _GGUF_SCALAR:
                off += _GGUF_SCALAR[vtype]
            else:
                return None                         # 复杂/数组类型,放弃(general.architecture 通常在前)
        return None
    except (struct.error, UnicodeDecodeError, IndexError):
        return None

def _map_gguf_arch(arch: str) -> str:
    a = (arch or "").lower()
    for needle, base in _GGUF_ARCH_MAP.items():
        if needle in a:
            return base
    return a or "unknown"

def infer_base(path: str, ext: str) -> tuple[str, str]:
    try:
        if ext == "safetensors":
            header = read_safetensors_header(path)
            meta = header.get("__metadata__") or {}
            matched = _from_metadata(meta)
            if matched:
                return matched
            arch = _from_tensor_keys(header)
            if arch:
                return arch, "tensor-heuristic"
        elif ext == "gguf":
            arch = read_gguf_architecture(path)
            if arch:
                mapped = _map_gguf_arch(arch)
                if mapped != "unknown":
                    return mapped, "gguf-arch"
    except Exception:
        return "unknown", ""
    return "unknown", ""

def enrich_bases(conn, batch: int | None = None) -> int:
    q = "SELECT id, path, ext FROM models WHERE base_arch IS NULL"
    if batch:
        q += f" LIMIT {int(batch)}"
    rows = conn.execute(q).fetchall()
    for r in rows:
        arch, source = infer_base(r["path"], r["ext"])
        conn.execute("UPDATE models SET base_arch=?, base_source=? WHERE id=?",
                     (arch, source or None, r["id"]))
    conn.commit()
    return len(rows)

def read_gguf_value(path: str, want_key: str) -> str | None:
    with open(path, "rb") as f:
        buf = f.read(_GGUF_READ_CAP)
    if buf[:4] != b"GGUF":
        return None
    try:
        off = 4
        off += 4                                    # version
        off += 8                                    # tensor_count
        (kv_count,) = struct.unpack_from("<Q", buf, off); off += 8
        for _ in range(kv_count):
            key, off = _gguf_read_string(buf, off)
            (vtype,) = struct.unpack_from("<I", buf, off); off += 4
            if vtype == 8:
                val, off = _gguf_read_string(buf, off)
                if key == want_key:
                    return val
            elif vtype in _GGUF_SCALAR:
                off += _GGUF_SCALAR[vtype]
            else:
                return None
        return None
    except (struct.error, UnicodeDecodeError, IndexError):
        return None

_DTYPE_PRECISION = {"F16": "fp16", "BF16": "bf16", "F8_E4M3": "fp8", "F8_E5M2": "fp8",
                    "F32": "fp32", "F64": "fp64"}
_HEADER_META_CAP = 8000  # 存元数据 JSON 的长度上限

def _facts_from_safetensors(path: str) -> dict:
    header = read_safetensors_header(path)
    meta = header.get("__metadata__") or {}
    precision = None
    param_count = 0
    for k, v in header.items():
        if k == "__metadata__" or not isinstance(v, dict):
            continue
        if precision is None and isinstance(v.get("dtype"), str):
            precision = _DTYPE_PRECISION.get(v["dtype"])
        shape = v.get("shape")
        if isinstance(shape, list) and shape:
            n = 1
            for d in shape:
                n *= int(d)
            param_count += n
    display_name = meta.get("modelspec.title") or meta.get("ss_output_name") or None
    hm = json.dumps(meta)[:_HEADER_META_CAP] if meta else None
    return {"precision": precision, "param_count": param_count or None,
            "display_name": display_name, "header_meta": hm}

_QUANT_RE = re.compile(r"(Q\d[_A-Z0-9]*|F16|BF16|F32)", re.I)

def _facts_from_gguf(path: str) -> dict:
    name = read_gguf_value(path, "general.name")
    m = _QUANT_RE.search(os.path.basename(path))
    precision = m.group(1).upper() if m else None
    return {"precision": precision, "param_count": None,
            "display_name": name, "header_meta": None}

def extract_facts(path: str, ext: str) -> dict:
    empty = {"precision": None, "param_count": None, "display_name": None, "header_meta": None}
    try:
        if ext == "safetensors":
            return _facts_from_safetensors(path)
        if ext == "gguf":
            return _facts_from_gguf(path)
    except Exception:
        return empty
    return empty

def enrich_models(conn, batch: int | None = None) -> int:
    q = "SELECT id, path, ext FROM models WHERE base_arch IS NULL OR precision IS NULL"
    if batch:
        q += f" LIMIT {int(batch)}"
    rows = conn.execute(q).fetchall()
    for r in rows:
        arch, source = infer_base(r["path"], r["ext"])
        f = extract_facts(r["path"], r["ext"])
        conn.execute(
            """UPDATE models SET base_arch=?, base_source=?, precision=?, param_count=?,
               display_name=?, header_meta=? WHERE id=?""",
            (arch, source or None, f["precision"] or "unknown", f["param_count"],
             f["display_name"], f["header_meta"], r["id"]))
    conn.commit()
    return len(rows)
