import os, time, threading, sqlite3
from . import config, scanner, workflows, resolver, headers

STATUS = {"running": False, "phase": "idle", "models_found": 0,
          "bases_done": 0, "workflows_done": 0, "errors": 0}
_LOCK = threading.Lock()

def run_scan(conn: sqlite3.Connection) -> dict:
    with _LOCK:
        if STATUS["running"]:
            return {"skipped": "already running"}
        STATUS.update(running=True, phase="scanning", models_found=0,
                      bases_done=0, workflows_done=0, errors=0)
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
        return {"models": STATUS["models_found"], "workflows": STATUS["workflows_done"]}
    finally:
        STATUS.update(running=False, phase="idle")
