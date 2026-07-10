import pathlib
import re
import tomllib

import yaml


def test_macos_dmg_script_adds_applications_alias():
    script = pathlib.Path("packaging/macos_dmg.sh").read_text(encoding="utf-8")
    assert "ln -s /Applications" in script
    assert "hdiutil create" in script


def test_desktop_workflows_use_macos_dmg_script():
    for path in [".github/workflows/desktop.yml", ".github/workflows/release.yml"]:
        data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
        text = pathlib.Path(path).read_text(encoding="utf-8")
        assert data["jobs"]["desktop" if "release" in path else "build"]
        assert "packaging/macos_dmg.sh" in text


def test_desktop_workflows_use_current_macos_arm_runner():
    for path in [".github/workflows/desktop.yml", ".github/workflows/release.yml"]:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        assert "os: macos-15" in text
        assert "macos-14" not in text


def test_release_desktop_assets_include_release_version():
    text = pathlib.Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert 'name=combuddy-${{ needs.prepare.outputs.version }}-${{ matrix.suffix }}' in text
    assert "dist/${{ steps.asset.outputs.name }}" in text


def test_manual_desktop_assets_include_resolved_version():
    text = pathlib.Path(".github/workflows/desktop.yml").read_text(encoding="utf-8")
    assert 'VERSION="${RELEASE_TAG#v}"' in text
    assert 'name=combuddy-$VERSION-${{ matrix.suffix }}' in text
    assert "packaging/dist/${{ steps.asset.outputs.name }}" in text


def test_readme_documents_desktop_asset_names_and_entrypoint():
    text = pathlib.Path("README.md").read_text(encoding="utf-8")
    assert "combuddy-X.Y.Z-macos-arm64.dmg" in text
    assert "combuddy-X.Y.Z-windows-x64.exe" in text
    assert "drag `combuddy.app` into Applications" in text
    assert 'pipx install "combuddy[desktop]"' in text
    assert "combuddy desktop" in text


def test_backend_ci_covers_declared_python_versions():
    pyproject = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        classifier.removeprefix("Programming Language :: Python :: ")
        for classifier in pyproject["project"]["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", classifier)
    }
    ci = yaml.safe_load(pathlib.Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))

    assert set(ci["jobs"]["backend"]["strategy"]["matrix"]["python-version"]) == declared


def test_releasing_docs_assume_existing_pypi_project():
    text = pathlib.Path("RELEASING.md").read_text(encoding="utf-8")
    assert "pending" not in text
    assert "project doesn't exist yet" not in text
    assert "If Trusted Publishing is not already configured" in text


def test_readme_documents_unsigned_desktop_warnings_and_workarounds():
    text = pathlib.Path("README.md").read_text(encoding="utf-8")
    assert "Unsigned app warnings" in text
    assert "not yet code-signed or notarized" in text
    assert "Open Anyway" in text
    assert "More info" in text
    assert "Run anyway" in text


def test_agent_docs_delegate_to_claude_and_release_docs_are_current():
    agents = pathlib.Path("AGENTS.md").read_text(encoding="utf-8")
    claude = pathlib.Path("CLAUDE.md").read_text(encoding="utf-8")
    assert "CLAUDE.md" in agents
    assert "combuddy-X.Y.Z-macos-arm64.dmg" in claude
    assert "`release.yml` publishes PyPI" in claude
    assert "versioned desktop assets" in claude
