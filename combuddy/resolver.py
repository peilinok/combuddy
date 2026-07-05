import os, sqlite3
from . import norm

NODE_DIR_TYPE = {
    "CheckpointLoaderSimple": "checkpoints", "CheckpointLoader": "checkpoints",
    "CheckpointLoader|pysssss": "checkpoints", "unCLIPCheckpointLoader": "checkpoints",
    "LoraLoader": "loras", "LoraLoaderModelOnly": "loras", "LoraLoader|pysssss": "loras",
    "VAELoader": "vae", "UpscaleModelLoader": "upscale_models",
    "ControlNetLoader": "controlnet", "ControlNetLoaderAdvanced": "controlnet",
    "CLIPVisionLoader": "clip_vision", "UNETLoader": "diffusion_models",
    "DualCLIPLoader": "text_encoders", "CLIPLoader": "text_encoders",
}

def _match(conn, ref_key, ref_base_key, dir_type):
    if dir_type:
        rows = conn.execute("SELECT id FROM models WHERE dir_type=? AND match_key=?",
                            (dir_type, ref_key)).fetchall()
    else:
        rows = conn.execute("SELECT id FROM models WHERE match_key=?", (ref_key,)).fetchall()
    if len(rows) == 1:
        return rows[0]["id"], "path"
    if len(rows) > 1:
        return None, "ambiguous"
    # basename 兜底
    if dir_type:
        rows = conn.execute("SELECT id FROM models WHERE dir_type=? AND name_key=?",
                            (dir_type, ref_base_key)).fetchall()
    else:
        rows = conn.execute("SELECT id FROM models WHERE name_key=?", (ref_base_key,)).fetchall()
    if len(rows) == 1:
        return rows[0]["id"], "basename"
    if len(rows) > 1:
        return None, "ambiguous"
    return None, None

def resolve_workflow(conn: sqlite3.Connection, workflow_id: int, refs: list[dict]) -> None:
    conn.execute("DELETE FROM edges WHERE workflow_id=?", (workflow_id,))
    for r in refs:
        ref = r["ref_string"]
        node_type = r.get("node_type")
        dir_type = NODE_DIR_TYPE.get(node_type) if node_type else None
        ref_key = norm.match_key(ref)
        ref_base_key = norm.match_key(os.path.basename(ref))
        model_id, kind = _match(conn, ref_key, ref_base_key, dir_type)
        conn.execute(
            """INSERT OR IGNORE INTO edges(workflow_id,ref_string,ref_key,ref_dir_type,
               node_type,model_id,match_kind) VALUES(?,?,?,?,?,?,?)""",
            (workflow_id, ref, ref_key, dir_type, node_type, model_id, kind))
    conn.execute("UPDATE workflows SET ref_count=? WHERE id=?", (len(refs), workflow_id))
    conn.commit()
