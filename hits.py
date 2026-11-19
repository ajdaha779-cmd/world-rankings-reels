"""Что «залетает» (20.11, просьба пользователя: «смотри, какие ролики залетают, и делай на похожие темы»).

По каждой площадке отдельно считаем средние просмотры тем и регионов и превращаем их в множители для выбора
следующих роликов: тема/регион вдвое лучше среднего канала → выпадает чаще, вдвое хуже → реже.
  Instagram — data/history_cloud.json (ключ ролика уже есть).
  YouTube   — data/youtube_stats.json (make_batch.py обновляет через API перед пачкой; тему узнаём по названию).
Мало роликов по теме → множитель ближе к 1 (сглаживание), пределы 0.4…3.
"""
import json, math, os, re

from catalog import BASE, TOPICS, RACE_TOPICS, GROUPS

YOUTUBE = os.environ.get("REELS_PLATFORM") == "youtube"
IG_HISTORY = os.path.join(BASE, "data", "history_cloud.json")
YT_STATS = os.path.join(BASE, "data", "youtube_stats.json")
PRIOR = 2  # «виртуальных» средних роликов в каждой теме — чтобы 1 случайный хит не перевешивал всё


def _where(gname):
    return f"among {gname}" if "countries" in gname else f"in {gname}"


def _patterns():
    out = []
    for kind, topics in (("ranking", TOPICS), ("race", RACE_TOPICS)):
        for t in topics:
            q = t["question"]
            rx = re.escape(q).replace(r"\{g\}", "(?P<g>.+?)").replace(r"\{y0\}", r"\d+").replace(r"\{y1\}", r"\d+")
            out.append((kind, t["id"], re.compile("^" + rx)))
    return out


# старые/ручные названия, которые не совпадают с текущими шаблонами
KEYWORDS = [("pop", r"most people|most populated|populous"), ("boom", r"growing the fastest"),
            ("shrink", r"shrinking|people leaving|are people leaving"), ("online", r"online|internet"),
            ("danger", r"dangerous"), ("safe", r"safest"), ("life", r"live (the )?longest|lives? longer"),
            ("rich", r"richest|richer|per person"), ("economy", r"econom"), ("army", r"military|army"),
            ("babies", r"babies|birth rate"), ("old", r"oldest"), ("unemp", r"unemployment"), ("jobs", r"find a job")]


def classify(title):
    """(вид, тема, регион) по названию ролика; что не узнали — None."""
    t = title.strip()
    for kind, tid, rx in PATTERNS:
        m = rx.match(t)
        if m:
            g = m.group("g")
            grp = next((k for k, v in GROUPS.items() if _where(v[0]) == g), None)
            return kind, tid, grp
    low = t.lower()
    if re.search(r"until \d{4}|lead changed|\(\d{4}[–-]\d{4}\)|\d{4}[–-]\d{4}\)", low):
        kind = "h2h"
    elif re.search(r"who (really )?wins|vs .*\?", low):
        kind = "duel"
    elif "→" in t:
        kind = "race"
    else:
        kind = "ranking"
    tid = next((k for k, rx in KEYWORDS if re.search(rx, low)), None)
    grp = next((k for k, v in GROUPS.items() if re.search(re.escape(v[0].replace("the ", "")), t)), None)
    return kind, tid, grp


PATTERNS = _patterns()


def _rows():
    """[(вид, тема, регион, просмотры)] для текущей площадки."""
    rows = []
    try:
        if YOUTUBE:
            for v in json.load(open(YT_STATS)):
                rows.append((*classify(v["title"]), v["views"]))
        else:
            for h in json.load(open(IG_HISTORY)):
                views = (h.get("stats") or {}).get("views")
                if views is None:
                    continue
                k = h.get("key", "")
                parts = k.split(":")
                if h["kind"] == "ranking" and len(parts) == 2:
                    rows.append(("ranking", parts[0], parts[1], views))
                elif h["kind"] == "race" and parts[0] == "race" and len(parts) == 3:
                    rows.append(("race", parts[1], parts[2], views))
                else:
                    rows.append((*classify(h["title"]), views))
    except (OSError, ValueError, KeyError):
        return []
    return rows


def _mult(rows, col, overall):
    acc = {}
    for r in rows:
        if r[col] is not None:
            acc.setdefault(r[col], []).append(r[3])
    out = {}
    for k, vs in acc.items():
        n = len(vs)
        avg = (sum(vs) + PRIOR * overall) / (n + PRIOR)
        out[k] = max(0.4, min(3.0, avg / overall))
    return out


def _build():
    rows = [r for r in _rows() if r[3] > 0]
    if len(rows) < 8:
        return {}, {}, {}
    overall = sum(math.log(r[3]) for r in rows) / len(rows)
    overall = math.exp(overall)  # среднее по логарифму — один вирусный ролик не задирает «норму»
    topic = _mult(rows, 1, overall)
    group = _mult(rows, 2, overall)
    kind = _mult(rows, 0, overall)
    return topic, group, kind


_CACHE = []


def _get():
    if not _CACHE:  # лениво: make_batch сначала обновляет youtube_stats.json, потом выбирает темы
        _CACHE.append(_build())
    return _CACHE[0]


def topic(tid):
    return _get()[0].get(tid, 1.0)


def group(g):
    return _get()[1].get(g, 1.0)


def report():
    rows = _rows()
    print(f"{'YouTube' if YOUTUBE else 'Instagram'}: {len(rows)} роликов")
    for name, d in zip(("темы", "регионы", "форматы"), _get()):
        print(name + ":", ", ".join(f"{k} ×{v:.2f}" for k, v in sorted(d.items(), key=lambda i: -i[1])))


if __name__ == "__main__":
    report()
