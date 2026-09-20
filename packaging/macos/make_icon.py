#!/usr/bin/env python3
"""生成 AppIcon.icns：深蓝渐变底 + 地球经纬 + 信号弧。"""
import os
import subprocess
import shutil
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
OUT_ICNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AppIcon.icns")
ICONSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AppIcon.iconset")


def draw_base(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 渐变圆角底
    grad = Image.new("RGB", (size, size))
    gd = ImageDraw.Draw(grad)
    top = (9, 20, 46)
    bottom = (16, 92, 140)
    for y in range(size):
        t = y / max(size - 1, 1)
        gd.line([(0, y), (size, y)],
                fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=int(size * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)

    s = size / 1024.0
    # 地球
    cx, cy, r = size * 0.46, size * 0.52, size * 0.28
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(235, 245, 255, 240), width=int(14 * s))
    for k in (0.42, 0.78):
        d.ellipse([cx - r * k, cy - r, cx + r * k, cy + r],
                  outline=(150, 205, 255, 170), width=int(9 * s))
    d.ellipse([cx - r, cy - r * 0.42, cx + r, cy + r * 0.42],
              outline=(150, 205, 255, 170), width=int(9 * s))
    d.ellipse([cx - r, cy - r * 0.78, cx + r, cy + r * 0.78],
              outline=(150, 205, 255, 140), width=int(7 * s))
    # 信号弧
    for i, rr in enumerate((0.40, 0.54, 0.68)):
        box = [cx - size * rr, cy - size * rr, cx + size * rr, cy + size * rr]
        d.arc(box, start=-70, end=20, fill=(90, 220, 235, 230 - i * 50), width=int(16 * s))
    # 中心点
    pr = size * 0.045
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(120, 235, 250, 255))

    img = img.filter(ImageFilter.GaussianBlur(radius=max(size * 0.0015, 0.4)))
    d2 = ImageDraw.Draw(img)
    rr2 = size * 0.045
    d2.ellipse([cx - rr2, cy - rr2, cx + rr2, cy + rr2], fill=(130, 240, 255, 255))
    return img


def main() -> None:
    base = draw_base(SIZE)
    shutil.rmtree(ICONSET, ignore_errors=True)
    os.makedirs(ICONSET, exist_ok=True)
    specs = [
        (16, 1, "icon_16x16.png"), (16, 2, "icon_16x16@2x.png"),
        (32, 1, "icon_32x32.png"), (32, 2, "icon_32x32@2x.png"),
        (128, 1, "icon_128x128.png"), (128, 2, "icon_128x128@2x.png"),
        (256, 1, "icon_256x256.png"), (256, 2, "icon_256x256@2x.png"),
        (512, 1, "icon_512x512.png"), (512, 2, "icon_512x512@2x.png"),
    ]
    for px, scale, name in specs:
        target = px * scale
        base.resize((target, target), Image.LANCZOS).save(os.path.join(ICONSET, name))
    subprocess.run(["iconutil", "-c", "icns", ICONSET, "-o", OUT_ICNS], check=True)
    shutil.rmtree(ICONSET, ignore_errors=True)
    print(f"icon: {OUT_ICNS}")


if __name__ == "__main__":
    main()
