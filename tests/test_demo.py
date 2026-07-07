import os

from combuddy import db, queries, stats
from combuddy.demo import gen_previews, seed


def _seeded(tmp_path):
    conn = db.connect(str(tmp_path / "demo.sqlite"))
    db.init_schema(conn)
    seed.seed_demo(conn)
    return conn


def test_seed_creates_at_least_30_models(tmp_path):
    conn = _seeded(tmp_path)
    assert conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"] >= 30


def test_model_files_are_real_and_dup_groups_have_distinct_inodes(tmp_path):
    conn = _seeded(tmp_path)
    rows = conn.execute("SELECT path, sha256 FROM models").fetchall()
    for r in rows:
        assert os.path.isfile(r["path"])            # real file, not a placeholder string
    by_sha = {}
    for r in rows:
        by_sha.setdefault(r["sha256"], []).append(r["path"])
    for sha, paths in by_sha.items():
        if len(paths) < 2:
            continue
        inodes = {os.stat(p).st_ino for p in paths}
        assert len(inodes) == len(paths)             # distinct copies, never hardlinks


def test_has_multiple_duplicate_sha256_groups(tmp_path):
    conn = _seeded(tmp_path)
    groups = conn.execute(
        "SELECT sha256 FROM models WHERE sha256 IS NOT NULL GROUP BY sha256 HAVING COUNT(*)>=2"
    ).fetchall()
    assert 2 <= len(groups) <= 3                     # brief: 2-3 duplicate groups


def test_duplicate_groups_resolve_via_real_query_and_referenced_wins_keep(tmp_path):
    # Exercises the actual dedup query end to end: a stat() failure on any
    # member's `path` would silently drop the whole group from the result,
    # which is exactly the failure mode the real-placeholder-file setup
    # (rather than a fake path string) guards against.
    conn = _seeded(tmp_path)
    groups = queries.list_duplicate_groups(conn)
    assert len(groups) >= 2
    assert any(g["reclaimable"] > 0 for g in groups)
    referenced_groups = [g for g in groups if any(m["ref_count"] > 0 for m in g["members"])]
    assert referenced_groups, "no duplicate group has a referenced member"
    g = referenced_groups[0]
    keep = next(m for m in g["members"] if m["id"] == g["suggested_keep_id"])
    assert keep["ref_count"] > 0                     # referenced copy, not just the shallowest path


def test_civitai_found_rows_exist_without_image_path(tmp_path):
    conn = _seeded(tmp_path)
    rows = conn.execute("SELECT * FROM civitai WHERE found=1").fetchall()
    assert len(rows) >= 20                           # brief: ~24 identified
    for r in rows:
        assert r["name"]
        # image_path is deliberately left unset here: the demo preview
        # endpoint (a later task) maps sha256 -> bundled cover on its own.
        assert r["image_path"] is None


def test_bundled_preview_covers_exist(tmp_path):
    files = sorted(f for f in os.listdir(gen_previews.OUT_DIR) if f.endswith(".jpg"))
    assert len(files) == 8
    for f in files:
        assert os.path.getsize(os.path.join(gen_previews.OUT_DIR, f)) > 0


def test_has_missing_edge(tmp_path):
    conn = _seeded(tmp_path)
    edges = conn.execute("SELECT model_id, match_kind FROM edges").fetchall()
    assert any(e["model_id"] is None and e["match_kind"] != "ambiguous" for e in edges)


def test_has_ambiguous_edge(tmp_path):
    conn = _seeded(tmp_path)
    row = conn.execute("SELECT * FROM edges WHERE match_kind='ambiguous'").fetchone()
    assert row is not None and row["model_id"] is None


def test_workflow_resolution_shows_all_three_states(tmp_path):
    conn = _seeded(tmp_path)
    statuses = set()
    for w in queries.list_workflows(conn):
        res = queries.get_workflow_resolution(conn, w["id"])
        statuses |= {e["status"] for e in res["edges"]}
    assert {"path", "missing", "ambiguous"} <= statuses


def test_stats_smoke(tmp_path):
    conn = _seeded(tmp_path)
    s = stats.get_stats(conn)
    assert s["model_count"] >= 30
    assert s["duplicate_waste"] > 0
    assert s["civitai_coverage"]["identified"] >= 20
