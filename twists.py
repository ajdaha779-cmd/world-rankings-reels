"""Форматы «твистов» (12.11): страна против целого континента, «кто кого обогнал» и «угадай страну по подсказкам».

Все цифры — World Bank. Звук — duel_track (удары, «вжух» на этап, нарастание перед развязкой).
"""
import math
from engine import *
from catalog import FMT, COUNTRIES, GROUPS
from render import _fit, _living_bg, _confetti, _draw_confetti, title_card, TITLE_CARD, progress, PANEL
from sound import duel_track
import tts

LAST = {}
INTRO = 1.0
LEFT_COL, RIGHT_COL = (226, 58, 74), (44, 108, 232)
SEG_COLS = [(64, 196, 255), (46, 204, 113), (255, 196, 46), (190, 120, 255), (255, 140, 50), (0, 210, 190),
            (255, 110, 200), (120, 160, 255)]


def _cta(im, t, t0, accent, l1, l2, l3):
    """Финальная белая карточка с призывом к комментарию."""
    im = Image.blend(im, Image.new("RGB", (W, H)), 0.6)
    d = ImageDraw.Draw(im)
    a = ease_back((t - t0) / 0.45)
    cy = int(H + 200 - a * (H // 2 + 200))
    d.rounded_rectangle((60, cy - 200, W - 60, cy + 200), 40, fill=(255, 255, 255))
    text(d, (W // 2, cy - 95), l1, _fit(l1, 66, W - 180, True), fill=(15, 15, 25))
    text(d, (W // 2, cy - 15), l2, _fit(l2, 66, W - 180, True), fill=(15, 15, 25))
    text(d, (W // 2, cy + 75), l3, font(44, False), fill=mix_color(accent, (0, 0, 0), 0.25))
    text(d, (W // 2, cy + 140), "Follow for daily battles", font(32, False), fill=(120, 120, 135))
    return im


def _paste_flag(im, d, code, cx, cy, w, h):
    fl = flag_box(code.lower(), w, h, 0.08)
    d.rounded_rectangle((cx - fl.width // 2 - 8, cy - fl.height // 2 - 8, cx + fl.width // 2 + 8,
                         cy + fl.height // 2 + 8), 20, fill=(255, 255, 255))
    im.paste(fl, (cx - fl.width // 2, cy - fl.height // 2), fl)


# ---------- 1. страна против целого континента ----------
def render_bigger(c, g, ind, fmt_id, noun, accent, out_path, seed=0):
    """Слева — одна страна, справа столбик континента собирается из стран по одной: догонит или нет?"""
    from data import indicator
    vals = indicator(ind)
    members = sorted((m for m in GROUPS[g][1] if m in vals and m != c), key=lambda m: -vals[m][0])
    cv, total = vals[c][0], sum(vals[m][0] for m in members)
    gname = GROUPS[g][0].replace("the ", "")
    fmt = FMT[fmt_id]
    S0, S1 = INTRO + 1.0, INTRO + 7.0
    final_t = S1 + 0.6
    card_end = final_t + 2.6
    dur = card_end + 3.0
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + хук"), (INTRO, "страна"), (S0, "континент собирается"),
                                    ((S0 + S1) / 2, "середина сборки"), (final_t, "вердикт"), (card_end, "призыв")]}
    win_c = cv > total
    step = (S1 - S0) / len(members)
    cum = [0.0]
    for m in members:
        cum.append(cum[-1] + vals[m][0])
    cross_i = next((i for i, s in enumerate(cum) if s > cv), None)
    cross_t = S0 + cross_i * step if cross_i else None
    v = Video(f"big{seed}", dur, out_path)
    bg = _living_bg(accent, seed + 3)
    conf = _confetti(accent, seed)
    name = COUNTRIES[c]
    top_h, base = 980, 1640
    mx = max(cv, total)
    h1, h2 = name.upper(), f"VS ALL OF {gname.upper()}"
    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im)
        text(d, (W // 2, 150), h1, _fit(h1, 84, W - 80, True))
        text(d, (W // 2, 245), h2, _fit(h2, 70, W - 80, True), fill=accent)
        sub = f"{noun[0].upper() + noun[1:]} · World Bank {vals[c][1]}"
        text(d, (W // 2, 330), sub, _fit(sub, 36, W - 100), fill=(170, 175, 200))
        # столбик страны
        a = ease_out((t - INTRO) / 0.8)
        ch = int(top_h * cv / mx * a)
        lx, rx = 290, W - 290
        d.rounded_rectangle((lx - 150, base - max(ch, 10), lx + 150, base), 26, fill=LEFT_COL)
        _paste_flag(im, d, c, lx, base + 95, 170, 100)
        if t >= INTRO:
            text(d, (lx, base - max(ch, 10) - 55), fmt(cv * a), _fit(fmt(cv), 62, 330, True))
            ly = base - int(top_h * cv / mx)  # пунктир «уровень страны»
            for x in range(lx + 160, W - 120, 46):
                d.line((x, ly, x + 24, ly), fill=(255, 255, 255, 140), width=4)
        # столбик континента: страны по одной, сначала крупные
        k = clamp((t - S0) / step, 0, len(members)) if t >= S0 else 0
        n_in = int(k)
        y = base
        for i, m in enumerate(members[:n_in + 1]):
            frac = 1 if i < n_in else k - n_in
            if frac <= 0:
                break
            sh = top_h * vals[m][0] / mx * frac
            col = SEG_COLS[i % len(SEG_COLS)]
            d.rectangle((rx - 150, int(y - sh), rx + 150, int(y)), fill=col)
            d.line((rx - 150, int(y - sh), rx + 150, int(y - sh)), fill=(15, 15, 25), width=2)
            if sh >= 48 and frac == 1:
                fl = flag_box(m.lower(), 90, int(min(sh - 10, 56)), 0.1)
                im.paste(fl, (rx - fl.width // 2, int(y - sh / 2 - fl.height / 2)), fl)
            y -= sh
        run = cum[min(n_in, len(members))] + (vals[members[n_in]][0] * (k - n_in) if n_in < len(members) else 0)
        if t >= S0:
            text(d, (rx, int(y) - 55), fmt(run), _fit(fmt(run), 62, 330, True),
                 fill=accent if run > cv else (255, 255, 255))
            text(d, (rx, base + 70), f"{min(n_in + 1, len(members))} of {len(members)}", font(40), fill=(220, 222, 235))
            text(d, (rx, base + 120), "countries", font(30, False), fill=(160, 165, 190))
        else:
            text(d, (rx, base - 60), "?", font(120), fill=(90, 95, 125))
        if cross_t and cross_t <= t < cross_t + 1.2:  # момент, когда континент обгоняет страну
            pop = ease_back((t - cross_t) / 0.3)
            text(d, (W // 2, 470), "OVERTAKEN!", font(int(80 * pop) + 1), fill=accent)
        if t < final_t:
            progress(d, t / final_t, 380, accent)
        # вердикт
        if final_t <= t < card_end + 0.35:
            a_in = ease_back((t - final_t) / 0.45)
            a_out = ease_out((t - card_end) / 0.35) if t >= card_end else 0
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.55 * (1 - a_out) * ease_out((t - final_t) / 0.2))
            d = ImageDraw.Draw(im)
            _draw_confetti(d, conf, t - final_t, W // 2, 1100)
            cy = int(H + 500 - a_in * (H // 2 + 400) - a_out * (H // 2 + 600))
            d.rounded_rectangle((80, cy - 330, W - 80, cy + 330), 50, fill=(20, 22, 34), outline=accent, width=8)
            if win_c:
                _paste_flag(im, d, c, W // 2, cy - 190, 220, 130)
                text(d, (W // 2, cy - 30), name, _fit(name, 90, W - 240, True))
                text(d, (W // 2, cy + 80), f"beats all {len(members)} countries", _fit("beats all 00 countries", 54, W - 220), fill=accent)
                text(d, (W // 2, cy + 150), f"of {gname} combined!", _fit(f"of {gname} combined!", 54, W - 220), fill=accent)
            else:
                text(d, (W // 2, cy - 200), "ALL OF", font(70), fill=(200, 200, 215))
                text(d, (W // 2, cy - 90), gname.upper(), _fit(gname.upper(), 110, W - 220, True), fill=accent)
                k_ = total / cv
                txt = f"{k_:.1f}× bigger than {name}" if k_ >= 1.15 else f"just {(k_ - 1) * 100:.0f}% ahead of {name}"
                text(d, (W // 2, cy + 50), txt, _fit(txt, 56, W - 220))
                if cross_i:
                    t2 = f"it took {cross_i} countries"
                    text(d, (W // 2, cy + 150), t2, _fit(t2, 50, W - 220, False), fill=(190, 195, 215))
        if t < TITLE_CARD:
            im = title_card(im, t, [(name.upper(), 110, (255, 255, 255)), ("VS ALL OF", 70, accent),
                                    (gname.upper(), 110, (255, 255, 255))], accent, flags=[c] + members[:4],
                            pill="WHO HAS MORE?", fh=110)
        if t >= card_end + 0.35:
            im = _cta(im, t, card_end + 0.35, accent, "Which country", "should we test next?", "Comment a country")
        v.write(im)
    q = f"Does {name} have {noun.replace('the ', '')} than all of {gname} combined?"
    plan = [(0.15, q), (S0 + 0.2, "Let's add them up.")]
    if cross_t:
        plan.append((cross_t + 0.05, f"After {cross_i} countries, {gname} finally wins."))
    plan += [(final_t + 0.1, f"Yes! {name} beats all of {gname}!" if win_c else f"{gname} wins!"),
             (card_end + 0.5, "Comment a country. We test it next!")]
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, INTRO), [(S0, cross_t or S1)], final_t, card_end + 0.35, seed=seed, voice=voice)
    return v.finish(audio=track)


# ---------- 2. кто кого обогнал ----------
def render_overtake(a, b, years, sa, sb, fmt_id, label, cross_year, accent, out_path, seed=0):
    """Две линии во времени; b догоняет и обгоняет a в cross_year."""
    fmt = FMT[fmt_id]
    ny = len(years)
    L0, L1 = INTRO + 0.3, INTRO + 0.3 + 8.0
    final_t = L1 + 1.0
    card_end = final_t + 2.6
    dur = card_end + 3.0
    ci = years.index(cross_year)
    cross_t = L0 + (L1 - L0) * ci / (ny - 1)
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + хук"), (L0, "линии пошли"), (cross_t, "обгон"),
                                    (final_t, "вердикт"), (card_end, "призыв")]}
    v = Video(f"ovt{seed}", dur, out_path)
    bg = _living_bg(accent, seed + 5)
    conf = _confetti(accent, seed)
    na, nb = COUNTRIES[a], COUNTRIES[b]
    x0, x1, y0, y1 = 110, W - 200, 640, 1520
    mx = max(max(v_ for v_ in sa if v_ is not None), max(v_ for v_ in sb if v_ is not None)) * 1.05

    def pt(i, val):
        return x0 + (x1 - x0) * i / (ny - 1), y1 - (y1 - y0) * val / mx

    h1 = f"WHEN DID {nb.upper()}"
    h2 = f"OVERTAKE {na.upper()}?"
    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im, "RGBA")
        text(d, (W // 2, 150), h1, _fit(h1, 76, W - 80, True))
        text(d, (W // 2, 240), h2, _fit(h2, 76, W - 80, True), fill=accent)
        text(d, (W // 2, 325), f"{label} · World Bank", _fit(f"{label} · World Bank", 36, W - 100), fill=(170, 175, 200))
        for k in range(5):  # сетка
            gy = y1 - (y1 - y0) * k / 4
            d.line((x0, gy, x1, gy), fill=(255, 255, 255, 25), width=2)
        f = clamp((t - L0) / (L1 - L0), 0, 1) * (ny - 1)
        n = int(f)
        year = years[min(n, ny - 1)]
        text(d, (W - 100, 545), str(year), font(76), fill=(255, 255, 255, 200), anchor="rm")
        for s, col, code in ((sa, LEFT_COL, a), (sb, RIGHT_COL, b)):
            pts = [pt(i, s[i]) for i in range(min(n + 1, ny)) if s[i] is not None]
            if n < ny - 1 and s[n] is not None and s[n + 1] is not None:
                p0, p1 = pt(n, s[n]), pt(n + 1, s[n + 1])
                k = f - n
                pts.append((p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k))
            if len(pts) >= 2:
                d.line(pts, fill=col, width=12, joint="curve")
            if pts and t >= L0:
                hx, hy = pts[-1]
                fl = flag_box(code.lower(), 92, 60, 0.1)
                d.ellipse((hx - 14, hy - 14, hx + 14, hy + 14), fill=col)
                im.paste(fl, (int(hx + 20), int(hy - fl.height / 2)), fl)
                cur = s[min(n, ny - 1)]
                if cur is not None:
                    text(d, (int(hx + 20 + fl.width / 2), int(hy - 58)), fmt(cur), font(34), fill=col)
        # легенда
        for side, (code, nm, col) in enumerate(((a, na, LEFT_COL), (b, nb, RIGHT_COL))):
            lx = 110 if side == 0 else W // 2 + 30
            d.rounded_rectangle((lx, 1600, lx + 36, 1636), 8, fill=col)
            text(d, (lx + 52, 1618), nm, _fit(nm, 44, W // 2 - 120, True), anchor="lm")
        if t >= cross_t:  # точка обгона остаётся на графике
            cx, cy_ = pt(ci, sb[ci])
            pulse = 1 + 0.4 * max(0, 1 - (t - cross_t) / 0.6)
            r = int(30 * pulse)
            d.ellipse((cx - r, cy_ - r, cx + r, cy_ + r), outline=accent, width=7)
            if t < cross_t + 1.6:
                pop = ease_back((t - cross_t) / 0.3)
                text(d, (W // 2, 420), f"OVERTAKEN IN {cross_year}!", font(int(60 * pop) + 1), fill=accent)
        if t < final_t:
            progress(d, t / final_t, 380, accent)
        if final_t <= t < card_end + 0.35:
            a_in = ease_back((t - final_t) / 0.45)
            a_out = ease_out((t - card_end) / 0.35) if t >= card_end else 0
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.55 * (1 - a_out) * ease_out((t - final_t) / 0.2))
            d = ImageDraw.Draw(im)
            _draw_confetti(d, conf, t - final_t, W // 2, 1100)
            cy = int(H + 500 - a_in * (H // 2 + 400) - a_out * (H // 2 + 600))
            d.rounded_rectangle((80, cy - 330, W - 80, cy + 330), 50, fill=(20, 22, 34), outline=accent, width=8)
            _paste_flag(im, d, b, W // 2 - 150, cy - 180, 200, 120)
            text(d, (W // 2, cy - 180), "→", font(80), fill=accent)
            _paste_flag(im, d, a, W // 2 + 150, cy - 180, 200, 120)
            text(d, (W // 2, cy - 10), f"{nb} overtook", _fit(f"{nb} overtook", 72, W - 220, True))
            text(d, (W // 2, cy + 80), na, _fit(na, 72, W - 220, True))
            text(d, (W // 2, cy + 200), f"in {cross_year}", font(90), fill=accent)
        if t < TITLE_CARD:
            im = title_card(im, t, [(nb.upper(), 100, (255, 255, 255)), ("OVERTAKES", 70, accent),
                                    (na.upper(), 100, (255, 255, 255))], accent, flags=(b, a), pill="GUESS THE YEAR", fh=150)
        if t >= card_end + 0.35:
            im = _cta(im, t, card_end + 0.35, accent, "Who will overtake", "who next?", "Comment 2 countries")
        v.write(im)
    plan = [(0.15, f"{na} was ahead for years. Guess the year {nb} overtakes."),
            (cross_t + 0.05, f"{cross_year}! {nb} takes the lead."),
            (final_t + 0.1, f"{nb} overtook {na} in {cross_year}."),
            (card_end + 0.5, "Who will overtake who next? Comment below!")]
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, 0.45), [(L0, cross_t)], final_t, card_end + 0.35, seed=seed, voice=voice)
    return v.finish(audio=track)


# ---------- 3. угадай страну по подсказкам ----------
def render_guess(code, clues, accent, out_path, seed=0):
    """clues — [(подпись, значение на экране, значение для голоса)] от трудной к лёгкой; в конце отсчёт и раскрытие."""
    CL = 2.3
    C0 = INTRO
    cd0 = C0 + len(clues) * CL
    reveal = cd0 + 3.0
    card_end = reveal + 2.8
    dur = card_end + 3.0
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + хук")] + [(C0 + i * CL, f"подсказка {i + 1}") for i in range(len(clues))] +
            [(cd0, "отсчёт"), (reveal, "ответ"), (card_end, "призыв")]}
    v = Video(f"gss{seed}", dur, out_path)
    bg = _living_bg(accent, seed + 11)
    conf = _confetti(accent, seed)
    name = COUNTRIES[code]
    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im)
        text(d, (W // 2, 150), "GUESS THE", font(84))
        text(d, (W // 2, 245), "COUNTRY", font(84), fill=accent)
        text(d, (W // 2, 330), f"{len(clues)} clues · World Bank data", font(36, False), fill=(170, 175, 200))
        # силуэт флага «?»
        if t < reveal:
            gl = 0.5 + 0.5 * math.sin(t * 5)
            d.rounded_rectangle((W // 2 - 190, 400, W // 2 + 190, 620), 26, fill=PANEL,
                                outline=mix_color(PANEL, accent, 0.4 + 0.5 * gl), width=5)
            text(d, (W // 2, 510), "?", font(150), fill=mix_color((90, 95, 125), accent, gl))
        # подсказки
        for i, (lbl, val, _) in enumerate(clues):
            st = C0 + i * CL
            if t < st:
                continue
            a = ease_out((t - st) / 0.35)
            y = 700 + i * 190
            dx = int((1 - a) * W)
            d.rounded_rectangle((60 + dx, y, W - 60 + dx, y + 165), 30, fill=(30, 33, 50),
                                outline=accent if t < st + CL else (60, 64, 90), width=4)
            text(d, (110 + dx, y + 48), f"CLUE {i + 1}", font(30), fill=accent, anchor="lm")
            text(d, (110 + dx, y + 112), lbl, _fit(lbl, 44, 520, False), fill=(200, 203, 220), anchor="lm")
            text(d, (W - 110 + dx, y + 112), val, _fit(val, 64, 420, True), anchor="rm")
        if cd0 <= t < reveal:  # отсчёт — время написать ответ
            n = 3 - int(t - cd0)
            k = (t - cd0) % 1
            text(d, (W // 2, 1640), "Comment your guess!", font(54), fill=(255, 255, 255))
            text(d, (W // 2, 1770), str(n), font(int(150 - 40 * k)), fill=accent)
        if t < reveal:
            progress(d, t / reveal, 372, accent)
        if reveal <= t < card_end + 0.35:
            a_in = ease_back((t - reveal) / 0.45)
            a_out = ease_out((t - card_end) / 0.35) if t >= card_end else 0
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.55 * (1 - a_out) * ease_out((t - reveal) / 0.2))
            d = ImageDraw.Draw(im)
            _draw_confetti(d, conf, t - reveal, W // 2, 1100)
            cy = int(H + 500 - a_in * (H // 2 + 400) - a_out * (H // 2 + 600))
            d.rounded_rectangle((80, cy - 330, W - 80, cy + 330), 50, fill=(20, 22, 34), outline=accent, width=8)
            text(d, (W // 2, cy - 250), "IT'S", font(70), fill=accent)
            _paste_flag(im, d, code, W // 2, cy - 60, 360, 220)
            text(d, (W // 2, cy + 180), name, _fit(name, 100, W - 240, True))
        if t < TITLE_CARD:
            im = title_card(im, t, [("GUESS THE", 110, (255, 255, 255)), ("COUNTRY", 120, accent),
                                    (f"IN {len(clues)} CLUES", 60, (175, 180, 205))], accent, pill="ONLY REAL DATA")
        if t >= card_end + 0.35:
            im = _cta(im, t, card_end + 0.35, accent, "How many clues", "did you need?", "Comment your score")
        v.write(im)
    words = ["one", "two", "three", "four", "five"]
    plan = [(0.15, f"Guess the country in {words[len(clues) - 1]} clues.")]
    plan += [(C0 + i * CL + 0.2, f"{lbl}: {said}.") for i, (lbl, _, said) in enumerate(clues)]
    plan += [(cd0 + 0.1, "Comment your guess. Three. Two. One."), (reveal + 0.05, f"It's {name}!"),
             (card_end + 0.5, "How many clues did you need?")]
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, 0.45), [(C0 + i * CL, C0 + i * CL + 0.4) for i in range(len(clues))],
                       reveal, card_end + 0.35, seed=seed, voice=voice)
    return v.finish(audio=track)
