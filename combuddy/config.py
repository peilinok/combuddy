import os, sqlite3

# 只 stat 这些已知精确路径的相对形态;绝不递归遍历。
def _classify(path: str) -> str | None:
    base = os.path.basename(path.rstrip("/"))
    if base == "workflows":
        return "workflow"
    if base == "models":
        return "model"
    # models 目录也可能直接被指认;有典型子目录则认作 model root
    if os.path.isdir(os.path.join(path, "checkpoints")) or os.path.isdir(os.path.join(path, "loras")):
        return "model"
    return None

def detect_candidates(explicit: list[str] | None = None) -> list[dict]:
    out: list[dict] = []
    for p in (explicit or []):
        rp = os.path.realpath(p)
        if not os.path.isdir(rp):
            continue
        kind = _classify(rp)
        if kind is None:
            continue
        out.append({"kind": kind, "path": rp, "label": os.path.basename(rp) or rp, "source": "manual"})
    return out

def set_roots(conn: sqlite3.Connection, roots: list[dict]) -> None:
    for r in roots:
        conn.execute(
            "INSERT OR IGNORE INTO roots(kind,path,label,source,enabled) VALUES(?,?,?,?,1)",
            (r["kind"], os.path.realpath(r["path"]), r.get("label"), r.get("source", "manual")),
        )
    conn.commit()

def get_roots(conn: sqlite3.Connection, kind: str | None = None) -> list[sqlite3.Row]:
    if kind:
        return conn.execute("SELECT * FROM roots WHERE kind=? AND enabled=1", (kind,)).fetchall()
    return conn.execute("SELECT * FROM roots WHERE enabled=1").fetchall()

def get_settings(conn: sqlite3.Connection) -> dict:
    have = {r["key"]: r["value"] for r in conn.execute(
        "SELECT key,value FROM meta WHERE key IN ('auto_hash','hash_workers','hash_max_mbps')")}
    return {
        "auto_hash": have.get("auto_hash", "1") == "1",
        "hash_workers": int(have.get("hash_workers", "1")),
        "hash_max_mbps": int(have.get("hash_max_mbps", "0")),
    }

def set_settings(conn: sqlite3.Connection, values: dict) -> None:
    if "auto_hash" in values:
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('auto_hash',?)",
                     ("1" if values["auto_hash"] else "0",))
    if "hash_workers" in values:
        w = max(1, min(int(values["hash_workers"]), 8))
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('hash_workers',?)", (str(w),))
    if "hash_max_mbps" in values:
        m = max(0, int(values["hash_max_mbps"]))
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('hash_max_mbps',?)", (str(m),))
    conn.commit()
