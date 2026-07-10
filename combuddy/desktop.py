"""Desktop shell: run the existing FastAPI app in-process and show it in a
native WebView. Lazy-imports webview so this module stays importable (and
testable) without the desktop extra installed."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from . import __version__

_WEBVIEW2_MIN_VERSION = (86, 0, 622, 0)
_WEBVIEW2_CLIENT_KEYS = (
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",  # Microsoft Edge WebView2 Runtime
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",  # Beta
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",  # Dev
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",  # Canary
)


def _bind_socket() -> "tuple[socket.socket, int]":
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))            # keep OPEN; hand this exact socket to uvicorn (no TOCTOU)
    return s, s.getsockname()[1]


def _wait_ready(port: int, timeout: float = 8.0) -> bool:
    """Poll our own /api/stats until it answers as us. Never raises."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats", timeout=1) as r:
                if r.status == 200 and "model_count" in json.load(r):
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def _newer(latest: str, current: str) -> bool:
    def parse(v):
        return tuple(int(x) for x in v.split("."))
    try:
        return parse(latest) > parse(current)
    except (ValueError, AttributeError):
        return False                    # any unparseable segment -> fail-quiet (no false banner)


def _check_update(state: dict) -> None:
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/peilinok/combuddy/releases/latest",
            headers={"User-Agent": "combuddy"})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.load(r)
        latest = str(data.get("tag_name", "")).lstrip("v")
        if _newer(latest, __version__):
            state["update"] = {"version": latest, "url": data.get("html_url")}
    except Exception:
        pass


def _version_at_least(version: str, minimum: tuple[int, ...]) -> bool:
    try:
        parts = tuple(int(p) for p in str(version).split("."))
    except ValueError:
        return False
    parts += (0,) * max(0, len(minimum) - len(parts))
    return parts >= minimum


def _webview2_registry_paths():
    for key in _WEBVIEW2_CLIENT_KEYS:
        yield rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{key}"
        yield rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{key}"


def _windows_has_webview2_runtime(winreg_module=None) -> bool:
    if winreg_module is None:
        if os.name != "nt":
            return False
        try:
            import winreg as winreg_module
        except Exception:
            return False
    for hive_name in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
        hive = getattr(winreg_module, hive_name)
        for path in _webview2_registry_paths():
            try:
                with winreg_module.OpenKey(hive, path) as key:
                    version, _ = winreg_module.QueryValueEx(key, "pv")
                if _version_at_least(str(version), _WEBVIEW2_MIN_VERSION):
                    return True
            except Exception:
                pass
    return False


def _show_windows_message(title: str, message: str) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
    except Exception:
        pass


class Bridge:
    """Exposed to the page as window.pywebview.api.* — validates every input."""

    def pick_folder(self):
        import webview
        r = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        return r[0] if r else None

    def reveal(self, path: str) -> bool:
        if not isinstance(path, str) or not os.path.exists(path):
            return False
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        elif os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        return True

    def open_external(self, url: str) -> bool:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return False
        return webbrowser.open(url)


def run_desktop() -> int:
    try:
        import webview                  # lazy: desktop extra only
    except ImportError:
        print('desktop UI needs the extra: pip install "combuddy[desktop]"')
        return 1
    import uvicorn
    from .__main__ import build_app

    sock, port = _bind_socket()
    state = {"update": None}
    app = build_app(desktop_state=state)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    t = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    t.start()                           # off-main-thread -> uvicorn skips signal handlers
    ready = _wait_ready(port)
    if not ready and not t.is_alive():  # server thread died during startup -> real failure
        print("combuddy server failed to start (see log above)")
        return 1
    threading.Thread(target=_check_update, args=(state,), daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    if os.name == "nt" and not _windows_has_webview2_runtime():
        _show_windows_message(
            "combuddy",
            "combuddy needs Microsoft Edge WebView2 Runtime for the native window.\n"
            "The app will open in your browser instead.",
        )
        webbrowser.open(url)
        t.join()
        return 0
    try:
        webview.create_window("combuddy", url, js_api=Bridge(),
                              width=1280, height=820, min_size=(900, 600))
        gui = "edgechromium" if os.name == "nt" else None
        webview.start(gui=gui)           # blocks until the window is closed
    except Exception:
        webbrowser.open(url)            # webview backend unavailable but server is up
        t.join()                        # serve the tab; RETURN if the server thread dies
    return 0
