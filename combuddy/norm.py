import unicodedata

def normalize_path(s: str) -> str:
    s = s.replace("\\", "/")
    s = unicodedata.normalize("NFC", s)
    while s.startswith("./"):
        s = s[2:]
    return s.strip("/") if s != "/" else s

def match_key(s: str) -> str:
    return normalize_path(s).casefold()
