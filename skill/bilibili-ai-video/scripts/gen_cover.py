# -*- coding: utf-8 -*-
"""生成 B 站封面 1920x1080（全息蓝科技风）。

用法:
  python gen_cover.py --title "贾维斯时刻！" --subtitle "DeepSeek V4 Flash 正式版实测" \
      --hints "1M 上下文标配,输入 1 元 / 百万 token,Agent 能力大幅增强" --out cover.png
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"
DOT = "\u00b7"


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def make_bg():
    top = np.array([10, 16, 34], dtype=np.float32)
    mid = np.array([18, 32, 66], dtype=np.float32)
    bot = np.array([6, 10, 24], dtype=np.float32)
    y = np.linspace(0, 1, H)[:, None]
    grad = top[None, :] * (1 - y) ** 2 + mid[None, :] * 2 * y * (1 - y) + bot[None, :] * y ** 2
    grad = np.clip(grad, 0, 255).astype(np.uint8)
    grad = np.repeat(grad[:, None, :], W, axis=1)
    img = Image.fromarray(grad, "RGB").convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(0, 229, 255, 22), width=1)
    for yy in range(0, H, 80):
        d.line([(0, yy), (W, yy)], fill=(0, 229, 255, 22), width=1)
    img = Image.alpha_composite(img, layer)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    dg.ellipse([W // 2 - 700, H // 2 - 650, W // 2 + 700, H // 2 + 650], fill=(0, 229, 255, 30))
    dg.ellipse([W // 2 - 500, H // 2 - 480, W // 2 + 500, H // 2 + 480], fill=(0, 200, 255, 26))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    img = Image.alpha_composite(img, glow)
    return img


def glow_text(base, xy, text, fnt, fill, glow_r, glow_a, anchor="mm"):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=fnt, fill=(*fill, 255), anchor=anchor)
    g = layer.filter(ImageFilter.GaussianBlur(glow_r))
    g.putalpha(g.getchannel("A").point(lambda a: int(a * glow_a / 255)))
    base.alpha_composite(g)
    base.alpha_composite(layer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True, help="主标题（大字）")
    ap.add_argument("--subtitle", required=True, help="副标题")
    ap.add_argument("--hints", default="", help="卖点，逗号分隔（圆角标签）")
    ap.add_argument("--brand", default="DEEPSEEK V4 FLASH")
    ap.add_argument("--brand-sub", default="OFFICIAL " + DOT + " 0731 " + DOT + " AGENT UPGRADE")
    ap.add_argument("--footer1", default="终端操作 " + DOT + " 工具调用 " + DOT + " 全栈开发 " + DOT + " 保姆级复现教程")
    ap.add_argument("--footer2", default="7/31 正式版公测 " + DOT + " 8/4 开源发布 " + DOT + " OpenRouter 调用量登顶")
    ap.add_argument("--out", default="cover.png")
    args = ap.parse_args()

    img = make_bg()
    d = ImageDraw.Draw(img)

    d.rectangle([60, 50, W - 60, 56], fill=(0, 229, 255, 130))
    d.rectangle([60, 44, W - 60, 50], fill=(255, 255, 255, 60))
    glow_text(img, (80, 92), args.brand, font(32, True), (200, 235, 255), 10, 150, anchor="lm")
    d.text((80, 132), args.brand_sub, font=font(22), fill=(255, 255, 255, 150), anchor="lm")

    glow_text(img, (W // 2, 330), args.title, font(190, True), (255, 255, 255), 40, 210)
    glow_text(img, (W // 2, 560), args.subtitle, font(76, True), (0, 229, 255), 22, 200)
    d.rectangle([W // 2 - 420, 660, W // 2 + 420, 668], fill=(0, 229, 255, 200))

    chips = [c for c in args.hints.split(",") if c.strip()]
    if chips:
        cw = [d.textlength(c, font=font(46, True)) + 70 for c in chips]
        total_w = sum(cw) + 60 * (len(chips) - 1)
        x = (W - total_w) // 2
        for c, w in zip(chips, cw):
            d.rounded_rectangle([x, 760, x + w, 840], radius=40, outline=(0, 229, 255, 200), width=2)
            glow_text(img, (x + w // 2, 800), c, font(46, True), (255, 255, 255), 10, 150)
            x += w + 60

    d.text((W // 2, 960), args.footer1, font=font(34), fill=(255, 255, 255, 190), anchor="mm")
    d.text((W // 2, 1020), args.footer2, font=font(28), fill=(200, 225, 255, 150), anchor="mm")

    img.convert("RGB").save(args.out, quality=95)
    print("cover saved:", args.out)


if __name__ == "__main__":
    main()
