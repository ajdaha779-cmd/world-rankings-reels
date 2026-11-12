"""Формат «дуэль»: две страны, 3 раунда по реальным показателям, счёт и победитель."""
import itertools, random
from engine import *
from catalog import FMT, COUNTRIES, DUEL_STATS
from data import indicator, history
from render import _fit, _living_bg, _confetti, _draw_confetti, title_card, TITLE_CARD, progress
from sound import duel_track
import tts

ROUNDS = 3  # 10.11: на 5 раундах уходили уже на 2-м
LAST = {}
INTRO, ROUND_LEN = 1.0, 2.6
WIN_AT = 1.25  # через сколько секунд раунда объявляется победитель раунда
LEFT_COL, RIGHT_COL = (226, 58, 74), (44, 108, 232)


def duel_rounds(a, b, seed=0):
    """Список раундов [(подпись, формат, значение A, значение B, победитель 0/1/None)] или None."""
    avail = []
    for ind, label, fmt, higher in DUEL_STATS:
        vals = indicator(ind)
        if a in vals and b in vals:
            avail.append((ind, label, fmt, higher, vals[a][0], vals[b][0]))
    if len(avail) < ROUNDS:
        return None
    rng = random.Random(f"{a}{b}{seed}")
    rows = []
    for ind, label, fmt, higher, va, vb in avail:
        win = None if abs(va - vb) < 1e-9 else (0 if (va > vb) == higher else 1)
        rows.append((label, fmt, va, vb, win))
    # интрига: из всех наборов по 5 раундов берём самые близкие по счёту (3:2 лучше 5:0)
    combos = list(itertools.combinations(rows, ROUNDS))
    rng.shuffle(combos)
    def gap(cmb):
        w = [sum(1 for r in cmb if r[4] == s) for s in (0, 1)]
        return abs(w[0] - w[1]) if w[0] != w[1] else 9  # ничья по итогу — хуже, чем 3:2
    best = min(combos, key=gap)
    # порядок: чередуем победителей, начиная с будущего проигравшего — лидер меняется, исход решается в конце
    w = [sum(1 for r in best if r[4] == s) for s in (0, 1)]
    loser = 0 if w[0] < w[1] else 1
    q = {0: [r for r in best if r[4] == 0], 1: [r for r in best if r[4] == 1]}
    draws = [r for r in best if r[4] is None]
    out, side = [], loser
    while q[0] or q[1]:
        if q[side]:
            out.append(q[side].pop(0))
        side = 1 - side
    return out[:1] + draws + out[1:]


# нейтральные подписи для пар с идущим конфликтом: без «лучше/хуже», без победителя
NEUTRAL_ORDER = [("SP.POP.TOTL", "Population", "people"), ("NY.GDP.PCAP.CD", "GDP per person", "money"),
                 ("SP.DYN.LE00.IN", "Life expectancy", "years"), ("IT.NET.USER.ZS", "Internet users", "pct"),
                 ("SH.XPD.CHEX.PC.CD", "Health spending per person", "money"), ("SP.DYN.TFRT.IN", "Births per woman", "dec1"),
                 ("SP.URB.TOTL.IN.ZS", "Living in cities", "pct")]


def neutral_rounds(a, b):
    rows = []
    for ind, label, fmt in NEUTRAL_ORDER:
        vals = indicator(ind)
        if a in vals and b in vals:
            rows.append((label, fmt, vals[a][0], vals[b][0], None))
    return rows[:ROUNDS] if len(rows) >= ROUNDS else None


# «Plot twist» (12.11): пары, которые за 60 лет поменялись местами по богатству — раньше A богаче B, теперь наоборот
FLIPS = [("VE", "KR"), ("PH", "KR"), ("VE", "ES"), ("GH", "CN"), ("ZA", "KR"), ("BR", "KR"), ("VE", "CN"),
         ("ZA", "ES"), ("VE", "JP"), ("NG", "ID"), ("EG", "CN"), ("CO", "KR"), ("VE", "SA"), ("ZA", "PT"),
         ("VE", "MX"), ("VE", "AR"), ("PH", "CN"), ("IR", "KR")]


def flip_rounds(a, b, mid=1990):
    """[(подпись, формат, A, B, кто богаче)] за первый год, mid и последний — или None, если твиста нет."""
    h = history("NY.GDP.PCAP.CD")
    ha, hb = h.get(a, {}), h.get(b, {})
    ys = sorted(y for y in ha if y in hb)
    if not ys or ys[0] > 1970 or mid not in ys:
        return None
    rows = [(f"In {y}", "money", ha[y], hb[y], 0 if ha[y] > hb[y] else 1) for y in (ys[0], mid, ys[-1])]
    if rows[0][4] == rows[-1][4]:
        return None
    return rows


def render_duel(a, b, rounds, accent, out_path, seed=0, pill="WHO WINS?", neutral=False, flip=False, cup=None):
    """neutral — пары с идущим конфликтом: «X и Y в цифрах», без счёта, победителя и мечей.
    flip — «plot twist»: кто был богаче тогда и кто сейчас (раунды — годы, без счёта).
    cup — матч турнира {"stage": "ROUND OF 16 · MATCH 3/8", "prev": {"code", "name", "pct"} | None}: цифры — подсказка,
    а кто проходит дальше, решают зрители в комментариях."""
    names = (COUNTRIES[a], COUNTRIES[b])
    final_t = INTRO + ROUNDS * ROUND_LEN + 0.9
    card_end = final_t + 2.3
    dur = card_end + 3.0
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + хук"), (INTRO, "раунд 1")] +
            [(INTRO + i * ROUND_LEN, f"раунд {i + 1}") for i in range(1, ROUNDS)] +
            [(final_t, "вердикт"), (card_end, "призыв к комментариям")]}
    v = Video(f"duel{seed}", dur, out_path)
    bg_tall = _living_bg(accent, seed + 7)
    conf = _confetti(accent, seed)
    score = [0, 0]
    wins_at = []
    for i, r in enumerate(rounds):
        wins_at.append(INTRO + i * ROUND_LEN + WIN_AT)
    total = [sum(1 for r in rounds if r[4] == s) for s in (0, 1)]
    winner = 0 if total[0] > total[1] else 1 if total[1] > total[0] else None
    if flip:
        winner = rounds[-1][4]
        k0 = max(rounds[0][2], rounds[0][3]) / max(min(rounds[0][2], rounds[0][3]), 1)
        k1 = max(rounds[-1][2], rounds[-1][3]) / max(min(rounds[-1][2], rounds[-1][3]), 1)
    f_name = [_fit(n, 50, 380, True) for n in names]
    f_lbl = font(60)
    f_val = font(64)
    f_score = font(110)

    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg_tall.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im)
        score = [sum(1 for i, r in enumerate(rounds) if r[4] == s and t >= wins_at[i]) for s in (0, 1)]

        if cup:
            text(d, (W // 2, 52), "WORLD CUP OF COUNTRIES · " + cup["stage"], _fit("WORLD CUP OF COUNTRIES · " + cup["stage"], 34, W - 60, True), fill=accent)
            if cup.get("prev") and INTRO <= t < final_t:  # итог прошлого голосования — повод ждать результатов
                pv = cup["prev"]
                d.rounded_rectangle((60, 1720, W - 60, 1830), 30, fill=(20, 22, 34), outline=(70, 75, 100), width=3)
                pf = flag_box(pv["code"].lower(), 110, 70, 0.1)
                im.paste(pf, (100, 1775 - pf.height // 2), pf)
                msg = f"Last match: {pv['name']} won with {pv['pct']}% of your votes"
                text(d, (230, 1775), msg, _fit(msg, 38, W - 330, True), anchor="lm")
        # шапка: флаги, имена, VS, счёт (видна с первого кадра — хук)
        for side in (0, 1):
            cx = 270 if side == 0 else W - 270
            punch = 1 + 0.18 * (1 - ease_out((t - (0.15 if side == 0 else 0.45)) / 0.35))
            fh = int(170 * punch)
            fl = flag_box((a, b)[side].lower(), int(300 * punch), fh, 0.08)
            d.rounded_rectangle((cx - fl.width // 2 - 10, 200 - fl.height // 2 - 10, cx + fl.width // 2 + 10,
                                 200 + fl.height // 2 + 10), 24, fill=(255, 255, 255))
            im.paste(fl, (cx - fl.width // 2, 200 - fl.height // 2), fl)
            text(d, (cx, 350), names[side], f_name[side])
            bump = max((1 - (t - w) / 0.4 for i, w in enumerate(wins_at) if rounds[i][4] == side and 0 <= t - w < 0.4),
                       default=0)
            if not neutral and not flip:
                text(d, (cx, 480), str(score[side]), font(int(110 * (1 + 0.35 * bump))),
                     fill=mix_color((255, 255, 255), accent, bump))
        d.ellipse((W // 2 - 70, 130, W // 2 + 70, 270), fill=(15, 15, 22), outline=accent, width=6)
        text(d, (W // 2, 203), "&" if neutral else "VS", font(56), fill=accent)
        if not neutral and not flip:
            text(d, (W // 2, 480), ":", f_score, fill=(150, 150, 170))

        if t < INTRO:
            gl = 0.5 + 0.5 * math.sin(t * 6)
            big = "IN NUMBERS" if neutral else "WHO WAS RICHER?" if flip else "YOU DECIDE!" if cup else "WHO WINS?"
            text(d, (W // 2, 900), big, _fit(big, 96, W - 80, True), fill=mix_color((255, 255, 255), accent, gl))
            small = (f"{ROUNDS} facts · then you vote" if cup else f"{ROUNDS} facts · World Bank data" if neutral else
                     f"{rounds[0][0][3:]} → {rounds[-1][0][3:]} · real data" if flip else f"{ROUNDS} rounds · real data")
            text(d, (W // 2, 1000), small, font(40, False), fill=(170, 175, 200))
        elif t < final_t:
            i = min(int((t - INTRO) // ROUND_LEN), ROUNDS - 1)
            lt = t - INTRO - i * ROUND_LEN
            label, fmt_id, va, vb, win = rounds[i]
            fmt = FMT[fmt_id]
            a_in = ease_out(lt / 0.3)
            oyc = int((1 - a_in) * 120)
            pill = f"FACT {i + 1}/{ROUNDS}" if neutral else label.upper() if flip else f"ROUND {i + 1}/{ROUNDS}"
            if flip:
                label = "GDP per person"
            pw = font(34).getlength(pill) + 60
            d.rounded_rectangle((W / 2 - pw / 2, 640 + oyc, W / 2 + pw / 2, 700 + oyc), 30, fill=accent)
            text(d, (W // 2, 670 + oyc), pill, font(34), fill=(20, 20, 30))
            text(d, (W // 2, 790 + oyc), label, _fit(label, 60, W - 100, True))
            cnt = ease_out((lt - 0.25) / 0.8)
            mx = max(abs(va), abs(vb)) or 1
            for side, val in ((0, va), (1, vb)):
                col = LEFT_COL if side == 0 else RIGHT_COL
                won = win == side and lt >= WIN_AT
                lost = win is not None and win != side and lt >= WIN_AT
                if lost:
                    col = mix_color(col, (40, 40, 50), 0.6)
                bh = int(560 * abs(val) / mx * cnt)
                cx = 300 if side == 0 else W - 300
                base = 1560 + oyc
                d.rounded_rectangle((cx - 130, base - max(bh, 12), cx + 130, base), 26, fill=col)
                if won and flip:
                    g = int(5 + 3 * math.sin((lt - WIN_AT) * 9))
                    d.rounded_rectangle((cx - 136, base - max(bh, 12) - 6, cx + 136, base + 6), 30, outline=accent,
                                        width=g)
                    text(d, (cx, base + 60), "RICHER", font(40), fill=accent)
                elif won:
                    g = int(5 + 3 * math.sin((lt - WIN_AT) * 9))
                    d.rounded_rectangle((cx - 136, base - max(bh, 12) - 6, cx + 136, base + 6), 30, outline=accent,
                                        width=g)
                    pop = ease_back((lt - WIN_AT) / 0.35)
                    # «+1» в центре со стрелкой к победителю раунда
                    py_, dir_ = 1250 + oyc, -1 if side == 0 else 1
                    text(d, (W // 2 + dir_ * 10, py_), "+1", font(int(76 * pop) + 1), fill=accent)
                    tx = W // 2 + dir_ * 95
                    d.polygon([(tx + dir_ * 34, py_), (tx, py_ - 26), (tx, py_ + 26)], fill=accent)
                text(d, (cx, base - max(bh, 12) - 60), fmt(val * cnt), _fit(fmt(val), 64, 420, True),
                     fill=(255, 255, 255) if not lost else (150, 150, 165))
            if win is None and lt >= WIN_AT and not neutral:
                text(d, (W // 2, 1640), "DRAW", font(60), fill=(200, 200, 210))
        elif t < final_t + 0.01:
            pass
        # пауза перед вердиктом
        if final_t - 0.9 <= t < final_t and not neutral:
            k = (t - final_t + 0.9) / 0.9
            text(d, (W // 2, 1700), "...", font(int(70 + 40 * k)), fill=accent)

        # вердикт
        if final_t <= t < card_end + 0.35 and neutral:  # спокойный итог без победителя
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.55 * ease_out((t - final_t) / 0.3))
            d = ImageDraw.Draw(im)
            text(d, (W // 2, 900), "Data only.", font(80), fill=(255, 255, 255))
            text(d, (W // 2, 1000), "No winners here.", font(60, False), fill=(190, 195, 215))
            text(d, (W // 2, 1100), "Source: World Bank Open Data", font(36, False), fill=(150, 155, 175))
        elif final_t <= t < card_end + 0.35:
            a_in = ease_back((t - final_t) / 0.45)
            a_out = ease_out((t - card_end) / 0.35) if t >= card_end else 0
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.55 * (1 - a_out) * ease_out((t - final_t) / 0.2))
            d = ImageDraw.Draw(im)
            _draw_confetti(d, conf, t - final_t, W // 2, 1100)
            cy = int(H + 500 - a_in * (H // 2 + 400) - a_out * (H // 2 + 600))
            d.rounded_rectangle((80, cy - 380, W - 80, cy + 380), 50, fill=(20, 22, 34), outline=accent, width=8)
            if flip:
                text(d, (W // 2, cy - 280), "RICHER TODAY", font(76), fill=accent)
                fl = flag((a, b)[winner].lower(), 240, 0.08)
                fy = cy - 75 - fl.height // 2
                d.rounded_rectangle((W // 2 - fl.width // 2 - 10, fy - 10, W // 2 + fl.width // 2 + 10,
                                     fy + fl.height + 10), 26, fill=(255, 255, 255))
                im.paste(fl, (W // 2 - fl.width // 2, fy), fl)
                text(d, (W // 2, cy + 140), names[winner], _fit(names[winner], 96, W - 240, True))
            elif winner is None:
                text(d, (W // 2, cy - 250), "IT'S A", font(70), fill=(200, 200, 215))
                text(d, (W // 2, cy - 140), "DRAW!", font(120), fill=accent)
                for side in (0, 1):
                    fl = flag_box((a, b)[side].lower(), 300, 170, 0.08)
                    cx = W // 2 - 190 if side == 0 else W // 2 + 190
                    im.paste(fl, (cx - fl.width // 2, cy + 105 - fl.height // 2), fl)
            else:
                text(d, (W // 2, cy - 280), "DATA SAYS" if cup else "WINNER", font(80), fill=accent)
                fl = flag((a, b)[winner].lower(), 240, 0.08)
                fy = cy - 75 - fl.height // 2
                d.rounded_rectangle((W // 2 - fl.width // 2 - 10, fy - 10, W // 2 + fl.width // 2 + 10,
                                     fy + fl.height + 10), 26, fill=(255, 255, 255))
                im.paste(fl, (W // 2 - fl.width // 2, fy), fl)
                text(d, (W // 2, cy + 140), names[winner], _fit(names[winner], 96, W - 240, True))
            if flip:
                tw = f"{k1:.0f}× richer" if k1 >= 2 else f"{k1:.1f}× richer"
                text(d, (W // 2, cy + 270), tw, font(80), fill=(255, 255, 255))
            else:
                text(d, (W // 2, cy + 280), f"{total[0]} : {total[1]}", font(90), fill=(255, 255, 255))

        if t < final_t:
            progress(d, t / final_t, 560, accent)
        if t < TITLE_CARD:
            im = title_card(im, t, [(names[0].upper(), 100, (255, 255, 255)), ("&" if neutral else "VS", 80, accent),
                                    (names[1].upper(), 100, (255, 255, 255))], accent, flags=(a, b),
                            pill=pill, fh=150)
        if t >= card_end + 0.35 and cup:  # голосование: кто проходит дальше — решают зрители
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.6)
            d = ImageDraw.Draw(im)
            a2 = ease_back((t - card_end - 0.35) / 0.45)
            cy = int(H + 300 - a2 * (H // 2 + 300))
            d.rounded_rectangle((60, cy - 330, W - 60, cy + 330), 40, fill=(255, 255, 255))
            text(d, (W // 2, cy - 250), "BUT YOU DECIDE!", font(70), fill=(15, 15, 25))
            text(d, (W // 2, cy - 175), "Comment who goes through", font(42, False), fill=(60, 60, 75))
            for side in (0, 1):
                cx = W // 2 - 230 if side == 0 else W // 2 + 230
                fl = flag_box((a, b)[side].lower(), 300, 170, 0.08)
                fx, fy = cx - fl.width // 2, cy - 10 - fl.height // 2
                d.rounded_rectangle((fx - 5, fy - 5, fx + fl.width + 5, fy + fl.height + 5), 18, outline=(200, 202, 212), width=4)
                im.paste(fl, (fx, fy), fl)
                text(d, (cx, cy + 115), names[side], _fit(names[side], 50, 400, True), fill=(15, 15, 25))
            text(d, (W // 2, cy - 10), "or", font(56), fill=mix_color(accent, (0, 0, 0), 0.25))
            text(d, (W // 2, cy + 230), "Results in the next match!", font(44), fill=mix_color(accent, (0, 0, 0), 0.25))
        elif t >= card_end + 0.35:
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.6)
            d = ImageDraw.Draw(im)
            a2 = ease_back((t - card_end - 0.35) / 0.45)
            cy = int(H + 200 - a2 * (H // 2 + 200))
            d.rounded_rectangle((60, cy - 200, W - 60, cy + 200), 40, fill=(255, 255, 255))
            lines_ = (("Peace to both", "countries 🕊") if neutral else ("Which 2 countries", "should we compare?") if flip
                      else ("Who should", "fight next?"))
            text(d, (W // 2, cy - 95), lines_[0], font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy - 15), lines_[1].replace(" 🕊", ""), font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy + 75), "Please keep comments respectful" if neutral else "Comment 2 countries",
                 font(40 if neutral else 44, False), fill=mix_color(accent, (0, 0, 0), 0.25))
            text(d, (W // 2, cy + 140), "Follow for daily battles", font(32, False), fill=(120, 120, 135))
        v.write(im)

    rounds_t = [(INTRO + i * ROUND_LEN, w) for i, w in enumerate(wins_at)]
    if neutral:
        plan = [(0.15, f"{names[0]} and {names[1]}, in numbers.")]
        plan += [(INTRO + i * ROUND_LEN + 0.15, f"{r[0]}.") for i, r in enumerate(rounds)]
        plan += [(final_t + 0.2, "Data only. No winners here.")]
    elif cup:
        plan = [(0.15, f"World Cup of Countries! {names[0]} versus {names[1]}. You decide who goes through.")]
        plan += [(INTRO + i * ROUND_LEN + 0.15, f"Round {i + 1}. {r[0]}.") for i, r in enumerate(rounds) if i > 0]
        plan += [(final_t + 0.05, f"The data says {names[winner]}." if winner is not None else "The data says it's a draw."),
                 (card_end + 0.5, f"But you decide! Comment {names[0]} or {names[1]}. Results in the next match!")]
    elif flip:
        early, late = names[rounds[0][4]], names[winner]
        plan = [(0.15, f"In {rounds[0][0][3:]}, {early} was richer than {late}. Then this happened.")]
        plan += [(INTRO + i * ROUND_LEN + 0.15, f"{r[0]}.") for i, r in enumerate(rounds[1:], 1)]
        plan += [(final_t - 0.9, "And today..."),
                 (final_t + 0.05, f"{late} is {k1:.0f} times richer!" if k1 >= 2 else f"{late} is richer!"),
                 (card_end + 0.5, "Comment two countries. We compare them next!")]
    else:
        plan = [(0.15, f"{names[0]} versus {names[1]}. {['', 'One', 'Two', 'Three', 'Four', 'Five'][ROUNDS]} rounds. Who wins?")]
        plan += [(INTRO + i * ROUND_LEN + 0.15, f"Round {i + 1}. {r[0]}.") for i, r in enumerate(rounds)]
        plan += [(final_t - 0.9, "And the winner is..."),
                 (final_t + 0.05, f"{names[winner]}!" if winner is not None else "It's a draw!"),
                 (card_end + 0.5, "Comment two countries. We battle them next!")]
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, 0.45), rounds_t, final_t, card_end + 0.35, seed=seed, voice=voice)
    return v.finish(audio=track)
