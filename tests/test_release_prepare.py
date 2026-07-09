import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_prepare.py"


def load_release_prepare():
    spec = importlib.util.spec_from_file_location("release_prepare", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(*args, input_text=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def test_normalize_version_removes_single_leading_v():
    release_prepare = load_release_prepare()

    assert release_prepare.normalize_version("v0.3.0") == "0.3.0"
    assert release_prepare.normalize_version("vv0.3.0") == "v0.3.0"
    assert release_prepare.normalize_version("0.3.0") == "0.3.0"


def test_is_valid_semver_accepts_only_plain_three_part_versions():
    release_prepare = load_release_prepare()

    assert release_prepare.is_valid_semver("0.3.0") is True
    assert release_prepare.is_valid_semver("10.20.30") is True
    assert release_prepare.is_valid_semver("v0.3.0") is False
    assert release_prepare.is_valid_semver("0.3") is False
    assert release_prepare.is_valid_semver("0.3.0rc1") is False


def test_pypi_has_version_checks_release_mapping():
    release_prepare = load_release_prepare()

    releases = {"0.2.0": [], "0.3.0": [{"filename": "pkg.whl"}]}

    assert release_prepare.pypi_has_version(releases, "0.3.0") is True
    assert release_prepare.pypi_has_version(releases, "0.4.0") is False


def test_needs_bump_only_when_current_and_target_differ():
    release_prepare = load_release_prepare()

    assert release_prepare.needs_bump("0.2.0", "0.3.0") is True
    assert release_prepare.needs_bump("0.3.0", "0.3.0") is False


def test_cli_normalize_outputs_normalized_version_for_valid_semver():
    result = run_cli("normalize", "v0.3.0")

    assert result.returncode == 0
    assert result.stdout == "0.3.0\n"
    assert result.stderr == ""


def test_cli_normalize_rejects_invalid_semver():
    result = run_cli("normalize", "v0.3")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "invalid semver" in result.stderr


def test_cli_pypi_check_returns_zero_when_version_missing():
    result = run_cli("pypi-check", "0.3.0", input_text='{"releases": {"0.2.0": []}}')

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_cli_pypi_check_returns_three_when_version_exists():
    result = run_cli("pypi-check", "0.3.0", input_text='{"releases": {"0.3.0": []}}')

    assert result.returncode == 3
    assert result.stdout == ""
    assert "already exists" in result.stderr


def test_cli_pypi_check_rejects_v_prefixed_version():
    result = run_cli("pypi-check", "v0.3.0", input_text='{"releases": {"0.3.0": []}}')

    assert result.returncode != 0
    assert result.stdout == ""
    assert "invalid semver" in result.stderr


def test_cli_pypi_check_rejects_non_three_part_version():
    result = run_cli("pypi-check", "0.3", input_text='{"releases": {"0.3.0": []}}')

    assert result.returncode != 0
    assert result.stdout == ""
    assert "invalid semver" in result.stderr


def test_cli_pypi_check_fails_closed_for_malformed_json():
    result = run_cli("pypi-check", "0.3.0", input_text="{")

    assert result.returncode != 0
    assert result.stdout == ""
    assert "invalid pypi json" in result.stderr


def test_cli_pypi_check_fails_closed_for_missing_releases():
    result = run_cli("pypi-check", "0.3.0", input_text="{}")

    assert result.returncode != 0
    assert result.stdout == ""
    assert "releases" in result.stderr


def test_cli_pypi_check_fails_closed_for_non_object_releases():
    result = run_cli("pypi-check", "0.3.0", input_text='{"releases": []}')

    assert result.returncode != 0
    assert result.stdout == ""
    assert "releases" in result.stderr


def test_cli_needs_bump_outputs_bump_or_skip():
    bump = run_cli("needs-bump", "0.2.0", "0.3.0")
    skip = run_cli("needs-bump", "0.3.0", "0.3.0")

    assert bump.returncode == 0
    assert bump.stdout == "bump\n"
    assert bump.stderr == ""
    assert skip.returncode == 0
    assert skip.stdout == "skip\n"
    assert skip.stderr == ""
