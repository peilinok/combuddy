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
    try:
        webview.create_window("combuddy", url, js_api=Bridge(),
                              width=1280, height=820, min_size=(900, 600))
        webview.start()                 # blocks until the window is closed
    except Exception:
        webbrowser.open(url)            # webview backend unavailable but server is up
        t.join()                        # serve the tab; RETURN if the server thread dies
    return 0
