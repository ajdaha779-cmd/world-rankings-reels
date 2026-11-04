"""Все форматы роликов в одном месте: выбор следующего ролика, рендер и тексты публикации.

Форматы чередуются по кругу ROTATION — канал не однообразный, но остаётся «миром в цифрах».
"""
import random
from catalog import TOPICS, GROUPS, RACE_TOPICS, RACE_GROUPS, DUEL_PAIRS, COUNTRIES, flag_emoji
from data import ranking, race_frames, indicator
from duel import duel_rounds

ROTATION = ["race", "duel", "race", "ranking", "race"]  # 04.11: гонка после правок — 45% пролистываний и 47% досмотра, лучший формат
RACE_WEIGHT = {"pop": 3, "economy": 3, "rich": 2.5, "life": 1.5, "online": 1.5, "old": 1, "co2": 1}
GROUP_WEIGHT = {"world": 3, "europe": 2, "asia": 2, "americas": 1.5, "exussr": 1.5, "africa": 1}
BASE_TAGS = "#shorts #countries #geography #comparison #data"


def _where(gname):
    return f"among {gname}" if "countries" in gname else f"in {gname}"


def _tags(extra):
    return BASE_TAGS + " " + " ".join("#" + x for x in extra.split())


def ranking_fact(t, g, rows):
    """«Вау-факт» для карточки №1: сравнение с средним по региону (или с последним местом)."""
    vals = indicator(t["ind"])
    members = [vals[c][0] for c in GROUPS[g][1] if c in vals]
    top = rows[0][2]
    if not members or top <= 0 or any(r[2] <= 0 for r in rows):
        return None
    avg = sum(members) / len(members)
    gname = GROUPS[g][0].replace("the ", "").replace(" countries", "")
    if t["fmt"] in ("money", "people", "density", "tonnes", "dec1", "dec2"):
        k = top / avg if t["order"] == "desc" else avg / top
        if k >= 1.3:
            return f"{k:.1f}× {'higher' if t['order'] == 'desc' else 'lower'} than the {gname} average"
    diff = (top - avg) if t["order"] == "desc" else (avg - top)
    if t["fmt"] == "years" and diff >= 1:
        return f"{diff:.1f} years {'above' if t['order'] == 'desc' else 'below'} the {gname} average"
    if t["fmt"] == "pct" and diff >= 1:
        return f"{diff:.1f} points {'above' if t['order'] == 'desc' else 'below'} the {gname} average"
    return None


def _teaser(fact):
    """Короткий тизер для строки №1: «3.0× the EU average» из «3.0× higher than the EU average»."""
    if not fact:
        return None
    return fact.replace(" higher than the ", " the ").replace(" lower than the ", " below the ")


def _ranking_items(used, rng, avoid):
    from render import render
    combos = [(t, g) for t in TOPICS for g in GROUPS]
    rng.shuffle(combos)
    for t, g in combos:
        key = f"{t['id']}:{g}"
        if key in used or t["id"] in avoid:
            continue
        rows = ranking(t, g, top_n=10)  # 10 мест — ролик короче, досматривают чаще
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
                   render=lambda out, seed, accent, rows=rows, t=t, gname=gname, fact=ranking_fact(t, g, rows):
                   render(rows, t, gname, accent, out, seed=seed, fact=fact, teaser=_teaser(fact)))


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


def make_duel(a, b, by=None):
    """Ролик-дуэль для пары стран (by — ники зрителей, которые её заказали) или None, если данных мало."""
    from duel import render_duel
    rounds = duel_rounds(a, b)
    if not rounds:
        return None
    na, nb = COUNTRIES[a], COUNTRIES[b]
    lines = "\n".join(f"• {r[0]}" for r in rounds)
    tags = _tags(f"{na.replace(' ', '').lower()} {nb.replace(' ', '').lower()} versus battle")
    credit = f"\nRequested by {' '.join('@' + u for u in by[:5])} 🙌\n" if by else ""
    return dict(kind="duel", key=f"duel:{'-'.join(sorted((a, b)))}", topic="duel", slug=f"duel_{a.lower()}_{b.lower()}",
                title=f"{na} vs {nb}: who wins? {flag_emoji(a)}⚔️{flag_emoji(b)}",
                description=(f"{na} vs {nb} — 5 rounds of real data:\n{lines}\n{credit}"
                             f"Source: World Bank Open Data.\n\n"
                             f"Who should fight next? Comment below 👇\n\n{tags}"),
                short=(f"{na} vs {nb}: who wins? {flag_emoji(a)}⚔️{flag_emoji(b)}{credit}"
                       f" Who should fight next? 👇\n\n{tags}"),
                render=lambda out, seed, accent: render_duel(a, b, rounds, accent, out, seed=seed))


# страны, про которые спорит весь мир: дуэль малоизвестных пар (Болгария–Румыния) держит хуже — 60% пролистываний
FAMOUS = set("US CN IN BR DE FR GB JP RU IT ES MX KR TR AR CA AU SA AE PT NL".split())


def _duel_items(used, rng, avoid):
    pairs = list(DUEL_PAIRS)
    rng.shuffle(pairs)
    pairs.sort(key=lambda p: -((p[0] in FAMOUS) + (p[1] in FAMOUS)))  # сначала пары из двух «громких» стран
    for a, b in pairs:
        if rng.random() < 0.5:
            a, b = b, a
        key = f"duel:{'-'.join(sorted((a, b)))}"
        if key in used:
            continue
        item = make_duel(a, b)
        if not item:
            used.add(key)
            continue
        yield item


SOURCES = {"ranking": _ranking_items, "race": _race_items, "duel": _duel_items}


def pick_kind(n_done, weights, recent_kinds, rng):
    """Формат следующего ролика: по весам статистики (если она есть), иначе по кругу ROTATION.
    Один и тот же формат не идёт три раза подряд."""
    if not weights:
        return ROTATION[n_done % len(ROTATION)]
    kinds = list(weights)
    if len(recent_kinds) >= 2 and recent_kinds[-1] == recent_kinds[-2]:
        kinds = [k for k in kinds if k != recent_kinds[-1]]
    return rng.choices(kinds, weights=[weights[k] for k in kinds])[0]


def next_item(n_done, used, rng=None, avoid=(), kind=None):
    """Следующий ролик нужного формата; если формат исчерпан — берём следующий по кругу."""
    rng = rng or random.Random(n_done)
    kind = kind or ROTATION[n_done % len(ROTATION)]
    order = [kind] + [k for k in ROTATION if k != kind]
    for k in dict.fromkeys(order):
        for item in SOURCES[k](used, rng, set(avoid)):
            return item
    return None
