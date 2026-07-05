import os, re, threading
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from . import db as dbm, config, stats, scan_service, queries, trash

def _sniff_image(path: str) -> str:
    with open(path, "rb") as f:
        head = f.read(12)
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"

def create_app(db_path: str, static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="combuddy")

    def conn():
        c = dbm.connect(db_path); dbm.init_schema(c); return c

    @app.get("/api/stats")
    def get_stats():
        c = conn()
        s = stats.get_stats(c)
        s["scanning"] = scan_service.STATUS["running"]
        s["scan"] = dict(scan_service.STATUS)
        c.close()
        return s

    @app.get("/api/roots")
    def get_roots():
        c = conn()
        rows = [dict(r) for r in config.get_roots(c)]
        c.close()
        return {"roots": rows}

    @app.post("/api/roots")
    def post_roots(body: dict):
        c = conn(); config.set_roots(c, body.get("roots", [])); c.close()
        return {"ok": True}

    @app.get("/api/unreferenced")
    def get_unreferenced():
        c = conn(); rows = stats.get_unreferenced(c); c.close()
        return {"models": rows}

    @app.post("/api/scan")
    def post_scan():
        if scan_service.STATUS["running"]:
            return JSONResponse({"started": False, "reason": "already running"}, status_code=409)
        def _bg():
            c = conn()
            try:
                scan_service.run_scan(c)
            finally:
                c.close()
        threading.Thread(target=_bg, daemon=True).start()
        return {"started": True}

    @app.post("/api/scan/cancel")
    def post_scan_cancel():
        scan_service.STATUS["cancel"] = True
        return {"ok": True}

    @app.get("/api/settings")
    def get_settings():
        c = conn(); s = config.get_settings(c); c.close()
        return s

    @app.post("/api/settings")
    def post_settings(body: dict):
        c = conn(); config.set_settings(c, body or {}); s = config.get_settings(c); c.close()
        return s

    @app.get("/api/models")
    def api_models(search: str = "", type: str = "", flag: str = ""):
        c = conn(); rows = queries.list_models(c, search, type, flag); c.close()
        return {"models": rows}

    @app.get("/api/models/{model_id}")
    def api_model(model_id: int):
        c = conn(); d = queries.get_model_detail(c, model_id); c.close()
        if d is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return d

    @app.get("/api/workflows")
    def api_workflows():
        c = conn(); rows = queries.list_workflows(c); c.close()
        return {"workflows": rows}

    @app.get("/api/workflows/{workflow_id}")
    def api_workflow(workflow_id: int):
        c = conn(); d = queries.get_workflow_resolution(c, workflow_id); c.close()
        if d is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return d

    @app.post("/api/cleanup/trash")
    def api_trash(body: dict):
        c = conn(); res = trash.move_to_trash(c, body.get("model_ids", [])); c.close()
        return res

    @app.get("/api/cleanup/trash")
    def api_list_trash():
        c = conn(); rows = trash.list_trash(c); c.close()
        return {"trash": rows}

    @app.post("/api/cleanup/restore")
    def api_restore(body: dict):
        c = conn(); res = trash.restore(c, body.get("trash_ids", [])); c.close()
        return res

    @app.get("/api/preview/{sha256}")
    def api_preview(sha256: str, hd: int = 0):
        if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
            return JSONResponse({"error": "bad hash"}, status_code=404)
        name = sha256 + ("_hd.jpg" if hd else ".jpg")
        path = os.path.join(os.path.dirname(db_path), "previews", name)
        if not os.path.isfile(path):
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(path, media_type=_sniff_image(path))

    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app
