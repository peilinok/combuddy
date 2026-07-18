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

def set_roots(conn: sqlite3.Connection, roots: list[dict]) -> list[dict]:
    results = []
    for r in roots:
        real = os.path.realpath(r["path"])
        if not os.path.isdir(real):
            results.append({"path": r["path"], "ok": False, "reason": "not_a_directory"})
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO roots(kind,path,label,source,enabled) VALUES(?,?,?,?,1)",
            (r["kind"], real, r.get("label"), r.get("source", "manual")),
        )
        results.append({"path": r["path"], "ok": cur.rowcount > 0,
                        "reason": None if cur.rowcount > 0 else "duplicate"})
    conn.commit()
    return results

def remove_root(conn: sqlite3.Connection, root_id: int) -> bool:
    if conn.execute("SELECT id FROM roots WHERE id=?", (root_id,)).fetchone() is None:
        return False
    mids = [r["id"] for r in conn.execute("SELECT id FROM models WHERE root_id=?", (root_id,))]
    if mids:
        ph = ",".join("?" * len(mids))
        # 先解除边绑定(edges.model_id 无级联;引用回归 missing 语义),再删模型(civitai 级联删除)
        conn.execute(f"UPDATE edges SET model_id=NULL, match_kind=NULL WHERE model_id IN ({ph})", mids)
        conn.execute(f"DELETE FROM models WHERE id IN ({ph})", mids)
    wids = [r["id"] for r in conn.execute("SELECT id FROM workflows WHERE root_id=?", (root_id,))]
    if wids:
        ph = ",".join("?" * len(wids))
        conn.execute(f"DELETE FROM edges WHERE workflow_id IN ({ph})", wids)
        conn.execute(f"DELETE FROM workflows WHERE id IN ({ph})", wids)
    # 物理删除而非 enabled=0:path 有 UNIQUE 约束,软停用会让同一路径永远无法重新添加
    conn.execute("DELETE FROM roots WHERE id=?", (root_id,))
    conn.commit()
    return True

def get_roots(conn: sqlite3.Connection, kind: str | None = None) -> list[sqlite3.Row]:
    if kind:
        return conn.execute("SELECT * FROM roots WHERE kind=? AND enabled=1", (kind,)).fetchall()
    return conn.execute("SELECT * FROM roots WHERE enabled=1").fetchall()

def get_settings(conn: sqlite3.Connection) -> dict:
    have = {r["key"]: r["value"] for r in conn.execute(
        """SELECT key,value FROM meta WHERE key IN
           ('auto_hash','hash_workers','hash_max_mbps','online_enrich','nsfw_blur_threshold')""")}
    return {
        "auto_hash": have.get("auto_hash", "1") == "1",
        "hash_workers": int(have.get("hash_workers", "1")),
        "hash_max_mbps": int(have.get("hash_max_mbps", "0")),
        "online_enrich": have.get("online_enrich", "1") == "1",
        "nsfw_blur_threshold": int(have.get("nsfw_blur_threshold", "1")),
    }

def get_api_key(conn: sqlite3.Connection) -> str:
    r = conn.execute("SELECT value FROM meta WHERE key='civitai_api_key'").fetchone()
    return r["value"] if r else ""

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
    if "online_enrich" in values:
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('online_enrich',?)",
                     ("1" if values["online_enrich"] else "0",))
    if "nsfw_blur_threshold" in values:
        t = max(0, min(int(values["nsfw_blur_threshold"]), 32))
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('nsfw_blur_threshold',?)", (str(t),))
    if "civitai_api_key" in values:
        v = values["civitai_api_key"]
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('civitai_api_key',?)",
                     (v if isinstance(v, str) else "",))
    conn.commit()
