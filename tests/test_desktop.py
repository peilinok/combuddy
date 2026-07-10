import importlib
import importlib.metadata as ilm
import pathlib


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


from fastapi.testclient import TestClient
from combuddy import api, desktop


def test_desktop_module_imports_without_webview():
    # 铁律:未装/未 import webview 也能收集本模块与其纯函数
    assert hasattr(desktop, "run_desktop") and hasattr(desktop, "Bridge")


def test_bind_socket_is_bound():
    s, port = desktop._bind_socket()
    try:
        assert isinstance(port, int) and port > 0
        assert s.getsockname()[1] == port
    finally:
        s.close()


def test_wait_ready_false_and_never_raises_for_dead_port():
    s, port = desktop._bind_socket(); s.close()      # nothing is listening
    assert desktop._wait_ready(port, timeout=0.3) is False


def test_newer_compares_and_fails_quiet():
    assert desktop._newer("0.3.0", "0.2.1") is True
    assert desktop._newer("0.3.0", "0.3.0") is False
    assert desktop._newer("0.3.0", "0.0.0+dev") is False   # malformed current -> quiet
    assert desktop._newer("garbage", "0.3.0") is False


def test_stats_exposes_desktop_flag_and_update():
    state = {"update": None}
    c = TestClient(api.create_app(":memory:", desktop_state=state))
    assert c.get("/api/stats").json()["desktop"] is True
    state["update"] = {"version": "9.9.9", "url": "http://x"}
    assert c.get("/api/stats").json()["update"]["version"] == "9.9.9"


def test_stats_no_desktop_key_by_default():
    c = TestClient(api.create_app(":memory:"))
    s = c.get("/api/stats").json()
    assert s["desktop"] is False and "update" not in s


def test_pyinstaller_spec_copies_metadata():
    # 硬前提:漏了 copy_metadata,冻结产物 importlib.metadata 取不到版本 -> 更新检查静默失效
    with open("packaging/combuddy.spec", "r", encoding="utf-8") as f:
        spec = f.read()
    assert 'copy_metadata("combuddy")' in spec or "copy_metadata('combuddy')" in spec


class _FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"

    def __init__(self, versions):
        self.versions = versions

    def OpenKey(self, hive, path):
        if (hive, path) not in self.versions:
            raise FileNotFoundError(path)
        return _FakeWinregKey(self.versions[(hive, path)])

    def QueryValueEx(self, key, name):
        assert name == "pv"
        return key.version, None


class _FakeWinregKey:
    def __init__(self, version):
        self.version = version

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_windows_webview2_runtime_check_detects_supported_version():
    path = next(desktop._webview2_registry_paths())
    fake = _FakeWinreg({("HKCU", path): "120.0.2210.144"})
    assert desktop._windows_has_webview2_runtime(fake) is True


def test_windows_webview2_runtime_check_rejects_missing_or_old_version():
    path = next(desktop._webview2_registry_paths())
    assert desktop._windows_has_webview2_runtime(_FakeWinreg({})) is False
    assert desktop._windows_has_webview2_runtime(_FakeWinreg({("HKLM", path): "85.0.1.0"})) is False


def test_frontend_has_nomodule_fallback_for_legacy_windows_webview():
    html = pathlib.Path("frontend/index.html").read_text(encoding="utf-8")
    assert "nomodule" in html
    assert "WebView2" in html
