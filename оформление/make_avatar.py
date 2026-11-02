"""Аватар канала: минималистичный знак — линии глобуса и пьедестал 2-1-3 (золото, серебро, бронза).
Рисуется в 3x и уменьшается — края гладкие. Читается даже в маленьком кружке.
  .venv/bin/python оформление/make_avatar.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S, K = 1080, 3
B = S * K  # холст с запасом для сглаживания


def background():
    y, x = np.mgrid[0:S, 0:S].astype(np.float64)
    d = np.sqrt((x - S / 2) ** 2 + (y - S * 0.46) ** 2) / (S * 0.75)
    inner, outer = np.array([34, 46, 120]), np.array([7, 8, 26])
    t = np.clip(d, 0, 1)[:, :, None] ** 1.3
    arr = inner * (1 - t) + outer * t
    return Image.fromarray(arr.astype(np.uint8)).resize((B, B), Image.BICUBIC).convert("RGBA")


def vertical_gradient(w, h, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t
    return Image.fromarray(np.repeat(arr, w, axis=1).astype(np.uint8))


def main():
    im = background()
    cx, cy, R = B / 2, B * 0.45, B * 0.34
    lw = int(B * 0.009)

    # линии глобуса — полупрозрачные, чтобы пьедестал был главным
    g = Image.new("RGBA", (B, B), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    line = (190, 210, 255, 95)
    d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(215, 228, 255, 150), width=int(lw * 1.4))
    for k in (0.38, 0.75):  # меридианы
        d.ellipse((cx - R * k, cy - R, cx + R * k, cy + R), outline=line, width=lw)
    d.line((cx, cy - R, cx, cy + R), fill=line, width=lw)
    for lat in (-0.5, 0.0, 0.5):  # параллели
        yy = cy + lat * R
        half = R * np.sqrt(1 - lat ** 2)
        d.line((cx - half, yy, cx + half, yy), fill=line, width=lw)
    im = Image.alpha_composite(im, g)

    # пьедестал 2-1-3
    bw, gap = B * 0.17, B * 0.025
    base = cy + R * 0.92
    bars = [(-1, 0.30, (232, 238, 250), (150, 165, 190)),   # серебро
            (0, 0.47, (255, 214, 92), (214, 140, 18)),       # золото
            (1, 0.22, (248, 170, 110), (176, 92, 40))]       # бронза
    glow = Image.new("RGBA", (B, B), (0, 0, 0, 0))
    gx0 = cx - bw / 2
    ImageDraw.Draw(glow).rounded_rectangle((gx0 - B * 0.04, base - B * 0.47 - B * 0.04, gx0 + bw + B * 0.04, base),
                                           int(B * 0.06), fill=(255, 190, 40, 140))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(B * 0.045)))
    f = ImageFont.truetype(os.path.join(BASE, "assets/fonts/Montserrat-Black.ttf"), int(B * 0.2))
    for pos, h, top, bottom in bars:
        x0 = cx - bw / 2 + pos * (bw + gap)
        y0 = base - B * h
        grad = vertical_gradient(int(bw), int(B * h), top, bottom).convert("RGBA")
        mask = Image.new("L", grad.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, grad.width - 1, grad.height - 1), int(B * 0.03), fill=255)
        # тень под столбиком
        sh = Image.new("RGBA", (B, B), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((x0 + B * 0.008, y0 + B * 0.012, x0 + bw + B * 0.008, base + B * 0.012),
                                             int(B * 0.03), fill=(0, 0, 0, 120))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(B * 0.01)))
        im.paste(grad, (int(x0), int(y0)), mask)
        if pos == 0:
            ImageDraw.Draw(im).text((cx, y0 + B * 0.15), "1", font=f, fill=(24, 26, 64), anchor="mm")

    out = os.path.join(BASE, "оформление", "аватар.png")
    im.convert("RGB").resize((S, S), Image.LANCZOS).save(out)
    return out


if __name__ == "__main__":
    print(main())
