from . import roles

def list_models(conn, search="", type_filter="", flag=""):
    sql = """SELECT m.*, (SELECT COUNT(DISTINCT workflow_id) FROM edges e WHERE e.model_id=m.id) ref_count
             FROM models m WHERE 1=1"""
    args = []
    if search:
        sql += " AND (m.filename LIKE ? OR m.display_name LIKE ?)"
        args += [f"%{search}%", f"%{search}%"]
    if type_filter:
        sql += " AND m.dir_type=?"; args.append(type_filter)
    sql += " ORDER BY m.size DESC"
    out = []
    for r in conn.execute(sql, args):
        d = dict(r)
        d["label"] = roles.label_for(r["base_arch"], r["dir_type"])
        if flag == "unreferenced" and d["ref_count"] > 0:
            continue
        if flag == "unknown" and d["label"] != "未识别":
            continue
        out.append(d)
    return out

def get_model_detail(conn, model_id):
    r = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["label"] = roles.label_for(r["base_arch"], r["dir_type"])
    d["workflows"] = [dict(w) for w in conn.execute(
        """SELECT DISTINCT w.id, w.filename FROM edges e JOIN workflows w ON w.id=e.workflow_id
           WHERE e.model_id=? ORDER BY w.filename""", (model_id,))]
    return d

def list_workflows(conn):
    return [dict(r) for r in conn.execute(
        """SELECT w.id, w.filename, w.ref_count, w.parse_error,
             (SELECT COUNT(*) FROM edges e WHERE e.workflow_id=w.id AND e.model_id IS NOT NULL) resolved,
             (SELECT COUNT(*) FROM edges e WHERE e.workflow_id=w.id AND e.model_id IS NULL) missing
           FROM workflows w ORDER BY w.filename""")]

def get_workflow_resolution(conn, workflow_id):
    w = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
    if not w:
        return None
    edges = []
    for e in conn.execute(
        """SELECT e.ref_string, e.node_type, e.match_kind, e.model_id, m.filename model_filename
           FROM edges e LEFT JOIN models m ON m.id=e.model_id WHERE e.workflow_id=?
           ORDER BY e.model_id IS NULL, e.ref_string""", (workflow_id,)):
        d = dict(e)
        d["status"] = "missing" if e["model_id"] is None and e["match_kind"] != "ambiguous" else (e["match_kind"] or "missing")
        edges.append(d)
    return {**dict(w), "edges": edges}
