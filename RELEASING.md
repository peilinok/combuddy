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

One action does everything: version bump, tag, GitHub Release, PyPI publish, and
desktop `.dmg` / `.exe` assets.

1. Make sure `main` is green (the CI workflow passes).
2. Go to GitHub → **Actions** → **Release** → **Run workflow**.
3. Select the `main` branch and enter the release version with no leading `v`
   (for example, `0.3.0`).
4. The workflow hard-checks that the version is semver and not already on PyPI.
5. The workflow idempotently bumps `pyproject.toml`, commits that bump to `main`,
   and creates tag `vX.Y.Z`.
   - If the tag does not exist, the workflow creates it.
   - If the tag already exists, it must point at the current `main` HEAD.
6. The workflow creates a draft GitHub Release, publishes PyPI, builds and uploads
   the macOS `.dmg` and Windows `.exe`, then publishes the GitHub Release.
7. Verify the release:
   - `pipx install combuddy` (or `uvx combuddy`) should start the server and serve the UI.
   - GitHub Releases should contain the desktop assets.

`combuddy.__version__` is read from package metadata, so only `pyproject.toml`
is bumped. After a release, run `git pull` locally so your `main` has the release
commit and tag.

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
It builds a macOS `.dmg` (arm64, ad-hoc signed) and Windows `.exe` (x64 portable,
unsigned beta), then uploads both files to the GitHub Release.

For a manual desktop-only build, go to GitHub → **Actions** → **Desktop builds** →
**Run workflow**. Leave `ref` blank to build the selected branch/ref, or set
`release_tag` (for example, `v0.3.0`) to build that tag and upload/replace assets
on an existing GitHub Release. The workflow always uploads the `.dmg` and `.exe`
as Actions artifacts.

First-open on macOS (unsigned): System Settings → Privacy & Security → **Open Anyway**
(older macOS: right-click the app → **Open**). Windows SmartScreen shows a first-run
warning → **More info → Run anyway**.

### macOS notarization is not implemented yet (TODO)

The current workflow only does ad-hoc signing. `MACOS_CERT_P12` is a placeholder
echo in `release.yml`; there is no `notarytool` submit step and no `stapler staple`
step yet.

To ship a notarized macOS build later, add an Apple Developer account, repo secrets
for the Developer ID certificate and notarization credentials, re-sign with
Developer ID plus hardened runtime, run `notarytool submit --wait`, then run
`stapler staple` on the final app or disk image.
