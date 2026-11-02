"""Все форматы роликов в одном месте: выбор следующего ролика, рендер и тексты публикации.

Форматы чередуются по кругу ROTATION — канал не однообразный, но остаётся «миром в цифрах».
"""
import random
from catalog import TOPICS, GROUPS, RACE_TOPICS, RACE_GROUPS, DUEL_PAIRS, COUNTRIES, flag_emoji
from data import ranking, race_frames
from duel import duel_rounds

ROTATION = ["ranking", "race", "ranking", "duel"]
RACE_WEIGHT = {"pop": 3, "economy": 3, "rich": 2.5, "life": 1.5, "online": 1.5, "old": 1, "co2": 1}
GROUP_WEIGHT = {"world": 3, "europe": 2, "asia": 2, "americas": 1.5, "exussr": 1.5, "africa": 1}
BASE_TAGS = "#shorts #countries #geography #comparison #data"


def _where(gname):
    return f"among {gname}" if "countries" in gname else f"in {gname}"


def _tags(extra):
    return BASE_TAGS + " " + " ".join("#" + x for x in extra.split())


def _ranking_items(used, rng, avoid):
    from render import render
    combos = [(t, g) for t in TOPICS for g in GROUPS]
    rng.shuffle(combos)
    for t, g in combos:
        key = f"{t['id']}:{g}"
        if key in used or t["id"] in avoid:
            continue
        rows = ranking(t, g)
        if not rows:
            used.add(key)
            continue
        gname = GROUPS[g][0]
        years = sorted({r[3] for r in rows})
        yrs = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
        q = t["question"].format(g=_where(gname))
        tags = _tags(t["tags"] + " ranking")
        yield dict(kind="ranking", key=key, topic=t["id"], slug=f"{t['id']}_{g}",
                   title=f"{q} 🌍",
                   description=(f"{t['sub']} — top {len(rows)} {_where(gname)}.\n"
                                f"Source: World Bank Open Data (latest available: {yrs}).\n\n"
                                f"Is your country on the list? What should we compare next? Comment below 👇\n\n{tags}"),
                   short=f"{q} 🌍 Where is your country? 👇\n\n{tags}",
                   render=lambda out, seed, accent, rows=rows, t=t, gname=gname:
                   render(rows, t, gname, accent, out, seed=seed))


def _race_items(used, rng, avoid):
    from race import render_race
    # сильные темы и крупные регионы выпадают чаще (взвешенная случайная сортировка)
    combos = sorted(((t, g) for t in RACE_TOPICS for g in RACE_GROUPS),
                    key=lambda tg: -rng.random() ** (1 / (RACE_WEIGHT.get(tg[0]["id"], 1) * GROUP_WEIGHT.get(tg[1], 1)) ** 2))
    for t, g in combos:
        key = f"race:{t['id']}:{g}"
        if key in used or f"race-{t['id']}" in avoid:
            continue
        rf = race_frames(t["ind"], g)
        if not rf:
            used.add(key)
            continue
        years, series = rf
        gname = GROUPS[g][0]
        q = t["question"].format(g=_where(gname), y0=years[0], y1=years[-1])
        tags = _tags(t["tags"] + " barchartrace")
        yield dict(kind="race", key=key, topic=f"race-{t['id']}", slug=f"race_{t['id']}_{g}",
                   title=f"{q} 📈",
                   description=(f"{t['sub']} {_where(gname)}, every year from {years[0]} to {years[-1]}.\n"
                                f"Source: World Bank Open Data.\n\n"
                                f"Did you expect this #1? What should we race next? Comment below 👇\n\n{tags}"),
                   short=f"{q} 📈 Who did you expect to win? 👇\n\n{tags}",
                   render=lambda out, seed, accent, years=years, series=series, t=t, gname=gname:
                   render_race(years, series, t, gname, accent, out, seed=seed))


def _duel_items(used, rng, avoid):
    from duel import render_duel
    pairs = list(DUEL_PAIRS)
    rng.shuffle(pairs)
    for a, b in pairs:
        if rng.random() < 0.5:
            a, b = b, a
        key = f"duel:{'-'.join(sorted((a, b)))}"
        if key in used:
            continue
        rounds = duel_rounds(a, b)
        if not rounds:
            used.add(key)
            continue
        na, nb = COUNTRIES[a], COUNTRIES[b]
        lines = "\n".join(f"• {r[0]}" for r in rounds)
        tags = _tags(f"{na.replace(' ', '').lower()} {nb.replace(' ', '').lower()} versus battle")
        yield dict(kind="duel", key=key, topic="duel", slug=f"duel_{a.lower()}_{b.lower()}",
                   title=f"{na} vs {nb}: who wins? {flag_emoji(a)}⚔️{flag_emoji(b)}",
                   description=(f"{na} vs {nb} — 5 rounds of real data:\n{lines}\n"
                                f"Source: World Bank Open Data.\n\n"
                                f"Who should fight next? Comment below 👇\n\n{tags}"),
                   short=f"{na} vs {nb}: who wins? {flag_emoji(a)}⚔️{flag_emoji(b)} Who should fight next? 👇\n\n{tags}",
                   render=lambda out, seed, accent, a=a, b=b, rounds=rounds:
                   render_duel(a, b, rounds, accent, out, seed=seed))


SOURCES = {"ranking": _ranking_items, "race": _race_items, "duel": _duel_items}


def next_item(n_done, used, rng=None, avoid=()):
    """Следующий ролик по ротации форматов; если формат исчерпан — берём следующий."""
    rng = rng or random.Random(n_done)
    start = n_done % len(ROTATION)
    for k in range(len(ROTATION)):
        kind = ROTATION[(start + k) % len(ROTATION)]
        for item in SOURCES[kind](used, rng, set(avoid)):
            return item
    return None
