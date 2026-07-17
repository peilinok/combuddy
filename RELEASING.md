# Releasing

combuddy publishes to [PyPI](https://pypi.org/project/combuddy/) via GitHub Actions
([`.github/workflows/release.yml`](.github/workflows/release.yml)) using **PyPI Trusted
Publishing** — no API tokens are stored anywhere.

## One-time setup (on PyPI)

1. Create/verify a PyPI account at https://pypi.org.
2. If Trusted Publishing is not already configured, add a Trusted Publisher for
   the existing `combuddy` project:
   PyPI → `combuddy` project → **Publishing** → **Add a publisher**:
   - **PyPI Project Name:** `combuddy`
   - **Owner:** `peilinok`
   - **Repository name:** `combuddy`
   - **Workflow name:** `release.yml`
   - **Environment name:** *(leave blank)*

## Cutting a release

`main` is protected (pull request + review required), so the release workflow
**cannot push the version bump itself** — the bump must already be on `main`
before you run the workflow. Releasing is two steps.

### Step 1 — land the version bump on `main` (via PR)

Open a PR that changes **only** `[project].version` in `pyproject.toml` to the new
`X.Y.Z` (title e.g. `chore(release): X.Y.Z`) and merge it into `main`. Because
`main` requires review and you can't approve your own PR, merge with an admin
bypass (`gh pr merge <n> --admin`) or a second reviewer. This mirrors how 0.3.0
(#20) and 0.4.0 (#22) shipped.

`combuddy.__version__` is read from package metadata, so `pyproject.toml` is the
only file to bump — never touch `combuddy/__init__.py`.

### Step 2 — run the Release workflow

1. Make sure `main` is green (the CI workflow passes) and its `pyproject.toml`
   already shows the target version.
2. Go to GitHub → **Actions** → **Release** → **Run workflow** (or
   `gh workflow run release.yml --ref main -f version=X.Y.Z`).
3. Select the `main` branch and enter the version with no leading `v`
   (for example, `0.4.0`).
4. The workflow hard-checks that the version is semver and not already on PyPI.
   Seeing `main` already at that version, it **skips the bump/push** and creates
   tag `vX.Y.Z`.
   - If the tag does not exist, the workflow creates it.
   - If the tag already exists, it must point at the current `main` HEAD.
5. The workflow creates a draft GitHub Release, publishes PyPI, builds and uploads
   the versioned macOS `.dmg` and Windows `.exe`, then publishes the GitHub Release.
6. Verify the release:
   - `pipx install combuddy` (or `uvx combuddy`) should start the server and serve the UI.
   - GitHub Releases should contain `combuddy-X.Y.Z-macos-arm64.dmg` and
     `combuddy-X.Y.Z-windows-x64.exe`.

> **If you skip Step 1**, the workflow fails fast in `prepare` with a message
> telling you to open the bump PR first. (Before that guard existed it instead
> failed on a rejected push — `remote: error: GH013: Repository rule violations
> found for refs/heads/main`.)

After a release, run `git pull` locally so your `main` has the bump commit and tag.

The frontend is rebuilt in CI on every release, so the published wheel always ships a current UI —
you never depend on the committed `combuddy/web/` being fresh at release time.

### If a release half-fails

- Transient failure before PyPI publish succeeds: use **Re-run failed jobs**, or
  rerun the whole workflow with the same version. The prepare step is idempotent.
- Transient failure after PyPI publish succeeds: use **Re-run failed jobs** only.
  Do not rerun the whole workflow, because the PyPI pre-check will block the
  already-published version.
- Code or workflow bug before PyPI publish succeeds: rerunning will replay the
  old commit. Fix `main`, delete the tag and draft release with
  `gh release delete vX.Y.Z --cleanup-tag`, then run the workflow again.
- Code or workflow bug after PyPI publish succeeds: the version is burned. Manually
  attach any missing Release assets, or ship a new patch version.

## Dry run (optional)

- Build locally without publishing: `python -m build` → inspect `dist/`.
- Do not run a TestPyPI end-to-end dry run from this repository. The release
  workflow intentionally writes to real `main`, creates real tags, and creates a
  real GitHub Release, so a TestPyPI rehearsal would still pollute production
  release state.

## Desktop installers

The `desktop` job in `release.yml` runs during the same release workflow as PyPI.
It builds `combuddy-X.Y.Z-macos-arm64.dmg` (arm64, ad-hoc signed) and
`combuddy-X.Y.Z-windows-x64.exe` (x64 portable, unsigned beta), then uploads both
files to the GitHub Release.

For a manual desktop-only build, go to GitHub → **Actions** → **Desktop builds** →
**Run workflow**. Leave `ref` blank to build the selected branch/ref, or set
`release_tag` (for example, `v0.3.0`) to build that tag and upload/replace assets
on an existing GitHub Release. The workflow always uploads the versioned `.dmg`
and `.exe` as Actions artifacts. If `release_tag` is omitted, the asset version
comes from the checked-out `pyproject.toml`.

First-open on macOS (unsigned): System Settings → Privacy & Security → **Open Anyway**
(older macOS: right-click the app → **Open**). Windows SmartScreen shows a first-run
warning → **More info → Run anyway**.

The macOS DMG opens with a Finder icon layout containing `combuddy.app` and an
`/Applications` symlink so users can drag the app into Applications. Windows
uses Edge WebView2 for the native shell; when the runtime is missing, the app
shows a notice and opens the local server in the user's browser instead of
falling back to a blank legacy MSHTML window.

### macOS notarization is not implemented yet (TODO)

The current workflow only does ad-hoc signing. `MACOS_CERT_P12` is a placeholder
echo in `release.yml`; there is no `notarytool` submit step and no `stapler staple`
step yet.

To ship a notarized macOS build later, add an Apple Developer account, repo secrets
for the Developer ID certificate and notarization credentials, re-sign with
Developer ID plus hardened runtime, run `notarytool submit --wait`, then run
`stapler staple` on the final app or disk image.
