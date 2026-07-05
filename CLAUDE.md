# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

combuddy is a **local-first** tool: it scans a ComfyUI model library and workflow files, maps the model↔workflow dependency graph, and serves a dark web UI (Dashboard, model library, workflow resolution, cleanup). Model identity (base architecture, precision, parameters) is computed from file headers; content hashes are calculated locally. Optional Civitai enrichment (real names, previews, trigger words) queries by hash only and is default on but toggleable in settings. A single `combuddy` command starts a FastAPI server and opens the browser.

## Commands

### Backend (Python, repo root)
- Install (editable + test deps): `pip install -e ".[dev]"`
- All tests: `pytest -q`
- Single test: `pytest tests/test_resolver.py::test_resolve_path_match_with_subdir_and_case -v`
- Run the app: `combuddy` (or `python -m combuddy`) — serves `http://127.0.0.1:8511` and opens a browser tab.

### Frontend (Vue, in `frontend/`)
- Install: `cd frontend && npm install`
- All tests: `npm test` (Vitest)
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

### Frontend
Vue 3, **no vue-router and no Pinia**. `App.vue` switches views with a plain `view` ref + `<component :is>`; each view owns a composable (`useDashboard`/`useLibrary`/`useWorkflows`/`useCleanup`) built on `ref`s, each exposing an `error` ref that its view renders. `api.ts` routes every call through `jsonOrThrow` (throws on non-2xx). Vite builds into `combuddy/web/`, served by FastAPI's static mount — so the whole app ships as one `pip install`.

## Conventions
- stdlib `sqlite3` only (no ORM); connections use `sqlite3.Row` — access columns by name, not position.
- Local-first core: no network calls in the base scan/match/resolve pipeline. Network is confined to the optional, toggleable Civitai enrichment layer (hash-only queries). SHA256 hashing is now computed locally for identity and enrichment.
- Match the terse, dependency-light style already in each module; each file has one clear responsibility.

## Design docs
Full design history — specs, implementation plans, and UI mockups — lives under `docs/superpowers/` on disk but is **gitignored (local-only, not published)**. It is the authoritative rationale for the decisions above; consult it when a design choice is unclear.
