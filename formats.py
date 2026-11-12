"""Все форматы роликов в одном месте: выбор следующего ролика, рендер и тексты публикации.

Форматы чередуются по кругу ROTATION — канал не однообразный, но остаётся «миром в цифрах».
"""
import os
import random
from catalog import TOPICS, GROUPS, RACE_TOPICS, RACE_GROUPS, DUEL_PAIRS, COUNTRIES, flag_emoji
from data import ranking, race_frames, indicator, leader_changes
from duel import duel_rounds, flip_rounds, FLIPS

ROTATION = ["race", "twist", "duel", "race", "ranking", "twist"]  # 12.11: + твисты  # 04.11: гонка после правок — 45% пролистываний и 47% досмотра, лучший формат
YOUTUBE = os.environ.get("REELS_PLATFORM") == "youtube"
# 11.11: на YouTube гонки про богатство в топе (461), в Instagram богатство пролистывают (77%)
RACE_WEIGHT = {"pop": 3, "economy": 3, "army": 3, "rich": 2.5 if YOUTUBE else 1, "life": 1.5, "online": 1.5, "old": 1, "co2": 1}
GROUP_WEIGHT = {"world": 3, "europe": 2, "asia": 2, "americas": 1.5, "exussr": 1.5, "africa": 1}
# рейтинги: темы про людей и крупные группы держат лучше (07.11: «most people in Asia» 51%, G20 52% пролистываний;
# EU/ex-USSR и безработица в Европе — 66–77%)
RANK_WEIGHT = {"pop": 3, "boom": 2.5, "shrink": 2, "economy": 2, "rich": 2 if YOUTUBE else 0.7, "life": 2,
               "young": 1.5, "old": 1.5, "babies": 1.5, "crowded": 1.5, "ppp": 1 if YOUTUBE else 0.5,
               # острые темы (11.11) — повод найти свою страну и поспорить
               "danger": 3, "safe": 2.5, "army": 3, "soldiers": 2.5, "fat": 2.5, "unequal": 2, "shortlife": 2}
RANK_GROUP_WEIGHT = {"world": 3, "g20": 3, "asia": 2.5, "europe": 1.5, "americas": 1.5, "mideast": 1, "africa": 1,
                     "exussr": 0.7, "eu": 0.7}
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
    combos = sorted(((t, g) for t in TOPICS for g in GROUPS),
                    key=lambda tg: -rng.random() ** (1 / (RANK_WEIGHT.get(tg[0]["id"], 1) * RANK_GROUP_WEIGHT.get(tg[1], 1)) ** 2))
    for t, g in combos:
        key = f"{t['id']}:{g}"
        if key in used or t["id"] in avoid:
            continue
        if t["id"] in ("army", "soldiers") and g in ("exussr", "europe", "mideast"):  # без войн: там цифры — про конфликты
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
                   title=f"{q} Is yours in the top 10? 🌍",
                   description=(f"{t['sub']} — top {len(rows)} {_where(gname)}.\n"
                                f"Source: World Bank Open Data (latest available: {yrs}).\n\n"
                                f"Is your country on the list? What should we compare next? Comment below 👇\n\n{tags}"),
                   short=f"{q} 🌍 Comment your country's flag — we'll reply with its rank 👇\n\n{tags}",
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
        if t["id"] == "army" and g in ("exussr", "europe", "asia"):  # без войн: в Азии — Израиль, Иран, Индия-Пакистан
            continue
        rf = race_frames(t["ind"], g)
        if not rf:
            used.add(key)
            continue
        years, series = rf
        if leader_changes(years, series) == 0:  # лидер не меняется — интриги нет
            continue
        gname = GROUPS[g][0]
        q = t["question"].format(g=_where(gname), y0=years[0], y1=years[-1])
        tags = _tags(t["tags"] + " barchartrace")
        yield dict(kind="race", key=key, topic=f"race-{t['id']}", slug=f"race_{t['id']}_{g}",
                   title=f"{q} 📈",
                   description=(f"{t['sub']} {_where(gname)}, every year from {years[0]} to {years[-1]}.\n"
                                f"Source: World Bank Open Data.\n\n"
                                f"Did you expect this #1? What should we race next? Comment below 👇\n\n{tags}"),
                   short=f"{q} 📈 Comment your country's flag — we'll reply with its rank 👇\n\n{tags}",
                   render=lambda out, seed, accent, years=years, series=series, t=t, gname=gname:
                   render_race(years, series, t, gname, accent, out, seed=seed))


# соперники, про которых спорят все (без идущих войн — см. requests_q.BLOCKED): выходят первыми, с пометкой RIVALS
RIVALS = [("US", "CN"), ("US", "RU"), ("CN", "JP"), ("JP", "KR"), ("GB", "FR"), ("DE", "FR"), ("TR", "GR"),
          ("GB", "AR"), ("RU", "GB"), ("US", "MX"), ("SA", "QA"), ("EG", "ET"), ("IN", "CN"), ("BR", "AR")]
RIVAL_SET = {frozenset(p) for p in RIVALS}
# пары с идущим конфликтом: только нейтрально («X и Y в цифрах»), не чаще раза в NEUTRAL_EVERY дней
CONFLICTS = [("RU", "UA"), ("IN", "PK"), ("IL", "IR")]
NEUTRAL_EVERY = 10


def make_neutral(a, b):
    from duel import render_duel, neutral_rounds
    rounds = neutral_rounds(a, b)
    if not rounds:
        return None
    na, nb = COUNTRIES[a], COUNTRIES[b]
    lines = "\n".join(f"• {r[0]}" for r in rounds)
    tags = _tags(f"{na.replace(' ', '').lower()} {nb.replace(' ', '').lower()} statistics")
    title = f"{na} and {nb} in numbers {flag_emoji(a)} {flag_emoji(b)}"
    note = "Data only, no winners. Please keep comments respectful 🙏"
    return dict(kind="duel", key=f"neutral:{'-'.join(sorted((a, b)))}", topic="neutral", slug=f"facts_{a.lower()}_{b.lower()}",
                title=title, neutral=True,
                description=f"{na} and {nb} — 5 facts from World Bank Open Data:\n{lines}\n\n{note}\n\n{tags}",
                short=f"{title}\n{note}\n\n{tags}",
                render=lambda out, seed, accent: render_duel(a, b, rounds, accent, out, seed=seed, pill="IN NUMBERS",
                                                             neutral=True))


def next_neutral(used, history):
    """Нейтральная пара, если с прошлой прошло NEUTRAL_EVERY дней; иначе None."""
    import datetime
    last = [h["at"] for h in history if h.get("key", "").startswith("neutral:")]
    if last:
        days = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(max(last).rstrip("Z"))).days
        if days < NEUTRAL_EVERY:
            return None
    for a, b in CONFLICTS:
        if f"neutral:{'-'.join(sorted((a, b)))}" not in used:
            return make_neutral(a, b)
    return None


def make_duel(a, b, by=None):
    """Ролик-дуэль для пары стран (by — ники зрителей, которые её заказали) или None, если данных мало."""
    from duel import render_duel
    rounds = duel_rounds(a, b)
    if not rounds:
        return None
    na, nb = COUNTRIES[a], COUNTRIES[b]
    lines = "\n".join(f"• {r[0]}" for r in rounds)
    rival = frozenset((a, b)) in RIVAL_SET
    tags = _tags(f"{na.replace(' ', '').lower()} {nb.replace(' ', '').lower()} versus battle" + (" rivals" if rival else ""))
    fl = f"{flag_emoji(a)}⚔️{flag_emoji(b)}"
    head = f"Rivals: {na} vs {nb} — who really wins? {fl}" if rival else f"{na} vs {nb}: who wins? {fl}"
    ask = "Who are you rooting for? Comment your side 👇" if rival else "Who should fight next? Comment below 👇"
    credit = f"\nRequested by {' '.join('@' + u for u in by[:5])} 🙌\n" if by else ""
    return dict(kind="duel", key=f"duel:{'-'.join(sorted((a, b)))}", topic="duel", slug=f"duel_{a.lower()}_{b.lower()}",
                title=head,
                description=(f"{na} vs {nb} — {len(rounds)} rounds of real data:\n{lines}\n{credit}"
                             f"Source: World Bank Open Data.\n\n{ask}\n\n{tags}"),
                short=f"{head}{credit} {ask}\n\n{tags}",
                render=lambda out, seed, accent: render_duel(a, b, rounds, accent, out, seed=seed,
                                                             pill="RIVALS · WHO WINS?" if rival else "WHO WINS?"))


def make_flip(a, b):
    """«Plot twist»: A был богаче B, а теперь B богаче в разы. None — если данных нет или твиста нет."""
    from duel import render_duel
    rounds = flip_rounds(a, b)
    if not rounds:
        return None
    early, late = (a, b) if rounds[0][4] == 0 else (b, a)
    ne, nl = COUNTRIES[early], COUNTRIES[late]
    y0, y1 = rounds[0][0][3:], rounds[-1][0][3:]
    fl = f"{flag_emoji(early)}➡️{flag_emoji(late)}"
    head = f"{ne} was richer than {nl} in {y0}. Then this happened 😳 {fl}"
    ask = "Which 2 countries should we compare next? Comment below 👇"
    tags = _tags(f"{ne.replace(' ', '').lower()} {nl.replace(' ', '').lower()} history economy plottwist")
    return dict(kind="duel", key=f"flip:{'-'.join(sorted((a, b)))}", topic="flip", slug=f"flip_{a.lower()}_{b.lower()}",
                title=head,
                description=(f"GDP per person: {ne} vs {nl} in {y0}, 1990 and {y1}.\n"
                             f"Source: World Bank Open Data (current US$).\n\n{ask}\n\n{tags}"),
                short=f"{head} {ask}\n\n{tags}",
                render=lambda out, seed, accent: render_duel(a, b, rounds, accent, out, seed=seed,
                                                             pill="PLOT TWIST", flip=True))


# страны, про которые спорит весь мир: дуэль малоизвестных пар (Болгария–Румыния) держит хуже — 60% пролистываний
FAMOUS = set("US CN IN BR DE FR GB JP RU IT ES MX KR TR AR CA AU SA AE PT NL".split())


def _duel_items(used, rng, avoid):
    pairs = list(DUEL_PAIRS)
    rng.shuffle(pairs)
    pairs.sort(key=lambda p: -((p[0] in FAMOUS) + (p[1] in FAMOUS)))  # сначала пары из двух «громких» стран
    rivals = list(RIVALS)
    rng.shuffle(rivals)
    pairs = rivals + pairs  # а ещё раньше — соперники
    flips = [p for p in FLIPS if f"flip:{'-'.join(sorted(p))}" not in used]
    if flips and rng.random() < 0.5:  # 12.11: «plot twist» — каждая вторая дуэль, пока не кончатся пары
        a, b = flips[0]
        item = make_flip(a, b)
        if item:
            yield item
        else:
            used.add(f"flip:{'-'.join(sorted((a, b)))}")
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


# ---------- твисты (12.11): страна против континента, «кто кого обогнал», «угадай страну» ----------
TWIST_COUNTRIES = sorted(FAMOUS | set("ID NG PK BD EG PH VN ET".split()))
BIGGER_STATS = [("SP.POP.TOTL", "people", "more people", "Population"),
                ("NY.GDP.MKTP.CD", "money", "a bigger economy", "Economy (GDP)")]
OVERTAKE_STATS = [("SP.POP.TOTL", "people", "Population", "pop"), ("NY.GDP.MKTP.CD", "money", "Economy (GDP)", "gdp"),
                  ("NY.GDP.PCAP.CD", "money", "GDP per person", "rich")]
GUESS_COUNTRIES = TWIST_COUNTRIES + "SE NO CH GR PL TH MY EG KE MA CO PE CL NZ IE".split()


def _no_conflict(a, b):
    return frozenset((a, b)) not in {frozenset(p) for p in CONFLICTS}


def _human(v, kind):
    """Число для голоса: «1.4 billion people», «12,300 dollars»."""
    if kind == "people":
        return f"{v / 1e9:.1f} billion" if v >= 1e9 else f"{v / 1e6:.0f} million" if v >= 1e6 else f"{v:,.0f}"
    if kind == "money":
        return f"{v / 1e12:.1f} trillion dollars" if v >= 1e12 else f"{round(v, -2):,.0f} dollars"
    return f"{v:.0f}"


def _bigger_items(used, rng):
    from twists import render_bigger
    cands = []
    for ind, fmt_id, noun, label in BIGGER_STATS:
        vals = indicator(ind)
        for c in TWIST_COUNTRIES:
            for g in ("europe", "africa", "americas", "asia", "eu", "mideast", "exussr"):
                mem = [m for m in GROUPS[g][1] if m in vals]
                if c not in vals or c in mem or len(mem) < 8:
                    continue
                r = sum(vals[m][0] for m in mem) / vals[c][0]
                if 0.5 <= r <= 2.0:
                    cands.append((abs(r - 1) + rng.random() * 0.5, c, g, ind, fmt_id, noun, label))
    for _, c, g, ind, fmt_id, noun, label in sorted(cands):
        key = f"bigger:{c}:{g}:{ind}"
        if key in used:
            continue
        name, gname = COUNTRIES[c], GROUPS[g][0].replace("the ", "")
        head = f"{name} vs ALL of {gname}: who has {noun}? {flag_emoji(c)}🌍"
        ask = "Which country should we test next? Comment below 👇"
        tags = _tags(f"{name.replace(' ', '').lower()} {gname.replace(' ', '').lower()} comparison")
        yield dict(kind="twist", key=key, topic="bigger", slug=f"bigger_{c.lower()}_{g}",
                   title=head, first_comment="Guess before the end: who wins? 👇",
                   description=f"{label}: {name} vs all of {gname} combined.\nSource: World Bank Open Data.\n\n{ask}\n\n{tags}",
                   short=f"{head} {ask}\n\n{tags}",
                   render=lambda out, seed, accent, c=c, g=g, ind=ind, fmt_id=fmt_id, noun=noun:
                   render_bigger(c, g, ind, fmt_id, noun, accent, out, seed=seed))


def _overtakes():
    """[(слава, a, b, год, ind, fmt, подпись, id)]: b долго был позади a и обогнал (колебания ≤ 6 лет)."""
    from data import history
    out = []
    for ind, fmt_id, label, sid in OVERTAKE_STATS:
        h = history(ind)
        for a in TWIST_COUNTRIES:
            for b in TWIST_COUNTRIES:
                if a == b or a not in h or b not in h or not _no_conflict(a, b):
                    continue
                ys = [y for y in range(1960, 2030) if y in h[a] and y in h[b]]
                if len(ys) < 30:
                    continue
                ahead = [h[b][y] > h[a][y] for y in ys]
                sw = [i for i in range(1, len(ys)) if ahead[i] != ahead[i - 1]]
                if not sw or ahead[0] or not ahead[-1] or ys[sw[-1]] - ys[sw[0]] > 6 or sw[0] < 10 or ys[sw[-1]] < 1985:
                    continue
                if h[b][ys[-1]] < h[a][ys[-1]] * 1.02:
                    continue
                fame = (a in FAMOUS) + (b in FAMOUS) + ys[sw[-1]] / 2000
                out.append((fame, a, b, ys[sw[-1]], ind, fmt_id, label, sid))
    return sorted(out, reverse=True)


def _overtake_items(used, rng):
    from twists import render_overtake
    from data import history
    cands = _overtakes()
    rng.shuffle(cands)
    cands.sort(key=lambda x: -x[0] // 1)  # сначала пары из двух громких стран, внутри — случайно
    for fame, a, b, year, ind, fmt_id, label, sid in cands:
        key = f"overtake:{a}-{b}:{sid}"
        if key in used:
            continue
        h = history(ind)
        years = [y for y in range(1960, 2030) if y in h[a] and y in h[b]]
        sa, sb = [h[a][y] for y in years], [h[b][y] for y in years]
        na, nb = COUNTRIES[a], COUNTRIES[b]
        head = f"The year {nb} overtook {na} 📈 {flag_emoji(b)}{flag_emoji(a)} Guess it?"
        ask = "Who will overtake who next? Comment 2 countries 👇"
        tags = _tags(f"{na.replace(' ', '').lower()} {nb.replace(' ', '').lower()} history")
        yield dict(kind="twist", key=key, topic="overtake", slug=f"overtake_{a.lower()}_{b.lower()}_{sid}",
                   title=head, first_comment="Did you guess the year? 👇",
                   description=f"{label}: {nb} vs {na}, {years[0]}–{years[-1]}.\nSource: World Bank Open Data.\n\n{ask}\n\n{tags}",
                   short=f"{head} {ask}\n\n{tags}",
                   render=lambda out, seed, accent, a=a, b=b, years=years, sa=sa, sb=sb, fmt_id=fmt_id, label=label,
                   year=year: render_overtake(a, b, years, sa, sb, fmt_id, label, year, accent, out, seed=seed))


def guess_clues(c):
    """4 подсказки от трудной к лёгкой или None."""
    life, gdp, pop = (indicator(i).get(c) for i in ("SP.DYN.LE00.IN", "NY.GDP.PCAP.CD", "SP.POP.TOTL"))
    region = next((GROUPS[g][0].replace("the ", "") for g in ("europe", "africa", "americas", "asia") if c in GROUPS[g][1]),
                  "Oceania")
    if not (life and gdp and pop):
        return None
    return [("Life expectancy", f"{life[0]:.0f} years", f"{life[0]:.0f} years"),
            ("GDP per person", f"${round(gdp[0], -2):,.0f}", _human(gdp[0], "money")),
            ("Population", _compact_people(pop[0]), _human(pop[0], "people") + " people"),
            ("Continent", region, region)]


def _compact_people(v):
    return f"{v / 1e9:.2f}B" if v >= 1e9 else f"{v / 1e6:.0f}M" if v >= 1e7 else f"{v / 1e6:.1f}M"


def _guess_items(used, rng):
    from twists import render_guess
    cs = list(GUESS_COUNTRIES)
    rng.shuffle(cs)
    for c in cs:
        key = f"guess:{c}"
        clues = guess_clues(c) if key not in used else None
        if not clues:
            continue
        head = "Guess the country in 4 clues 🤔 How fast did you get it?"
        tags = _tags("guessthecountry quiz geography")
        yield dict(kind="twist", key=key, topic="guess", slug=f"guess_{c.lower()}",
                   title=head, first_comment="Comment your guess BEFORE the reveal 👀 How many clues did you need?",
                   description=f"Guess the country from 4 real-data clues.\nSource: World Bank Open Data.\n\n"
                               f"Comment your guess 👇\n\n{tags}",
                   short=f"{head} Comment your guess 👇\n\n{tags}",
                   render=lambda out, seed, accent, c=c, clues=clues: render_guess(c, clues, accent, out, seed=seed))


TWIST_SOURCES = {"bigger": _bigger_items, "overtake": _overtake_items, "guess": _guess_items}


def _twist_items(used, rng, avoid):
    subs = [s for s in TWIST_SOURCES if s not in avoid] or list(TWIST_SOURCES)
    rng.shuffle(subs)
    for s in subs:
        yield from TWIST_SOURCES[s](used, rng)


SOURCES["twist"] = _twist_items
