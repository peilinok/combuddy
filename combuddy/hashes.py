import hashlib, threading, time

_CHUNK = 8 << 20     # 8 MiB，与实测吞吐一致
_MAX_WORKERS = 8
_CANCELLED = object()

class _Throttle:
    """全局令牌桶：把累计已读字节配速到 max_mbps。max_mbps<=0 表示不限速。"""
    def __init__(self, max_mbps: int):
        self.bps = int(max_mbps) * 1_000_000 if max_mbps and max_mbps > 0 else 0
        self.lock = threading.Lock()
        self.start = time.monotonic()
        self.bytes = 0

    def account(self, n: int) -> None:
        if not self.bps:
            return
        with self.lock:
            self.bytes += n
            target = self.start + self.bytes / self.bps
            wait = target - time.monotonic()
        if wait > 0:
            time.sleep(wait)

def sha256_file(path, throttle=None, should_cancel=None):
    """流式 sha256。返回摘要 / None(读失败)/ _CANCELLED(仅当传入 should_cancel 且中途取消)。"""
    h = hashlib.sha256()
    try:
        with open(path, "rb", buffering=0) as f:
            while True:
                if should_cancel and should_cancel():
                    return _CANCELLED
                b = f.read(_CHUNK)
                if not b:
                    break
                h.update(b)
                if throttle:
                    throttle.account(len(b))
    except OSError:
        return None
    return h.hexdigest()

def compute_hashes(conn, workers=1, max_mbps=0, progress=None, should_cancel=None) -> dict:
    rows = conn.execute(
        "SELECT id, path FROM models WHERE sha256 IS NULL ORDER BY size").fetchall()
    total = len(rows)
    if progress:
        progress(0, total)
    workers = max(1, min(int(workers or 1), _MAX_WORKERS))
    throttle = _Throttle(max_mbps)
    write_lock = threading.Lock()
    state_lock = threading.Lock()
    idx_lock = threading.Lock()
    state = {"done": 0, "hashed": 0, "errors": 0, "cancelled": False}
    idx = {"i": 0}

    def next_row():
        with idx_lock:
            i = idx["i"]
            if i >= total:
                return None
            idx["i"] = i + 1
            return rows[i]

    def worker():
        while True:
            if should_cancel and should_cancel():
                with state_lock:
                    state["cancelled"] = True
                return
            r = next_row()
            if r is None:
                return
            res = sha256_file(r["path"], throttle, should_cancel)
            if res is _CANCELLED:
                with state_lock:
                    state["cancelled"] = True
                return
            with write_lock:
                if res is not None:
                    conn.execute("UPDATE models SET sha256=? WHERE id=?", (res, r["id"]))
                    conn.commit()               # 逐文件提交 → 断点续跑
            with state_lock:
                state["done"] += 1
                if res is None:
                    state["errors"] += 1
                else:
                    state["hashed"] += 1
                d = state["done"]
            if progress:
                progress(d, total)

    if workers == 1:
        worker()
    else:
        threads = [threading.Thread(target=worker) for _ in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    return {"hashed": state["hashed"], "errors": state["errors"],
            "total": total, "cancelled": state["cancelled"]}
