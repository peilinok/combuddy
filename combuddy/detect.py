"""Zero-config detection: read-only, candidates-only, never writes the DB.

Finds ComfyUI installs / shared model libraries / config-declared dirs at a
fixed set of well-known locations (never a full-disk search). model_count is a
bounded, soft-timeout best-effort label. The caller (GET /api/detect) passes the
set of already-configured root realpaths so both RootsSetup and SettingsView get
the same filtered result.
"""
import os
import sys
import time

from .roles import KNOWN_DIR_TYPES
from .scanner import MODEL_EXTS
from .trash import TRASH_DIRNAME


def _has_canonical_children(p: str) -> bool:
    """True iff >=2 immediate subdirs are known dir_types (casefolded)."""
    hits = 0
    try:
        with os.scandir(p) as it:
            for e in it:
                if e.is_dir(follow_symlinks=False) and e.name.casefold() in KNOWN_DIR_TYPES:
                    hits += 1
                    if hits >= 2:
                        return True
    except OSError:
        return False
    return False


def _count_models(path, cap=1000, max_depth=4, budget_s=1.0):
    """(count, capped). Bounded (depth+cap) + soft-timeout, checked between entries
    (every 512 entries, so a single wide/flat directory is still bounded by budget_s)
    and once per directory popped.
    (None, False) on IO error or budget exceeded before finishing -> UI shows "若干"."""
    deadline = time.monotonic() + budget_s
    count = 0
    stack = [(path, 0)]
    while stack:
        if time.monotonic() > deadline:
            return (None, False)
        d, depth = stack.pop()
        try:
            with os.scandir(d) as it:
                for i, e in enumerate(it):
                    if (i & 0x1FF) == 0 and time.monotonic() > deadline:
                        return (None, False)
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.name == TRASH_DIRNAME or depth >= max_depth:
                                continue
                            stack.append((e.path, depth + 1))
                        elif e.is_file(follow_symlinks=True):
                            if os.path.splitext(e.name)[1].lower() in MODEL_EXTS:
                                count += 1
                                if count >= cap:
                                    return (cap, True)
                    except OSError:
                        continue
        except OSError:
            return (None, False)
    return (count, False)


def _short(p: str) -> str:
    home = os.path.expanduser("~")
    return "~" + p[len(home):] if p.startswith(home) else p


def _seed_locations() -> list[str]:
    """Well-known ComfyUI install roots (and StabilityMatrix containers)."""
    h = os.path.expanduser("~")
    seeds = [os.path.join(h, "ComfyUI"), os.path.join(h, "comfyui"),
             os.path.join(h, "Documents", "ComfyUI")]
    if os.name == "nt":
        seeds += [r"C:\ComfyUI_windows_portable\ComfyUI",
                  r"D:\ComfyUI_windows_portable\ComfyUI",
                  os.path.join(h, "ComfyUI_windows_portable", "ComfyUI")]
    return seeds


def _seed_config_files() -> list[str]:
    """Official Comfy Desktop user-dir config file (parsed in Task 3)."""
    h = os.path.expanduser("~")
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.join(h, "AppData", "Roaming"))
        return [os.path.join(base, "ComfyUI", "extra_models_config.yaml")]
    if sys.platform == "darwin":
        return [os.path.join(h, "Library", "Application Support", "ComfyUI", "extra_models_config.yaml")]
    return [os.path.join(h, ".config", "ComfyUI", "extra_models_config.yaml")]


def sweep(existing_realpaths: set[str]) -> dict:
    """Whole read-only sweep. existing_realpaths = casefolded realpaths already
    configured as roots (excluded from candidates)."""
    cands: list[dict] = []
    seen = set(existing_realpaths)
    skipped = 0

    def add(kind, path, source, label):
        rp = os.path.realpath(path)
        key = rp.casefold()
        if key in seen:
            return
        seen.add(key)
        mc, capped = _count_models(rp) if kind == "model" else (None, False)
        cands.append({"kind": kind, "path": rp, "source": source, "label": label,
                      "model_count": mc, "count_capped": capped})

    for root in _seed_locations():
        try:
            models = os.path.join(root, "models")
            if os.path.isdir(models) and _has_canonical_children(models):
                add("model", models, "comfyui", f"ComfyUI · {_short(root)}")
                wf = os.path.join(root, "user", "default", "workflows")
                if os.path.isdir(wf):
                    add("workflow", wf, "comfyui", f"Workflows · {_short(root)}")
            elif _has_canonical_children(root):
                add("model", root, "bare", f"Models · {_short(root)}")
            # extra_model_paths.yaml under this install root -> Task 3 fills this in
            skipped += _consume_config(os.path.join(root, "extra_model_paths.yaml"), add)
        except OSError:
            continue

    for cfg in _seed_config_files():
        skipped += _consume_config(cfg, add)

    return {"candidates": cands, "skipped_config_mappings": skipped}


def _consume_config(path, add) -> int:
    """Parse a YAML config file and feed model-root candidates to add().
    Returns count of non-canonical mappings skipped. Task 3 implements the body;
    Task 2 stubs it so sweep() runs with zero config contribution."""
    return 0
