"""Рендер ролика-рейтинга: строки открываются с последнего места к первому, перед №1 пауза."""
from engine import *
from catalog import FMT

BAR, PANEL = (66, 78, 112), (27, 30, 44)
T0, STEP, PAUSE = 0.7, 1.15, 1.1


def _fit(s, size, max_w, black=False):
    while size > 22 and font(size, black).getlength(s) > max_w:
        size -= 2
    return font(size, black)


def render(rows, topic, group_name, accent, out_path, seed=0):
    n = len(rows)
    fmt = FMT[topic["fmt"]]
    years = sorted({r[3] for r in rows})
    yrs = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"

    reveal = {}
    for i, rank in enumerate(range(n, 1, -1)):
        reveal[rank] = T0 + i * STEP
    reveal[1] = reveal[2] + STEP + PAUSE
    end = reveal[1] + 2.6
    dur = end + 3.2

    v = Video(f"r{seed}", dur, out_path)
    bg = gradient((22, 24, 40), (8, 9, 16))
    row_y0 = 400
    gap = 6
    row_h = min(90, int((1790 - row_y0) / n) - gap)
    maxv = max(abs(r[2]) for r in rows) or 1

    for rank in range(n, 1, -1):
        t = reveal[rank]
        v.sfx(t, "whoosh", 0.6, seed=rank + seed)
        v.sfx(t + 0.08, "pop", 0.8)
        v.sfx(t + 0.6, "tick", 0.6)
    v.sfx(reveal[2] + STEP, "riser", 0.9, dur=PAUSE)
    v.sfx(reveal[1], "boom", 1.0)
    v.sfx(reveal[1] + 0.05, "tada", 0.8)
    v.sfx(end, "whoosh", 0.7, dur=0.5)
    v.sfx(end + 0.2, "ding", 0.6)

    h1, h2 = topic["hook"]
    sub = f"{topic['sub']} · {group_name}"
    f_sub = _fit(sub, 36, W - 100)
    f_rank, f_q, f_src = font(int(row_h * 0.44)), font(int(row_h * 0.52)), font(26, False)
    f_val = font(int(row_h * 0.46))
    f_h1 = _fit(h1, 84, W - 80, True)
    f_h2 = _fit(h2, 84, W - 80, True)

    for fi in range(v.n):
        t = fi / FPS
        im = bg.copy()
        d = ImageDraw.Draw(im)
        text(d, (W // 2, 160), h1, f_h1)
        text(d, (W // 2, 255), h2, f_h2, fill=accent)
        text(d, (W // 2, 340), sub, f_sub, fill=(170, 175, 200))
        text(d, (W // 2, 1850), f"Source: World Bank Open Data · {yrs}", f_src, fill=(110, 115, 140))

        for idx, (code, name, val, _) in enumerate(rows):
            rank = idx + 1
            y = row_y0 + idx * (row_h + gap)
            x0, x1 = 40, W - 40
            rt = reveal[rank]
            is_top = rank == 1
            if t < rt:
                d.rounded_rectangle((x0, y, x1, y + row_h), 22, fill=PANEL)
                text(d, (x0 + 55, y + row_h // 2), f"{rank}", f_rank, fill=(90, 95, 120))
                text(d, (W // 2, y + row_h // 2), "?", f_q, fill=(70, 75, 100))
                continue
            a = ease_out((t - rt) / 0.4)
            dx = int((1 - a) * W * 0.8)
            cnt = ease_out((t - rt - 0.1) / 0.6)
            col = accent if is_top else BAR
            d.rounded_rectangle((x0 + dx, y, x1 + dx, y + row_h), 22, fill=PANEL)
            bw = int((x1 - x0 - 110) * (abs(val) / maxv) * cnt)
            if bw > 10:
                d.rounded_rectangle((x0 + 110 + dx, y + 8, x0 + 110 + bw + dx, y + row_h - 8), 16, fill=col)
            if 0 <= t - rt < STEP and not is_top:
                d.rounded_rectangle((x0 + dx, y, x1 + dx, y + row_h), 22, outline=(200, 205, 230), width=3)
            if is_top:
                glow = int(4 + 3 * math.sin((t - rt) * 8))
                d.rounded_rectangle((x0 - 4 + dx, y - 4, x1 + 4 + dx, y + row_h + 4), 26, outline=accent, width=glow)
            text(d, (x0 + 55 + dx, y + row_h // 2), f"{rank}", f_rank)
            fh = int(row_h * 0.6)
            fl = flag(code.lower(), fh)
            im.paste(fl, (x0 + 125 + dx, y + (row_h - fh) // 2), fl)
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

        if reveal[2] + STEP <= t < reveal[1]:
            k = (t - reveal[2] - STEP) / PAUSE
            text(d, (W // 2, row_y0 + row_h // 2), "...", font(int(60 + 30 * k)), fill=accent)

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

    roots = (55.0, 49.0, 46.25, 51.9, 58.3)
    return v.finish(music_bed(dur + 1, bpm=114 + (seed % 4) * 4, root=roots[seed % len(roots)]))
