import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import __version__, norm

MANIFEST_VERSION = 1


class ManifestError(Exception):
    """业务错误 → HTTP。reason 是稳定机器码,前端据此做 i18n 映射 [M9]"""

    def __init__(self, reason: str, status: int = 400):
        super().__init__(reason)
        self.reason = reason
        self.status = status


# 一条 JOIN 取全 manifest 所需列:get_workflow_resolution 不 SELECT sha256/
# ref_dir_type/rel_in_type/size/base_arch/civitai 任一列,复用它只会逼出 N+1 [M4]
_EDGE_SQL = """
SELECT e.ref_string, e.node_type, e.ref_dir_type, e.match_kind, e.model_id,
       m.sha256, m.filename, m.rel_in_type, m.size, m.base_arch,
       c.found civitai_found, c.name civitai_name,
       c.version_name civitai_version, c.civitai_url
FROM edges e
LEFT JOIN models m ON m.id = e.model_id
LEFT JOIN civitai c ON c.model_id = m.id
WHERE e.workflow_id = ?
ORDER BY e.ref_string
"""


def _lock_for(model_id, match_kind, sha256):
    """exact 是唯一可驱动 mismatch 的档:basename 是最弱的已绑定层,其 sha 可能
    pin 的是误命中的模型,故一律降为 weak [H3];ambiguous 保留源侧「有多个候选」
    的信号,不与 missing 一起塌缩成 expected [M5]。"""
    if model_id is not None:
        return "exact" if (match_kind == "path" and sha256) else "weak"
    return "ambiguous" if match_kind == "ambiguous" else "expected"


def _entry(r):
    e = {
        "ref_string": r["ref_string"],
        "node_type": r["node_type"],
        "dir_type": r["ref_dir_type"],
        "lock": _lock_for(r["model_id"], r["match_kind"], r["sha256"]),
        "filename": r["filename"] or os.path.basename(norm.normalize_path(r["ref_string"])),
    }
    if r["model_id"] is not None:
        e["match_kind"] = r["match_kind"]
        if r["sha256"]:
            e["sha256"] = r["sha256"]
        e["rel_in_type"] = r["rel_in_type"]
        e["size"] = r["size"]
        if r["base_arch"]:
            e["base_arch"] = r["base_arch"]
        if r["civitai_found"] and r["civitai_url"]:
            e["civitai"] = {"name": r["civitai_name"],
                            "version_name": r["civitai_version"],
                            "url": r["civitai_url"]}
    return e


def build_manifest(conn, wf):
    return {
        "combuddy_manifest": MANIFEST_VERSION,
        "generated_by": f"combuddy {__version__}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": {"filename": wf["filename"], "ref_count": wf["ref_count"]},
        "models": [_entry(r) for r in conn.execute(_EDGE_SQL, (wf["id"],))],
    }


def build_bundle(conn, workflow_id):
    wf = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
    if wf is None:
        raise ManifestError("not_found", 404)
    try:
        with open(wf["path"], "rb") as f:
            wf_bytes = f.read()
    except OSError:
        raise ManifestError("source_missing", 409)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json",
                   json.dumps(build_manifest(conn, wf), ensure_ascii=False, indent=2))
        z.writestr("workflow.json", wf_bytes)
    return buf.getvalue(), os.path.splitext(wf["filename"])[0]
