import json, os, time, urllib.request, urllib.error, urllib.parse
from . import norm

_API = "https://civitai.com/api/v1/model-versions/by-hash/"
_SEARCH_API = "https://civitai.com/api/v1/models"
_UA = "combuddy (model identity lookup)"
_TIMEOUT = 10
_DELAY = 0.3          # 礼貌延迟(秒),顺序请求
# dir_type → Civitai types（2026-07-17 对官方 enums 端点实测核实精确大小写；缺失即不过滤）。
# 键取 dir_type 词汇(=resolver.NODE_DIR_TYPE 值域子集)。text_encoders/clip_vision 故意不映射:Civitai 无对应类型。
_TYPES = {"checkpoints": ["Checkpoint"], "diffusion_models": ["Checkpoint"],  # UNET 近似,裸 unet 有的归 Other,靠 nofilter 兜底 [L12]
          "loras": ["LORA", "LoCon", "DoRA"], "vae": ["VAE"],
          "controlnet": ["Controlnet"], "upscale_models": ["Upscaler"]}

def _pick_preview(imgs: list) -> dict:
    """预览优先图片;没有图片再退视频;都没有 type 标记则取第一张。"""
    for want in ("image", "video"):
        for im in imgs:
            if im.get("type") == want:
                return im
    return imgs[0] if imgs else {}

def parse_version(data: dict) -> dict:
    model = data.get("model") or {}
    img = _pick_preview(data.get("images") or [])
    return {
        "name": model.get("name"),
        "version_name": data.get("name"),
        "base_model": data.get("baseModel"),
        "model_type": model.get("type"),
        "trigger_words": json.dumps(data.get("trainedWords") or []),
        "nsfw_level": img.get("nsfwLevel"),
        "civitai_url": f"https://civitai.com/models/{data.get('modelId')}?modelVersionId={data.get('id')}",
        "image_url": img.get("url"),
    }

def fetch_by_hash(sha256: str):
    req = urllib.request.Request(_API + sha256, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read().decode())
        return ("found", parse_version(data))
    except urllib.error.HTTPError as e:
        return ("notfound", None) if e.code == 404 else ("skip", None)
    except Exception:
        return ("skip", None)

def _sized(url: str, width: int) -> str:
    """把 Civitai 图片 URL 的变换段改成 anim=false,width=N(视频取静态帧 + 限宽)。"""
    parts = url.rsplit("/", 2)
    if len(parts) == 3 and "civitai" in parts[0]:
        return f"{parts[0]}/anim=false,width={width}/{parts[2]}"
    return url

def download_image(url: str, dest: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False

def _previews_dir(conn) -> str:
    for r in conn.execute("PRAGMA database_list"):
        if r["name"] == "main" and r["file"]:
            return os.path.join(os.path.dirname(r["file"]), "previews")
    return "previews"

def _upsert(conn, model_id, sha256, found, ident=None, image_path=None):
    ident = ident or {}
    conn.execute(
        """INSERT INTO civitai(model_id,sha256,found,name,version_name,base_model,model_type,
             trigger_words,nsfw_level,civitai_url,image_path,checked_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(model_id) DO UPDATE SET sha256=excluded.sha256, found=excluded.found,
             name=excluded.name, version_name=excluded.version_name, base_model=excluded.base_model,
             model_type=excluded.model_type, trigger_words=excluded.trigger_words,
             nsfw_level=excluded.nsfw_level, civitai_url=excluded.civitai_url,
             image_path=excluded.image_path, checked_at=excluded.checked_at""",
        (model_id, sha256, found, ident.get("name"), ident.get("version_name"),
         ident.get("base_model"), ident.get("model_type"), ident.get("trigger_words"),
         ident.get("nsfw_level"), ident.get("civitai_url"), image_path, time.time()))

def enrich_models(conn, progress=None, should_cancel=None, fetch=fetch_by_hash, download=download_image) -> dict:
    pv = _previews_dir(conn); os.makedirs(pv, exist_ok=True)
    rows = conn.execute(
        """SELECT m.id, m.sha256 FROM models m LEFT JOIN civitai c ON c.model_id = m.id
           WHERE m.sha256 IS NOT NULL AND (c.model_id IS NULL OR c.sha256 != m.sha256)
           ORDER BY m.id""").fetchall()
    total = len(rows); done = found = 0
    if progress:
        progress(0, total)
    for r in rows:
        if should_cancel and should_cancel():
            break
        kind, ident = fetch(r["sha256"])
        if kind == "found":
            image_path = None
            url = ident.get("image_url")
            if url:
                sha = r["sha256"]
                if download(_sized(url, 256), os.path.join(pv, sha + ".jpg")):
                    image_path = sha + ".jpg"
                    download(_sized(url, 1024), os.path.join(pv, sha + "_hd.jpg"))  # HD 尽力而为
            _upsert(conn, r["id"], r["sha256"], 1, ident, image_path)
            conn.commit(); found += 1
        elif kind == "notfound":
            _upsert(conn, r["id"], r["sha256"], 0)
            conn.commit()
        # kind == "skip": 不写,下次重试
        done += 1
        if progress:
            progress(done, total)
        time.sleep(_DELAY)
    return {"found": found, "checked": done, "total": total}

def _int_id(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)   # bool 是 int 子类,须排除 [L4]

def _pick_file(files: list) -> dict | None:
    """展示文件:primary 优先 → 首个 type=='Model' → 首个。"""
    for f in files:
        if f.get("primary"):
            return f
    for f in files:
        if f.get("type") == "Model":
            return f
    return files[0] if files else None

def normalize_search(items: list, ref_name, limit: int = 5) -> list:
    """把 /api/v1/models 搜索结果归一成 UI 候选。file_match 两侧走 norm.match_key(NFC+反斜杠+casefold)。"""
    key = norm.match_key(ref_name) if ref_name else None
    out = []
    for item in items:
        mid = item.get("id")
        versions = item.get("modelVersions") or []
        chosen, matched = None, False
        if key:                                   # 优先含匹配文件的版本 → 深链到确切版本
            for v in versions:
                if any(norm.match_key(f.get("name") or "") == key for f in (v.get("files") or [])):
                    chosen, matched = v, True
                    break
        if chosen is None:                        # 否则取首个有文件的版本(Civitai 首个=最新)
            for v in versions:
                if v.get("files"):
                    chosen = v
                    break
        if chosen is None:                        # 空 modelVersions / 全部无文件 → 跳过,不取 [0] [M2①]
            continue
        vid = chosen.get("id")
        if not (_int_id(mid) and _int_id(vid)):   # id 非 int → URL 不可信,丢弃候选 [L4]
            continue
        f = _pick_file(chosen.get("files") or [])
        if f is None:
            continue
        out.append({
            "model_name": item.get("name"),
            "version_name": chosen.get("name"),
            "model_type": item.get("type"),
            "base_model": chosen.get("baseModel"),          # 版本级字符串,非 model 级数组 [L9]
            "civitai_url": f"https://civitai.com/models/{mid}?modelVersionId={vid}",
            "file": {"name": f.get("name"), "size_kb": f.get("sizeKB")},
            "file_match": matched,
        })
    out.sort(key=lambda c: not c["file_match"])   # file_match 优先,稳定排序保留组内原序
    return out[:limit]

def fetch_search(q, types=None, limit=20):
    """按名搜索 Civitai。内部抓宽窗口(limit≈20)给 file_match 排序空间。
    注:Civitai #1848(query+limit 组合异常)当前不复现;实现后需对活接口验一次该 limit 不触发 0 命中 [M4]。"""
    params = [("query", q), ("limit", limit)]
    if types:
        params += [("types", t) for t in types]
    url = _SEARCH_API + "?" + urllib.parse.urlencode(params, doseq=True)   # 中和注入 [L3]
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return ("rate_limited", None) if e.code == 429 else ("error", None)
    except Exception:
        return ("error", None)
    if not (isinstance(data, dict) and isinstance(data.get("items"), list)):
        return ("error", None)                     # 形状意外(200 但缺 items)→ error,不 500 [M2③]
    return ("ok", data["items"])
