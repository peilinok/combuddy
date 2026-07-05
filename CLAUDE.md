# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

combuddy is a standalone, **100% local** tool: it scans a ComfyUI model library and workflow files, maps the model↔workflow dependency graph, and serves a dark web UI (Dashboard, model library, workflow resolution, cleanup). There are **no network calls and no sha256 hashing** by design — model identity is derived only from reading file headers. A single `combuddy` command starts a FastAPI server and opens the browser.

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
"Show first, fill in later": a fast `os.scandir` pass records model files (path/type/size/mtime) so the Dashboard lights up immediately, then workflows are parsed + resolved, then `headers.enrich_models` reads file headers to fill base architecture / precision / params. Guarded by a `threading.Lock` + module-global `STATUS` (single-flight); filesystem errors on a root or file are skipped-and-continue (`STATUS["errors"]`), never aborting the whole scan. The API runs this on a background thread with its own connection; the frontend **polls `/api/stats`** (there is deliberately no SSE).

### Identity from headers (offline)
`headers.py` reads only file headers (safetensors: 8-byte length + JSON, capped at 16 MiB with magic/length defense; GGUF: bounded KV read). `infer_base` yields base architecture from metadata keys or tensor-shape heuristics; `extract_facts` yields precision (from dtype), param_count (from shapes), display_name, and raw metadata. `roles.py` turns a `dir_type` that has no meaningful base (text_encoders, vae, controlnet, …) into a role label instead of showing `unknown`.

### Schema migration
`db.SCHEMA_VERSION` + additive migration inside `init_schema`: fresh DBs get the full schema via `CREATE TABLE IF NOT EXISTS`; existing DBs are upgraded in place with `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` (idempotent, never destructive). Migrations must stay additive — do not rebuild/copy tables.

### Trash (the only destructive path)
`trash.py` "delete" = move the file into `<model_root>/.combuddy-trash/` (recoverable) and drop the DB row. Safety is non-negotiable here: a per-item 0-reference re-check at move time (TOCTOU guard), a **per-item commit** with **undo-on-failure** (if the DB write fails after the file moved, the file is moved back), a unique dest dir per model id (no overwrite), and `scanner._walk` excludes `.combuddy-trash` so trashed files never reappear as models.

### Frontend
Vue 3, **no vue-router and no Pinia**. `App.vue` switches views with a plain `view` ref + `<component :is>`; each view owns a composable (`useDashboard`/`useLibrary`/`useWorkflows`/`useCleanup`) built on `ref`s, each exposing an `error` ref that its view renders. `api.ts` routes every call through `jsonOrThrow` (throws on non-2xx). Vite builds into `combuddy/web/`, served by FastAPI's static mount — so the whole app ships as one `pip install`.

## Conventions
- stdlib `sqlite3` only (no ORM); connections use `sqlite3.Row` — access columns by name, not position.
- Keep it local: no network calls, no sha256 (both are reserved for a future enrichment layer; `models.sha256` is an unused reserved column).
- Match the terse, dependency-light style already in each module; each file has one clear responsibility.

## Design docs
Full design history — specs, implementation plans, and UI mockups — lives under `docs/superpowers/` on disk but is **gitignored (local-only, not published)**. It is the authoritative rationale for the decisions above; consult it when a design choice is unclear.
