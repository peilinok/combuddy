from combuddy import roles

def test_role_for_non_base_types():
    assert roles.role_for("text_encoders") == "文本编码器"
    assert roles.role_for("vae") == "VAE"
    assert roles.role_for("controlnet") == "ControlNet"
    assert roles.role_for("checkpoints") is None   # base-bearing → no role

def test_label_prefers_base_then_role_then_unknown():
    assert roles.label_for("sdxl", "checkpoints") == "sdxl"
    assert roles.label_for("unknown", "text_encoders") == "文本编码器"  # role beats unknown-base
    assert roles.label_for("unknown", "checkpoints") == "未识别"
    assert roles.label_for(None, "clip_vision") == "CLIP Vision"
