"""One-off: generate combuddy .icns/.ico (node-check mark). Pillow imported lazily (dev-only)."""
import os
import subprocess
import sys

OUT = os.path.join(os.path.dirname(__file__), "icons")


def _base_png(size: int):
    from PIL import Image, ImageDraw
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=(16, 185, 129, 255))
    def _p(x, y): return (x / 100 * s, y / 100 * s)
    pts = [_p(27, 53), _p(44, 69), _p(74, 30)]
    white = (255, 255, 255, 255)
    d.line([pts[0], pts[1], pts[2]], fill=white, width=max(2, int(s * 0.075)), joint="curve")
    for (cx, cy), rr in zip(pts, (0.08, 0.08, 0.095)):
        rad = rr * s
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=white)
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
