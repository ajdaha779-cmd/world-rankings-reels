"""«Light Up the World» (12.11): тёмная карта мира, страна загорается, когда зритель пишет её флаг в комментариях,
и на ней навсегда остаётся ник того, кто её зажёг. Ролик: вчерашняя карта → камера летит к каждой новой стране →
вся карта и счётчик «N / 195». Контуры — Natural Earth 1:110m (общественное достояние).
"""
import json, math, os
from PIL import ImageFilter
from engine import *
from engine import SR
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
            main = max(polys, key=lambda pl: (max(x for x, _ in pl) - min(x for x, _ in pl)) *
                       (max(y for _, y in pl) - min(y for _, y in pl)))  # для камеры: без Чукотки за краем карты и т. п.
            _GEO[iso] = {"polys": polys, "label": _xy(p["LABEL_X"], p["LABEL_Y"]),
                         "bbox": (min(xs), min(ys), max(xs), max(ys)),
                         "main": (min(x for x, _ in main), min(y for _, y in main), max(x for x, _ in main), max(y for _, y in main))}
    return _GEO


def _flag_fill(iso, w, h):
    """Флаг, растянутый на прямоугольник страны: все полосы видны и у вытянутых стран (Россия, Чили)."""
    path = os.path.join(BASE, "assets", "flags", f"{iso.lower()}.png")
    if not os.path.exists(path):
        return Image.new("RGB", (w, h), LIT)
    return Image.open(path).convert("RGB").resize((w, h), Image.LANCZOS)


def _map(lit):
    """Карта (RGB, MW×MH): зажжённые страны залиты своим флагом, вокруг — мягкое свечение."""
    im = Image.new("RGB", (MW, MH), OCEAN)
    d = ImageDraw.Draw(im)
    for gy in range(0, MH, 54):  # точечная сетка океана
        for gx in range(0, MW, 54):
            d.point((gx, gy), fill=(28, 34, 60))
    glow = Image.new("L", (MW, MH), 0)
    gd = ImageDraw.Draw(glow)
    geo = shapes()
    for iso, s_ in geo.items():
        for pl in s_["polys"]:
            d.polygon(pl, fill=LAND, outline=BORDER)
            if iso in lit:
                gd.polygon(pl, fill=255)
    if lit:
        halo = glow.filter(ImageFilter.GaussianBlur(14))
        im = Image.composite(Image.new("RGB", (MW, MH), (255, 255, 255)), im, halo.point(lambda v: int(v * 0.45)))
        d = ImageDraw.Draw(im)
    for iso in lit:
        g = geo.get(iso)
        if not g:
            continue
        x0, y0, x1, y1 = (int(v) for v in g["bbox"])
        x1, y1 = x1 + 2, y1 + 2
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        for pl in g["polys"]:
            md.polygon([(x - x0, y - y0) for x, y in pl], fill=255)
        mx0, my0, mx1, my1 = (int(v) for v in g["main"])  # флаг ложится на основную часть страны,
        main_fl = _flag_fill(iso, max(1, mx1 - mx0 + 2), max(1, my1 - my0 + 2))  # острова — средним цветом флага
        fill = Image.new("RGB", (w, h), main_fl.resize((1, 1), Image.BOX).getpixel((0, 0)))
        fill.paste(main_fl, (mx0 - x0, my0 - y0))
        im.paste(fill, (x0, y0), mask)
        for pl in g["polys"]:
            d.line(pl + [pl[0]], fill=(255, 255, 255), width=3)
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


def _speakable(nick):
    """Ник для голоса: «raj_22» → «raj 22», «lucas.br» → «lucas b r»."""
    import re
    parts = re.split(r"[._]+", nick.strip("._"))
    return " ".join(" ".join(p) if len(p) <= 2 and p.isalpha() and len(parts) > 1 else p for p in parts if p)


LINES = ["{nick} just put {country} on the map!", "{country} is lit, thanks to {nick}!",
         "Welcome to the map, {country}! Lit by {nick}.", "{nick} lights up {country}!",
         "And here's {country}, lit by {nick}!"]


def _who(nicks):
    """«@a, @b +2» — кто зажёг страну."""
    return ", ".join("@" + n for n in nicks[:2]) + (f" +{len(nicks) - 2}" if len(nicks) > 2 else "")


def _say_who(nicks):
    names = [_speakable(n) for n in nicks[:2]]
    return " and ".join(names) + (f" and {len(nicks) - 2} more" if len(nicks) > 2 else "")


def _tag(im, d, x, y, label, size, hot=False):
    """Ник на стране: тёмная плашка с белым текстом, по центру точки (x, y)."""
    f = font(size)
    w = f.getlength(label) + size
    h = size * 1.5
    x = min(max(x, w / 2 + 6), W - w / 2 - 6)
    d.rounded_rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), int(h / 2), fill=(12, 14, 26),
                        outline=LIT if hot else (255, 255, 255), width=3 if hot else 2)
    text(d, (int(x), int(y)), label, f, fill=LIT if hot else (255, 255, 255))


def render_lightup(before, new, lit_by, total, accent, out_path, seed=0):
    """before — страны, горевшие раньше; new — [iso] загораются в этом ролике (по порядку); lit_by — {iso: [ники]};
    total — сколько стран горит после ролика. Диктор объясняет правила и называет каждого, кто зажёг страну;
    картинка подстраивается под длину реплик."""
    import random
    geo = shapes()
    new = [c for c in new if c in geo][:16]  # больше — ролик слишком длинный; остальные войдут в следующий
    lit_by = {c: ([v] if isinstance(v, str) else list(v)) for c, v in lit_by.items()}
    short = len(new) > 8  # много стран (первый ролик) — короткие реплики, чтобы ролик не затянулся
    n_before = total - len(new)
    rnd = random.Random(seed)
    voice_on = tts.available()
    vname = tts.voice_for(seed)

    def clip(txt):
        return tts.say(tts.spoken(txt), vname) if voice_on else None

    def length(a, fallback):
        return len(a) / SR if a is not None else fallback

    intro_txt = ("This map lights up from your comments. Comment your country's flag, and the first person "
                 "to do it gets their name on that country. Forever." if not before else
                 f"Yesterday, {n_before} countries were lit. Comment your flag to light yours. Here's who joined the map!")
    intro = clip(intro_txt)
    S0 = 0.3 + length(intro, 4.0) + 0.3  # пока диктор объясняет — тёмная карта и три шага на экране
    lines, seg = [], []
    t = S0
    for i, iso in enumerate(new):
        by = lit_by.get(iso)
        cn = COUNTRIES.get(iso, iso)
        if not by:
            txt = f"{cn} is lit!"
        elif short:
            txt = f"{cn}, {_say_who(by)}!"
        else:
            txt = rnd.choice(LINES).format(nick=_say_who(by), country=cn)
        a = clip(txt)
        L = max(1.2 if short else 1.6, 0.45 + length(a, 1.0) + 0.2)
        seg.append((t, L))
        lines.append((t + 0.45, a))
        t += L
    S1 = t
    final_t = S1 + 0.4
    outro = clip(f"{total} countries lit. {GOAL - total} still dark.")
    end = final_t + max(2.4, length(outro, 2.0) + 0.4)
    cta = clip("Is your country still dark? Comment its flag, and your name appears on the map in the next video!")
    dur = end + max(3.0, length(cta, 3.0) + 0.6)
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + правила"), (S0, "новые страны"), (final_t, "вся карта"), (end, "призыв")]}
    stages = [_map(set(before) | set(new[:k])) for k in range(len(new) + 1)]
    fit = W / MW
    world = (MW / 2, MH / 2 + 60, fit)

    def _target(iso):
        x0, y0, x1, y1 = geo[iso]["main"]
        lx, ly = geo[iso]["label"]
        span = max(x1 - x0, (y1 - y0) * W / VIEW_H, 140)
        return lx, ly, min(W / (span * 1.5), 3.2)

    def where(t):
        """(индекс страны, время внутри её отрезка) или (None, 0)."""
        for i, (st, L) in enumerate(seg):
            if st <= t < st + L:
                return i, t - st
        return None, 0

    def cam_at(t):
        if t < S0 or not new:
            return world
        if t >= S1:
            k = ease_out((t - S1) / 0.8)
            last = _target(new[-1])
            return tuple(last[j] + (world[j] - last[j]) * k for j in range(3))
        i, lt = where(t)
        prev = world if i == 0 else _target(new[i - 1])
        k = ease_out(lt / 0.55)
        tg = _target(new[i])
        return tuple(prev[j] + (tg[j] - prev[j]) * k for j in range(3))

    v = Video(f"map{seed}", dur, out_path)
    bg = _living_bg(accent, seed + 31)
    conf = _confetti(accent, seed)
    steps = [("1", "Comment your country's flag"), ("2", "It lights up on this map"), ("3", "First one = your name on it")]
    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg.crop((0, oy, W, oy + H))
        i, lt = where(t)
        k = 0 if t < S0 else len(new) if t >= S1 else i + (1 if lt >= 0.45 else 0)  # загорается, когда камера долетела
        cx, cy, s = cam_at(t)
        view, box = _cam_view(stages[k], cx, cy, s)
        im.paste(view, (0, VIEW_Y0))
        d = ImageDraw.Draw(im)
        # ники прямо на странах: кто её зажёг
        tsize = 22 if s < 0.6 else 30 if s < 1.5 else 36
        cur = new[i] if i is not None and t >= S0 else None
        for iso in list(before) + new[:k]:
            if iso not in geo or not lit_by.get(iso):
                continue
            lx, ly = geo[iso]["label"]
            px = (lx - box[0]) / (box[2] - box[0]) * W
            py = VIEW_Y0 + (ly - box[1]) / (box[3] - box[1]) * VIEW_H
            if 0 <= px <= W and VIEW_Y0 + 20 <= py <= VIEW_Y0 + VIEW_H - 20:
                _tag(im, d, px, py, _who(lit_by[iso]) if iso == cur else "@" + lit_by[iso][0], tsize, iso == cur)
        lit_now = n_before + k
        text(d, (W // 2, 140), "LIGHT UP", font(96))
        text(d, (W // 2, 240), "THE WORLD", font(96), fill=LIT)
        cnt = f"{lit_now} / {GOAL} countries lit"
        pulse = 1 + 0.25 * max(0, 1 - (lt - 0.45) / 0.4) if i is not None and lt >= 0.45 else 1
        text(d, (W // 2, 350), cnt, _fit(cnt, int(54 * pulse), W - 100, True))
        if t < S0:  # правила, пока диктор их объясняет
            for j, (num, txt) in enumerate(steps):
                st_ = 0.7 + j * (S0 - 1.0) / 3
                if t < st_:
                    continue
                a = ease_out((t - st_) / 0.35)
                y = VIEW_Y0 + 260 + j * 230
                dx = int((1 - a) * W)
                d.rounded_rectangle((70 + dx, y, W - 70 + dx, y + 190), 34, fill=(20, 22, 34), outline=LIT, width=4)
                d.ellipse((110 + dx, y + 45, 210 + dx, y + 145), fill=LIT)
                text(d, (160 + dx, y + 95), num, font(60), fill=(20, 20, 30))
                text(d, (250 + dx, y + 95), txt, _fit(txt, 52, W - 380, True), anchor="lm")
        elif i is not None and lt >= 0.45:  # подпись новой страны: флаг + кто зажёг
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
                text(d, (290, cy_ + 32), f"by {_who(by)}", _fit(f"by {_who(by)}", 40, W - 400), fill=LIT, anchor="lm")
            if lt < 0.75:  # вспышка на стране
                lx, ly = geo[iso]["label"]
                px = (lx - box[0]) / (box[2] - box[0]) * W
                py = VIEW_Y0 + (ly - box[1]) / (box[3] - box[1]) * VIEW_H
                r = int(40 + 260 * (lt - 0.45) / 0.3)
                d.ellipse((px - r, py - r, px + r, py + r), outline=(255, 255, 255), width=6)
        elif t >= S1:
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
            text(d, (W // 2, cy_ - 40), "Comment its flag", font(64), fill=(15, 15, 25))
            text(d, (W // 2, cy_ + 55), "Your name goes on the map", font(44, False), fill=mix_color(accent, (0, 0, 0), 0.25))
            text(d, (W // 2, cy_ + 130), "in the next video", font(34, False), fill=(120, 120, 135))
        v.write(im)
    voice = [(0.3, intro)] + lines + [(final_t + 0.1, outro), (end + 0.3, cta)]
    voice = [(tt, a) for tt, a in voice if a is not None]
    track = duel_track(dur, (0.15, 0.45), [(st + 0.0, st + 0.45) for st, _ in seg], final_t, end, seed=seed, voice=voice)
    return v.finish(audio=track)
