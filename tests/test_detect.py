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


def test_count_models_caps_at_limit(tmp_path):
    d = tmp_path / "checkpoints"; d.mkdir()
    for i in range(4):
        (d / f"m{i}.safetensors").write_bytes(b"x")
    n, capped = detect._count_models(str(tmp_path), cap=3)   # cap param exists
    assert n == 3 and capped is True


def test_count_models_soft_timeout_returns_none(tmp_path):
    d = tmp_path / "checkpoints"; d.mkdir()
    (d / "m.safetensors").write_bytes(b"x")
    n, capped = detect._count_models(str(tmp_path), budget_s=-1.0)  # deadline already passed
    assert n is None and capped is False


def test_count_models_entry_level_timeout_bounds_wide_dir(tmp_path, monkeypatch):
    # Regression guard for the entry-level check inside `for i, e in enumerate(it):`,
    # which is distinct from the outer per-directory check at the top of `while stack:`.
    # `test_count_models_soft_timeout_returns_none` above trips the OUTER check (deadline
    # already passed before scandir is even entered) and would stay green even if the
    # entry-level check were reverted away -- this test targets the inner one specifically.
    #
    # `_count_models` is called on `d` directly (not tmp_path), so exactly one directory
    # is ever pushed/popped: the outer per-directory check can fire only once, for `d`
    # itself. That rules out the outer check "covering" for a removed inner check by
    # tripping one level down (which is what happens if the 600 files sit in a subdirectory
    # of the scanned root -- the outer check for that subdirectory would consume the
    # past-deadline tick before the inner loop is ever reached, so both the current code
    # and a reverted-to-`for e in it:` version would return (None, False) alike).
    d = tmp_path / "checkpoints"; d.mkdir()
    for i in range(600):                     # >512 so the periodic entry-check is exercised
        (d / f"m{i}.safetensors").write_bytes(b"")
    # tick[0] deadline calc, tick[1] outer while-check (for popping `d`) -- both before
    # the deadline; tick[2] the in-loop check at i=0 sees a time far past it.
    ticks = iter([0.0, 0.0] + [100.0] * 50)
    monkeypatch.setattr(detect.time, "monotonic", lambda: next(ticks))
    n, capped = detect._count_models(str(d), budget_s=1.0)
    assert n is None and capped is False


def test_count_models_ioerror_returns_none(tmp_path):
    n, capped = detect._count_models(str(tmp_path / "does-not-exist"))
    assert n is None and capped is False


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


import textwrap


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text))


def test_config_base_path_models_becomes_candidate(tmp_path, monkeypatch):
    store = tmp_path / "central"
    for t in ("checkpoints", "loras"):
        os.makedirs(store / "models" / t)
    cfg = tmp_path / "extra_model_paths.yaml"
    _write(cfg, f"""
        comfyui:
          base_path: {store}
          checkpoints: models/checkpoints
          loras: models/loras
    """)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [str(cfg)])
    res = detect.sweep(set())
    paths = {c["path"] for c in res["candidates"]}
    assert os.path.realpath(str(store / "models")) in paths     # base_path/models canonical
    assert res["skipped_config_mappings"] == 0


def test_config_multiline_and_canonical_named_dirs(tmp_path, monkeypatch):
    base = tmp_path / "b"
    os.makedirs(base / "extra" / "loras")            # canonical basename 'loras'
    os.makedirs(base / "extra" / "vae")
    cfg = tmp_path / "extra_models_config.yaml"
    _write(cfg, f"""
        comfyui_desktop:
          base_path: {base}
          loras: |
            extra/loras
            extra/vae
    """)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [str(cfg)])
    res = detect.sweep(set())
    paths = {c["path"] for c in res["candidates"]}
    # each canonical-named mapped dir -> its parent (base/extra) is the model root
    assert os.path.realpath(str(base / "extra")) in paths


def test_config_a1111_noncanonical_skipped_and_counted(tmp_path, monkeypatch):
    a = tmp_path / "sd-webui"
    os.makedirs(a / "models" / "Stable-diffusion")
    os.makedirs(a / "models" / "Lora")
    cfg = tmp_path / "extra_model_paths.yaml"
    _write(cfg, f"""
        a1111:
          base_path: {a}
          checkpoints: models/Stable-diffusion
          loras: models/Lora
    """)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [str(cfg)])
    res = detect.sweep(set())
    assert res["candidates"] == []                   # nothing combuddy can scan correctly
    assert res["skipped_config_mappings"] == 2       # both non-canonical mappings surfaced as a hint


def test_config_custom_nodes_key_ignored(tmp_path, monkeypatch):
    base = tmp_path / "b"; os.makedirs(base / "custom_nodes")
    cfg = tmp_path / "extra_model_paths.yaml"
    _write(cfg, f"""
        comfyui:
          base_path: {base}
          custom_nodes: custom_nodes
    """)
    monkeypatch.setattr(detect, "_seed_locations", lambda: [])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [str(cfg)])
    res = detect.sweep(set())
    assert res["candidates"] == [] and res["skipped_config_mappings"] == 0   # custom_nodes never a model dir


def test_config_broken_yaml_is_silently_skipped(tmp_path, monkeypatch):
    cfg = tmp_path / "extra_model_paths.yaml"
    _write(cfg, "comfyui: : : not valid : yaml [")
    monkeypatch.setattr(detect, "_seed_locations", lambda: [])
    monkeypatch.setattr(detect, "_seed_config_files", lambda: [str(cfg)])
    res = detect.sweep(set())                        # must not raise
    assert res["candidates"] == [] and res["skipped_config_mappings"] == 0
