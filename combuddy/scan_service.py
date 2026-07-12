import os, time, threading, sqlite3
from contextlib import contextmanager
from . import config, scanner, workflows, resolver, headers, hashes, civitai

STATUS = {"running": False, "phase": "idle", "models_found": 0,
          "bases_done": 0, "workflows_done": 0, "errors": 0,
          "hash_done": 0, "hash_total": 0, "enrich_done": 0, "enrich_total": 0,
          "cancel": False, "revision": 0}
_LOCK = threading.Lock()
_MUTATION_LOCK = threading.Lock()

@contextmanager
def mutation_guard(blocking: bool = True):
    acquired = _MUTATION_LOCK.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            _MUTATION_LOCK.release()

def run_scan(conn: sqlite3.Connection) -> dict:
    with _LOCK:
        if STATUS["running"]:
            return {"skipped": "already running"}
        STATUS.update(running=True, phase="scanning", models_found=0,
                      bases_done=0, workflows_done=0, errors=0,
                      hash_done=0, hash_total=0,
                      enrich_done=0, enrich_total=0, cancel=False)
    with mutation_guard():
        try:
            for root in config.get_roots(conn, "model"):
                scanner.scan_model_root(conn, root["id"], root["path"])
            STATUS["models_found"] = conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"]

            STATUS["phase"] = "workflows"
            for root in config.get_roots(conn, "workflow"):
                try:
                    for name in sorted(os.listdir(root["path"])):
                        if not name.endswith(".json"):
                            continue
                        path = os.path.join(root["path"], name)
                        try:
                            st = os.stat(path)
                            cur = conn.execute(
                                """INSERT INTO workflows(root_id,path,filename,mtime,last_scanned)
                                   VALUES(?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime,
                                   last_scanned=excluded.last_scanned RETURNING id""",
                                (root["id"], path, name, st.st_mtime, time.time()))
                            wf_id = cur.fetchone()["id"]
                            refs, err = workflows.parse_workflow(path)
                            conn.execute("UPDATE workflows SET parse_error=? WHERE id=?", (err, wf_id))
                            resolver.resolve_workflow(conn, wf_id, refs)
                        except OSError:
                            STATUS["errors"] += 1
                            continue
                        STATUS["workflows_done"] += 1
                except OSError:
                    STATUS["errors"] += 1
                    continue
            conn.commit()

            STATUS["phase"] = "bases"
            headers.enrich_models(conn)
            STATUS["bases_done"] = conn.execute(
                "SELECT COUNT(*) c FROM models WHERE base_arch IS NOT NULL").fetchone()["c"]

            cfg = config.get_settings(conn)
            if cfg["auto_hash"] and not STATUS["cancel"]:
                STATUS["phase"] = "hashing"
                hashes.compute_hashes(
                    conn, workers=cfg["hash_workers"], max_mbps=cfg["hash_max_mbps"],
                    progress=lambda d, t: STATUS.update(hash_done=d, hash_total=t),
                    should_cancel=lambda: STATUS["cancel"])

            if cfg["online_enrich"] and not STATUS["cancel"]:
                STATUS["phase"] = "enriching"
                civitai.enrich_models(
                    conn,
                    progress=lambda d, t: STATUS.update(enrich_done=d, enrich_total=t),
                    should_cancel=lambda: STATUS["cancel"])
            return {"models": STATUS["models_found"], "workflows": STATUS["workflows_done"]}
        finally:
            STATUS.update(running=False, phase="idle", revision=STATUS["revision"] + 1)
