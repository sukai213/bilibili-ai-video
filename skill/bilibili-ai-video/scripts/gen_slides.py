# -*- coding: utf-8 -*-
"""生成全息科技风幻灯片 PNG（1920x1080），每段一张，含标题/要点/底部字幕。

用法:
  python gen_slides.py --segments segments.json --out slides \
      --brand "DEEPSEEK V4 FLASH" --watermark "「 贾维斯时刻 」"
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

SCENE_ACCENT = {
    "opening": (0, 229, 255), "intro": (0, 200, 255), "what": (64, 200, 255),
    "upgrade": (96, 190, 255), "bench": (0, 215, 255), "price": (80, 220, 180),
    "demo1": (0, 210, 255), "demo2": (60, 200, 255), "demo3": (0, 220, 220),
    "tutorial": (90, 200, 255), "pitfalls": (255, 190, 60),
    "conclusion": (0, 229, 255), "ending": (0, 235, 255),
}


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def make_bg(accent):
    top = np.array([10, 16, 34], dtype=np.float32)
    mid = np.array([16, 28, 58], dtype=np.float32)
    bot = np.array([6, 10, 24], dtype=np.float32)
    y = np.linspace(0, 1, H)[:, None]
    grad = (top[None, :] * (1 - y) * (1 - y) + mid[None, :] * 2 * y * (1 - y) + bot[None, :] * y * y)
    grad = np.clip(grad, 0, 255).astype(np.uint8)
    grad = np.repeat(grad[:, None, :], W, axis=1)
    img = Image.fromarray(grad, "RGB")

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    step = 80
    col = (accent[0], accent[1], accent[2], 26)
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=col, width=1)
    for yy in range(0, H, step):
        d.line([(0, yy), (W, yy)], fill=col, width=1)
    img = Image.alpha_composite(img.convert("RGBA"), layer)

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    cx, cy, r = W // 2, H // 2 - 60, 560
    dg.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(accent[0], accent[1], accent[2], 26))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img, glow)
    return img.convert("RGB")


def glow_text(base, xy, text, fnt, fill, glow_r=10, glow_alpha=160, anchor="mm"):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=fnt, fill=(fill[0], fill[1], fill[2], 255), anchor=anchor)
    g = layer.filter(ImageFilter.GaussianBlur(glow_r))
    g.putalpha(g.getchannel("A").point(lambda a: int(a * glow_alpha / 255)))
    base.alpha_composite(g)
    base.alpha_composite(layer)
    return base


def wrap_text(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def render_segment(seg, idx, total, out_dir, brand, watermark):
    accent = SCENE_ACCENT.get(seg["scene"], (0, 229, 255))
    img = make_bg(accent).convert("RGBA")
    d = ImageDraw.Draw(img)

    d.rectangle([60, 46, W - 60, 52], fill=(accent[0], accent[1], accent[2], 120))
    d.rectangle([60, 40, W - 60, 46], fill=(255, 255, 255, 60))

    glow_text(img, (80, 90), brand, font(30, True), (200, 235, 255), glow_r=8, glow_alpha=140, anchor="lm")
    d.text((80, 128), watermark, font=font(24), fill=(255, 255, 255, 160), anchor="lm")
    d.text((W - 80, 90), f"{idx:02d} / {total:02d}", font=font(30, True), fill=(255, 255, 255, 200), anchor="rm")

    title = seg["title"]
    glow_text(img, (W // 2, 300), title, font(96, True), (255, 255, 255), glow_r=24, glow_alpha=200)
    tw = d.textlength(title, font=font(96, True))
    lw = min(tw, 1200)
    d.rectangle([W // 2 - lw // 2, 380, W // 2 + lw // 2, 388], fill=(accent[0], accent[1], accent[2], 200))

    y = 470
    for pt in seg.get("points", []) or []:
        d.ellipse([W // 2 - 260, y + 8, W // 2 - 240, y + 28], fill=(accent[0], accent[1], accent[2], 230))
        glow_text(img, (W // 2 + 16, y), pt, font(50), (225, 245, 255), glow_r=8, glow_alpha=120, anchor="lm")
        y += 86

    bar = Image.new("RGBA", (W, 190), (0, 0, 0, 0))
    db = ImageDraw.Draw(bar)
    db.rectangle([0, 0, W, 190], fill=(8, 14, 30, 205))
    bar = bar.filter(ImageFilter.GaussianBlur(1))
    img.alpha_composite(bar, (0, H - 200))
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 200, W, H - 194], fill=(accent[0], accent[1], accent[2], 190))

    fsub = font(42)
    lines = wrap_text(d, seg["narration"], fsub, W - 200)[:3]
    sy = H - 200 + (200 - len(lines) * 58) // 2 + 20
    for ln in lines:
        d.text((W // 2, sy), ln, font=fsub, fill=(255, 255, 255, 255), anchor="mm")
        sy += 58

    out = os.path.join(out_dir, f"slide_{seg['id']:02d}.png")
    img.convert("RGB").save(out, quality=95)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", default="DEEPSEEK V4 FLASH")
    ap.add_argument("--watermark", default="「 贾维斯时刻 」")
    args = ap.parse_args()
    segments = json.load(open(args.segments, encoding="utf-8-sig"))
    os.makedirs(args.out, exist_ok=True)
    total = len(segments)
    for i, seg in enumerate(segments, 1):
        render_segment(seg, i, total, args.out, args.brand, args.watermark)
        print(f"slide {seg['id']:02d} ok", flush=True)
    print("SLIDES DONE", flush=True)


if __name__ == "__main__":
    main()
