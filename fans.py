"""Фанаты (12.11): каждый комментарий со страной — +1 очко ей в недельной «Fan Table»; ники комментаторов
попадают в следующий ролик («Thanks for commenting: @nick 🇮🇳»). Отдельный ролик-таблица — когда стран ≥ MIN_COUNTRIES.

Очко — один раз на (ролик, зритель, страна), чтобы не было спама. Сезон — неделя (ISO), в понедельник чемпион и сброс.
Состояние — data/fans.json.
"""
import datetime, json, os
from catalog import BASE, COUNTRIES, flag_emoji
import requests_q

STATE = os.path.join(BASE, "data", "fans.json")
MIN_COUNTRIES = 8  # меньше — таблица выглядит пустой, ролик не делаем
EVERY_H = 22


def _season(d=None):
    y, w, _ = (d or datetime.date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def load():
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    st.setdefault("season", _season())
    for k, v in (("points", {}), ("fans", {}), ("counted", []), ("recent", []), ("past", []), ("lit", {}), ("lit_shown", [])):
        st.setdefault(k, v)
    if st["season"] != _season():  # новая неделя: чемпион прошлой и сброс
        if st["points"]:
            top = max(st["points"], key=st["points"].get)
            st["past"].append({"season": st["season"], "code": top, "points": st["points"][top]})
        st.update(season=_season(), points={}, fans={}, counted=[], recent=[])
    return st


def save(st):
    st["counted"] = st["counted"][-20000:]
    st["recent"] = st["recent"][-60:]
    json.dump(st, open(STATE, "w"), ensure_ascii=False, indent=1)


def collect(c, st, history, me=None):
    """Читает комментарии последних роликов и начисляет очки (только комментарии этой недели)."""
    import instagram
    counted = set(st["counted"])
    start = datetime.date.fromisocalendar(*map(int, st["season"].replace("W", "").split("-")), 1)
    for h in history[-15:]:
        if not h.get("media_id"):
            continue
        try:
            r = instagram.http("GET", f"{c['api']}/{h['media_id']}/comments",
                               {"fields": "id,text,username,timestamp", "limit": 100, "access_token": c["token"]})
        except Exception as e:
            print(f"фанаты: комментарии недоступны: {str(e)[:160]}")
            break
        for cm in r.get("data", []):
            u = cm.get("username")
            if not u or u == me or (cm.get("timestamp") or "9")[:10] < start.isoformat():
                continue
            for iso in requests_q.countries_in(cm.get("text", ""))[:2]:
                key = f"{h['media_id']}:{u}:{iso}"
                if key in counted:
                    continue
                counted.add(key)
                st["counted"].append(key)
                st["points"][iso] = st["points"].get(iso, 0) + 1
                if iso not in st["lit"]:  # «Light Up the World»: первый, кто назвал страну, зажигает её навсегда
                    st["lit"][iso] = {"by": u, "at": (cm.get("timestamp") or "")[:10]}
                st["fans"].setdefault(iso, {})[u] = st["fans"].get(iso, {}).get(u, 0) + 1
                if [u, iso] not in st["recent"]:
                    st["recent"].append([u, iso])
    return st


def shoutouts(st, n=6):
    """Последние комментаторы для строки «Thanks for commenting» — [(ник, страна)]."""
    out, seen = [], set()
    for u, iso in reversed(st["recent"]):
        if u not in seen:
            seen.add(u)
            out.append((u, iso))
        if len(out) == n:
            break
    return out


def table(st, n=10):
    """[(страна, очки, лучший фанат)] по убыванию."""
    rows = sorted(st["points"].items(), key=lambda x: -x[1])[:n]
    return [(iso, p, max(st["fans"][iso], key=st["fans"][iso].get)) for iso, p in rows]


def due(st, now=None):
    now = now or datetime.datetime.utcnow()
    if len(st["points"]) < MIN_COUNTRIES:
        return False
    la = st.get("last_at")
    return not la or (now - datetime.datetime.fromisoformat(la.rstrip("Z"))).total_seconds() >= EVERY_H * 3600


def make_item(st):
    rows = table(st)
    top = COUNTRIES[rows[0][0]]
    head = f"Fan Table 🏆 Which country has the most active fans this week? #1: {top} {flag_emoji(rows[0][0])}"
    ask = "Comment your country's flag — every comment = +1 point for your country! 👇"
    tags = "#shorts #countries #fans #leaderboard #geography"
    lines = "\n".join(f"{i + 1}. {flag_emoji(iso)} {COUNTRIES[iso]} — {p} pts (top fan @{u})" for i, (iso, p, u) in enumerate(rows))
    return dict(kind="fans", key=f"fans:{st['season']}:{datetime.date.today()}", topic="fans",
                slug=f"fans_{datetime.date.today():%m%d}", title=head,
                first_comment="Drop your flag 👇 Every comment = +1 point. Top fans appear in the next video! 🏆",
                description=f"Points from YOUR comments this week:\n{lines}\n\n{ask}\n\n{tags}",
                short=f"{head}\n\n{ask}\n\n{tags}",
                render=lambda out, seed, accent: render_table(rows, shoutouts(st, 12), st["season"], accent, out, seed=seed))


def posted(st, at):
    st["last_at"] = at


LAST = {}


def render_table(rows, shouts, season, accent, out_path, seed=0):
    """Топ стран по очкам фанатов: места снизу вверх, у каждой — лучший фанат; внизу бегущая строка с никами."""
    import math
    from engine import (Video, Image, ImageDraw, W, H, FPS, font, text, flag_box, ease_out, ease_back, mix_color)
    from render import _fit, _living_bg, _confetti, _draw_confetti, title_card, TITLE_CARD, PANEL, BAR
    from sound import duel_track
    import tts
    n = len(rows)
    step = 0.45
    t0 = 1.0
    reveal = {i: t0 + (n - 1 - i) * step for i in range(1, n)}
    top_t = t0 + (n - 1) * step + 1.0
    end = top_t + 2.6
    dur = end + 3.0
    global LAST
    LAST = {"dur": dur, "moments": [(0, "титул + хук"), (t0, "места снизу"), (top_t, "№1"), (end, "призыв")]}
    v = Video(f"fans{seed}", dur, out_path)
    bg = _living_bg(accent, seed + 21)
    conf = _confetti(accent, seed)
    row_y0, gap = 420, 8
    row_h = min(118, int((1560 - row_y0) / n) - gap)
    mx = rows[0][1]
    ticker = "   ".join(f"@{u} {COUNTRIES.get(iso, '')}" for u, iso in shouts)
    f_tick = font(36)
    tw = f_tick.getlength(ticker + "   ") or 1
    for fi in range(v.n):
        t = fi / FPS
        oy = int(300 + 260 * math.sin(t * 0.22 + seed))
        im = bg.crop((0, oy, W, oy + H))
        d = ImageDraw.Draw(im)
        text(d, (W // 2, 150), "FAN TABLE", font(90))
        text(d, (W // 2, 250), "MOST ACTIVE FANS", font(64), fill=accent)
        text(d, (W // 2, 335), f"Points from your comments · week {season[-2:]}", font(34, False), fill=(170, 175, 200))
        for i, (iso, p, u) in enumerate(rows):
            y = row_y0 + i * (row_h + gap)
            rt = reveal.get(i, top_t)
            if t < rt:
                d.rounded_rectangle((40, y, W - 40, y + row_h), 22, fill=PANEL)
                text(d, (95, y + row_h // 2), str(i + 1), font(int(row_h * 0.42)), fill=(90, 95, 120))
                text(d, (W // 2, y + row_h // 2), "?", font(int(row_h * 0.5)), fill=(70, 75, 100))
                continue
            a = ease_out((t - rt) / 0.35)
            dx = int((1 - a) * W * 0.8)
            col = accent if i == 0 else BAR
            bw = int((W - 200) * p / mx * a)
            d.rounded_rectangle((40 + dx, y, W - 40 + dx, y + row_h), 22, fill=PANEL)
            d.rounded_rectangle((120 + dx, y + 6, 120 + max(bw, 30) + dx, y + row_h - 6), 18, fill=mix_color(PANEL, col, 0.55))
            text(d, (80 + dx, y + row_h // 2), str(i + 1), font(int(row_h * 0.42)), fill=(255, 255, 255))
            fl = flag_box(iso.lower(), int(row_h * 1.2), int(row_h * 0.62), 0.1)
            im.paste(fl, (140 + dx, y + (row_h - fl.height) // 2), fl)
            nx = 160 + fl.width + dx
            text(d, (nx, y + row_h * 0.36), COUNTRIES[iso], _fit(COUNTRIES[iso], int(row_h * 0.36), 460, True), anchor="lm")
            text(d, (nx, y + row_h * 0.74), f"top fan @{u}", _fit(f"top fan @{u}", int(row_h * 0.26), 460), fill=(200, 205, 225), anchor="lm")
            text(d, (W - 75 + dx, y + row_h // 2), f"{p}", font(int(row_h * 0.44)), anchor="rm")
        # бегущая строка с никами — «ты попал в ролик»
        d.rounded_rectangle((0, 1610, W, 1700), 0, fill=(20, 22, 34))
        text(d, (W // 2, 1590), "THANKS FOR COMMENTING", font(30), fill=accent)
        x = -int((t * 220) % tw)
        while x < W:
            text(d, (x, 1655), ticker, f_tick, anchor="lm")
            x += int(tw)
        if top_t <= t < end:
            _draw_confetti(d, conf, t - top_t, W // 2, row_y0 + row_h // 2)
        if t < TITLE_CARD:
            im = title_card(im, t, [("FAN TABLE", 120, (255, 255, 255)), ("WHO HAS THE", 64, accent),
                                    ("MOST ACTIVE FANS?", 64, accent)], accent, flags=[r[0] for r in rows[:5]],
                            pill="ARE YOU HERE?")
        if t >= end:
            im = Image.blend(im, Image.new("RGB", (W, H)), 0.6)
            d = ImageDraw.Draw(im)
            a2 = ease_back((t - end) / 0.45)
            cy = int(H + 200 - a2 * (H // 2 + 200))
            d.rounded_rectangle((60, cy - 200, W - 60, cy + 200), 40, fill=(255, 255, 255))
            text(d, (W // 2, cy - 95), "Comment your flag", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy - 15), "= +1 point", font(66), fill=(15, 15, 25))
            text(d, (W // 2, cy + 75), "Top fans appear in the next video!", font(40, False), fill=mix_color(accent, (0, 0, 0), 0.25))
        v.write(im)
    top = COUNTRIES[rows[0][0]]
    plan = [(0.15, "Which country has the most active fans this week?"),
            (top_t - 0.9, "And number one is..."), (top_t + 0.05, f"{top}! Top fan: {rows[0][2]}."),
            (end + 0.3, "Comment your flag. Every comment is a point for your country!")]
    voice = tts.lines(plan, seed)
    track = duel_track(dur, (0.15, 0.45), [(reveal.get(i, top_t), reveal.get(i, top_t) + 0.1) for i in range(1, n)],
                       top_t, end, seed=seed, voice=voice)
    return v.finish(audio=track)


# ---------- «Light Up the World»: карта, которая загорается от комментариев ----------
def map_due(st, now=None):
    now = now or datetime.datetime.utcnow()
    new = [c for c in st["lit"] if c not in st["lit_shown"]]
    la = st.get("map_at")
    return bool(new) and (not la or (now - datetime.datetime.fromisoformat(la.rstrip("Z"))).total_seconds() >= EVERY_H * 3600)


def make_map_item(st):
    from worldmap import render_lightup, shapes, GOAL
    geo = shapes()
    new_all = [c for c in st["lit"] if c not in st["lit_shown"]]
    anim = [c for c in new_all if c in geo][:6]
    total = len(st["lit"])
    before = [c for c in st["lit"] if c not in anim and c in geo]
    by = {c: st["lit"][c]["by"] for c in st["lit"]}
    names = ", ".join(f"{flag_emoji(c)} {COUNTRIES[c]} (by @{by[c]})" for c in new_all[:10])
    head = f"Light Up the World 🌍 {total}/{GOAL} countries lit — is yours? Comment your flag 👇"
    tags = "#shorts #countries #worldmap #geography #challenge"
    return dict(kind="map", key=f"map:{datetime.date.today()}", topic="map", slug=f"map_{datetime.date.today():%m%d}",
                title=head, lit_now=list(st["lit"]),
                first_comment="Is your country still dark? 🌑 Comment its flag 👇 The first to light it gets their name on it forever!",
                description=f"Every comment lights up a country. Newly lit: {names}.\n\n"
                            f"Is YOUR country dark? Comment its flag — your name stays on it forever 🌍\n\n{tags}",
                short=f"{head}\nNewly lit: {names}\n\n{tags}",
                render=lambda out, seed, accent: render_lightup(before, anim, by, total, accent, out, seed=seed))


def map_posted(st, lit_now, at):
    st["lit_shown"] = list(lit_now)
    st["map_at"] = at
