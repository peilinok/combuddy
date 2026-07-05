import os, time, shutil, sqlite3

TRASH_DIRNAME = ".combuddy-trash"

def _root_of(conn, model_id):
    r = conn.execute("""SELECT m.path, m.rel_path, m.dir_type, m.size, r.path root
                        FROM models m JOIN roots r ON r.id=m.root_id WHERE m.id=?""", (model_id,)).fetchone()
    return r

def move_to_trash(conn: sqlite3.Connection, model_ids) -> dict:
    model_ids = list(dict.fromkeys(model_ids))
    moved, skipped = [], []
    for mid in model_ids:
        # re-check 0 references at move time (TOCTOU guard)
        refs = conn.execute("SELECT COUNT(*) c FROM edges WHERE model_id=?", (mid,)).fetchone()["c"]
        r = _root_of(conn, mid)
        if refs > 0 or r is None or not os.path.exists(r["path"]):
            skipped.append(mid); continue
        tdir = os.path.join(r["root"], TRASH_DIRNAME, f"{int(time.time() * 1000)}_{mid}")
        dest = os.path.join(tdir, os.path.basename(r["path"]))
        try:
            os.makedirs(tdir, exist_ok=True)
            shutil.move(r["path"], dest)
        except OSError:
            skipped.append(mid); continue
        try:
            conn.execute("""INSERT INTO trash(model_path,rel_path,dir_type,size,trashed_at,trash_path)
                            VALUES(?,?,?,?,?,?)""",
                         (r["path"], r["rel_path"], r["dir_type"], r["size"], time.time(), dest))
            conn.execute("DELETE FROM models WHERE id=?", (mid,))
            conn.commit()
        except Exception:
            conn.rollback()
            shutil.move(dest, r["path"])  # undo the file move
            skipped.append(mid); continue
        moved.append(mid)
    return {"moved": moved, "skipped": skipped}

def list_trash(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM trash ORDER BY trashed_at DESC")]

def restore(conn, trash_ids) -> dict:
    restored, conflict, error = [], [], []
    for tid in trash_ids:
        r = conn.execute("SELECT * FROM trash WHERE id=?", (tid,)).fetchone()
        if not r:
            continue
        if os.path.exists(r["model_path"]):
            conflict.append(tid); continue
        try:
            os.makedirs(os.path.dirname(r["model_path"]), exist_ok=True)
            shutil.move(r["trash_path"], r["model_path"])
        except OSError:
            error.append(tid); continue
        conn.execute("DELETE FROM trash WHERE id=?", (tid,))
        conn.commit()
        restored.append(tid)
    return {"restored": restored, "conflict": conflict, "error": error}
