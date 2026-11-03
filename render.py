"""Рендер ролика-рейтинга: строки открываются в такт музыке с последнего места к первому,
перед №1 пауза, затем большая карточка победителя с конфетти."""
from engine import *
from catalog import FMT
from sound import ranking_track, bpm_for
import tts

BAR, PANEL = (66, 78, 112), (27, 30, 44)
CARD_HOLD = 1.9  # сколько висит большая карточка №1


def _fit(s, size, max_w, black=False):
    while size > 22 and font(size, black).getlength(s) > max_w:
        size -= 2
    return font(size, black)


def _living_bg(accent, seed):
    """Фон выше кадра с мягкими цветными бликами — в кадре он медленно плывёт."""
    hh = H + 600
    t = np.linspace(0, 1, hh)[:, None, None]
    arr = np.array((22, 24, 40))[None, None, :] * (1 - t) + np.array((8, 9, 16))[None, None, :] * t
    arr = np.repeat(arr, W, axis=1).astype(np.float64)
    y, x = np.mgrid[0:hh, 0:W]
    rng = np.random.default_rng(seed)
    for k in range(3):
        cx, cy = rng.uniform(0.1, 0.9) * W, rng.uniform(0.15, 0.85) * hh
        r = rng.uniform(380, 560)
        glow = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * r * r))[:, :, None]
        col = np.array(accent if k == 0 else (60, 80, 160) if k == 1 else (120, 60, 140))
        arr += glow * col * (0.16 if k == 0 else 0.12)
    d = np.sqrt(((x - W / 2) / W) ** 2 + ((y - hh / 2) / hh) ** 2)
    arr *= (1 - 0.4 * np.clip(d - 0.25, 0, 1))[:, :, None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def _confetti(accent, seed, n=150):
    rng = np.random.default_rng(seed + 99)
    palette = [accent, (255, 255, 255), (255, 92, 120), (64, 196, 255), (46, 204, 113)]
    ang = rng.uniform(-np.pi * 0.92, -np.pi * 0.08, n)  # веер вверх
    sp = rng.uniform(900, 2100, n)
    return dict(vx=np.cos(ang) * sp, vy=np.sin(ang) * sp, rot=rng.uniform(0, 6.3, n), vr=rng.uniform(-14, 14, n),
                w=rng.uniform(14, 26, n), h=rng.uniform(8, 14, n), col=[palette[i % 5] for i in range(n)],
                delay=rng.uniform(0, 0.12, n))


def _draw_confetti(d, c, dt, ox, oy):
    g, drag = 2300.0, 1.6
    for i in range(len(c["vx"])):
        tt = dt - c["delay"][i]
        if tt <= 0:
            continue
        k = (1 - math.exp(-drag * tt)) / drag  # сопротивление воздуха
        x = ox + c["vx"][i] * k
        y = oy + c["vy"][i] * k + 0.5 * g * tt * tt * 0.55
        if y > H + 40:
            continue
        a = c["rot"][i] + c["vr"][i] * tt
        w, h = c["w"][i] / 2, c["h"][i] / 2 * abs(math.cos(a * 1.7)) + 1  # «переворачивается» в воздухе
        ca, sa = math.cos(a), math.sin(a)
        pts = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in ((-w, -h), (w, -h), (w, h), (-w, h))]
        d.polygon(pts, fill=c["col"][i])


def render(rows, topic, group_name, accent, out_path, seed=0, fact=None):
    n = len(rows)
    fmt = FMT[topic["fmt"]]
    years = sorted({r[3] for r in rows})
    yrs = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"

    # тайминг в долях такта: место открывается каждые 2 доли, пауза перед №1 — 2 доли
    beat = 60 / bpm_for(seed)
    step, pause, t0 = 2 * beat, 2 * beat, beat
    reveal = {}
    for i, rank in enumerate(range(n, 1, -1)):
        reveal[rank] = t0 + i * step
    pause_start = reveal[2] + step
    top_t = pause_start + pause
    card_out = top_t + CARD_HOLD
    end = card_out + 1.1
    dur = end + 3.2

    v = Video(f"r{seed}", dur, out_path)
    bg_tall = _living_bg(accent, seed)
    conf = _confetti(accent, seed)
    row_y0 = 400
    gap = 6
    row_h = min(90, int((1790 - row_y0) / n) - gap)
    maxv = max(abs(r[2]) for r in rows) or 1
    top_code, top_name, top_val, _ = rows[0]

    h1, h2 = topic["hook"]
    sub = f"{topic['sub']} · {group_name}"
    f_sub = _fit(sub, 36, W - 100)
    f_rank, f_q, f_src = font(int(row_h * 0.44)), font(int(row_h * 0.52)), font(26, False)
    f_val = font(int(row_h * 0.46))
    f_guess = font(int(row_h * 0.44))
    f_h1 = _fit(h1, 84, W - 80, True)
    f_h2 = _fit(h2, 84, W - 80, True)
    f_card_name = _fit(top_name, 96, W - 240, True)

    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg_tall.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im)
        # лёгкий «удар» заголовка в такт
        bp = (t % beat) / beat
        pulse = 1 + 0.025 * math.exp(-bp * 6) if t < top_t else 1
        text(d, (W // 2, 160), h1, _fit(h1, int(84 * pulse), W - 80, True) if pulse > 1.001 else f_h1)
        text(d, (W // 2, 255), h2, _fit(h2, int(84 * pulse), W - 80, True) if pulse > 1.001 else f_h2, fill=accent)
        text(d, (W // 2, 340), sub, f_sub, fill=(170, 175, 200))
        text(d, (W // 2, 1850), f"Source: World Bank Open Data · {yrs}", f_src, fill=(110, 115, 140))

        for idx, (code, name, val, _) in enumerate(rows):
            rank = idx + 1
            y = row_y0 + idx * (row_h + gap)
            x0, x1 = 40, W - 40
            rt = reveal.get(rank, top_t)
            is_top = rank == 1
            if t < rt:
                d.rounded_rectangle((x0, y, x1, y + row_h), 22, fill=PANEL)
                text(d, (x0 + 55, y + row_h // 2), f"{rank}", f_rank, fill=(90, 95, 120))
                if is_top and t >= pause_start:
                    pass  # в паузе на месте №1 только «...»
                elif is_top:  # хук: зритель угадывает №1 с первого кадра
                    gl = 0.5 + 0.5 * math.sin(t * 5)
                    d.rounded_rectangle((x0, y, x1, y + row_h), 22, outline=mix_color(PANEL, accent, 0.4 + 0.5 * gl),
                                        width=3)
                    text(d, (W // 2, y + row_h // 2), "GUESS #1 ?", f_guess, fill=mix_color((90, 95, 120), accent, gl))
                else:
                    text(d, (W // 2, y + row_h // 2), "?", f_q, fill=(70, 75, 100))
                continue
            a = ease_out((t - rt) / 0.35)
            dx = int((1 - a) * W * 0.8)
            cnt = ease_out((t - rt - 0.08) / 0.55)
            flash = max(0.0, 1 - (t - rt) / 0.3)
            col = accent if is_top else BAR
            d.rounded_rectangle((x0 + dx, y, x1 + dx, y + row_h), 22, fill=mix_color(PANEL, (120, 128, 175), flash))
            bw = int((x1 - x0 - 110) * (abs(val) / maxv) * cnt)
            if bw > 10:
                d.rounded_rectangle((x0 + 110 + dx, y + 8, x0 + 110 + bw + dx, y + row_h - 8), 16,
                                    fill=mix_color(col, (255, 255, 255), flash * 0.5))
            if 0 <= t - rt < step and not is_top:
                d.rounded_rectangle((x0 + dx, y, x1 + dx, y + row_h), 22, outline=(200, 205, 230), width=3)
            if is_top:
                glow = int(4 + 3 * math.sin((t - rt) * 8))
                d.rounded_rectangle((x0 - 4 + dx, y - 4, x1 + 4 + dx, y + row_h + 4), 26, outline=accent, width=glow)
            text(d, (x0 + 55 + dx, y + row_h // 2), f"{rank}", f_rank)
            fh = int(row_h * 0.6)
            fl = flag(code.lower(), fh)
            im.paste(fl, (x0 + 125 + dx, y + (row_h - fl.height) // 2), fl)
            vs = fmt(val * cnt)
            val_w = f_val.getlength(fmt(val)) + 40
            name_x = x0 + 140 + fl.width
            f_name = _fit(name, int(row_h * 0.42), x1 - 30 - val_w - name_x)
            dark = (25, 22, 10)
            name_on_bar = is_top and x0 + 110 + bw > name_x + f_name.getlength(name)
            val_on_bar = is_top and x0 + 110 + bw > x1 - val_w
            text(d, (name_x + dx, y + row_h // 2), name, f_name, fill=dark if name_on_bar else (255, 255, 255),
                 anchor="lm")
            text(d, (x1 - 30 + dx, y + row_h // 2), vs, f_val, fill=dark if val_on_bar else (255, 255, 255),
                 anchor="rm")

        if pause_start <= t < top_t:
            k = (t - pause_start) / pause
            text(d, (W // 2, row_y0 + row_h // 2), "...", font(int(60 + 30 * k)), fill=accent)

        # большая карточка победителя
        if top_t <= t < card_out + 0.35:
            a_in = ease_back((t - top_t) / 0.45)
            a_out = ease_out((t - card_out) / 0.35) if t >= card_out else 0
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.62 * (1 - a_out) * ease_out((t - top_t) / 0.2))
            d = ImageDraw.Draw(im)
            _draw_confetti(d, conf, t - top_t, W // 2, H // 2 + 80)  # за карточкой, чтобы не закрывать флаг
            cy = int(H + 500 - a_in * (H // 2 + 500) - a_out * (H // 2 + 600))
            d.rounded_rectangle((80, cy - 400, W - 80, cy + 400), 50, fill=(20, 22, 34), outline=accent, width=8)
            text(d, (W // 2, cy - 290), "#1", font(120), fill=accent)
            fl = flag(top_code.lower(), 240, 0.08)
            fy = cy - 75 - fl.height // 2  # центр флага всегда в одной точке, какой бы формы он ни был
            d.rounded_rectangle((W // 2 - fl.width // 2 - 10, fy - 10, W // 2 + fl.width // 2 + 10, fy + fl.height + 10),
                                26, fill=(255, 255, 255))
            im.paste(fl, (W // 2 - fl.width // 2, fy), fl)
            text(d, (W // 2, cy + 140), top_name, f_card_name)
            cnt = ease_out((t - top_t - 0.15) / 0.7)
            text(d, (W // 2, cy + 270), fmt(top_val * cnt), font(104), fill=accent)
            if fact and t - top_t > 0.7:  # «вау-факт»: во сколько раз №1 отрывается от среднего
                fa = ease_out((t - top_t - 0.7) / 0.3)
                text(d, (W // 2, cy + 352), fact, _fit(fact, 38, W - 220, False),
                     fill=mix_color((20, 22, 34), (235, 238, 250), fa))
        if card_out + 0.35 <= t < top_t + 3.2:
            _draw_confetti(d, conf, t - top_t, W // 2, H // 2 + 80)

        if t < top_t:
            progress(d, t / top_t, 372, accent)
        if t < TITLE_CARD:
            im = title_card(im, t, [(h1, 120, (255, 255, 255)), (h2, 120, accent), (group_name.upper(), 56, (175, 180, 205))],
                            accent, flags=[r[0] for r in rows[1:6]], pill="GUESS #1 ?")
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

    where = f"among {group_name}" if "countries" in group_name else f"in {group_name}"
    voice = tts.lines([(0.15, topic["question"].format(g=where)),
                       (pause_start, "And number one is..."),
                       (top_t + 0.05, f"{top_name}!"),
                       (top_t + 0.9, fact),
                       (end + 0.35, "Where is your country? Comment below!")], seed)
    track = ranking_track(dur, reveal | {1: top_t}, n, pause_start, top_t, end, seed=seed, whooshes=(card_out,),
                          voice=voice)
    return v.finish(audio=track)


TITLE_CARD = 0.6  # сек: титульная карточка в начале — она же обложка в сетке профиля


def title_card(im, t, lines, accent, flags=(), pill=None, fh=92):
    """Крупный заголовок по центру кадра (в зоне, которую видно в сетке профиля 3:4), затем растворяется."""
    if t >= TITLE_CARD:
        return im
    fade = 1 - ease_out((t - TITLE_CARD * 0.55) / (TITLE_CARD * 0.45)) if t > TITLE_CARD * 0.55 else 1.0
    card = Image.blend(im, Image.new("RGB", (W, H), (8, 9, 18)), 0.97)
    d = ImageDraw.Draw(card)
    total = sum(sz for _, sz, _ in lines) + 26 * (len(lines) - 1)
    y = 860 - total // 2
    for s, sz, colr in lines:
        text(d, (W // 2, y + sz // 2), s, _fit(s, sz, W - 90, True), fill=colr)
        y += sz + 26
    if flags:
        fls = [flag_box(c.lower(), int(fh * 1.75), fh, 0.12) for c in flags]
        tw = sum(f.width for f in fls) + 22 * (len(fls) - 1)
        x = W // 2 - tw // 2
        for f in fls:
            card.paste(f, (x, y + 40 + (fh - f.height) // 2), f)
            x += f.width + 22
        y += 40 + fh
    if pill:
        pw = font(40).getlength(pill) + 70
        d.rounded_rectangle((W / 2 - pw / 2, y + 50, W / 2 + pw / 2, y + 122), 36, fill=accent)
        text(d, (W // 2, y + 86), pill, font(40), fill=(20, 20, 30))
    return Image.blend(im, card, fade) if fade < 1 else card


def progress(d, frac, y, accent):
    """Тонкая полоска «сколько осталось до развязки» — зритель видит, что №1 близко, и не уходит."""
    x0, x1 = 60, W - 60
    d.rounded_rectangle((x0, y, x1, y + 8), 4, fill=(45, 48, 70))
    xe = x0 + int((x1 - x0) * clamp(frac))
    if xe > x0 + 8:
        d.rounded_rectangle((x0, y, xe, y + 8), 4, fill=accent)
