"""Загрузка данных Всемирного банка с кэшем на неделю."""
import json, os, ssl, time, datetime, urllib.request
import certifi
from catalog import COUNTRIES, GROUPS, BASE

CACHE = os.path.join(BASE, "data", "cache")
os.makedirs(CACHE, exist_ok=True)
MAX_AGE_YEARS = 6
SSL = ssl.create_default_context(cafile=certifi.where())


def indicator(ind):
    """{iso2: (value, year)} — последнее непустое значение по каждой стране."""
    path = os.path.join(CACHE, f"{ind}.json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 6 * 86400:
        url = f"https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&mrnev=1&per_page=20000"
        raw = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=60, context=SSL) as r:
                    raw = json.load(r)
                break
            except Exception:
                time.sleep(5)
        if raw is not None:
            json.dump(raw, open(path, "w"))
        elif not os.path.exists(path):  # нет сети и нет старого кэша
            raise RuntimeError(f"World Bank API недоступен: {ind}")
    raw = json.load(open(path))
    min_year = datetime.date.today().year - MAX_AGE_YEARS
    out = {}
    for row in raw[1] or []:
        iso, val = row["country"]["id"], row["value"]
        # API иногда отдаёт все годы, а не только последний — берём самый свежий (12.11: была безработица за 2020 г.)
        if iso in COUNTRIES and val is not None and int(row["date"]) >= min_year and int(row["date"]) > out.get(iso, (0, 0))[1]:
            out[iso] = (float(val), int(row["date"]))
    return out


SMALL_NOISY = {"danger", "safe", "womendanger", "womensafe"}


def ranking(topic, group, top_n=15, min_n=8):
    """Список [(iso2, имя, значение, год)] или None, если данных мало."""
    vals = indicator(topic["ind"])
    members = [c for c in GROUPS[group][1] if c in vals]
    if topic["id"] in SMALL_NOISY:  # 23.11: на 100 тыс. жителей — в крошечных странах 1 случай = скачок (Лихтенштейн)
        pop = indicator("SP.POP.TOTL")
        members = [c for c in members if pop.get(c, (0,))[0] >= 1e6]
    if len(members) < min_n:
        return None
    rows = sorted(members, key=lambda c: vals[c][0], reverse=topic["order"] == "desc")
    if topic["id"] == "moveout":
        rows = [c for c in rows if vals[c][0] < 0]
    elif topic["id"] == "movein":
        rows = [c for c in rows if vals[c][0] > 0]
    if len(rows) < min_n:
        return None
    return [(c, COUNTRIES[c], vals[c][0], vals[c][1]) for c in rows[:top_n]]


def history(ind):
    """{iso2: {год: значение}} — вся история с 1960 г. (для гонки графиков)."""
    path = os.path.join(CACHE, f"hist_{ind}.json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 6 * 86400:
        url = f"https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&date=1960:2030&per_page=30000"
        raw = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=120, context=SSL) as r:
                    raw = json.load(r)
                break
            except Exception:
                time.sleep(5)
        if raw is not None:
            json.dump(raw, open(path, "w"))
        elif not os.path.exists(path):
            raise RuntimeError(f"World Bank API недоступен: {ind}")
    raw = json.load(open(path))
    out = {}
    for row in raw[1] or []:
        iso, val = row["country"]["id"], row["value"]
        if iso in COUNTRIES and val is not None:
            out.setdefault(iso, {})[int(row["date"])] = float(val)
    return out


def race_frames(ind, group, top_n=10, min_countries=12, min_pop=0):
    """Ряды для гонки: (годы, {iso: [значение по годам]}) с заполнением пропусков. None — если данных мало.
    min_pop — без крошечных стран (20.11: в «most dangerous» лезли Сент-Китс, Доминика — шум малых чисел)."""
    h = history(ind)
    members = [c for c in GROUPS[group][1] if c in h and len(h[c]) >= 5]
    if min_pop:
        pop = indicator("SP.POP.TOTL")
        members = [c for c in members if pop.get(c, (0,))[0] >= min_pop]
    if len(members) < min_countries:
        return None
    years_all = sorted({y for c in members for y in h[c]})
    # начинаем с года, когда данные есть хотя бы у 70% стран
    start = next(y for y in years_all if sum(1 for c in members if min(h[c]) <= y) >= 0.7 * len(members))
    end = max(y for y in years_all if sum(1 for c in members if y in h[c]) >= 0.6 * len(members))
    years = list(range(start, end + 1))
    series = {}
    for c in members:
        pts = sorted(h[c].items())
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        import numpy as _np
        vals = _np.interp(years, xs, ys, left=_np.nan, right=ys[-1])
        series[c] = [None if _np.isnan(v) else float(v) for v in vals]
    # оставляем только тех, кто хоть раз был в топе — остальные не появятся на экране
    ever = set()
    for i in range(len(years)):
        ranked = sorted((c for c in series if series[c][i] is not None), key=lambda c: -series[c][i])
        ever.update(ranked[:top_n + 2])
    return years, {c: series[c] for c in ever}


def leader_changes(years, series):
    """Сколько раз сменился лидер гонки. Гонка без смены #1 скучная (Америки по ВВП: 72% пролистали)."""
    lead, n = None, 0
    for i in range(len(years)):
        cur = max((c for c in series if series[c][i] is not None), key=lambda c: series[c][i], default=None)
        if cur != lead:
            n += lead is not None
            lead = cur
    return n
