import os, time, sqlite3
from . import norm
from .trash import TRASH_DIRNAME

MODEL_EXTS = {".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin", ".onnx", ".sft"}
_EXCLUDE_NAMES = {".DS_Store"}

def is_model_file(name: str, size: int) -> bool:
    if size <= 0 or name in _EXCLUDE_NAMES or name.startswith("put_"):
        return False
    return os.path.splitext(name)[1].lower() in MODEL_EXTS

def _walk(root_path: str):
    stack = [root_path]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        if e.name == TRASH_DIRNAME:
                            continue
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=True):
                        yield e
        except (PermissionError, FileNotFoundError):
            continue

def scan_model_root(conn: sqlite3.Connection, root_id: int, root_path: str) -> dict:
    now = time.time()
    added = updated = skipped = excluded = 0
    for e in _walk(root_path):
        try:
            st = e.stat()
        except (FileNotFoundError, PermissionError):
            continue
        if not is_model_file(e.name, st.st_size):
            excluded += 1
            continue
        rel = norm.normalize_path(os.path.relpath(e.path, root_path))
        parts = rel.split("/", 1)
        dir_type = parts[0] if len(parts) > 1 else ""
        rel_in_type = parts[1] if len(parts) > 1 else parts[0]
        real = os.path.realpath(e.path)
        existing = conn.execute(
            "SELECT id, mtime, size FROM models WHERE path=?", (real,)).fetchone()
        if existing and existing["mtime"] == st.st_mtime and existing["size"] == st.st_size:
            conn.execute("UPDATE models SET last_scanned=? WHERE id=?", (now, existing["id"]))
            skipped += 1
            continue
        ext = os.path.splitext(e.name)[1].lower().lstrip(".")
        row = (root_id, real, rel, dir_type, rel_in_type, e.name, ext,
               st.st_size, st.st_mtime, norm.match_key(rel_in_type),
               norm.match_key(e.name), now, now)
        if existing:
            conn.execute(
                """UPDATE models SET root_id=?, rel_path=?, dir_type=?, rel_in_type=?,
                   filename=?, ext=?, size=?, mtime=?, match_key=?, name_key=?,
                   base_arch=NULL, base_source=NULL, precision=NULL, sha256=NULL, last_scanned=? WHERE path=?""",
                (root_id, rel, dir_type, rel_in_type, e.name, ext, st.st_size,
                 st.st_mtime, norm.match_key(rel_in_type), norm.match_key(e.name), now, real))
            updated += 1
        else:
            conn.execute(
                """INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,
                   ext,size,mtime,match_key,name_key,first_seen,last_scanned)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)
            added += 1
    conn.commit()
    return {"added": added, "updated": updated, "skipped": skipped, "excluded": excluded}
