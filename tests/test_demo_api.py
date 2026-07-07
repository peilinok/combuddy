from fastapi.testclient import TestClient

from combuddy import api, db, scan_service
from combuddy.demo import seed


def _seed_demo_db(tmp_path) -> str:
    dbp = str(tmp_path / "demo.sqlite")
    conn = db.connect(dbp)
    db.init_schema(conn)
    seed.seed_demo(conn)
    conn.close()
    return dbp


def test_stats_reports_demo_true_with_seeded_data(tmp_path):
    c = TestClient(api.create_app(_seed_demo_db(tmp_path), demo=True))
    s = c.get("/api/stats").json()
    assert s["demo"] is True
    assert s["model_count"] >= 30


def test_scan_is_a_noop_in_demo_mode(tmp_path):
    c = TestClient(api.create_app(_seed_demo_db(tmp_path), demo=True))
    scan_service.STATUS["running"] = False
    r = c.post("/api/scan")
    assert r.json() == {"started": False, "demo": True}
    assert scan_service.STATUS["running"] is False  # no background scan thread started


def test_preview_returns_bundled_cover_for_any_valid_hash_in_demo_mode(tmp_path):
    c = TestClient(api.create_app(_seed_demo_db(tmp_path), demo=True))
    r = c.get(f"/api/preview/{'a' * 64}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"


def test_preview_ignores_hd_param_in_demo_mode(tmp_path):
    c = TestClient(api.create_app(_seed_demo_db(tmp_path), demo=True))
    plain = c.get(f"/api/preview/{'a' * 64}")
    hd = c.get(f"/api/preview/{'a' * 64}?hd=1")
    assert plain.content == hd.content


def test_preview_still_validates_hash_shape_in_demo_mode(tmp_path):
    c = TestClient(api.create_app(_seed_demo_db(tmp_path), demo=True))
    r = c.get("/api/preview/not-a-valid-hash")
    assert r.status_code == 404


def test_stats_reports_demo_false_by_default(tmp_path):
    c = TestClient(api.create_app(_seed_demo_db(tmp_path)))
    assert c.get("/api/stats").json()["demo"] is False


def test_preview_unknown_hash_still_404s_without_demo(tmp_path):
    c = TestClient(api.create_app(_seed_demo_db(tmp_path)))
    r = c.get(f"/api/preview/{'a' * 64}")
    assert r.status_code == 404
    assert r.json() == {"error": "not found"}
