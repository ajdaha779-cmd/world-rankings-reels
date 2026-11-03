"""Формат «дуэль»: две страны, 5 раундов по реальным показателям, счёт и победитель."""
import itertools, random
from engine import *
from catalog import FMT, COUNTRIES, DUEL_STATS
from data import indicator
from render import _fit, _living_bg, _confetti, _draw_confetti, title_card, TITLE_CARD, progress
from sound import duel_track
import tts

ROUNDS = 5
INTRO, ROUND_LEN = 1.2, 3.2
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


def render_duel(a, b, rounds, accent, out_path, seed=0):
    names = (COUNTRIES[a], COUNTRIES[b])
    final_t = INTRO + ROUNDS * ROUND_LEN + 0.9
    card_end = final_t + 2.6
    dur = card_end + 3.2
    v = Video(f"duel{seed}", dur, out_path)
    bg_tall = _living_bg(accent, seed + 7)
    conf = _confetti(accent, seed)
    score = [0, 0]
    wins_at = []
    for i, r in enumerate(rounds):
        wins_at.append(INTRO + i * ROUND_LEN + 1.6)
    total = [sum(1 for r in rounds if r[4] == s) for s in (0, 1)]
    winner = 0 if total[0] > total[1] else 1 if total[1] > total[0] else None
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

        # шапка: флаги, имена, VS, счёт (видна с первого кадра — хук)
        for side in (0, 1):
            cx = 270 if side == 0 else W - 270
            punch = 1 + 0.18 * (1 - ease_out((t - (0.15 if side == 0 else 0.45)) / 0.35))
            fh = int(170 * punch)
            fl = flag((a, b)[side].lower(), fh, 0.08)
            d.rounded_rectangle((cx - fl.width // 2 - 10, 200 - fh // 2 - 10, cx + fl.width // 2 + 10, 200 + fh // 2 + 10),
                                24, fill=(255, 255, 255))
            im.paste(fl, (cx - fl.width // 2, 200 - fh // 2), fl)
            text(d, (cx, 350), names[side], f_name[side])
            bump = max((1 - (t - w) / 0.4 for i, w in enumerate(wins_at) if rounds[i][4] == side and 0 <= t - w < 0.4),
                       default=0)
            text(d, (cx, 480), str(score[side]), font(int(110 * (1 + 0.35 * bump))),
                 fill=mix_color((255, 255, 255), accent, bump))
        d.ellipse((W // 2 - 70, 130, W // 2 + 70, 270), fill=(15, 15, 22), outline=accent, width=6)
        text(d, (W // 2, 203), "VS", font(56), fill=accent)
        text(d, (W // 2, 480), ":", f_score, fill=(150, 150, 170))

        if t < INTRO:
            gl = 0.5 + 0.5 * math.sin(t * 6)
            text(d, (W // 2, 900), "WHO WINS?", font(96), fill=mix_color((255, 255, 255), accent, gl))
            text(d, (W // 2, 1000), "5 rounds · real data", font(40, False), fill=(170, 175, 200))
        elif t < final_t:
            i = min(int((t - INTRO) // ROUND_LEN), ROUNDS - 1)
            lt = t - INTRO - i * ROUND_LEN
            label, fmt_id, va, vb, win = rounds[i]
            fmt = FMT[fmt_id]
            a_in = ease_out(lt / 0.3)
            oyc = int((1 - a_in) * 120)
            pill = f"ROUND {i + 1}/{ROUNDS}"
            pw = font(34).getlength(pill) + 60
            d.rounded_rectangle((W / 2 - pw / 2, 640 + oyc, W / 2 + pw / 2, 700 + oyc), 30, fill=accent)
            text(d, (W // 2, 670 + oyc), pill, font(34), fill=(20, 20, 30))
            text(d, (W // 2, 790 + oyc), label, _fit(label, 60, W - 100, True))
            cnt = ease_out((lt - 0.3) / 1.0)
            mx = max(abs(va), abs(vb)) or 1
            for side, val in ((0, va), (1, vb)):
                col = LEFT_COL if side == 0 else RIGHT_COL
                won = win == side and lt >= 1.6
                lost = win is not None and win != side and lt >= 1.6
                if lost:
                    col = mix_color(col, (40, 40, 50), 0.6)
                bh = int(560 * abs(val) / mx * cnt)
                cx = 300 if side == 0 else W - 300
                base = 1560 + oyc
                d.rounded_rectangle((cx - 130, base - max(bh, 12), cx + 130, base), 26, fill=col)
                if won:
                    g = int(5 + 3 * math.sin((lt - 1.6) * 9))
                    d.rounded_rectangle((cx - 136, base - max(bh, 12) - 6, cx + 136, base + 6), 30, outline=accent,
                                        width=g)
                    pop = ease_back((lt - 1.6) / 0.35)
                    # «+1» в центре со стрелкой к победителю раунда
                    py_, dir_ = 1250 + oyc, -1 if side == 0 else 1
                    text(d, (W // 2 + dir_ * 10, py_), "+1", font(int(76 * pop) + 1), fill=accent)
                    tx = W // 2 + dir_ * 95
                    d.polygon([(tx + dir_ * 34, py_), (tx, py_ - 26), (tx, py_ + 26)], fill=accent)
                text(d, (cx, base - max(bh, 12) - 60), fmt(val * cnt), _fit(fmt(val), 64, 420, True),
                     fill=(255, 255, 255) if not lost else (150, 150, 165))
            if win is None and lt >= 1.6:
                text(d, (W // 2, 1640), "DRAW", font(60), fill=(200, 200, 210))
        elif t < final_t + 0.01:
            pass
        # пауза перед вердиктом
        if final_t - 0.9 <= t < final_t:
            k = (t - final_t + 0.9) / 0.9
            text(d, (W // 2, 1700), "...", font(int(70 + 40 * k)), fill=accent)

        # вердикт
        if final_t <= t < card_end + 0.35:
            a_in = ease_back((t - final_t) / 0.45)
            a_out = ease_out((t - card_end) / 0.35) if t >= card_end else 0
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.55 * (1 - a_out) * ease_out((t - final_t) / 0.2))
            d = ImageDraw.Draw(im)
            _draw_confetti(d, conf, t - final_t, W // 2, 1100)
            cy = int(H + 500 - a_in * (H // 2 + 400) - a_out * (H // 2 + 600))
            d.rounded_rectangle((80, cy - 380, W - 80, cy + 380), 50, fill=(20, 22, 34), outline=accent, width=8)
            if winner is None:
                text(d, (W // 2, cy - 250), "IT'S A", font(70), fill=(200, 200, 215))
                text(d, (W // 2, cy - 140), "DRAW!", font(120), fill=accent)
                for side in (0, 1):
                    fl = flag((a, b)[side].lower(), 170, 0.08)
                    cx = W // 2 - 190 if side == 0 else W // 2 + 190
                    im.paste(fl, (cx - fl.width // 2, cy + 20), fl)
            else:
                text(d, (W // 2, cy - 280), "WINNER", font(80), fill=accent)
                fl = flag((a, b)[winner].lower(), 240, 0.08)
                d.rounded_rectangle((W // 2 - fl.width // 2 - 10, cy - 200, W // 2 + fl.width // 2 + 10, cy + 50), 26,
                                    fill=(255, 255, 255))
                im.paste(fl, (W // 2 - fl.width // 2, cy - 195), fl)
                text(d, (W // 2, cy + 140), names[winner], _fit(names[winner], 96, W - 240, True))
            text(d, (W // 2, cy + 280), f"{total[0]} : {total[1]}", font(90), fill=(255, 255, 255))

        if t < final_t:
            progress(d, t / final_t, 560, accent)
        if t < TITLE_CARD:
            im = title_card(im, t, [(names[0].upper(), 100, (255, 255, 255)), ("VS", 80, accent),
                                    (names[1].upper(), 100, (255, 255, 255))], accent, flags=(a, b),
                            pill="WHO WINS?", fh=150)
        if t >= card_end + 0.35:
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.6)
            d = ImageDraw.Draw(im)
            a2 = ease_back((t - card_end - 0.35) / 0.45)
            cy = int(H + 200 - a2 * (H // 2 + 200))
            d.rounded_rectangle((60, cy - 200, W - 60, cy + 200), 40, fill=(255, 255, 255))
            text(d, (W // 2, cy - 95), "Who should", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy - 15), "fight next?", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy + 75), "Comment below", font(44, False), fill=mix_color(accent, (0, 0, 0), 0.25))
            text(d, (W // 2, cy + 140), "Follow for daily battles", font(32, False), fill=(120, 120, 135))
        v.write(im)

    rounds_t = [(INTRO + i * ROUND_LEN, w) for i, w in enumerate(wins_at)]
    plan = [(0.15, f"{names[0]} versus {names[1]}. Five rounds. Who wins?")]
    plan += [(INTRO + i * ROUND_LEN + 0.15, f"Round {i + 1}. {r[0]}.") for i, r in enumerate(rounds)]
    plan += [(final_t - 0.9, "And the winner is..."),
             (final_t + 0.05, f"{names[winner]}!" if winner is not None else "It's a draw!"),
             (card_end + 0.5, "Who should fight next? Comment below!")]
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, 0.45), rounds_t, final_t, card_end + 0.35, seed=seed, voice=voice)
    return v.finish(audio=track)
