"""One-off: generate placeholder .icns/.ico. Pillow imported lazily (dev-only)."""
import os
import subprocess
import sys

OUT = os.path.join(os.path.dirname(__file__), "icons")


def _base_png(size: int):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (size, size), (30, 33, 41))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([size * 0.18, size * 0.18, size * 0.82, size * 0.82],
                        radius=size * 0.12, fill=(59, 130, 246))
    return img


def generate():
    os.makedirs(OUT, exist_ok=True)
    _base_png(256).save(os.path.join(OUT, "combuddy.ico"),
                        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    png = os.path.join(OUT, "_icon.png"); _base_png(1024).save(png)
    if sys.platform == "darwin":               # build .icns via iconutil
        iconset = os.path.join(OUT, "combuddy.iconset"); os.makedirs(iconset, exist_ok=True)
        for s in (16, 32, 128, 256, 512):
            _base_png(s).save(os.path.join(iconset, f"icon_{s}x{s}.png"))
            _base_png(s * 2).save(os.path.join(iconset, f"icon_{s}x{s}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", "-o", os.path.join(OUT, "combuddy.icns"), iconset], check=True)
    print("icons written to", OUT)


if __name__ == "__main__":
    generate()
