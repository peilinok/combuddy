# combuddy

[![CI](https://github.com/peilinok/combuddy/actions/workflows/ci.yml/badge.svg)](https://github.com/peilinok/combuddy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A model & workflow dependency manager for [ComfyUI](https://github.com/comfyanonymous/ComfyUI). Point it at your local model library and workflow files, and it shows you how they depend on each other — which workflows use which models, which models nothing uses, and which models a workflow is missing. **100% local: no network, no accounts, no hashing.**

## Why

Community workflows reference models by bare filename — no download link, no hash. Over time you lose track of what a model is, which workflows need it, and what's safe to delete. combuddy answers those from what's already on your disk:

- **Dashboard** — total models & size, base-architecture coverage, and how many models nothing references.
- **Model library** — search/filter every model; click one to see its details and the **workflows that reference it** (reverse dependencies).
- **Workflow resolution** — pick a workflow, see each referenced model marked **hit / ambiguous / missing**.
- **Cleanup** — the models no workflow uses, with reclaimable space, moved to a **recoverable trash** (never a hard delete; only 0-reference models can go).
- **Offline identity** — base architecture (SD1.5/SDXL/Flux/…, incl. GGUF), role labels (text encoder, VAE, ControlNet, …), and precision, all read straight from file headers.

## Install & run

Requires Python 3.11+.

```bash
pip install -e .
combuddy
```

This starts a local server on `http://127.0.0.1:8511` and opens your browser. On first run, point it at your ComfyUI **models** directory and **workflows** directory (e.g. `.../user/default/workflows`); it scans and populates the Dashboard in seconds.

## How it works

- Scans model directories (skipping noise and its own trash), and parses ComfyUI workflow JSON for model references.
- Matches references to local files by **directory type + normalized relative path** (handling subfolders, case, Unicode, and backslashes) — not by fragile basename guessing.
- Reads only file headers for identity — no full-file hashing, no uploads.
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

v1.1 — fully local. Planned next: online enrichment (real names / preview / trigger words via Civitai by content hash), a download center for missing models, and dependency pinning for shareable, self-healing workflows.
