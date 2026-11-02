"""Формат «гонка графиков»: топ-10 стран год за годом, столбики обгоняют друг друга."""
import hashlib
from engine import *
from catalog import FMT, COUNTRIES
from render import _fit, _living_bg, _confetti, _draw_confetti, title_card, TITLE_CARD
from sound import race_track

TOP = 10
BAR_COLORS = [(255, 92, 120), (64, 196, 255), (46, 204, 113), (255, 196, 46), (190, 120, 255), (255, 140, 50),
              (0, 210, 190), (255, 110, 200), (120, 160, 255), (170, 220, 60), (255, 170, 120), (90, 200, 255)]


def _color(iso):
    return BAR_COLORS[int(hashlib.md5(iso.encode()).hexdigest(), 16) % len(BAR_COLORS)]


def render_race(years, series, topic, group_name, accent, out_path, seed=0):
    fmt = FMT[topic["fmt"]]
    ny = len(years)
    per_year = max(0.28, min(0.6, 21.0 / max(1, ny - 1)))
    t0 = 0.6
    race_end = t0 + (ny - 1) * per_year
    hold = 2.2
    end = race_end + hold
    dur = end + 3.2
    codes = list(series)

    def values_at(t):
        f = clamp((t - t0) / per_year, 0, ny - 1)
        i = min(int(f), ny - 2)
        k = f - i
        out = {}
        for c in codes:
            a, b = series[c][i], series[c][i + 1]
            if a is None and b is None:
                continue
            a = b if a is None else a
            b = a if b is None else b
            out[c] = a + (b - a) * k
        return out, years[0] + f

    # заранее считаем порядок по кадрам: события для звука и плавные позиции
    v = Video(f"race{seed}", dur, out_path)
    pos = {}
    leader, top3 = None, None
    leader_changes, top3_changes, decades = [], [], []
    frames = []
    for fi in range(v.n):
        t = fi / FPS
        vals, yf = values_at(t)
        ranked = sorted(vals, key=lambda c: -vals[c])
        for r, c in enumerate(ranked):
            target = r if r < TOP else TOP + 1
            pos[c] = target if c not in pos else pos[c] + (target - pos[c]) * 0.22
        if t0 <= t <= race_end:
            if leader and ranked[0] != leader:
                leader_changes.append(t)
            tt = tuple(ranked[:3])
            if top3 and tt != top3:
                top3_changes.append(t)
            leader, top3 = ranked[0], tt
        frames.append((vals, yf, ranked, dict(pos)))
    decades = [t0 + (y - years[0]) * per_year for y in years if y % 10 == 0 and y > years[0]]

    bg_tall = _living_bg(accent, seed + 3)
    conf = _confetti(accent, seed)
    h1, h2 = topic["hook"]
    y0, y1 = years[0], years[-1]
    sub = f"{topic['sub']} · {group_name}"
    f_h1, f_h2 = _fit(h1, 80, W - 80, True), _fit(f"{y0} → {y1}", 80, W - 80, True)
    f_sub, f_src = _fit(sub, 34, W - 100), font(26, False)
    f_name, f_val = font(34), font(36)
    f_year = font(230)
    slot0, slot_h, bar_h = 450, 112, 84
    x0 = 40
    max_bw = W - x0 - 250

    for fi, (vals, yf, ranked, pos) in enumerate(frames):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg_tall.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im)
        text(d, (W // 2, 150), h1, f_h1)
        text(d, (W // 2, 240), f"{y0} → {y1}", f_h2, fill=accent)
        text(d, (W // 2, 322), sub, f_sub, fill=(170, 175, 200))
        if t < race_end:
            gl = 0.5 + 0.5 * math.sin(t * 5)
            text(d, (W // 2, 385), f"WHO IS #1 IN {y1}?", font(34), fill=mix_color((150, 150, 175), accent, gl))
        text(d, (W // 2, 1850), "Source: World Bank Open Data", f_src, fill=(110, 115, 140))
        # год — огромной цифрой за столбиками
        yr = int(min(yf, y1))
        text(d, (W - 60, 1700), str(yr), f_year, fill=(60, 64, 92), anchor="rm")

        top_val = vals[ranked[0]] if ranked else 1
        for c in sorted(pos, key=lambda c: -pos[c]):  # нижние рисуем первыми
            p = pos[c]
            if p > TOP + 0.5 or c not in vals:
                continue
            y = int(slot0 + p * slot_h)
            val = vals[c]
            bw = max(8, int(max_bw * (abs(val) / (abs(top_val) or 1))))
            col = _color(c)
            is_lead = ranked and c == ranked[0]
            d.rounded_rectangle((x0, y, x0 + bw, y + bar_h), 20, fill=col)
            if is_lead and t >= race_end:
                glow = int(5 + 3 * math.sin((t - race_end) * 8))
                d.rounded_rectangle((x0 - 5, y - 5, x0 + bw + 5, y + bar_h + 5), 24, outline=(255, 255, 255), width=glow)
            fl = flag(c.lower(), 56)
            fx_ = x0 + bw - fl.width - 14 if bw > fl.width + 28 else x0 + bw + 12
            im.paste(fl, (fx_, y + (bar_h - 56) // 2), fl)
            name = COUNTRIES[c]
            nw = f_name.getlength(name)
            vs = fmt(val)
            vx = max(fx_ + fl.width + 14, x0 + bw + 14)
            if bw - fl.width - 44 > nw:
                text(d, (x0 + 20, y + bar_h // 2), name, f_name, fill=(255, 255, 255), anchor="lm",
                     stroke=2, stroke_fill=mix_color(col, (0, 0, 0), 0.45))
                text(d, (vx, y + bar_h // 2), vs, f_val, anchor="lm")
            else:
                text(d, (vx, y + bar_h // 2 - 20), name, font(28), anchor="lm")
                text(d, (vx, y + bar_h // 2 + 18), vs, font(30), fill=(200, 205, 225), anchor="lm")

        # финал: плашка победителя текущего года
        if race_end <= t < end + 0.3:
            a = ease_back((t - race_end) / 0.45)
            lead = ranked[0]
            cy = int(1440 + (1 - a) * 700)
            d.rounded_rectangle((90, cy - 95, W - 90, cy + 95), 40, fill=(20, 22, 34), outline=accent, width=6)
            fl = flag(lead.lower(), 96, 0.1)
            im.paste(fl, (140, cy - 48), fl)
            text(d, (160 + fl.width + 20, cy - 30), f"#1 in {y1}", font(40), fill=accent, anchor="lm")
            text(d, (160 + fl.width + 20, cy + 30), COUNTRIES[lead], _fit(COUNTRIES[lead], 56, W - 300 - fl.width, True),
                 anchor="lm")
            _draw_confetti(d, conf, t - race_end, W // 2, 700)

        if t < TITLE_CARD:
            im = title_card(im, t, [(h1, 110, (255, 255, 255)), (h2, 110, (255, 255, 255)), (f"{y0} → {y1}", 110, accent)],
                            accent, flags=ranked[:5], pill=f"WHO IS #1 IN {y1}?")
        if t >= end:
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.6 * ease_out((t - end) / 0.3))
            d = ImageDraw.Draw(im)
            a = ease_back((t - end) / 0.45)
            cy = int(H + 200 - a * (H // 2 + 200))
            d.rounded_rectangle((60, cy - 200, W - 60, cy + 200), 40, fill=(255, 255, 255))
            text(d, (W // 2, cy - 95), "Where is YOUR", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy - 15), "country?", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy + 75), "Comment below", font(44, False), fill=mix_color(accent, (0, 0, 0), 0.25))
            text(d, (W // 2, cy + 140), "Follow for daily rankings", font(32, False), fill=(120, 120, 135))
        v.write(im)

    track = race_track(dur, race_end, end, decades=decades, leader_changes=leader_changes,
                       top3_changes=top3_changes, seed=seed)
    return v.finish(audio=track)
