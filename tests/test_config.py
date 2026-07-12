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
    m = tmp_path / "models"; m.mkdir(); w = tmp_path / "wf"; w.mkdir()
    config.set_roots(conn, [
        {"kind": "model", "path": str(m), "label": "share", "source": "manual"},
        {"kind": "workflow", "path": str(w), "label": "wf", "source": "manual"},
    ])
    assert len(config.get_roots(conn, "model")) == 1
    assert len(config.get_roots(conn)) == 2

def test_settings_defaults(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    assert config.get_settings(conn) == {"auto_hash": True, "hash_workers": 1, "hash_max_mbps": 0,
                                         "online_enrich": True, "nsfw_blur_threshold": 1}

def test_set_settings_partial_and_clamp(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    config.set_settings(conn, {"auto_hash": False, "hash_workers": 99, "hash_max_mbps": 50})
    assert config.get_settings(conn) == {"auto_hash": False, "hash_workers": 8, "hash_max_mbps": 50,
                                         "online_enrich": True, "nsfw_blur_threshold": 1}
    config.set_settings(conn, {"hash_workers": 0, "hash_max_mbps": -5})
    got = config.get_settings(conn)
    assert got["hash_workers"] == 1 and got["hash_max_mbps"] == 0
    assert got["auto_hash"] is False            # 未在本次 patch 中 → 保持上次

def test_settings_include_civitai_defaults(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    s = config.get_settings(conn)
    assert s["online_enrich"] is True and s["nsfw_blur_threshold"] == 1

def test_set_civitai_settings_and_clamp(tmp_path):
    conn = db.connect(str(tmp_path / "c.sqlite")); db.init_schema(conn)
    config.set_settings(conn, {"online_enrich": False, "nsfw_blur_threshold": 99})
    s = config.get_settings(conn)
    assert s["online_enrich"] is False and s["nsfw_blur_threshold"] == 32
    config.set_settings(conn, {"nsfw_blur_threshold": -5})
    assert config.get_settings(conn)["nsfw_blur_threshold"] == 0
