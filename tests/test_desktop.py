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


import socket as _socket
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
