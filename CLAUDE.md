# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

combuddy is a **local-first** tool: it scans a ComfyUI model library and workflow files, maps the model↔workflow dependency graph, and serves a themeable web UI (Dashboard with data-viz, model library, workflow resolution, cleanup incl. duplicate detection, settings). Model identity (base architecture, precision, parameters) is computed from file headers; content hashes are calculated locally. Optional Civitai enrichment (real names, previews, trigger words) queries by hash only and is default on but toggleable in settings.

**Three forms, one codebase** (the split is load-bearing — see the demo/desktop sections below): `combuddy` runs a FastAPI server and opens the browser; `combuddy demo` opens the same UI on bundled synthetic data (throwaway DB, never touches `~/.combuddy`, no network); `combuddy desktop` shows the same app in a native window (pywebview). First run **auto-detects** ComfyUI installs (incl. the official Comfy Desktop) so the user confirms candidates instead of typing paths. The desktop app ships as versioned CI assets (`combuddy-X.Y.Z-macos-arm64.dmg`, `combuddy-X.Y.Z-windows-x64.exe`); macOS is ad-hoc signed but not notarized, and Windows is unsigned beta.

## Commands

### Backend (Python, repo root)
- Install (editable + test deps): `pip install -e ".[dev]"`; add the native shell with `pip install -e ".[dev,desktop]"` (pulls `pywebview`).
- All tests: `pytest -q`
- Single test: `pytest tests/test_resolver.py::test_resolve_path_match_with_subdir_and_case -v`
- Run the app: `combuddy` (browser) · `combuddy demo` (bundled sample data) · `combuddy desktop` (native window; needs the `desktop` extra). All serve `http://127.0.0.1:8511`.

### Desktop packaging (`packaging/`, macOS/Windows)
- Build the `.app`/`.exe`: `pip install pyinstaller && cd packaging && pyinstaller combuddy.spec --noconfirm` → `packaging/dist/`. The spec **must** `copy_metadata("combuddy")` (else the frozen app can't read its version). Run from `packaging/` (cwd-sensitive). CI builds+signs+uploads on release — you rarely build locally.
- Regenerate placeholder icons: `python packaging/gen_icons.py` (not `python -m …` — `packaging` shadows the PyPI package; Pillow is a dev-only, lazily-imported tool, not a runtime dep).

### Frontend (Vue, in `frontend/`)
- Install: `cd frontend && npm install`
- All tests: `npm test` (Vitest). If the default pool OOMs locally, use `npx vitest run --pool=forks`.
- Single test: `npx vitest run src/useLibrary.test.ts`
- Build: `npm run build` — outputs to `../combuddy/web`, which the backend serves as static files.
- Dev server (proxies `/api` → `127.0.0.1:8511`): `npm run dev`

**The built frontend (`combuddy/web/`) is committed and shipped inside the Python package.** After changing anything under `frontend/src`, run `npm run build` so the packaged app reflects it — otherwise `combuddy` serves a stale UI.

## Architecture — the parts that span multiple files

### The matching contract (load-bearing invariant)
A workflow references a model by a filename string (often with a subdir prefix like `SD1.5/foo.safetensors`, and often with CJK/spaces/backslashes). Models are matched to those refs by **`dir_type` + normalized `rel_path`**, never by bare basename. The key is `norm.match_key(s)` = `normalize_path` (`\`→`/`, Unicode NFC) then `casefold()`. `scanner.py` stores `match_key(rel_in_type)` on each model; `resolver.py` computes `match_key(ref)` and joins on `(dir_type, match_key)`. These two must stay consistent — that agreement is the correctness spine. Basename (`name_key`) is a fallback only; when a ref matches multiple models it is marked `ambiguous` and **never** bound (`model_id` stays NULL). `resolver.NODE_DIR_TYPE` maps loader node types → `dir_type` to anchor the match.

### The data model / graph
`db.py` owns the schema: `roots` (model/workflow directories) → `models` + `workflows` → `edges` (one row per model reference in a workflow). "Unreferenced models" is a **live `LEFT JOIN` query**, never a materialized column (`stats.get_unreferenced`, `queries.list_models(flag="unreferenced")` — both agree). `edges` has `UNIQUE(workflow_id, ref_string, node_type)`; re-parsing a workflow does `DELETE FROM edges WHERE workflow_id=?` before re-inserting. An edge's rendered status is `path`/`basename` (resolved), `ambiguous`, or `missing` (`model_id IS NULL AND match_kind != 'ambiguous'`) — computed in `queries.get_workflow_resolution`.

### The scan pipeline (`scan_service.run_scan`)
"Show first, fill in later": a fast `os.scandir` pass records model files (path/type/size/mtime) so the Dashboard lights up immediately, then workflows are parsed + resolved, then `headers.enrich_models` reads file headers to fill base architecture / precision / params. Guarded by a `threading.Lock` + module-global `STATUS` (single-flight); filesystem errors on a root or file are skipped-and-continue (`STATUS["errors"]`), never aborting the whole scan. The API runs this on a background thread with its own connection; the frontend **polls `/api/stats`** (there is deliberately no SSE). After the header pass, two more **gated background phases run in the same thread** (preserving the single-writer invariant): `hashing` (sha256, if `auto_hash`) then `enriching` (Civitai, if `online_enrich`) — each streams progress into `STATUS`, honors a shared `cancel` flag, and is skip-and-continue + resumable (see below).

### Identity from headers (offline)
`headers.py` reads only file headers (safetensors: 8-byte length + JSON, capped at 16 MiB with magic/length defense; GGUF: bounded KV read). `infer_base` yields base architecture from metadata keys or tensor-shape heuristics; `extract_facts` yields precision (from dtype), param_count (from shapes), display_name, and raw metadata. `roles.py` turns a `dir_type` that has no meaningful base (text_encoders, vae, controlnet, …) into a role label instead of showing `unknown`.

### Content hashing (`hashes.py`)
combuddy computes a full-file **sha256** per model (into the reserved `models.sha256` column). A bounded worker pool hashes in parallel but **serializes every DB write under one lock** (single-writer); a global token-bucket caps read throughput (`hash_max_mbps`). Per-file commit makes it resumable (the work set is `WHERE sha256 IS NULL`); `scanner` nulls `sha256` when a file's size/mtime changes, so the hash cache invalidates itself. Gated by the `auto_hash` setting; runs as the `hashing` scan phase.

### Civitai enrichment (`civitai.py`) — the only network path
The single place combuddy talks to the network, gated by `online_enrich` (default on) and confined to the `enriching` scan phase (same background thread → single-writer). For each model whose sha256 hasn't been checked (or whose sha changed), it queries Civitai `by-hash/{sha256}` — **only the hash leaves the machine** — and caches the identity (name / base / type / trigger words) in the `civitai` table (FK `ON DELETE CASCADE` to `models`, so trash still works). Resilient by design: 404 → `found=0` **negative cache** (never re-queried), 429 / timeout / error → **skip** (retried next scan), a download failure keeps the identity text — one failure never aborts the batch, and a full outage degrades to "0 identified". It caches two local previews per hit — a 256px thumbnail + a 1024px HD (`~/.combuddy/previews/{sha256}.jpg` and `…_hd.jpg`), **preferring `type=="image"` over video** and sizing via `anim=false,width=N`; served by `GET /api/preview/{sha256}?hd=` (64-hex-validated, content-type sniffed). `queries.list_models`/`get_model_detail` LEFT JOIN `civitai` so the library **smart-merges** the real name + thumbnail (Civitai base overrides a local `unknown`); the detail view adds a Civitai block + an HD lightbox. All settings (`auto_hash`, `hash_workers`, `hash_max_mbps`, `online_enrich`, `nsfw_blur_threshold`) live in the `meta` table via `config.get_settings`/`set_settings`, exposed at `/api/settings`.

### Schema migration
`db.SCHEMA_VERSION` (currently **3**) + additive migration inside `init_schema`: fresh DBs get the full schema via `CREATE TABLE IF NOT EXISTS` (this also adds whole new tables to existing DBs — e.g. `trash`, `civitai`); existing DBs also gain new columns in place via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` (idempotent, never destructive). Migrations must stay additive — do not rebuild/copy tables.

### Trash (the only destructive path)
`trash.py` "delete" = move the file into `<model_root>/.combuddy-trash/` (recoverable) and drop the DB row. Safety is non-negotiable here: a per-item 0-reference re-check at move time (TOCTOU guard), a **per-item commit** with **undo-on-failure** (if the DB write fails after the file moved, the file is moved back), a unique dest dir per model id (no overwrite), and `scanner._walk` excludes `.combuddy-trash` so trashed files never reappear as models.

### Duplicate detection (live query, no schema)
`queries.list_duplicate_groups` groups models by `sha256`, and for each member `os.stat`s its path for the inode — a member is *deletable* when it is unreferenced and shares no inode with the kept copy. **Keep** is 3-tier: a referenced copy wins, else the shallowest path, else `first_seen`. `reclaimable` dedups by inode (hardlinks counted once); if `os.stat` fails on any keep-candidate the whole group is skipped (never mis-deletes). `stats.duplicate_waste` + `GET /api/cleanup/duplicates` feed the Dashboard tile and CleanupView's Duplicates tab; deletion reuses the trash path. Pure query layer — zero schema change.

### Workflow dependency manifest (`manifest.py`)
`GET /api/workflows/{workflow_id}/bundle` zips the **verbatim** workflow file + a `manifest.json` built
from one `edges ⋈ models ⋈ civitai` query (never `get_workflow_resolution` — it lacks
sha256/rel_in_type/civitai). Each ref gets a **four-state `lock`**: `exact` (path-matched **and**
hashed — the *only* state whose sha may drive a mismatch), `weak` (basename-matched, or matched
but unhashed), `ambiguous` (source had multiple candidates), `expected` (source had none).
`POST /api/manifest/verify` takes the zip as a **raw body** (`request.stream()` with a size cap —
`UploadFile` would pull in `python-multipart`, and `request.body()` buffers before the cap) and
returns four tiers: **present** (`confidence: exact|unverified` + `needs_hash`), **mismatch**,
**ambiguous** (with candidates, never a single bound `model_id`), **missing**. The algorithm is
sha-first (a full-table sha hit wins regardless of `lock`), then a **`dir_type`-scoped** candidate
lookup (a bare `name_key` would cross-match `loras/foo` against `checkpoints/foo`), then: multiple
candidates → ambiguous; single candidate → mismatch **only if** `lock=="exact"` and the local
candidate **is itself hashed** (otherwise `present/unverified + needs_hash` — an unhashed importer
must never be told everything is the wrong version). Bundles are untrusted input: manifest.json is
read with a bounded `zf.open().read(MAX+1)` (`zipfile.read()` decompresses without limit), and
`civitai.url` is dropped unless it is `https://civitai.com` (it lands in a clickable link).
Zero schema change; `zipfile`/`io`/`json` are stdlib.

### Demo mode (`combuddy demo`)
`combuddy/demo/seed.py::seed_demo(conn)` fills a **tempfile** SQLite DB with synthetic data (models across the dir_types, byte-identical sha256 dup groups, Civitai rows, workflows covering hit/ambiguous/missing) and `__main__` builds the app with `demo=True`. The `demo` flag threads `build_app → create_app`: `/api/stats` reports `demo`, `/api/scan` no-ops, `/api/preview` returns a bundled cover (deterministic `int(sha[:8],16) % 8`). **It never touches `~/.combuddy`, never scans, never hits the network.** Non-demo paths are byte-for-byte unchanged (the flag defaults False everywhere) — the discipline that keeps demo from leaking into real runs.

### Desktop app + zero-config detection (`combuddy desktop`)
Same FastAPI app, third form. `combuddy/desktop.py` binds a socket and hands it straight to `uvicorn.run(sockets=[sock])` (no port race), waits on `/api/stats`, then opens a pywebview window; a JS `Bridge` exposes native folder-pick / reveal-in-Finder / open-external, and a startup thread checks GitHub for updates (the desktop-only network touch). **Import-safety is an invariant**: `desktop.py` must never `import webview` at module top level (lazy only) so it stays importable/testable without the `desktop` extra. `combuddy/detect.py` is the **read-only, candidates-only** zero-config layer (never writes the DB — the user confirms, then the normal `POST /api/roots` writes): it signature-checks well-known ComfyUI locations + parses `extra_model_paths.yaml` / Comfy Desktop's `extra_models_config.yaml` (key-aware; A1111-style non-canonical mappings are counted, not added), with a bounded soft-timeout `model_count`. `GET /api/detect` excludes already-configured roots server-side. **Version single source**: `combuddy/__init__.py.__version__` derives from `importlib.metadata.version("combuddy")` (fallback `0.0.0+dev`) — bump only `pyproject.toml`; the PyInstaller spec must ship the metadata (`copy_metadata`) or the frozen app's version check breaks.

### Frontend
Vue 3 + **PrimeVue** + Tailwind + **vue-i18n** (zh/en), **no vue-router and no Pinia**. `App.vue` switches views with a plain `view` ref + `<component :is>`; each view owns a composable built on `ref`s exposing an `error` ref the view renders (`useDashboard`/`useLibrary`/`useWorkflows`/`useCleanup`/`useDuplicates`/`useSettings`). Cross-cutting state uses **module-level singletons** (`useNav`, `useTheme`, `useDemo`, `useDesktop`, `useDetect` — a module `export const ref` + a one-time `started` guard, `use*()` returns the shared refs); `useTheme` drives the 5-palette × light/dark PrimeVue theming, `useDetect` powers the first-run detect flow (RootsSetup/DetectPanel), `useDesktop` gates the native-only bits on `window.pywebview`. **Test convention:** logic lives in composables (unit-tested with Vitest, mocking `./api`); `.vue` views stay thin and are **not** unit-tested (no jsdom/@vue/test-utils) — verified on the real machine. `api.ts` routes every call through `jsonOrThrow` (throws on non-2xx). Vite builds into `combuddy/web/`, served by FastAPI's static mount — so the whole app ships as one `pip install`.

## Conventions
- stdlib `sqlite3` only (no ORM); connections use `sqlite3.Row` — access columns by name, not position.
- Local-first core: no network in the base scan/match/resolve pipeline. The **only** network touches are the optional/toggleable Civitai enrichment (hash-only queries) and the desktop app's startup update-check (version query only). sha256 is computed locally.
- **Dependency discipline** (dependency-light is the brand): base deps stay `fastapi`/`uvicorn`/`pyyaml`; `pywebview` lives in the `desktop` extra; PyInstaller and Pillow are build-only, never runtime deps (Pillow is lazily imported in `packaging/gen_icons.py` so the module stays importable without it).
- **Non-target paths stay byte-unchanged**: new run modes (`demo`/`desktop`) and backend params default off/None, so CLI + browser behavior never changes. This "flag defaults false everywhere" discipline is what keeps demo/desktop from leaking into real runs.
- Match the terse style already in each module; each file has one clear responsibility.
- Releases: bump `pyproject.toml` (version is single-source there — don't touch `__init__.py`), then publish a GitHub Release with a matching `vX.Y.Z` tag → `release.yml` publishes PyPI and builds versioned desktop assets. `desktop.yml` is for manual desktop-only rebuilds and can upload/replace assets on an existing release. See `RELEASING.md`.

## Design docs
Full design history — specs, implementation plans, and UI mockups — lives under `docs/superpowers/` on disk but is **gitignored (local-only, not published)**. It is the authoritative rationale for the decisions above; consult it when a design choice is unclear.
