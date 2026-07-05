import json, os, re, time, urllib.request, urllib.error

_API = "https://civitai.com/api/v1/model-versions/by-hash/"
_UA = "combuddy (model identity lookup)"
_TIMEOUT = 10
_DELAY = 0.3          # 礼貌延迟(秒),顺序请求

def parse_version(data: dict) -> dict:
    model = data.get("model") or {}
    imgs = data.get("images") or []
    img = imgs[0] if imgs else {}
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

def download_thumb(url: str, dest: str) -> bool:
    thumb = re.sub(r"/width=\d+/", "/width=256/", url)     # 尽量取小图
    try:
        req = urllib.request.Request(thumb, headers={"User-Agent": _UA})
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

def enrich_models(conn, progress=None, should_cancel=None, fetch=fetch_by_hash, download=download_thumb) -> dict:
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
            if ident.get("image_url"):
                if download(ident["image_url"], os.path.join(pv, r["sha256"] + ".jpg")):
                    image_path = r["sha256"] + ".jpg"
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
