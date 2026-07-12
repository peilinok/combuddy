# combuddy

A local-first dependency manager for your ComfyUI models and workflows — see what's used, what's missing, and what's safe to delete.

[![CI](https://github.com/peilinok/combuddy/actions/workflows/ci.yml/badge.svg)](https://github.com/peilinok/combuddy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/combuddy)](https://pypi.org/project/combuddy/)
[![Python](https://img.shields.io/pypi/pyversions/combuddy)](https://pypi.org/project/combuddy/)

![combuddy dashboard](https://raw.githubusercontent.com/peilinok/combuddy/main/.github/images/hero-dashboard.png)

combuddy indexes your local ComfyUI model library and workflow files, then shows the dependency graph in a web UI. It helps answer practical questions: which workflows use this model, which models are missing for a workflow, what is safe to move to recoverable trash, and which duplicate files are wasting disk space.

Screenshots in this README use the bundled demo data.

## Try It First

Run the demo without adding combuddy to your Python environment:

```bash
uvx combuddy demo
```

The demo opens the same app with bundled sample models and workflows. It uses a temporary database, does not scan your local library, does not write to `~/.combuddy`, and does not contact Civitai.

## Install

### Desktop App

If you prefer a native window and no Python setup, download the latest desktop build from [Releases](https://github.com/peilinok/combuddy/releases/latest):

- **macOS Apple Silicon:** `combuddy-X.Y.Z-macos-arm64.dmg`
- **Windows x64 beta:** `combuddy-X.Y.Z-windows-x64.exe`

On macOS, open the DMG and drag `combuddy.app` into Applications. The macOS build is ad-hoc signed but not notarized, and the Windows build is unsigned, so your OS may show a one-time security prompt on first launch.

### Terminal Install

Requires Python 3.11+.

```bash
pipx install combuddy
combuddy
```

You can also install into the current Python environment:

```bash
pip install combuddy
combuddy
```

### Run Without Installing

```bash
uvx combuddy
```

## First Run

`combuddy` starts a local server at `http://127.0.0.1:8511` and opens your browser. On first run it performs read-only detection of common ComfyUI locations, including the official Comfy Desktop, and shows candidates for you to confirm. If your library lives somewhere custom, you can add model and workflow directories manually.

Initial model and workflow counts should appear quickly. Full SHA-256 hashing can continue in the background; if online enrichment is enabled, combuddy looks up Civitai metadata by content hash only.

## What You Can Do

### Dashboard

See total model count, disk usage, base-architecture coverage, duplicate waste, and how much of your library is currently unreferenced.

### Model Library

Search and filter every indexed model. Open a model to see local metadata, optional Civitai identity, trigger words, cached preview images, and reverse dependencies: the workflows that reference that model.

![library](https://raw.githubusercontent.com/peilinok/combuddy/main/.github/images/library.png)

### Workflow Resolution

Pick a workflow and inspect every referenced model. References are marked as resolved, ambiguous, or missing, so you can tell what a shared workflow needs before you run it.

### Cleanup and Duplicates

Review models that no workflow references and move them to a recoverable trash instead of deleting them permanently. Duplicate detection groups exact byte-for-byte matches by SHA-256 and helps identify unreferenced copies that can be reclaimed safely.

![duplicates](https://raw.githubusercontent.com/peilinok/combuddy/main/.github/images/duplicates.png)

## How It Works

combuddy scans configured model directories and ComfyUI workflow JSON files into a local SQLite index. Workflow references are matched to local files by directory type plus normalized relative path, so subfolders, case differences, Unicode names, and backslashes are handled without relying on fragile basename-only guesses.

Model identity is read locally from file headers where possible: base architecture, role labels, precision, and parameter counts. Content hashes are computed locally and cached for duplicate detection and optional Civitai enrichment.

## Privacy & Network

combuddy is local-first: model files, workflow files, and local filesystem paths stay on your machine. The local index is stored under `~/.combuddy` for normal runs.

Two network paths are intentional and limited:

- **Civitai enrichment** is on by default and can be turned off in Settings. Model lookup sends the locally computed SHA-256 hash to Civitai; model files and local paths are not uploaded. When a match is found, combuddy downloads and caches preview images.
- **Desktop update checks** run only in the desktop app and `combuddy desktop`. They fetch GitHub latest-release metadata to decide whether to show an update banner. Plain `combuddy` and `combuddy demo` do not perform this check.

The demo uses bundled sample data, a temporary database, and no online enrichment.

## Desktop App Notes

The desktop app bundles the same local FastAPI app and web UI into a native shell. On Windows, it needs Microsoft Edge WebView2 Runtime for the native window; if WebView2 is missing, combuddy shows a notice and opens the same local app in your browser.

Unsigned app warnings are expected for current desktop builds. The macOS build is ad-hoc signed for packaging, but it is not yet code-signed or notarized as an Apple Developer ID release. The Windows build is an unsigned beta. Download desktop builds only from the [Releases](https://github.com/peilinok/combuddy/releases/latest) page.

- **macOS:** after the first blocked launch, open **System Settings → Privacy & Security**, scroll down, and click **Open Anyway**. On older macOS versions, right-click `combuddy.app` in Finder → **Open** → confirm. If macOS still blocks it, run `xattr -c combuddy.app` from the folder containing the app.
- **Windows:** SmartScreen may say "Windows protected your PC". Click **More info** → **Run anyway**.

Advanced terminal install for the same native shell:

```bash
pipx install "combuddy[desktop]"
combuddy desktop
```

## For Developers

### Prerequisites

- Python 3.11+
- Node 20 recommended, matching CI

### Backend Service

```bash
pip install -e ".[dev]"
combuddy
```

This starts the FastAPI/Uvicorn backend at `http://127.0.0.1:8511` and serves the built frontend from `combuddy/web`.

### Frontend Dev Server

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Keep the backend running while using Vite. The dev server proxies `/api` to `http://127.0.0.1:8511`; open the Vite URL for hot module reload, not the backend's static page.

### Demo-Backed UI Development

Use the demo backend instead of the normal backend when you do not have a local ComfyUI library handy.

Terminal 1:

```bash
combuddy demo
```

Terminal 2:

```bash
cd frontend
npm run dev
```

The demo backend does not scan real files, write `~/.combuddy`, or use real path detection and scanning behavior.

### Desktop Shell

```bash
pip install -e ".[dev,desktop]"
combuddy desktop
```

The desktop shell serves the built frontend bundle. After changing `frontend/src`, run `npm run build` before testing those changes through `combuddy` or `combuddy desktop`.

### Tests And Builds

```bash
pytest -q

cd frontend
npm test
npm run build
```

`npm run build` writes the packaged frontend to `../combuddy/web`. Release builds also include this generated web bundle.

For release and desktop packaging details, see [RELEASING.md](RELEASING.md).

## Status & Roadmap

combuddy is beta software for local ComfyUI library management. Current releases include local indexing, workflow resolution, duplicate detection, recoverable cleanup, optional Civitai enrichment, demo mode, and desktop builds for macOS Apple Silicon and Windows x64.

Possible next areas include a download workflow for missing models and dependency pinning for shareable workflows. Those are roadmap ideas, not current product capabilities.
