# combuddy

A local-first dependency manager for your ComfyUI models and workflows — see what's used, what's missing, and what's safe to delete.

[![CI](https://github.com/peilinok/combuddy/actions/workflows/ci.yml/badge.svg)](https://github.com/peilinok/combuddy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/combuddy)](https://pypi.org/project/combuddy/)
[![Python](https://img.shields.io/pypi/pyversions/combuddy)](https://pypi.org/project/combuddy/)

<!-- TODO: replace hero with an animated demo.gif once recorded -->
![combuddy dashboard](https://raw.githubusercontent.com/peilinok/combuddy/main/.github/images/hero-dashboard.png)

A model & workflow dependency manager for [ComfyUI](https://github.com/comfyanonymous/ComfyUI). Point it at your local model library and workflow files, and it shows you how they depend on each other — which workflows use which models, which models nothing uses, and which models a workflow is missing. **Local-first**: model identity (base architecture, precision, parameters) is computed from file headers; optional Civitai enrichment by content hash is on by default and toggleable in settings.

## Why

Community workflows reference models by bare filename — no download link, no hash. Over time you lose track of what a model is, which workflows need it, and what's safe to delete. combuddy answers those from what's already on your disk:

- **Dashboard** — total models & size, base-architecture coverage, and how many models nothing references.
- **Model library** — search/filter every model; click one to see its details and the **workflows that reference it** (reverse dependencies).
- **Workflow resolution** — pick a workflow, see each referenced model marked **hit / ambiguous / missing**.
- **Cleanup** — the models no workflow uses, with reclaimable space, moved to a **recoverable trash** (never a hard delete; only 0-reference models can go).
- **Offline identity** — base architecture (SD1.5/SDXL/Flux/…, incl. GGUF), role labels (text encoder, VAE, ControlNet, …), and precision, all read straight from file headers.
- **Civitai identity** — for models found on Civitai by content hash: real name, base model, trigger words, and a cached preview thumbnail with **HD zoom**. Enrichment sends **only the hash**, is on by default, and is toggleable in settings.

## Features

- **Model library + Civitai enrichment** — every model in one searchable, filterable grid, with real names, preview thumbnails, and trigger words looked up from Civitai by content hash (only the hash ever leaves your machine). Offline identity — base architecture, precision, parameter count — comes straight from local file headers, Civitai match or not.

  ![library](https://raw.githubusercontent.com/peilinok/combuddy/main/.github/images/library.png)

- **Reclaimable duplicate detection** — models are grouped by exact (byte-for-byte, sha256) content match, so you see at a glance how much disk space duplicates are wasting, then clear the unreferenced copies in one click to a recoverable trash.

  ![duplicates](https://raw.githubusercontent.com/peilinok/combuddy/main/.github/images/duplicates.png)

- **Workflow dependency resolution** — pick a workflow and see every model it references marked hit, ambiguous, or missing, so you know what a shared workflow actually needs before you run it.

## Install & run

Requires Python 3.11+.

```bash
pipx install combuddy   # recommended — isolated env, `combuddy` always on PATH
pip install combuddy    # alternative, into your current environment
uvx combuddy            # or run without installing (needs uv)

combuddy         # scan your own model library and workflows
combuddy demo    # zero-config tour: bundled sample data, no local library needed
```

`combuddy` starts a local server on `http://127.0.0.1:8511` and opens your browser. On first run it **auto-detects** common ComfyUI installs (including the official Comfy Desktop) and offers them for one-click confirmation; if your library lives somewhere custom, you can point it there manually. It scans and populates the Dashboard in seconds. No library handy? `combuddy demo` seeds a temporary database with bundled sample models and workflows and opens the same UI — a full tour, no setup required.

## Desktop app

Prefer not to touch a terminal? Download the desktop app — no Python, no command line:

- **macOS (Apple Silicon):** `combuddy-X.Y.Z-macos-arm64.dmg`
- **Windows (x64):** `combuddy-X.Y.Z-windows-x64.exe` *(beta)*

Get the latest from the [**Releases**](https://github.com/peilinok/combuddy/releases/latest) page. On macOS, open the DMG and drag `combuddy.app` into Applications; on Windows, run the `.exe`. It bundles everything and opens combuddy in a native window; first launch auto-detects your ComfyUI.

### Unsigned app warnings

The desktop app is not yet code-signed or notarized, so macOS and Windows cannot
verify the publisher on first open. Download it only from the
[Releases](https://github.com/peilinok/combuddy/releases/latest) page, then use
the OS-provided one-time override:

- **macOS:** after the first blocked launch, open **System Settings → Privacy & Security**, scroll down, and click **Open Anyway**. On older macOS versions, right-click `combuddy.app` in Finder → **Open** → confirm.
- **Windows:** SmartScreen may say "Windows protected your PC". Click **More info** → **Run anyway**.

Windows also needs Microsoft Edge WebView2 Runtime for the native window. If it
is missing, combuddy shows a notice and opens the same local app in your browser
instead of showing a blank window.

The desktop app checks GitHub once at startup for a newer release. That request sends only a version query — **no model data, paths, or usage** — though, like any web request, GitHub sees your IP and user agent. The CLI and browser modes never make this check.

Advanced terminal install for the same native window:

```bash
pipx install "combuddy[desktop]"   # or: pip install "combuddy[desktop]"
combuddy desktop
```

## How it works

- Scans model directories (skipping noise and its own trash), and parses ComfyUI workflow JSON for model references.
- Matches references to local files by **directory type + normalized relative path** (handling subfolders, case, Unicode, and backslashes) — not by fragile basename guessing.
- Computes content hashes for identity; optional Civitai enrichment sends only the hash to look up real names and metadata.
- Stores everything in a single local SQLite index; the UI reads it live.

## Tech stack

- **Backend:** Python 3.11+, FastAPI, standard-library `sqlite3` (no ORM). One command (`combuddy`) runs Uvicorn and serves both the API and the UI.
- **Frontend:** Vue 3, Vite, PrimeVue, Tailwind — built into `combuddy/web/` and served by the backend, so the whole app installs as one package.

## Development

```bash
pip install -e ".[dev]"     # backend + test deps
pytest -q                    # backend tests

cd frontend
npm install
npm test                     # frontend tests (Vitest)
npm run dev                  # dev server, proxies /api to :8511
npm run build                # rebuild the bundle into ../combuddy/web
```

After changing anything in `frontend/src`, run `npm run build` — the packaged app serves the committed `combuddy/web/` bundle.

## Status & roadmap

Local-first, with optional Civitai enrichment (real names, preview images, and trigger words looked up by content hash — default on, toggleable) and a native **desktop app** for macOS and Windows with zero-config ComfyUI detection. Planned next: a download center for missing models, and dependency pinning for shareable, self-healing workflows.
