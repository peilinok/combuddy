# Contributing to combuddy

Thanks for your interest! combuddy is a **100% local** tool — no network calls and no hashing, by design. Please keep contributions aligned with that.

## Development setup

Backend (Python 3.11+):

```bash
pip install -e ".[dev]"
pytest -q
```

Frontend (in `frontend/`):

```bash
npm install
npm test          # Vitest
npm run build     # rebuilds the bundle into ../combuddy/web
npm run dev       # dev server, proxies /api to :8511
```

The built frontend (`combuddy/web/`) is committed and shipped in the package — **run `npm run build` after changing anything in `frontend/src`**, or the packaged app serves a stale UI.

## Guidelines

- **Keep it local.** No network calls in the core; identity comes from file headers only.
- **Match the existing style** — terse, dependency-light modules, one responsibility each; standard-library `sqlite3` (no ORM), rows accessed by name.
- **Add tests** (pytest / Vitest) for new behavior and keep the whole suite green.
- **Keep changes surgical.** See [CLAUDE.md](CLAUDE.md) for the architecture, especially the model↔workflow matching contract, the scan pipeline, and the trash safety rules.

## Pull requests

Fork, branch, make sure `pytest -q` and `cd frontend && npm test` pass, then open a PR. CI runs both test suites plus the frontend build on every push and PR.
