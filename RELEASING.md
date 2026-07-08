# Releasing

combuddy publishes to [PyPI](https://pypi.org/project/combuddy/) via GitHub Actions
([`.github/workflows/release.yml`](.github/workflows/release.yml)) using **PyPI Trusted
Publishing** — no API tokens are stored anywhere.

## One-time setup (on PyPI)

1. Create/verify a PyPI account at https://pypi.org.
2. Add a **pending** Trusted Publisher (the project doesn't exist yet, so it must be "pending"):
   PyPI → account → **Publishing** → *Add a pending publisher*:
   - **PyPI Project Name:** `combuddy`
   - **Owner:** `peilinok`
   - **Repository name:** `combuddy`
   - **Workflow name:** `release.yml`
   - **Environment name:** *(leave blank)*

   After the first successful publish, `combuddy` exists on PyPI and this becomes a normal
   trusted publisher.

## Cutting a release

1. Make sure `main` is green (the CI workflow passes).
2. **Bump the version** in `pyproject.toml` (e.g. `0.1.0` → `0.1.1`), commit, and push to `main`.
   PyPI versions are **immutable** — a version can never be re-uploaded, so every release needs
   a new number. (Semver: patch = fixes, minor = features, major = breaking.)
3. On GitHub → **Releases → Draft a new release**:
   - **Tag:** `v<version>` — must match `pyproject.toml` exactly (e.g. `v0.1.1`), targeting `main`.
   - Write notes, then **Publish release**.
4. `release.yml` runs automatically: it checks the tag matches the version, rebuilds the frontend,
   builds the wheel + sdist, verifies the frontend is bundled, and publishes to PyPI. Watch it in
   the **Actions** tab.
5. Verify it landed: `pipx install combuddy` (or `uvx combuddy`) → the `combuddy` command should
   start the server and serve the UI.

The frontend is rebuilt in CI on every release, so the published wheel always ships a current UI —
you never depend on the committed `combuddy/web/` being fresh at release time.

## Dry run (optional)

- Build locally without publishing: `python -m build` → inspect `dist/`.
- For a full end-to-end rehearsal, add a matching pending publisher on
  [TestPyPI](https://test.pypi.org) and temporarily point the publish step at TestPyPI
  (`with: repository-url: https://test.pypi.org/legacy/`), then `pip install -i
  https://test.pypi.org/simple/ combuddy`.

## Desktop installers

`desktop.yml` builds on the same `release: published` event as the PyPI workflow, so
one GitHub Release ships PyPI + `.dmg` (macOS arm64, ad-hoc signed) + `.exe`
(Windows x64, portable, unsigned — **beta** until real-machine verified).

First-open on macOS (unsigned): System Settings → Privacy & Security → **Open Anyway**
(older macOS: right-click the app → **Open**). Windows SmartScreen shows a first-run
warning → **More info → Run anyway**.

### Upgrading macOS to notarized (later, needs Apple Developer, US$99/yr)
Add repo secrets `MACOS_CERT_P12`, `MACOS_CERT_PWD`, `APPLE_ID`, `APPLE_TEAM_ID`,
`APPLE_APP_PWD`; the notarize step in `desktop.yml` runs when `MACOS_CERT_P12` is set.
