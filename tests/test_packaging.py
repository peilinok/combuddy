import pathlib

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
