import os
from combuddy import detect
from combuddy.roles import KNOWN_DIR_TYPES


def _mk_comfy(root, types=("checkpoints", "loras"), with_wf=True):
    for t in types:
        os.makedirs(os.path.join(root, "models", t), exist_ok=True)
    if with_wf:
        os.makedirs(os.path.join(root, "user", "default", "workflows"), exist_ok=True)


def test_known_dir_types_has_18():
    assert {"checkpoints", "loras", "vae", "text_encoders"} <= KNOWN_DIR_TYPES
    assert len(KNOWN_DIR_TYPES) == 18


def test_canonical_children_needs_two_known(tmp_path):
    root = tmp_path / "c"; _mk_comfy(str(root));
    assert detect._has_canonical_children(str(root / "models")) is True
    one = tmp_path / "one"; os.makedirs(one / "checkpoints")
    assert detect._has_canonical_children(str(one)) is False   # <2 known


def test_count_models_counts_and_caps(tmp_path):
    d = tmp_path / "models" / "checkpoints"; d.mkdir(parents=True)
    for i in range(3):
        (d / f"m{i}.safetensors").write_bytes(b"x")
    (d / "note.txt").write_text("no")           # non-model ext ignored
    n, capped = detect._count_models(str(tmp_path / "models"))
    assert n == 3 and capped is False


def test_count_models_skips_trash(tmp_path):
    d = tmp_path / "checkpoints"; d.mkdir(parents=True)
    (d / "a.safetensors").write_bytes(b"x")
    trash = tmp_path / ".combuddy-trash"; trash.mkdir()
    (trash / "b.safetensors").write_bytes(b"x")
    n, _ = detect._count_models(str(tmp_path))
    assert n == 1                                # trashed file not counted


def test_sweep_finds_comfyui_install_model_and_workflow(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"; _mk_comfy(str(root))
    (root / "models" / "checkpoints" / "a.safetensors").write_bytes(b"x")
    monkeypatch.setattr(detect, "_seed_locations", lambda: [str(root)])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [])
    res = detect.sweep(set())
    kinds = {c["kind"]: c for c in res["candidates"]}
    assert kinds["model"]["path"] == os.path.realpath(str(root / "models"))
    assert kinds["model"]["source"] == "comfyui" and kinds["model"]["model_count"] == 1
    assert kinds["workflow"]["path"] == os.path.realpath(str(root / "user" / "default" / "workflows"))
    assert res["skipped_config_mappings"] == 0


def test_sweep_bare_model_library(tmp_path, monkeypatch):
    root = tmp_path / "Shared" / "models"
    for t in ("checkpoints", "vae"):
        os.makedirs(root / t)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [str(root)])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [])
    res = detect.sweep(set())
    assert [c["source"] for c in res["candidates"]] == ["bare"]
    assert res["candidates"][0]["path"] == os.path.realpath(str(root))


def test_sweep_excludes_configured_roots(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"; _mk_comfy(str(root), with_wf=False)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [str(root)])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [])
    already = {os.path.realpath(str(root / "models")).casefold()}
    res = detect.sweep(already)
    assert res["candidates"] == []               # the one model candidate is filtered out
