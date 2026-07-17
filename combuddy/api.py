import os, re, threading, mimetypes
from urllib.parse import quote
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from . import db as dbm, config, stats, scan_service, queries, trash, detect, manifest, civitai

# Windows 常把注册表 .js 的 Content Type 设成 text/plain,StaticFiles 据此对打包好的
# 前端 JS 返回 text/plain,而浏览器/WebView2 以严格 MIME 拒绝执行 <script type="module">,
# 导致 Vue 不挂载、整页白屏。强制把 .js/.mjs 修正为 JS MIME,覆盖系统注册表的错误值。
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")

_DEMO_PREVIEWS_DIR = os.path.join(os.path.dirname(__file__), "demo", "previews")

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

def _hash_candidate(ident: dict) -> dict:
    # 白名单挑字段:剔除 image_url/trigger_words/nsfw_level(隐私:不返回缩略图),remap name→model_name [M11]
    return {"model_name": ident.get("name"), "version_name": ident.get("version_name"),
            "model_type": ident.get("model_type"), "base_model": ident.get("base_model"),
            "civitai_url": ident.get("civitai_url")}

def _demo_locate(sha256: str, q: str):
    if sha256:
        return {"mode": "hash", "found": True, "candidate": {
            "model_name": "Demo Aurora XL", "version_name": "v1.0", "model_type": "Checkpoint",
            "base_model": "SDXL 1.0", "civitai_url": "https://civitai.com/models/1"}}
    if q:
        return {"mode": "name", "types_filter": None, "candidates": [
            {"model_name": "Demo Aurora XL", "version_name": "v1.0", "model_type": "Checkpoint",
             "base_model": "SDXL 1.0", "civitai_url": "https://civitai.com/models/1",
             "file": {"name": "auroraXL_v1.safetensors", "size_kb": 6775434.0}, "file_match": True},
            {"model_name": "Demo Nebula", "version_name": "v2", "model_type": "Checkpoint",
             "base_model": "SDXL 1.0", "civitai_url": "https://civitai.com/models/2",
             "file": {"name": "nebula.safetensors", "size_kb": 2100000.0}, "file_match": False}]}
    return JSONResponse({"reason": "bad_request"}, status_code=400)

def create_app(db_path: str, static_dir: str | None = None, demo: bool = False,
               desktop_state: dict | None = None) -> FastAPI:
    app = FastAPI(title="combuddy")

    def conn():
        c = dbm.connect(db_path); dbm.init_schema(c); return c

    @app.get("/api/stats")
    def get_stats():
        status = dict(scan_service.STATUS)
        c = conn()
        s = stats.get_stats(c, skip_duplicates=status["running"])
        s["scanning"] = status["running"]
        s["scan"] = status
        s["demo"] = demo
        s["desktop"] = desktop_state is not None
        if desktop_state and desktop_state.get("update"):
            s["update"] = desktop_state["update"]
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
        c = conn(); results = config.set_roots(c, body.get("roots", [])); c.close()
        return {"ok": True, "results": results}

    @app.delete("/api/roots/{root_id}")
    def delete_root(root_id: int):
        with scan_service.mutation_guard():
            c = conn(); ok = config.remove_root(c, root_id); c.close()
        if not ok:
            return JSONResponse({"error": "not found"}, status_code=404)
        return {"ok": True}

    @app.get("/api/detect")
    def get_detect():
        c = conn()
        existing = {os.path.realpath(r["path"]).casefold() for r in config.get_roots(c)}
        c.close()
        return detect.sweep(existing)

    @app.get("/api/unreferenced")
    def get_unreferenced():
        c = conn(); rows = stats.get_unreferenced(c); c.close()
        return {"models": rows}

    @app.post("/api/scan")
    def post_scan():
        if demo:
            return {"started": False, "demo": True}
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

    @app.get("/api/workflows/{workflow_id}/bundle")
    def api_workflow_bundle(workflow_id: int):
        c = conn()
        try:
            data, stem = manifest.build_bundle(c, workflow_id)
        except manifest.ManifestError as e:
            return JSONResponse({"reason": e.reason}, status_code=e.status)
        finally:
            c.close()
        # Starlette 用 latin-1 编码响应头,CJK 文件名原样进 filename= 会 UnicodeEncodeError → 500。
        # filename= 收紧到 ASCII 安全子集兜底(顺带挡住引号/CRLF 注入 [L12]),
        # filename*= 按 RFC 5987 传 UTF-8 原名,现代浏览器优先用它。
        safe = re.sub(r"[^A-Za-z0-9\-. ]", "_", stem)[:80] or "workflow"
        star = quote(f"{stem}.combuddy.zip", safe="")
        return Response(content=data, media_type="application/zip",
                        headers={"Content-Disposition":
                                 f"attachment; filename=\"{safe}.combuddy.zip\"; filename*=UTF-8''{star}"})

    @app.post("/api/manifest/verify")
    async def api_manifest_verify(request: Request):
        # 不用 UploadFile:那会拉入 python-multipart 新依赖。
        # 流式累加封顶,绝不 await request.body() 后再判大小 [H5]
        size, chunks = 0, []
        async for chunk in request.stream():
            size += len(chunk)
            if size > manifest.BODY_MAX:
                return JSONResponse({"reason": "too_large"}, status_code=413)
            chunks.append(chunk)
        c = conn()
        try:
            # verify_bundle 同步且含多次 SQLite 查询(sha256 无索引 → 全表扫描),在唯一的 async
            # 端点里内联跑会阻塞事件循环;卸载到线程池,避免大 manifest 拖垮 /api/stats 等并发请求 [审查]
            return await run_in_threadpool(manifest.verify_bundle, c, b"".join(chunks))
        except manifest.ManifestError as e:
            return JSONResponse({"reason": e.reason}, status_code=e.status)
        finally:
            c.close()

    @app.post("/api/cleanup/trash")
    def api_trash(body: dict):
        with scan_service.mutation_guard():
            c = conn(); res = trash.move_to_trash(c, body.get("model_ids", [])); c.close()
        return res

    @app.get("/api/cleanup/trash")
    def api_list_trash():
        c = conn(); rows = trash.list_trash(c); c.close()
        return {"trash": rows}

    @app.get("/api/cleanup/duplicates")
    def api_duplicates():
        c = conn()
        groups = queries.list_duplicate_groups(c)
        total = sum(g["reclaimable"] for g in groups)
        unhashed = c.execute("SELECT COUNT(*) n FROM models WHERE sha256 IS NULL").fetchone()["n"]
        c.close()
        return {"groups": groups, "total_reclaimable": total, "unhashed_count": unhashed}

    @app.post("/api/cleanup/restore")
    def api_restore(body: dict):
        c = conn(); res = trash.restore(c, body.get("trash_ids", [])); c.close()
        return res

    # 校验优先级(spec 未定、此处定稿):demo → 跨源守卫 → online 门控 → 参数校验 → 分派 [M1]。
    # 跨源请求即便参数非法也先得 403(而非 400);TestClient 默认不发 sec-fetch-site → None → 放行,故
    # test_locate_bad_request_no_params 能拿到 400——这是有意依赖的前提。
    @app.get("/api/locate")
    def api_locate(request: Request, sha256: str = "", q: str = "", ref: str = "",
                   dir_type: str = "", nofilter: int = 0):
        if demo:                                          # 首行短路:canned、零网络、零 DB
            return _demo_locate(sha256, q)
        if request.headers.get("sec-fetch-site") not in (None, "same-origin", "none"):
            return JSONResponse({"reason": "forbidden"}, status_code=403)   # 跨源 drive-by 守卫 [H1]
        c = conn(); enabled = config.get_settings(c)["online_enrich"]; c.close()   # 按惯例 close [L2]
        if not enabled:
            return JSONResponse({"reason": "online_disabled"}, status_code=409)
        if sha256:
            if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
                return JSONResponse({"reason": "bad_request"}, status_code=400)
            kind, ident = civitai.lookup_by_hash(sha256.lower())
            if kind == "found":
                return {"mode": "hash", "found": True, "candidate": _hash_candidate(ident)}
            if kind == "notfound":
                return {"mode": "hash", "found": False}
            if kind == "rate_limited":
                return JSONResponse({"reason": "rate_limited"}, status_code=429)
            return JSONResponse({"reason": "civitai_unreachable"}, status_code=502)
        if q:
            if len(q) > 200 or len(ref) > 200:            # ref 也须封顶(spec API 表 ≤200)[M2]
                return JSONResponse({"reason": "bad_request"}, status_code=400)
            types = None if nofilter else civitai._TYPES.get(dir_type)
            kind, items = civitai.fetch_search(q, types)
            if kind == "rate_limited":
                return JSONResponse({"reason": "rate_limited"}, status_code=429)
            if kind == "error":
                return JSONResponse({"reason": "civitai_unreachable"}, status_code=502)
            return {"mode": "name", "types_filter": types,
                    "candidates": civitai.normalize_search(items, ref or None)}
        return JSONResponse({"reason": "bad_request"}, status_code=400)

    @app.get("/api/preview/{sha256}")
    def api_preview(sha256: str, hd: int = 0):
        if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
            return JSONResponse({"error": "bad hash"}, status_code=404)
        if demo:
            idx = int(sha256[:8], 16) % 8
            path = os.path.join(_DEMO_PREVIEWS_DIR, f"demo_{idx:02d}.jpg")
            return FileResponse(path, media_type=_sniff_image(path))
        name = sha256 + ("_hd.jpg" if hd else ".jpg")
        path = os.path.join(os.path.dirname(db_path), "previews", name)
        if not os.path.isfile(path):
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(path, media_type=_sniff_image(path))

    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app
