"""Аватар канала: объёмный глобус из флагов + золотая медаль #1 с лентами.
  .venv/bin/python оформление/make_avatar.py
"""
import glob, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 1080
y, x = np.mgrid[0:S, 0:S].astype(np.float64)


def flag_texture(tw=2600, th=1300, cw=104, ch=70):
    codes = [os.path.basename(p)[:-4] for p in sorted(glob.glob(os.path.join(BASE, "assets/flags/*.png")))]
    random.Random(11).shuffle(codes)
    tex = Image.new("RGB", (tw, th), (12, 12, 20))
    k = 0
    for yy in range(0, th, ch):
        off = (yy // ch) % 2 * cw // 2
        for xx in range(-cw, tw, cw):
            f = Image.open(os.path.join(BASE, f"assets/flags/{codes[k % len(codes)]}.png")).convert("RGB")
            tex.paste(f.resize((cw - 5, ch - 5), Image.LANCZOS), (xx + off + 2, yy + 2))
            k += 1
    a = np.asarray(tex).astype(np.float64) / 255
    gray = a.mean(axis=2, keepdims=True)
    return np.clip(gray + (a - gray) * 1.25, 0, 1)  # чуть сочнее цвета


def globe(cx, cy, R, rot=0.6, tilt=-0.32):
    T = flag_texture()
    th, tw = T.shape[:2]
    nx, ny = (x - cx) / R, (y - cy) / R
    rr = nx ** 2 + ny ** 2
    nz = np.sqrt(np.clip(1 - rr, 0, 1))
    py = ny * np.cos(tilt) - nz * np.sin(tilt)
    pz = ny * np.sin(tilt) + nz * np.cos(tilt)
    lat = np.arcsin(np.clip(-py, -1, 1))
    lon = np.arctan2(nx, pz) + rot
    u = ((lon / (2 * np.pi)) % 1 * (tw - 1)).astype(int)
    v = ((0.5 - lat / np.pi) * (th - 1)).astype(int).clip(0, th - 1)
    col = T[v, u]
    L = np.array([-0.5, -0.62, 0.6]); L /= np.linalg.norm(L)
    lam = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    spec = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1) ** 55
    rim = np.clip((np.sqrt(rr) - 0.8) / 0.2, 0, 1) ** 2
    sph = col * (0.18 + 1.0 * lam)[:, :, None] + spec[:, :, None] * 0.6
    sph = sph * (1 - 0.4 * rim[:, :, None]) + np.array([0.35, 0.65, 1.0]) * 0.4 * rim[:, :, None]
    alpha = np.clip((1 - np.sqrt(rr)) * R, 0, 1)  # мягкий край
    return sph, alpha


def background(cx, cy, R):
    t = (y / S)[:, :, None]
    bg = np.array([0.11, 0.09, 0.25]) * (1 - t) + np.array([0.02, 0.02, 0.07]) * t
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / R
    halo = np.exp(-((d - 1.0) / 0.13) ** 2) * (d > 0.97)
    return bg + halo[:, :, None] * np.array([0.25, 0.5, 1.0]) * 0.6


def medal(im, mx, my, mr):
    d = ImageDraw.Draw(im)
    # ленты за медалью
    for dx, colr in ((-0.42, (214, 48, 64)), (0.42, (40, 110, 230))):
        bx = mx + dx * mr
        pts = [(bx - 0.28 * mr, my), (bx + 0.28 * mr, my), (bx + 0.28 * mr + dx * 0.5 * mr, my + 1.25 * mr),
               (bx + dx * 0.5 * mr, my + 1.02 * mr), (bx - 0.28 * mr + dx * 0.5 * mr, my + 1.25 * mr)]
        d.polygon(pts, fill=colr)
    # тень
    sh = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sh).ellipse((mx - mr, my - mr + 22, mx + mr, my + mr + 22), fill=180)
    im.paste((0, 0, 0), mask=sh.filter(ImageFilter.GaussianBlur(24)))
    arr = np.asarray(im).astype(np.float64) / 255
    md = np.sqrt((x - mx) ** 2 + (y - my) ** 2) / mr
    gy = np.clip((y - (my - mr)) / (2 * mr), 0, 1)[:, :, None]
    face = np.array([1.0, 0.88, 0.42]) * (1 - gy) + np.array([0.86, 0.56, 0.10]) * gy
    ring = np.array([0.80, 0.50, 0.06]) * (1 - gy) + np.array([1.0, 0.84, 0.36]) * gy  # ободок наоборот — даёт объём
    groove = np.abs(md - 0.80) < 0.025
    m = np.where((md <= 0.82)[:, :, None], face, ring)
    m = np.where(groove[:, :, None], m * 0.62, m)
    # блик по верхней дуге
    shine = np.clip(1 - np.abs(md - 0.62) / 0.12, 0, 1) * np.clip((my - y) / mr, 0, 1) * np.clip((mx - x) / mr + 0.6, 0, 1)
    m = m + shine[:, :, None] * 0.35
    aa = np.clip((1 - md) * mr, 0, 1)[:, :, None]
    arr = arr * (1 - aa) + m.clip(0, 1) * aa
    im = Image.fromarray((arr.clip(0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(os.path.join(BASE, "assets/fonts/Montserrat-Black.ttf"), int(mr * 0.98))
    d.text((mx + 5, my + 8), "#1", font=f, fill=(128, 76, 0), anchor="mm")
    d.text((mx, my), "#1", font=f, fill=(255, 252, 240), anchor="mm", stroke_width=2, stroke_fill=(150, 92, 0))
    return im


def main():
    cx, cy, R = S * 0.47, S * 0.45, S * 0.36
    sph, a = globe(cx, cy, R)
    bg = background(cx, cy, R)
    img = sph * a[:, :, None] + bg * (1 - a[:, :, None])
    im = Image.fromarray((img.clip(0, 1) * 255).astype(np.uint8))
    im = medal(im, S * 0.655, S * 0.635, S * 0.18)
    out = os.path.join(BASE, "оформление", "аватар.png")
    im.save(out)
    return out


if __name__ == "__main__":
    print(main())
