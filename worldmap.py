"""«Light Up the World» (12.11): тёмная карта мира, страна загорается, когда зритель пишет её флаг в комментариях,
и на ней навсегда остаётся ник того, кто её зажёг. Ролик: вчерашняя карта → камера летит к каждой новой стране →
вся карта и счётчик «N / 195». Контуры — Natural Earth 1:110m (общественное достояние).
"""
import json, math, os
from PIL import ImageFilter
from engine import *
from catalog import COUNTRIES
from render import _fit, _living_bg, _confetti, _draw_confetti, title_card, TITLE_CARD
from sound import duel_track
import tts

GEO = os.path.join(BASE, "assets", "map", "ne_110m_countries.geojson")
MW, MH = 3240, 1530  # карта в равнопромежуточной проекции, широты 84…-58 (без Антарктиды)
LAT0, LAT1 = 84.0, -58.0
GOAL = 195
VIEW_Y0, VIEW_H = 430, 1150  # где в кадре карта
OCEAN, LAND, BORDER = (10, 14, 30), (38, 46, 74), (60, 70, 105)
LIT, LIT_EDGE = (255, 205, 60), (255, 240, 170)
LAST = {}
_GEO = None


def _xy(lon, lat):
    return (lon + 180) / 360 * MW, (LAT0 - lat) / (LAT0 - LAT1) * MH


def shapes():
    """{iso2: {"polys": [[(x, y)...]], "label": (x, y), "bbox": (x0, y0, x1, y1)}}"""
    global _GEO
    if _GEO is None:
        _GEO = {}
        for f in json.load(open(GEO))["features"]:
            p = f["properties"]
            iso = p.get("ISO_A2_EH") if p.get("ISO_A2_EH", "-99") != "-99" else p.get("ISO_A2")
            if not iso or iso == "-99":
                continue
            g = f["geometry"]
            rings = [g["coordinates"][0]] if g["type"] == "Polygon" else [poly[0] for poly in g["coordinates"]]
            polys = [[_xy(lon, lat) for lon, lat in r] for r in rings]
            xs = [x for pl in polys for x, _ in pl]
            ys = [y for pl in polys for _, y in pl]
            _GEO[iso] = {"polys": polys, "label": _xy(p["LABEL_X"], p["LABEL_Y"]),
                         "bbox": (min(xs), min(ys), max(xs), max(ys))}
    return _GEO


def _map(lit):
    """Карта (RGB, MW×MH) с подсвеченными странами lit."""
    im = Image.new("RGB", (MW, MH), OCEAN)
    d = ImageDraw.Draw(im)
    for gy in range(0, MH, 54):  # точечная сетка океана
        for gx in range(0, MW, 54):
            d.point((gx, gy), fill=(28, 34, 60))
    glow = Image.new("L", (MW, MH), 0)
    gd = ImageDraw.Draw(glow)
    for iso, s in shapes().items():
        on = iso in lit
        for pl in s["polys"]:
            d.polygon(pl, fill=LIT if on else LAND, outline=LIT_EDGE if on else BORDER)
            if on:
                gd.polygon(pl, fill=255)
    if lit:
        halo = glow.filter(ImageFilter.GaussianBlur(18))
        im = Image.composite(Image.new("RGB", (MW, MH), (255, 170, 40)), im, halo.point(lambda v: int(v * 0.55)))
        d = ImageDraw.Draw(im)
        for iso in lit:
            for pl in shapes().get(iso, {}).get("polys", []):
                d.polygon(pl, fill=LIT, outline=LIT_EDGE)
    return im


def _cam_view(big, cx, cy, s):
    """Кадр камеры: центр (cx, cy) в координатах карты, s — пикселей кадра на пиксель карты."""
    vw, vh = W / s, VIEW_H / s
    box = (int(cx - vw / 2), int(cy - vh / 2), int(cx + vw / 2), int(cy + vh / 2))
    crop = big.crop(box)
    if box[0] < 0 or box[1] < 0 or box[2] > MW or box[3] > MH:  # поля за краем — цвет океана
        bg = Image.new("RGB", crop.size, OCEAN)
        bg.paste(big.crop((max(box[0], 0), max(box[1], 0), min(box[2], MW), min(box[3], MH))),
                 (max(-box[0], 0), max(-box[1], 0)))
        crop = bg
    return crop.resize((W, VIEW_H), Image.BILINEAR), box


def render_lightup(before, new, lit_by, total, accent, out_path, seed=0):
    """before — страны, горевшие вчера; new — [iso] загораются в этом ролике (по порядку); lit_by — {iso: ник};
    total — сколько стран горит после ролика (могут быть и мелкие, которых нет на карте 1:110m)."""
    geo = shapes()
    new = [c for c in new if c in geo][:6]
    S0 = 2.2  # до этого — вчерашняя карта целиком
    PER = 1.6
    S1 = S0 + PER * len(new)
    final_t = S1 + 0.9
    end = final_t + 2.6
    dur = end + 3.0
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + хук"), (0.6, "вчерашняя карта"), (S0, "новые страны"),
                                    (final_t, "вся карта"), (end, "призыв")]}
    stages = [_map(set(before) | set(new[:k])) for k in range(len(new) + 1)]
    fit = W / MW  # вся карта по ширине кадра
    world = (MW / 2, MH / 2 + 60, fit)

    def cam_at(t):
        if t < S0 or not new:
            return world
        if t >= S1:
            k = ease_out((t - S1) / 0.8)
            last = _target(new[-1])
            return tuple(last[i] + (world[i] - last[i]) * k for i in range(3))
        i = min(int((t - S0) / PER), len(new) - 1)
        lt = (t - S0) - i * PER
        prev = world if i == 0 else _target(new[i - 1])
        k = ease_out(lt / 0.55)
        tg = _target(new[i])
        return tuple(prev[j] + (tg[j] - prev[j]) * k for j in range(3))

    def _target(iso):
        x0, y0, x1, y1 = geo[iso]["bbox"]
        lx, ly = geo[iso]["label"]
        span = max(x1 - x0, (y1 - y0) * W / VIEW_H, 140)
        return lx, ly, min(W / (span * 2.4), 3.2)

    v = Video(f"map{seed}", dur, out_path)
    bg = _living_bg(accent, seed + 31)
    conf = _confetti(accent, seed)
    n_before = total - len(new)
    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg.crop((0, oy, W, oy + H))
        k = 0 if t < S0 + 0.45 else min(len(new), int((t - S0 - 0.45) / PER) + 1)  # загорается, когда камера долетела
        cx, cy, s = cam_at(t)
        view, box = _cam_view(stages[k], cx, cy, s)
        im.paste(view, (0, VIEW_Y0))
        d = ImageDraw.Draw(im)
        lit_now = n_before + k
        text(d, (W // 2, 140), "LIGHT UP", font(96))
        text(d, (W // 2, 240), "THE WORLD", font(96), fill=LIT)
        cnt = f"{lit_now} / {GOAL}"
        pulse = 1 + 0.25 * max(0, 1 - ((t - S0) % PER) / 0.4) if S0 <= t < S1 else 1
        text(d, (W // 2, 350), cnt + " countries lit", _fit(cnt + " countries lit", int(54 * pulse), W - 100, True))
        if t < S0:
            text(d, (W // 2, VIEW_Y0 + VIEW_H + 70), "YESTERDAY", font(54), fill=(170, 175, 200))
        elif t < S1 and new:  # подпись новой страны: флаг + кто зажёг
            i = min(int((t - S0) / PER), len(new) - 1)
            lt = (t - S0) - i * PER
            if lt >= 0.45:
                iso = new[i]
                a = ease_back((lt - 0.45) / 0.35)
                cy_ = VIEW_Y0 + VIEW_H + 80
                d.rounded_rectangle((70, cy_ - 75, W - 70, cy_ + 75), 36, fill=(20, 22, 34), outline=LIT, width=5)
                fl = flag_box(iso.lower(), 150, 96, 0.1)
                im.paste(fl, (110, cy_ - fl.height // 2), fl)
                nm = COUNTRIES.get(iso, iso)
                text(d, (290, cy_ - 25), f"{nm} is lit!", _fit(f"{nm} is lit!", int(52 * a) + 1, W - 400, True), anchor="lm")
                by = lit_by.get(iso)
                if by:
                    text(d, (290, cy_ + 32), f"by @{by}", _fit(f"by @{by}", 40, W - 400), fill=LIT, anchor="lm")
                if lt < 0.75:  # вспышка на стране
                    lx, ly = geo[iso]["label"]
                    px = (lx - box[0]) / (box[2] - box[0]) * W
                    py = VIEW_Y0 + (ly - box[1]) / (box[3] - box[1]) * VIEW_H
                    r = int(40 + 260 * (lt - 0.45) / 0.3)
                    d.ellipse((px - r, py - r, px + r, py + r), outline=(255, 255, 255), width=6)
        else:
            text(d, (W // 2, VIEW_Y0 + VIEW_H + 70), f"TODAY · +{len(new)} new", font(54), fill=LIT)
        if final_t <= t < end:
            _draw_confetti(d, conf, t - final_t, W // 2, VIEW_Y0 + VIEW_H // 2)
        if t < TITLE_CARD:
            im = title_card(im, t, [("LIGHT UP", 120, (255, 255, 255)), ("THE WORLD", 120, LIT),
                                    (f"{lit_now} / {GOAL} COUNTRIES", 56, (175, 180, 205))], accent,
                            pill="IS YOUR COUNTRY LIT?")
        if t >= end:
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.6)
            d = ImageDraw.Draw(im)
            a2 = ease_back((t - end) / 0.45)
            cy_ = int(H + 200 - a2 * (H // 2 + 200))
            d.rounded_rectangle((60, cy_ - 220, W - 60, cy_ + 220), 40, fill=(255, 255, 255))
            text(d, (W // 2, cy_ - 120), "Is YOUR country dark?", font(64), fill=(15, 15, 25))
            text(d, (W // 2, cy_ - 40), "Comment its flag 👇".replace(" 👇", ""), font(64), fill=(15, 15, 25))
            text(d, (W // 2, cy_ + 55), "Your name stays on it forever", font(44, False), fill=mix_color(accent, (0, 0, 0), 0.25))
            text(d, (W // 2, cy_ + 130), "First to light it wins the spot", font(34, False), fill=(120, 120, 135))
        v.write(im)
    plan = [(0.15, f"Every comment lights up a country. Yesterday, {n_before} countries were lit.")]
    for i, iso in enumerate(new):
        by = lit_by.get(iso)
        plan.append((S0 + i * PER + 0.45, f"{COUNTRIES.get(iso, iso)}!" if i else
                     f"Today: {COUNTRIES.get(iso, iso)}, lit by {by}!" if by else f"{COUNTRIES.get(iso, iso)}!"))
    plan += [(final_t + 0.1, f"{total} countries lit. {GOAL - total} still dark."),
             (end + 0.3, "Is your country dark? Comment its flag. Your name stays on it forever!")]
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, 0.45), [(S0 + i * PER, S0 + i * PER + 0.45) for i in range(len(new))],
                       final_t, end, seed=seed, voice=voice)
    return v.finish(audio=track)
