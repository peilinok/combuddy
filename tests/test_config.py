from combuddy import db, config

def test_detect_candidates_only_stats_given_paths(tmp_path):
    models = tmp_path / "share" / "models"; models.mkdir(parents=True)
    wf = tmp_path / "install" / "user" / "default" / "workflows"; wf.mkdir(parents=True)
    cands = config.detect_candidates(explicit=[str(models), str(wf), str(tmp_path / "missing")])
    kinds = {c["path"]: c["kind"] for c in cands}
    assert kinds[str(models)] == "model"
    assert kinds[str(wf)] == "workflow"
    assert str(tmp_path / "missing") not in kinds   # 不存在的不返回

def test_set_and_get_roots(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    config.set_roots(conn, [
        {"kind": "model", "path": "/a/models", "label": "share", "source": "manual"},
        {"kind": "workflow", "path": "/a/wf", "label": "wf", "source": "manual"},
    ])
    assert len(config.get_roots(conn, "model")) == 1
    assert len(config.get_roots(conn)) == 2
