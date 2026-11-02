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
        if iso in COUNTRIES and val is not None and int(row["date"]) >= min_year:
            out[iso] = (float(val), int(row["date"]))
    return out


def ranking(topic, group, top_n=15, min_n=8):
    """Список [(iso2, имя, значение, год)] или None, если данных мало."""
    vals = indicator(topic["ind"])
    members = [c for c in GROUPS[group][1] if c in vals]
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
