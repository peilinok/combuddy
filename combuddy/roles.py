_ROLES = {
    "text_encoders": "文本编码器", "clip": "文本编码器", "vae": "VAE",
    "controlnet": "ControlNet", "clip_vision": "CLIP Vision",
    "upscale_models": "放大模型", "embeddings": "Embedding",
    "model_patches": "模型补丁", "style_models": "风格模型",
    "insightface": "InsightFace", "sams": "SAM", "ultralytics": "检测模型",
    "facerestore_models": "面部修复", "vae_approx": "VAE 近似",
}
# dir_types where base architecture is the meaningful identity
_BASE_TYPES = {"checkpoints", "unet", "diffusion_models", "loras"}
# every dir_type combuddy recognizes (role dirs + base-arch dirs), casefolded for matching
KNOWN_DIR_TYPES = {d.casefold() for d in set(_ROLES) | _BASE_TYPES}

def role_for(dir_type: str) -> str | None:
    if dir_type in _BASE_TYPES:
        return None
    return _ROLES.get(dir_type)

def label_for(base_arch, dir_type: str) -> str:
    if base_arch and base_arch != "unknown":
        return base_arch
    role = role_for(dir_type)
    if role:
        return role
    return "未识别"
