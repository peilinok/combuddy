import sqlite3

def get_stats(conn: sqlite3.Connection) -> dict:
    model_count = conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"]
    total_size = conn.execute("SELECT COALESCE(SUM(size),0) s FROM models").fetchone()["s"]
    workflow_count = conn.execute("SELECT COUNT(*) c FROM workflows").fetchone()["c"]
    done = conn.execute("SELECT COUNT(*) c FROM models WHERE base_arch IS NOT NULL").fetchone()["c"]
    hashed = conn.execute("SELECT COUNT(*) c FROM models WHERE sha256 IS NOT NULL").fetchone()["c"]
    by_type = [dict(r) for r in conn.execute(
        """SELECT dir_type, COUNT(*) count, COALESCE(SUM(size),0) size
           FROM models GROUP BY dir_type ORDER BY size DESC""")]
    unref = conn.execute(
        """SELECT COUNT(*) c FROM models m
           LEFT JOIN edges e ON e.model_id = m.id WHERE e.id IS NULL""").fetchone()["c"]
    return {
        "model_count": model_count, "total_size": total_size,
        "workflow_count": workflow_count,
        "base_coverage": {"done": done, "total": model_count},
        "hash_coverage": {"hashed": hashed, "total": model_count},
        "unreferenced_count": unref, "by_type": by_type,
    }

def get_unreferenced(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT m.* FROM models m
           LEFT JOIN edges e ON e.model_id = m.id
           WHERE e.id IS NULL ORDER BY m.size DESC""")]
