from combuddy import __main__ as m

def test_default_db_path_under_home():
    assert m.default_db_path().endswith("combuddy.sqlite")

def test_app_builds():
    app = m.build_app(db_path=":memory:", static_dir=None)
    assert any(r.path == "/api/stats" for r in app.routes)
