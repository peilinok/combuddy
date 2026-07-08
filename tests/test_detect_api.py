import os
from fastapi.testclient import TestClient
from combuddy import api, detect


def _client(tmp_path):
    return TestClient(api.create_app(str(tmp_path / "db.sqlite")))


def test_detect_endpoint_returns_candidates(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"
    for t in ("checkpoints", "loras"):
        os.makedirs(root / "models" / t)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [str(root)])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [])
    r = _client(tmp_path).get("/api/detect")
    assert r.status_code == 200
    body = r.json()
    assert any(c["source"] == "comfyui" for c in body["candidates"])
    assert body["skipped_config_mappings"] == 0


def test_detect_excludes_already_configured_roots(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"
    for t in ("checkpoints", "loras"):
        os.makedirs(root / "models" / t)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [str(root)])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [])
    c = _client(tmp_path)
    c.post("/api/roots", json={"roots": [
        {"kind": "model", "path": str(root / "models"), "source": "manual"}]})
    body = c.get("/api/detect").json()
    assert body["candidates"] == []          # the configured root is filtered server-side
