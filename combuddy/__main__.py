import os, sys, threading, webbrowser
from .api import create_app

def default_db_path() -> str:
    d = os.path.join(os.path.expanduser("~"), ".combuddy")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "combuddy.sqlite")

def _static_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "web")

def build_app(db_path: str | None = None, static_dir: str | None = None):
    return create_app(db_path or default_db_path(),
                      static_dir if static_dir is not None else _static_dir())

def main(argv: list[str] | None = None) -> int:
    import uvicorn
    host, port = "127.0.0.1", 8511
    app = build_app()
    threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port)
    return 0

if __name__ == "__main__":
    sys.exit(main())
