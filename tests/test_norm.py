from combuddy import norm

def test_normalize_path_backslash_and_nfc():
    assert norm.normalize_path("SD1.5\\foo.safetensors") == "SD1.5/foo.safetensors"

def test_match_key_casefold():
    assert norm.match_key("LTXVideo/A.SafeTensors") == norm.match_key("ltxvideo/a.safetensors")
