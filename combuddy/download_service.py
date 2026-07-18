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
        if not config.get_settings(conn)["online_enrich"]:                        # 总闸,同 /api/locate [review I-1]
            return _fail("online_disabled")
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
    except Exception:
        # 未预期异常(os.makedirs/disk_usage/sqlite/Windows commonpath ValueError 等)不得静默崩掉后台线程、
        # 不设 error、留 .part;顶层兜底 fail-closed 成机器码 [review Important I-2]。pre-flight 阶段还没写盘,
        # 无 .part 需清——_download_and_import 自己的 try/except 才需要清。
        return _fail("network")
    finally:
        DOWNLOAD_STATUS.update(running=False, phase="idle", revision=DOWNLOAD_STATUS["revision"] + 1)

def _download_and_import(conn, spec, dest, sha, size):
    part = dest + ".part"
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        token = config.get_api_key(conn)                       # 只从此取,绝不经前端
        max_bytes = int(size * 1.05) if size > 0 else _DEFAULT_MAX_BYTES   # size=0 时兜底,勿 `or None` [H2]
        kind, got = civitai.download_file(
            spec["url"], part, token,
            progress=lambda d, t: DOWNLOAD_STATUS.update(downloaded=d, total=t),
            should_cancel=lambda: DOWNLOAD_STATUS["cancel"], max_bytes=max_bytes)
        if kind != "ok":
            _rm(part)
            return _fail("network" if kind == "error" else kind)   # auth/forbidden/cancelled/network
        if (got or "").lower() != sha:
            _rm(part)
            return _fail("sha_mismatch")
        if os.path.exists(dest) or DOWNLOAD_STATUS["cancel"]:       # rename 前再查 [L1/L6]
            _rm(part)
            return _fail("cancelled" if DOWNLOAD_STATUS["cancel"] else "exists")
        os.replace(part, dest)                                      # 原子入库
        conn.execute("UPDATE models SET sha256=? WHERE path=?", (sha, dest))  # 若已存行(极少);正常靠 run_scan
        conn.commit()
        DOWNLOAD_STATUS["phase"] = "importing"
        if not _ensure_scanned(conn):                               # 轮询确保 run_scan 跑完一次 [H1];耗尽则报 import_pending
            return _fail("import_pending")                          # 文件已下但入库未成(scan 持续忙),不删文件、报可区分状态
        conn.execute("UPDATE models SET sha256=? WHERE path=?", (sha, dest))  # scan 插行后写回已验证 sha [M2]
        conn.commit()
        return {"ok": True}
    except Exception:
        # os.makedirs/os.replace/sqlite 等未预期异常:.part 可能已写了部分字节,必须清,否则残留孤儿文件 [review I-2]
        _rm(part)
        return _fail("network")

def _rm(p):
    try: os.remove(p)
    except OSError: pass

def _ensure_scanned(conn, tries=60):
    # run_scan single-flight:若 scan 在跑则 skip;轮询等它落下再重试,确保文件真入库 [H1]
    for _ in range(tries):
        if not scan_service.run_scan(conn).get("skipped"):
            return True                      # 真跑完一次入库
        deadline = time.monotonic() + 5
        while scan_service.STATUS["running"] and time.monotonic() < deadline:
            time.sleep(0.05)
    return False                             # 耗尽,入库未成
