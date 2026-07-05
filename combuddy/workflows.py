import json, os
from . import norm
from .scanner import MODEL_EXTS

SKIP_NODE_TYPES = {"MarkdownNote", "Note", "Reroute", "PrimitiveNode",
                   "PrimitiveString", "PrimitiveStringMultiline", "Comment"}

def _looks_like_model(v) -> bool:
    if not isinstance(v, str) or "\n" in v or len(v) > 300:
        return False
    return os.path.splitext(v)[1].lower() in MODEL_EXTS

def parse_workflow(path: str) -> tuple[list[dict], str | None]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"
    nodes = data.get("nodes") if isinstance(data, dict) else None
    if not isinstance(nodes, list):
        return [], "not a ui-graph workflow"
    seen: set[tuple[str, str | None]] = set()
    refs: list[dict] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        node_type = n.get("type")
        if node_type in SKIP_NODE_TYPES:
            continue
        wv = n.get("widgets_values")
        values = wv if isinstance(wv, list) else (list(wv.values()) if isinstance(wv, dict) else [])
        for v in values:
            if _looks_like_model(v):
                ref = norm.normalize_path(v)
                key = (ref, node_type)
                if key not in seen:
                    seen.add(key)
                    refs.append({"ref_string": ref, "node_type": node_type})
    return refs, None
