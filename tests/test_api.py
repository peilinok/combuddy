from fastapi.testclient import TestClient
from combuddy import api, scan_service

def test_stats_and_scan_flow(tmp_path):
    app = api.create_app(str(tmp_path / "c.sqlite"))
    c = TestClient(app)
    # 配置 roots(空目录也行,重点测通路)
    (tmp_path / "m").mkdir(); (tmp_path / "w").mkdir()
    r = c.post("/api/roots", json={"roots": [
        {"kind": "model", "path": str(tmp_path/"m"), "source": "manual"},
        {"kind": "workflow", "path": str(tmp_path/"w"), "source": "manual"}]})
    assert r.status_code == 200
    assert len(c.get("/api/roots").json()["roots"]) == 2
    s = c.get("/api/stats").json()
    assert s["model_count"] == 0 and "scanning" in s
    assert c.post("/api/scan").json()["started"] is True

def test_scan_conflict_when_running(tmp_path):
    app = api.create_app(str(tmp_path / "c.sqlite")); c = TestClient(app)
    scan_service.STATUS["running"] = True
    try:
        assert c.post("/api/scan").json()["started"] is False
    finally:
        scan_service.STATUS["running"] = False

def test_stats_skips_duplicate_waste_while_scanning(tmp_path):
    app = api.create_app(str(tmp_path / "c.sqlite")); c = TestClient(app)
    assert c.get("/api/stats").json()["duplicate_waste"] == 0
    scan_service.STATUS["running"] = True
    try:
        assert c.get("/api/stats").json()["duplicate_waste"] is None
    finally:
        scan_service.STATUS["running"] = False

def test_stats_uses_consistent_scan_status_snapshot(tmp_path, monkeypatch):
    original_get_stats = api.stats.get_stats
    def finish_scan(conn, skip_duplicates=False):
        result = original_get_stats(conn, skip_duplicates=skip_duplicates)
        if skip_duplicates:
            scan_service.STATUS["running"] = False
        return result
    monkeypatch.setattr(api.stats, "get_stats", finish_scan)
    app = api.create_app(str(tmp_path / "c.sqlite")); c = TestClient(app)
    scan_service.STATUS["running"] = True
    try:
        s = c.get("/api/stats").json()
        assert s["duplicate_waste"] is None
        assert s["scanning"] is True
        assert s["scan"]["running"] is True
    finally:
        scan_service.STATUS["running"] = False
