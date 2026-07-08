import os, sys, tempfile, threading, webbrowser
from .api import create_app
from . import db
from .demo.seed import seed_demo

def default_db_path() -> str:
    d = os.path.join(os.path.expanduser("~"), ".combuddy")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "combuddy.sqlite")

def _static_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "web")

def build_app(db_path: str | None = None, static_dir: str | None = None,
              demo: bool = False, desktop_state: dict | None = None):
    return create_app(db_path or default_db_path(),
                      static_dir if static_dir is not None else _static_dir(),
                      demo=demo, desktop_state=desktop_state)

def main(argv: list[str] | None = None) -> int:
    import uvicorn
    argv = argv if argv is not None else sys.argv[1:]
    host, port = "127.0.0.1", 8511
    if argv[:1] == ["desktop"]:
        from .desktop import run_desktop
        return run_desktop()
    if argv[:1] == ["demo"]:
        d = tempfile.mkdtemp(prefix="combuddy-demo-")
        path = os.path.join(d, "demo.sqlite")
        conn = db.connect(path)
        db.init_schema(conn)
        seed_demo(conn)
        conn.close()
        app = build_app(path, demo=True)
    else:
        app = build_app()
    threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port)
    return 0

if __name__ == "__main__":
    sys.exit(main())
