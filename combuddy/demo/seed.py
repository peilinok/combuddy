"""Static demo dataset for `combuddy demo`.

seed_demo(conn) populates an already-init_schema'd sqlite connection with a
realistic-looking (but entirely synthetic) ComfyUI model library + workflow
set, so the full UI -- dashboard, library, workflow resolution, cleanup /
duplicates -- has content without any real model files, network access, or
a local ComfyUI install.

Model rows point at real (tiny, few-byte) placeholder files under a fresh
tempfile.mkdtemp() directory rather than a fabricated path string: several
backend queries (e.g. queries.list_duplicate_groups) os.stat() a model's
`path` to tell physical copies apart by inode, and a stat() on a
non-existent path makes that whole duplicate group silently disappear from
the UI. The files' content is irrelevant -- grouping is keyed off the
`sha256` column value, not a live hash of the bytes on disk -- so every
model gets the same few bytes; what matters is that each has its own real,
distinct inode.

No network access, no Civitai calls: `civitai` rows are inserted directly
with made-up-but-schema-accurate identity fields. `civitai.image_path` is
intentionally left NULL -- the demo preview endpoint (wired in a later
task) maps sha256 -> bundled cover deterministically on its own, so this
module's only responsibility for covers is that the 8 bundled jpgs exist
under combuddy/demo/previews/.
"""
import hashlib
import json
import os
import sqlite3
import tempfile
import time

from .. import norm

ROOT_LABEL = "Demo-Shared"
_WORKFLOW_ROOT_PATH = "/demo/ComfyUI/workflows"
_PLACEHOLDER_BYTES = b"demo"

# 40 models across the 8 dir_types ComfyUI actually uses on disk.
# (dir_type, rel_in_type, base_arch, precision, param_count, size_bytes, dup_key)
# base_arch is None for dir_types whose identity is a role (vae/controlnet/...),
# matching roles.role_for's _BASE_TYPES split. dup_key groups rows that must
# share one sha256 (a "same file, several copies" duplicate); None = unique.
_MODELS = [
    # checkpoints (9: 6 unique + a 3-way duplicate)
    ("checkpoints", "sd_xl_base_1.0.safetensors", "SDXL", "fp16", 3521130592, 6938078334, None),
    ("checkpoints", "sd_xl_refiner_1.0.safetensors", "SDXL", "fp16", 3086501248, 6075981930, None),
    ("checkpoints", "dreamshaper_xl_v21_turbo.safetensors", "SDXL", "fp16", 3520000000, 6938040378, None),
    ("checkpoints", "sd_v1-5-pruned-emaonly.safetensors", "SD1.5", "fp16", 859520964, 2132625894, None),
    ("checkpoints", "flux1-dev-fp8.safetensors", "FLUX", "fp8", 11901000000, 11897535942, None),
    ("checkpoints", "sd3.5_large.safetensors", "SD3", "fp16", 8100000000, 16457142612, None),
    ("checkpoints", "juggernaut_xl_v9.safetensors", "SDXL", "fp16", 3520000000, 6617930814, "juggernaut"),
    ("checkpoints", "SDXL/juggernaut_xl_v9.safetensors", "SDXL", "fp16", 3520000000, 6617930814, "juggernaut"),
    ("checkpoints", "_old_backup/juggernaut_xl_v9.safetensors", "SDXL", "fp16", 3520000000, 6617930814, "juggernaut"),
    # unet (4)
    ("unet", "flux1-schnell.safetensors", "FLUX", "fp8", 11900000000, 11933252694, None),
    ("unet", "flux1-dev-Q4_K_S.gguf", "FLUX", "Q4_K_S", None, 6800000000, None),
    ("unet", "flux1-kontext-dev.safetensors", "FLUX", "fp8", 11900000000, 11902000000, None),
    ("unet", "sd3.5_large_unet.safetensors", "SD3", "fp16", 8100000000, 16200000000, None),
    # loras (11: a same-basename-different-file ambiguous pair + a 2-way duplicate)
    ("loras", "characters/detail_slider_xl.safetensors", "SDXL", "fp16", 89915776, 228695256, None),
    ("loras", "style/detail_slider_xl.safetensors", "SDXL", "fp16", 91226112, 231400112, None),
    ("loras", "sdxl_lightning_8step.safetensors", "SDXL", "fp16", 34400000, 87571968, None),
    ("loras", "pytorch_lora_weights_lcm_sdxl.safetensors", "SDXL", "fp16", 52960000, 134807648, None),
    ("loras", "flux_realism_lora.safetensors", "FLUX", "bf16", 67450000, 171966880, None),
    ("loras", "flux_turbo_alpha.safetensors", "FLUX", "fp8", 34300000, 87393312, None),
    ("loras", "epi_noiseoffset_sd15.safetensors", "SD1.5", "fp16", 9850000, 37687920, None),
    ("loras", "more_details_sd15.safetensors", "SD1.5", "fp16", 29950000, 76383168, None),
    ("loras", "anime_screencap_style_xl.safetensors", "SDXL", "fp16", 89600000, 227540992, "anime_screencap"),
    ("loras", "_sorted/by_style/anime_screencap_style_xl.safetensors", "SDXL", "fp16", 89600000, 227540992, "anime_screencap"),
    ("loras", "film_grain_xl.safetensors", "SDXL", "fp16", 22500000, 57318912, None),
    # vae (3) -- base_arch None, role-labeled
    ("vae", "sdxl_vae.safetensors", None, "fp32", None, 334695048, None),
    ("vae", "vae-ft-mse-840000-ema-pruned.safetensors", None, "fp16", None, 167335342, None),
    ("vae", "ae.safetensors", None, "bf16", None, 167666656, None),
    # controlnet (3)
    ("controlnet", "control_v11p_sd15_openpose.safetensors", None, "fp16", None, 1445157120, None),
    ("controlnet", "control_v11f1p_sd15_depth.safetensors", None, "fp16", None, 1445157120, None),
    ("controlnet", "controlnet_union_sdxl_1.0.safetensors", None, "fp16", None, 2502139696, None),
    # upscale_models (4: 2 unique + a 2-way duplicate)
    ("upscale_models", "4x-UltraSharp.pth", None, "fp32", None, 66961958, None),
    ("upscale_models", "4x_NMKD-Siax_200k.pth", None, "fp32", None, 67002332, None),
    ("upscale_models", "RealESRGAN_x4plus.pth", None, "fp32", None, 67040989, "realesrgan_x4plus"),
    ("upscale_models", "legacy/RealESRGAN_x4plus.pth", None, "fp32", None, 67040989, "realesrgan_x4plus"),
    # text_encoders (3)
    ("text_encoders", "clip_l.safetensors", None, "fp16", None, 246144152, None),
    ("text_encoders", "t5xxl_fp8_e4m3fn.safetensors", None, "fp8", None, 4893934592, None),
    ("text_encoders", "clip_g.safetensors", None, "fp16", None, 1389382176, None),
    # clip_vision (3)
    ("clip_vision", "clip_vision_g.safetensors", None, "fp16", None, 3689912664, None),
    ("clip_vision", "CLIP-ViT-H-14-laion2B.safetensors", None, "fp32", None, 1972245568, None),
    ("clip_vision", "sigclip_vision_384.safetensors", None, "fp16", None, 857575234, None),
]

# Civitai identity for ~24 of the 40 models above (the rest get no civitai
# row at all, i.e. "never enriched" rather than a found=0 negative cache).
# (dir_type, rel_in_type) -> (name, version_name, base_model, model_type, trigger_words)
_CIVITAI = {
    ("checkpoints", "sd_xl_base_1.0.safetensors"): ("SD XL", "v1.0 base", "SDXL 1.0", "Checkpoint", []),
    ("checkpoints", "sd_xl_refiner_1.0.safetensors"): ("SD XL Refiner", "v1.0", "SDXL 1.0", "Checkpoint", []),
    ("checkpoints", "dreamshaper_xl_v21_turbo.safetensors"): ("DreamShaper XL", "v2.1 Turbo", "SDXL 1.0", "Checkpoint", []),
    ("checkpoints", "sd_v1-5-pruned-emaonly.safetensors"): ("Stable Diffusion 1.5", "v1.5 pruned", "SD 1.5", "Checkpoint", []),
    ("checkpoints", "flux1-dev-fp8.safetensors"): ("FLUX.1", "dev fp8", "Flux.1 D", "Checkpoint", []),
    ("checkpoints", "sd3.5_large.safetensors"): ("Stable Diffusion 3.5", "Large", "SD 3.5", "Checkpoint", []),
    ("checkpoints", "juggernaut_xl_v9.safetensors"): ("Juggernaut XL", "v9", "SDXL 1.0", "Checkpoint", []),
    ("checkpoints", "SDXL/juggernaut_xl_v9.safetensors"): ("Juggernaut XL", "v9", "SDXL 1.0", "Checkpoint", []),
    ("checkpoints", "_old_backup/juggernaut_xl_v9.safetensors"): ("Juggernaut XL", "v9", "SDXL 1.0", "Checkpoint", []),
    ("unet", "flux1-schnell.safetensors"): ("FLUX.1", "schnell", "Flux.1 S", "Checkpoint", []),
    ("unet", "flux1-kontext-dev.safetensors"): ("FLUX.1 Kontext", "dev", "Flux.1 D", "Checkpoint", []),
    ("unet", "sd3.5_large_unet.safetensors"): ("Stable Diffusion 3.5", "Large (unet only)", "SD 3.5", "Checkpoint", []),
    ("loras", "characters/detail_slider_xl.safetensors"): ("Detail Slider XL", "v1.0", "SDXL 1.0", "LORA", ["detail slider"]),
    ("loras", "sdxl_lightning_8step.safetensors"): ("SDXL Lightning", "8-step", "SDXL 1.0", "LORA", []),
    ("loras", "pytorch_lora_weights_lcm_sdxl.safetensors"): ("LCM LoRA SDXL", "v1", "SDXL 1.0", "LORA", []),
    ("loras", "flux_realism_lora.safetensors"): ("Flux Realism LoRA", "v2", "Flux.1 D", "LORA", ["realistic photo"]),
    ("loras", "flux_turbo_alpha.safetensors"): ("Flux Turbo Alpha", "v1", "Flux.1 D", "LORA", []),
    ("loras", "epi_noiseoffset_sd15.safetensors"): ("Epi Noise Offset", "v2", "SD 1.5", "LORA", []),
    ("loras", "more_details_sd15.safetensors"): ("More Details", "v1", "SD 1.5", "LORA", ["more details"]),
    ("loras", "anime_screencap_style_xl.safetensors"): ("Anime Screencap Style XL", "v3", "SDXL 1.0", "LORA", ["anime screencap", "1990s anime"]),
    ("loras", "_sorted/by_style/anime_screencap_style_xl.safetensors"): ("Anime Screencap Style XL", "v3", "SDXL 1.0", "LORA", ["anime screencap", "1990s anime"]),
    ("vae", "ae.safetensors"): ("FLUX VAE", "ae", "Flux.1 D", "VAE", []),
    ("controlnet", "control_v11p_sd15_openpose.safetensors"): ("ControlNet 1.1 OpenPose", "v1.1", "SD 1.5", "Controlnet", []),
    ("upscale_models", "4x-UltraSharp.pth"): ("4x-UltraSharp", "v1", "Other", "Upscaler", []),
}

# 4 workflows exercising all three resolution states.
# Each edge: (ref_string, node_type, ref_dir_type, kind, target)
# kind "hit" -> target is the (dir_type, rel_in_type) key of the model it binds to.
# kind "missing" -> model_id NULL, match_kind NULL (no candidate at all).
# kind "ambiguous" -> model_id NULL, match_kind "ambiguous" (basename collides).
_WORKFLOWS = [
    ("sdxl_txt2img_basic.json", [
        ("sd_xl_base_1.0.safetensors", "CheckpointLoaderSimple", "checkpoints", "hit",
         ("checkpoints", "sd_xl_base_1.0.safetensors")),
        ("sdxl_vae.safetensors", "VAELoader", "vae", "hit", ("vae", "sdxl_vae.safetensors")),
        ("sdxl_lightning_8step.safetensors", "LoraLoader", "loras", "hit",
         ("loras", "sdxl_lightning_8step.safetensors")),
    ]),
    ("flux_kontext_edit.json", [
        ("flux1-schnell.safetensors", "UNETLoader", "unet", "hit", ("unet", "flux1-schnell.safetensors")),
        ("t5xxl_fp8_e4m3fn.safetensors", "DualCLIPLoader", "text_encoders", "hit",
         ("text_encoders", "t5xxl_fp8_e4m3fn.safetensors")),
        ("ae.safetensors", "VAELoader", "vae", "hit", ("vae", "ae.safetensors")),
        ("flux1-upscaler-4x.safetensors", "UpscaleModelLoader", "upscale_models", "missing", None),
    ]),
    ("controlnet_openpose_portrait.json", [
        ("sd_v1-5-pruned-emaonly.safetensors", "CheckpointLoaderSimple", "checkpoints", "hit",
         ("checkpoints", "sd_v1-5-pruned-emaonly.safetensors")),
        ("control_v11p_sd15_openpose.safetensors", "ControlNetLoader", "controlnet", "hit",
         ("controlnet", "control_v11p_sd15_openpose.safetensors")),
        # bare basename: collides with both characters/ and style/ detail_slider_xl copies
        ("detail_slider_xl.safetensors", "LoraLoader", "loras", "ambiguous", None),
    ]),
    ("sdxl_backup_restore_check.json", [
        # references the deepest of the 3 juggernaut copies -> it (not the
        # shallowest-path copy) becomes the suggested "keep" for that group
        ("_old_backup/juggernaut_xl_v9.safetensors", "CheckpointLoaderSimple", "checkpoints", "hit",
         ("checkpoints", "_old_backup/juggernaut_xl_v9.safetensors")),
        ("clip_vision_h.safetensors", "CLIPVisionLoader", "clip_vision", "missing", None),
        ("4x-UltraSharp.pth", "UpscaleModelLoader", "upscale_models", "hit",
         ("upscale_models", "4x-UltraSharp.pth")),
    ]),
]


def _sha_for(dir_type: str, rel_in_type: str, dup_key: str | None) -> str:
    label = f"dup:{dup_key}" if dup_key else f"{dir_type}/{rel_in_type}"
    return hashlib.sha256(f"combuddy-demo:{label}".encode()).hexdigest()


def _insert_models(conn: sqlite3.Connection, root_id: int, tmp_root: str) -> dict:
    """Writes tiny real placeholder files + one models row per _MODELS entry.
    Returns {(dir_type, rel_in_type): model_id}."""
    now = time.time()
    base_t = now - len(_MODELS) * 3600
    ids: dict[tuple, int] = {}
    dup_sha: dict[str, str] = {}
    for i, (dir_type, rel_in_type, base_arch, precision, param_count, size, dup_key) in enumerate(_MODELS):
        filename = os.path.basename(rel_in_type)
        ext = os.path.splitext(filename)[1].lstrip(".").lower()
        rel_path = f"{dir_type}/{rel_in_type}"
        abs_path = os.path.join(tmp_root, dir_type, rel_in_type)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(_PLACEHOLDER_BYTES)
        if dup_key:
            sha = dup_sha.setdefault(dup_key, _sha_for(dir_type, rel_in_type, dup_key))
        else:
            sha = _sha_for(dir_type, rel_in_type, None)
        first_seen = base_t + i * 3600
        cur = conn.execute(
            """INSERT INTO models(root_id,path,rel_path,dir_type,rel_in_type,filename,ext,
               size,mtime,base_arch,sha256,precision,param_count,match_key,name_key,
               first_seen,last_scanned)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (root_id, abs_path, rel_path, dir_type, rel_in_type, filename, ext, size,
             first_seen, base_arch, sha, precision, param_count,
             norm.match_key(rel_in_type), norm.match_key(filename), first_seen, now),
        )
        ids[(dir_type, rel_in_type)] = cur.lastrowid
    return ids


def _insert_civitai(conn: sqlite3.Connection, model_ids: dict) -> None:
    now = time.time()
    for i, (key, (name, version_name, base_model, model_type, trigger_words)) in enumerate(_CIVITAI.items()):
        model_id = model_ids[key]
        sha = conn.execute("SELECT sha256 FROM models WHERE id=?", (model_id,)).fetchone()["sha256"]
        conn.execute(
            """INSERT INTO civitai(model_id,sha256,found,name,version_name,base_model,
               model_type,trigger_words,nsfw_level,civitai_url,checked_at)
               VALUES(?,?,1,?,?,?,?,?,?,?,?)""",
            (model_id, sha, name, version_name, base_model, model_type,
             json.dumps(trigger_words), 1,
             f"https://civitai.com/models/{100000 + i}?modelVersionId={200000 + i}", now),
        )


def _insert_workflows(conn: sqlite3.Connection, wf_root_id: int, model_ids: dict) -> None:
    now = time.time()
    for filename, refs in _WORKFLOWS:
        wf_cur = conn.execute(
            """INSERT INTO workflows(root_id,path,filename,mtime,ref_count,last_scanned)
               VALUES(?,?,?,?,?,?)""",
            (wf_root_id, f"{_WORKFLOW_ROOT_PATH}/{filename}", filename, now, len(refs), now),
        )
        workflow_id = wf_cur.lastrowid
        for ref_string, node_type, ref_dir_type, kind, target in refs:
            if kind == "hit":
                model_id, match_kind = model_ids[target], "path"
            elif kind == "ambiguous":
                model_id, match_kind = None, "ambiguous"
            else:
                model_id, match_kind = None, None
            conn.execute(
                """INSERT INTO edges(workflow_id,ref_string,ref_key,ref_dir_type,node_type,
                   model_id,match_kind) VALUES(?,?,?,?,?,?,?)""",
                (workflow_id, ref_string, norm.match_key(ref_string), ref_dir_type, node_type,
                 model_id, match_kind),
            )


def seed_demo(conn: sqlite3.Connection) -> None:
    """Populates conn (already init_schema'd) with the demo dataset."""
    tmp_root = tempfile.mkdtemp(prefix="combuddy-demo-models-")
    root_id = conn.execute(
        "INSERT INTO roots(kind,path,label,source) VALUES('model',?,?,'demo')",
        (tmp_root, ROOT_LABEL),
    ).lastrowid
    wf_root_id = conn.execute(
        "INSERT INTO roots(kind,path,label,source) VALUES('workflow',?,?,'demo')",
        (_WORKFLOW_ROOT_PATH, "Demo Workflows"),
    ).lastrowid
    model_ids = _insert_models(conn, root_id, tmp_root)
    _insert_civitai(conn, model_ids)
    _insert_workflows(conn, wf_root_id, model_ids)
    conn.commit()
