import importlib
import importlib.metadata as ilm


def test_version_matches_package_metadata():
    import combuddy
    assert combuddy.__version__ == ilm.version("combuddy")


def test_version_falls_back_when_metadata_missing(monkeypatch):
    def boom(name):
        raise ilm.PackageNotFoundError(name)
    monkeypatch.setattr(ilm, "version", boom)
    import combuddy
    importlib.reload(combuddy)
    assert combuddy.__version__ == "0.0.0+dev"
    monkeypatch.undo()
    importlib.reload(combuddy)   # restore real value for the rest of the suite
