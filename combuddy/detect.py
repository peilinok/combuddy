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

import yaml

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
    """Well-known ComfyUI install roots and Windows portable paths."""
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


_NON_DIR_KEYS = {"base_path", "is_default"}
_SKIP_KEYS = {"custom_nodes"}   # code dir, never a model library


def _consume_config(path, add) -> int:
    """Parse extra_model_paths.yaml / extra_models_config.yaml. Feed canonical
    model-root candidates to add(); return count of non-canonical (A1111-style)
    mappings we cannot scan correctly and therefore only surface as a hint.
    Any parse/IO error -> treat as absent (return 0)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return 0
    if not isinstance(data, dict):
        return 0
    skipped = 0
    for cfg in data.values():
        if not isinstance(cfg, dict):
            continue
        base = os.path.expanduser(str(cfg.get("base_path", "")))
        # 1) base_path itself (or its models/) as a canonical container
        for cand in (os.path.join(base, "models"), base):
            if base and os.path.isdir(cand) and _has_canonical_children(cand):
                add("model", cand, "yaml", f"ComfyUI · {_short(base)}")
        # 2) per-key mapped dirs (key = model type; value = dir, maybe multiline)
        for key, val in cfg.items():
            if key in _NON_DIR_KEYS or key in _SKIP_KEYS or not isinstance(val, str):
                continue
            for line in val.splitlines():
                rel = line.strip()
                if not rel:
                    continue
                d = rel if os.path.isabs(rel) else os.path.join(base, rel)
                if not os.path.isdir(d):
                    continue
                if os.path.basename(d.rstrip("/\\")).casefold() in KNOWN_DIR_TYPES:
                    parent = os.path.dirname(d.rstrip("/\\"))
                    if _has_canonical_children(parent):
                        add("model", parent, "yaml", f"ComfyUI · {_short(parent)}")
                else:
                    skipped += 1     # A1111-style non-canonical dir name -> v1 hint only
    return skipped
