"""Generate the 8 placeholder cover images bundled with `combuddy demo`.

One-off asset build script: `python -m combuddy.demo.gen_previews`. Only this
module imports Pillow -- it is a dev-time tool, not a runtime dependency. The
produced jpgs are abstract linear-gradient placeholders (no real model art)
and are committed to the repo so the package ships them without needing
Pillow installed at runtime.
"""
import colorsys
import os

from PIL import Image, ImageOps

OUT_DIR = os.path.join(os.path.dirname(__file__), "previews")
SIZE = 512
COUNT = 8


def _gradient_image(hue: float, horizontal: bool) -> Image.Image:
    base = Image.linear_gradient("L").resize((SIZE, SIZE), Image.Resampling.BICUBIC)
    if horizontal:
        base = base.transpose(Image.Transpose.ROTATE_90)
    dark = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.65, 0.22))
    light = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.45, 0.95))
    return ImageOps.colorize(base, black=dark, white=light).convert("RGB")


def generate() -> list[str]:
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []
    for i in range(COUNT):
        hue = i / COUNT
        img = _gradient_image(hue, horizontal=bool(i % 2))
        dest = os.path.join(OUT_DIR, f"demo_{i:02d}.jpg")
        img.save(dest, "JPEG", quality=82)
        written.append(dest)
    return written


if __name__ == "__main__":
    for path in generate():
        print(path)
