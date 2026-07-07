import os
from . import roles

def list_models(conn, search="", type_filter="", flag=""):
    sql = """SELECT m.*, (SELECT COUNT(DISTINCT workflow_id) FROM edges e WHERE e.model_id=m.id) ref_count,
                    c.found civitai_found, c.name civitai_name, c.base_model civitai_base,
                    c.model_type civitai_type, c.trigger_words, c.nsfw_level, c.civitai_url,
                    (c.image_path IS NOT NULL) has_preview
             FROM models m LEFT JOIN civitai c ON c.model_id=m.id WHERE 1=1"""
    args = []
    if search:
        sql += " AND (m.filename LIKE ? OR m.display_name LIKE ? OR c.name LIKE ?)"
        args += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if type_filter:
        sql += " AND m.dir_type=?"; args.append(type_filter)
    sql += " ORDER BY m.size DESC"
    out = []
    for r in conn.execute(sql, args):
        d = dict(r)
        d["label"] = roles.label_for(r["base_arch"], r["dir_type"])
        if flag == "unreferenced" and d["ref_count"] > 0:
            continue
        if flag == "unknown" and (d["label"] != "未识别" or d["civitai_found"]):
            continue
        out.append(d)
    return out

def get_model_detail(conn, model_id):
    r = conn.execute(
        """SELECT m.*, c.found civitai_found, c.name civitai_name, c.version_name civitai_version,
                  c.base_model civitai_base, c.model_type civitai_type, c.trigger_words,
                  c.nsfw_level, c.civitai_url, (c.image_path IS NOT NULL) has_preview
           FROM models m LEFT JOIN civitai c ON c.model_id=m.id WHERE m.id=?""", (model_id,)).fetchone()
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

def _pick_keep(members):
    # members 已按 first_seen 升序;被引用优先(取最早),否则路径层级最浅→字典序→first_seen
    referenced = [m for m in members if m["ref_count"] > 0]
    if referenced:
        return referenced[0]
    return min(members, key=lambda m: (m["rel_path"].count("/"), m["rel_path"], m["first_seen"]))

_MEMBER_KEYS = ("id", "path", "rel_path", "dir_type", "filename", "size",
                "ref_count", "root_label", "root_path", "inode", "deletable")

def _member_out(m):
    return {k: m[k] for k in _MEMBER_KEYS}

def list_duplicate_groups(conn):
    rows = conn.execute("""
        SELECT m.id, m.sha256, m.path, m.rel_path, m.dir_type, m.filename, m.size, m.first_seen,
               r.path root_path, COALESCE(r.label, r.path) root_label,
               (SELECT COUNT(DISTINCT workflow_id) FROM edges e WHERE e.model_id=m.id) ref_count
        FROM models m JOIN roots r ON r.id=m.root_id
        WHERE m.sha256 IN (SELECT sha256 FROM models WHERE sha256 IS NOT NULL
                           GROUP BY sha256 HAVING COUNT(*) > 1)
        ORDER BY m.sha256, m.first_seen
    """).fetchall()
    by_sha = {}
    for r in rows:
        by_sha.setdefault(r["sha256"], []).append(dict(r))
    groups = []
    for sha, members in by_sha.items():
        for m in members:
            try:
                st = os.stat(m["path"]); m["inode"] = f"{st.st_dev}:{st.st_ino}"
            except OSError:
                m["inode"] = None
        keep = _pick_keep(members)
        if keep["inode"] is None:            # keep 候选 stat 失败 → 整组跳过
            continue
        members = [m for m in members if m["inode"] is not None]
        keep_inode = keep["inode"]
        for m in members:
            m["deletable"] = (m["ref_count"] == 0 and m["inode"] != keep_inode)
        seen, reclaimable = set(), 0
        for m in members:
            if m["deletable"] and m["id"] != keep["id"] and m["inode"] not in seen:
                seen.add(m["inode"]); reclaimable += m["size"]
        groups.append({
            "sha256": sha, "size": members[0]["size"], "count": len(members),
            "reclaimable": reclaimable, "suggested_keep_id": keep["id"],
            "members": [_member_out(m) for m in members],
        })
    groups.sort(key=lambda g: g["reclaimable"], reverse=True)
    return groups
