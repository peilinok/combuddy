import os, re, time, shutil, threading, sqlite3
from . import config, civitai, manifest, resolver, norm, scan_service

DOWNLOAD_STATUS = {"running": False, "phase": "idle", "filename": "", "downloaded": 0,
                   "total": 0, "error": None, "cancel": False, "revision": 0}
_LOCK = threading.Lock()
_SHA_RE = re.compile(r"[0-9a-fA-F]{64}")
_DISK_MARGIN = 64 * 1024 * 1024
_DEFAULT_MAX_BYTES = 50 * 1024 ** 3   # size_kb 缺失/0 时的硬上限兜底,防无界写盘 [H2]

def _fail(code):
    DOWNLOAD_STATUS.update(running=False, phase="idle", error=code)
    return {"error": code}

def start_download(conn: sqlite3.Connection, spec: dict) -> dict:
    with _LOCK:
        if DOWNLOAD_STATUS["running"]:
            return {"error": "already_running"}
        DOWNLOAD_STATUS.update(running=True, phase="checking", filename="",
                               downloaded=0, total=0, error=None, cancel=False)   # 起点复位 [H9]
    try:
        sha = spec.get("sha256", "")
        if not (isinstance(sha, str) and _SHA_RE.fullmatch(sha)):
            return _fail("bad_request")
        sha = sha.lower()
        # 不可信 HTTP body:字段类型畸形须返机器码而非崩溃(fail-closed)[review Important]
        if not isinstance(spec.get("ref_string"), str) or not isinstance(spec.get("dir_type"), str) \
           or isinstance(spec.get("size_kb"), bool) or not isinstance(spec.get("size_kb"), (int, float)):
            return _fail("bad_request")
        if manifest._safe_civitai_url(spec.get("url")) is None:                   # 域复校验 [B4]
            return _fail("bad_url")
        dir_type = spec.get("dir_type")
        if dir_type not in set(resolver.NODE_DIR_TYPE.values()):                  # dir_type 白名单
            return _fail("path_unsafe")
        root = conn.execute("SELECT path FROM roots WHERE id=? AND kind='model' AND enabled=1",
                            (spec.get("root_id"),)).fetchone()
        if root is None:
            return _fail("root_not_found")
        droot = os.path.realpath(root["path"])
        dest = os.path.realpath(os.path.join(droot, dir_type, norm.normalize_path(spec.get("ref_string", ""))))
        if os.path.commonpath([droot, dest]) != droot:                           # 前缀碰撞 [H4]
            return _fail("path_unsafe")
        if os.path.exists(dest):
            return _fail("exists")
        size = int((spec.get("size_kb") or 0) * 1024)
        if shutil.disk_usage(droot).free < size + _DISK_MARGIN:
            return _fail("disk_full")
        DOWNLOAD_STATUS.update(phase="downloading", filename=os.path.basename(dest))
        return _download_and_import(conn, spec, dest, sha, size)   # Task 5 填充;本 task 先 stub 成功
    finally:
        DOWNLOAD_STATUS.update(running=False, phase="idle", revision=DOWNLOAD_STATUS["revision"] + 1)

def _download_and_import(conn, spec, dest, sha, size):
    # Task 5 实现;本 task 临时:直接返回 ok 以让前置校验测试通过
    return {"ok": True}
