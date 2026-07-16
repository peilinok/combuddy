import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import __version__, norm

MANIFEST_VERSION = 1
BODY_MAX = 10 * 1024 * 1024        # 上传体上限(压缩后)
MANIFEST_MAX = 4 * 1024 * 1024     # manifest.json 解压后上限 [H4]
MODELS_MAX = 10_000                # 条目数上限,防 N× SQL 放大 [M3]


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


def _read_manifest(body):
    """解析不可信 bundle。只按固定名读进内存、从不解包落盘 → zip-slip 不适用。"""
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
    except Exception:
        # ZipFile() 会解析整个中央目录(不止 manifest.json 那条),能抛的裸异常远不止
        # BadZipFile/OSError:UTF-8 标志位配非法文件名字节 → UnicodeDecodeError,
        # version-needed 超 MAX_EXTRACT_VERSION → NotImplementedError。理由同下方
        # 解压处:单行纯 stdlib 调用、不含本项目逻辑,故兜底而非维护必然遗漏的白名单。
        raise ManifestError("bad_zip")
    try:
        info = z.getinfo("manifest.json")
    except KeyError:
        raise ManifestError("missing_manifest")
    if info.file_size > MANIFEST_MAX:
        raise ManifestError("too_large")       # cheap 提前拒绝:file_size 是攻击者元数据
    try:
        with z.open("manifest.json") as fp:
            raw = fp.read(MANIFEST_MAX + 1)        # 有界解压:权威判据 [H4]
    except Exception:
        # 合法容器 + 恶意成员:损坏的 local header / 加密位 / 不支持的压缩方法 /
        # 谎报 file_size 致 CRC 失配 / 损坏的 DEFLATE 流(zlib.error)或 LZMA 流
        # (lzma.LZMAError)—— 后两者是裸 Exception 子类,接不住。枚举 stdlib 内部
        # 异常类型的白名单已两轮被 PoC 绕过,故兜底:这个 try 只包两行 stdlib 调用、
        # 不含本项目逻辑,不存在把编程错误误吞成 bad_zip 的风险。
        raise ManifestError("bad_zip")
    # 防御性冗余:ZipExtFile 按声明的 file_size 硬截断输出,故上面的 cheap 检查通过后
    # 这里理论不可达(谎报小 size 的包会先撞 CRC 失配 → bad_zip)。保留以防实现变化。
    if len(raw) > MANIFEST_MAX:
        raise ManifestError("too_large")
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        raise ManifestError("bad_json")
    if not isinstance(data, dict):
        raise ManifestError("bad_json")
    ver = data.get("combuddy_manifest")
    # bool 是 int 的子类,True 会骗过 isinstance(ver, int)
    if isinstance(ver, bool) or not isinstance(ver, int) or not 1 <= ver <= MANIFEST_VERSION:
        raise ManifestError("unsupported_version")
    models = data.get("models")
    if not isinstance(models, list):
        raise ManifestError("bad_json")
    if len(models) > MODELS_MAX:
        raise ManifestError("too_large")
    for m in models:                            # 结构校验必须在跑算法之前 [M2]
        if not isinstance(m, dict) or not isinstance(m.get("ref_string"), str):
            raise ManifestError("bad_json")
    return data


_SHA_RE = re.compile(r"[0-9a-fA-F]{64}")

# 多命中时裸 fetchone() 会让 SQLite 任意返回一行 → model_id 未定义、跨次不可复现。
# 与 queries._pick_keep 同精神:被引用优先 → 路径最浅 → 字典序 → first_seen [H2]
_ORDER = """ORDER BY (SELECT COUNT(*) FROM edges e WHERE e.model_id = m.id) DESC,
                     (LENGTH(m.rel_path) - LENGTH(REPLACE(m.rel_path, '/', ''))) ASC,
                     m.rel_path ASC, m.first_seen ASC, m.id ASC"""


def _safe_civitai_url(url):
    """bundle 不可信:只放行 https://civitai.com,其余(含 javascript: / 仿冒域)丢弃 [B1]"""
    if not isinstance(url, str) or not url:
        return None
    # 浏览器(WHATWG)对 http(s) 把 `\` 当 `/`、并在解析前 strip tab/LF/CR,而 urlparse 不会。
    # 这类分歧能让 "https://evil.tld\@civitai.com/" 骗过 hostname 检查却导航到 evil.tld。
    # 合法 civitai 链接不含反斜杠或控制字符,直接拒掉整个分歧输入面。
    if "\\" in url or any(ord(c) < 0x20 or ord(c) == 0x7f for c in url):
        return None
    try:
        p = urlparse(url)
    except ValueError:
        return None
    return url if (p.scheme == "https" and p.hostname == "civitai.com") else None


def _candidates(conn, entry):
    """按 dir_type + match_key 找候选,空了才退同 dir_type 内的 name_key。
    name_key 兜底绝不能丢 dir_type 约束,否则跨类型同名会假命中 [H1]。
    - dir_type 已知(非空字符串)→ 加约束;
    - dir_type 为 null(未指定)→ 裸 name_key 兜底;`WHERE dir_type=?` 传 None 是
      `= NULL` 恒 false,故用 Python 分支省略约束 [L11];
    - 其它非法值(空串 / 非 str,均属攻击者可控)→ 无候选,绝不当作「未指定」去跨类型匹配 [H1]。"""
    dt = entry.get("dir_type")
    mk = norm.match_key(entry["ref_string"])
    nk = norm.match_key(entry.get("filename") or os.path.basename(entry["ref_string"]))
    if isinstance(dt, str) and dt:
        rows = conn.execute(
            f"SELECT m.* FROM models m WHERE m.dir_type=? AND m.match_key=? {_ORDER}",
            (dt, mk)).fetchall()
        return rows or conn.execute(
            f"SELECT m.* FROM models m WHERE m.dir_type=? AND m.name_key=? {_ORDER}",
            (dt, nk)).fetchall()
    if dt is None:
        rows = conn.execute(f"SELECT m.* FROM models m WHERE m.match_key=? {_ORDER}", (mk,)).fetchall()
        return rows or conn.execute(
            f"SELECT m.* FROM models m WHERE m.name_key=? {_ORDER}", (nk,)).fetchall()
    return []
