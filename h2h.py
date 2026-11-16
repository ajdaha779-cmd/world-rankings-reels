"""«X vs Y (1960 → 2025)» (16.11): две страны год за годом — два больших столбика, бегущий год, корона у лидера,
вспышка «OVERTAKE!» при смене лидера. На YouTube такие ролики пользователя (сделанные вручную) — лучшие на канале
(«Indonesia vs Malaysia» — 463 просмотра за 5 ч, 59% досмотра). У нас — только реальные данные World Bank, без прогнозов.
"""
import math
from engine import *
from catalog import FMT, COUNTRIES, flag_emoji
from render import _fit, _living_bg, _confetti, _draw_confetti, title_card, TITLE_CARD, progress, shout_strip
from sound import duel_track
import tts

LAST = {}
COLS = [(226, 58, 74), (44, 108, 232)]
# индикатор, что сравниваем (для заголовка), подпись, формат
STATS = [("NY.GDP.PCAP.CD", "richer per person", "GDP per person (USD)", "money"),
         ("NY.GDP.MKTP.CD", "the bigger economy", "GDP (USD)", "money"),
         ("SP.POP.TOTL", "more people", "Population", "people"),
         ("SP.DYN.LE00.IN", "longer lives", "Life expectancy (years)", "years"),
         ("MS.MIL.XPND.CD", "the bigger military budget", "Military spending (USD)", "money")]
BONUS = {"NY.GDP.PCAP.CD": 0.8, "NY.GDP.MKTP.CD": 0.5, "SP.POP.TOTL": 0.2, "SP.DYN.LE00.IN": -1.5,
         "MS.MIL.XPND.CD": -0.8}  # «кто богаче» цепляет сильнее всего; армия — изредка, жизнь — спокойная тема
QUESTION = {"NY.GDP.PCAP.CD": "who's richer?", "NY.GDP.MKTP.CD": "whose economy is bigger?",
            "SP.POP.TOTL": "who has more people?", "SP.DYN.LE00.IN": "who lives longer?",
            "MS.MIL.XPND.CD": "who spends more on the army?"}
PAST = {"NY.GDP.PCAP.CD": "richer", "NY.GDP.MKTP.CD": "a bigger economy", "SP.POP.TOTL": "more populous",
        "SP.DYN.LE00.IN": "living longer", "MS.MIL.XPND.CD": "spending more on its army"}
PAIRS = [("IN", "CN"), ("ID", "MY"), ("KR", "JP"), ("PH", "VN"), ("ID", "PH"), ("TR", "IR"), ("BR", "AR"), ("MX", "BR"),
         ("NG", "ZA"), ("EG", "SA"), ("CN", "JP"), ("US", "CN"), ("RU", "CN"), ("VN", "TH"), ("TH", "MY"), ("KZ", "UZ"),
         ("AZ", "GE"), ("SA", "AE"), ("IN", "ID"), ("KR", "TW"), ("PL", "PT"), ("TR", "GR"), ("CL", "AR"), ("BD", "PK"),
         ("IE", "GB"), ("ES", "IT"), ("DE", "JP"), ("CN", "BR"), ("NG", "EG"), ("PH", "TH"), ("VN", "ID"),
         ("KE", "ET"), ("UZ", "AZ"), ("CO", "PE"), ("TR", "PL"), ("KR", "IT"), ("MY", "SG"), ("IN", "BD")]


def series(a, b, ind):
    """(годы, va, vb, годы смены лидера) — только годы, где есть данные у обеих стран."""
    from data import history
    h = history(ind)
    if a not in h or b not in h:
        return None
    years = [y for y in range(1960, 2030) if y in h[a] and y in h[b]]
    if len(years) < 20:
        return None
    va, vb = [h[a][y] for y in years], [h[b][y] for y in years]
    flips = [years[i] for i in range(1, len(years)) if (va[i] > vb[i]) != (va[i - 1] > vb[i - 1])]
    return years, va, vb, flips


def best_stat(a, b):
    """Самое острое сравнение для пары: смена лидера (чем позже — тем неожиданнее) и большой итоговый разрыв.
    «Пила» (много смен) — скучно. Военные бюджеты — только для пар без конфликтов (BLOCKED отсеян в PAIRS)."""
    best = None
    for ind, what, label, fmt in STATS:
        s = series(a, b, ind)
        if not s:
            continue
        years, va, vb, flips = s
        ratio = max(va[-1], vb[-1]) / max(min(va[-1], vb[-1]), 1e-9)
        if not 1 <= len(flips) <= 3:
            score = math.log(ratio) * 0.5  # без обгона — интересно только огромным разрывом
        else:
            score = 3 + (flips[-1] - years[0]) / 30 + min(math.log(ratio), 2) - 0.8 * (len(flips) - 1)
            if flips[-1] - flips[0] <= 2 and len(flips) > 1:  # «пила» в соседние годы — шум
                score -= 1.5
        score += BONUS.get(ind, 0)
        if best is None or score > best[0]:
            best = (score, ind, what, label, fmt, s)
    return best and best[1:]


def title_for(a, b, ind, what, s):
    """Острый заголовок: «India was richer than China until 1990 😳» или «China vs India: who's richer? 1960 → 2025»."""
    years, va, vb, flips = s
    na, nb = COUNTRIES[a], COUNTRIES[b]
    if len(flips) == 1:  # 16.11: «until» только при одной смене лидера, иначе неправда («China lived longer than USA until 2023»)
        y = flips[-1]
        i = years.index(y) - 1
        lead, other = (na, nb) if va[i] > vb[i] else (nb, na)
        return f"{lead} was {PAST[ind]} than {other} until {y} 😳 {flag_emoji(a)}🆚{flag_emoji(b)}"
    if flips:
        return f"{na} vs {nb}: {QUESTION[ind]} The lead changed {len(flips)} times 😳 {flag_emoji(a)}🆚{flag_emoji(b)}"
    return f"{na} vs {nb}: {QUESTION[ind]} {years[0]} → {years[-1]} {flag_emoji(a)}🆚{flag_emoji(b)}"


GAP = {"GDP per person (USD)": "richer per person", "GDP (USD)": "bigger economy", "Population": "more people",
       "Military spending (USD)": "bigger military budget"}


def gap_text(label, hi, lo):
    """Подпись разрыва на финальной карточке: «+0.4 years longer life», «12% richer per person», «3.4× more people»."""
    if label.startswith("Life expectancy"):
        return f"+{hi - lo:.1f} years longer life"
    r = hi / max(lo, 1e-9)
    if r < 1.5:
        return f"{(r - 1) * 100:.0f}% {GAP.get(label, 'ahead')}"
    return f"{r:.1f}× {GAP.get(label, 'ahead')}" if r < 10 else f"{r:.0f}× {GAP.get(label, 'ahead')}"


def render_h2h(a, b, years, va, vb, flips, label, fmt_id, accent, out_path, seed=0, what=""):
    fmt = FMT[fmt_id]
    ny = len(years)
    per_year = max(0.17, min(0.32, 13.0 / max(1, ny - 1)))
    t0 = 1.2
    race_end = t0 + (ny - 1) * per_year
    final_t = race_end + 0.5
    card_end = final_t + 2.6
    dur = card_end + 3.0
    flip_t = [t0 + years.index(y) * per_year for y in flips]
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + хук"), (t0, "годы пошли"), ((t0 + race_end) / 2, "середина"),
                                    (race_end, "последний год"), (final_t, "вердикт"), (card_end, "призыв")]}
    names = (COUNTRIES[a], COUNTRIES[b])
    v = Video(f"h2h{seed}", dur, out_path)
    bg = _living_bg(accent, seed + 41)
    conf = _confetti(accent, seed)
    base, top_h = 1500, 820

    def at(t):
        f = clamp((t - t0) / per_year, 0, ny - 1)
        i = min(int(f), ny - 2)
        k = f - i
        return years[i] + k, va[i] + (va[i + 1] - va[i]) * k, vb[i] + (vb[i + 1] - vb[i]) * k

    win = 0 if va[-1] > vb[-1] else 1
    ratio = max(va[-1], vb[-1]) / max(min(va[-1], vb[-1]), 1e-9)
    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im)
        year, xa, xb = at(t)
        mx = max(xa, xb) * 1.08 or 1
        head = f"{names[0].upper()} vs {names[1].upper()}"
        text(d, (W // 2, 140), head, _fit(head, 80, W - 80, True))
        text(d, (W // 2, 225), label, _fit(label, 40, W - 100), fill=(170, 175, 200))
        text(d, (W // 2, 360), str(int(year)), font(150), fill=accent)
        lead = 0 if xa >= xb else 1
        for side, val in ((0, xa), (1, xb)):
            cx = 300 if side == 0 else W - 300
            bh = int(top_h * val / mx * ease_out((t - 0.6) / 0.6))
            col = COLS[side] if side == lead else mix_color(COLS[side], (40, 40, 55), 0.35)
            d.rounded_rectangle((cx - 150, base - max(bh, 12), cx + 150, base), 28, fill=col)
            if side == lead and t >= t0:
                d.rounded_rectangle((cx - 156, base - max(bh, 12) - 6, cx + 156, base + 6), 32, outline=accent, width=6)
                text(d, (cx, base - max(bh, 12) - 140), "👑".replace("👑", "LEADER"), font(36), fill=accent)
            text(d, (cx, base - max(bh, 12) - 70), fmt(val), _fit(fmt(val), 60, 340, True))
            fl = flag_box((a, b)[side].lower(), 230, 140, 0.08)
            d.rounded_rectangle((cx - fl.width // 2 - 8, base + 40 - 8, cx + fl.width // 2 + 8, base + 40 + fl.height + 8), 20,
                                fill=(255, 255, 255))
            im.paste(fl, (cx - fl.width // 2, base + 40), fl)
            text(d, (cx, base + 230), names[side], _fit(names[side], 48, 420, True))
        for ft in flip_t:  # смена лидера — вспышка
            if ft <= t < ft + 1.1:
                pop = ease_back((t - ft) / 0.3)
                text(d, (W // 2, 490), "OVERTAKE!", font(int(76 * pop) + 1), fill=accent)
        if t < final_t:
            progress(d, (t - t0) / max(race_end - t0, 1e-6) if t > t0 else 0, 270, accent)
        if final_t <= t < card_end + 0.35:
            a_in = ease_back((t - final_t) / 0.45)
            a_out = ease_out((t - card_end) / 0.35) if t >= card_end else 0
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.55 * (1 - a_out) * ease_out((t - final_t) / 0.2))
            d = ImageDraw.Draw(im)
            _draw_confetti(d, conf, t - final_t, W // 2, 1100)
            cy = int(H + 500 - a_in * (H // 2 + 400) - a_out * (H // 2 + 600))
            d.rounded_rectangle((80, cy - 330, W - 80, cy + 330), 50, fill=(20, 22, 34), outline=accent, width=8)
            text(d, (W // 2, cy - 250), f"IN {years[-1]}", font(64), fill=accent)
            fl = flag((a, b)[win].lower(), 220, 0.08)
            d.rounded_rectangle((W // 2 - fl.width // 2 - 10, cy - 180, W // 2 + fl.width // 2 + 10, cy - 160 + fl.height),
                                26, fill=(255, 255, 255))
            im.paste(fl, (W // 2 - fl.width // 2, cy - 170), fl)
            text(d, (W // 2, cy + 110), names[win], _fit(names[win], 90, W - 240, True))
            sub = gap_text(label, max(va[-1], vb[-1]), min(va[-1], vb[-1]))
            text(d, (W // 2, cy + 220), sub, _fit(sub, 56, W - 220))
        if t < TITLE_CARD:
            im = title_card(im, t, [(names[0].upper(), 100, (255, 255, 255)), ("VS", 80, accent),
                                    (names[1].upper(), 100, (255, 255, 255))], accent, flags=(a, b),
                            pill=f"{years[0]} – {years[-1]}", fh=150)
        if t >= card_end + 0.35:
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.6)
            d = ImageDraw.Draw(im)
            a2 = ease_back((t - card_end - 0.35) / 0.45)
            cy = int(H + 200 - a2 * (H // 2 + 200))
            d.rounded_rectangle((60, cy - 200, W - 60, cy + 200), 40, fill=(255, 255, 255))
            text(d, (W // 2, cy - 95), "Which 2 countries", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy - 15), "should race next?", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy + 75), "Comment 2 flags 👇".replace(" 👇", ""), font(44, False),
                 fill=mix_color(accent, (0, 0, 0), 0.25))
            text(d, (W // 2, cy + 140), "Follow for daily battles", font(32, False), fill=(120, 120, 135))
            shout_strip(im, cy, accent)
        v.write(im)
    first = names[0] if va[0] > vb[0] else names[1]
    plan = [(0.15, f"{names[0]} versus {names[1]}. In {years[0]}, {first} was ahead. Watch what happens."),
            (final_t + 0.05, f"In {years[-1]}, {names[win]} wins!"),
            (card_end + 0.5, "Which two countries should race next? Comment below!")]
    if flips:
        plan.insert(1, (flip_t[0] + 0.05, f"{years[years.index(flips[0])]}! The lead changes!"))
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, 0.45), [(ft - 0.3, ft) for ft in flip_t[:4]], final_t, card_end + 0.35, seed=seed,
                       voice=voice)
    return v.finish(audio=track)
