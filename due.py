"""Пора ли публиковать? Запускается каждый час в «эфирное» время (только стандартная библиотека — быстро).

Каждый день — свой случайный план: N разных часов в эфирном окне, промежутки между роликами
всегда разные. Внутри часа — ещё случайная задержка 0–8 минут (плюс собственный разброс запуска GitHub),
поэтому время выходит «живым»: 15:24, 17:51, 21:09...
Если GitHub пропустил запуск — следующий час догонит. Сколько роликов в день — data/schedule.json → per_day.
"""
import datetime, json, os, random, sys

BASE = os.path.dirname(os.path.abspath(__file__))
MIN_GAP = 85          # минут между роликами, не меньше
DAY_START_UTC = 11    # «эфирные сутки» начинаются в 11:00 UTC (15:00 по Баку)
WINDOW = 20           # часов в эфирном окне: 15:00–10:59 по Баку
# 23.11: по статистике лучше всего заходят ролики, выложенные утром по Баку (06–11: медиана 245–281, пролистали 56%),
# хуже — ночью (00–05) и днём (15–17): ~180, 63%. При 2 роликах в день — один утром, один вечером (20–23, медиана ~209).
PREFERRED = [[15, 16, 17, 18, 19], [5, 6, 7, 8]]  # смещения от 15:00 Баку: 06–10 утра и 20–23 вечера
MAX_SLEEP = 8 * 60    # случайная задержка внутри часа, секунд
MAP_HOUR = 6          # ролик-карта — раз в сутки СВЕРХ основных, с 17:00 UTC (21:00 по Баку) и позже


def day_start(now):
    start = now.replace(hour=DAY_START_UTC, minute=0, second=0, microsecond=0)
    return start if now >= start else start - datetime.timedelta(days=1)


def plan(start, per_day):
    """Случайные часы публикаций на эти сутки (одинаковые для всех запусков в течение суток)."""
    rng = random.Random(f"plan-{start:%Y-%m-%d}-{per_day}")
    if per_day <= len(PREFERRED):
        hours = sorted(rng.choice(PREFERRED[i]) for i in range(per_day))
        return [start + datetime.timedelta(hours=h, minutes=17) for h in hours]
    for _ in range(200):  # ищем раскладку, где соседние ролики не ближе 2 часов
        hours = sorted(rng.sample(range(WINDOW), per_day))
        if all(b - a >= 2 for a, b in zip(hours, hours[1:])):
            break
    return [start + datetime.timedelta(hours=h, minutes=17) for h in hours]


def map_due(now, start, hist, times):
    """Карта: раз в сутки, после MAP_HOUR, если есть люди, которых ещё не показывали (data/fans.json)."""
    if now < start + datetime.timedelta(hours=MAP_HOUR):
        return False
    if any(h.get("kind") == "map" and datetime.datetime.fromisoformat(h["at"].rstrip("Z")) >= start for h in hist if h.get("at")):
        return False
    if times and (now - max(times)).total_seconds() < MIN_GAP * 60:
        return False
    path = os.path.join(BASE, "data", "fans.json")
    st = json.load(open(path)) if os.path.exists(path) else {}
    shown, lit_shown = set(st.get("fans_shown", [])), set(st.get("lit_shown", []))
    return any(c not in lit_shown or any(f"{c}:{u}" not in shown for u in e.get("fans", []))
               for c, e in st.get("lit", {}).items())


def is_due(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    sched = json.load(open(os.path.join(BASE, "data", "schedule.json")))
    if sched.get("paused"):
        return False, "пауза в data/schedule.json", 0
    per_day = max(1, min(8, int(sched.get("per_day", 3))))
    start = day_start(now)
    slots = plan(start, per_day)
    passed = [s for s in slots if s <= now + datetime.timedelta(minutes=5)]
    hist_path = os.path.join(BASE, "data", "history_cloud.json")
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else []
    times = [datetime.datetime.fromisoformat(h["at"].rstrip("Z")) for h in hist if h.get("at")]
    today = [datetime.datetime.fromisoformat(h["at"].rstrip("Z")) for h in hist
             if h.get("at") and h.get("kind") != "map" and datetime.datetime.fromisoformat(h["at"].rstrip("Z")) >= start]
    nice = ", ".join(f"{(s + datetime.timedelta(hours=4)):%H:%M}" for s in slots)
    if len(today) >= len(passed):
        if map_due(now, start, hist, times):
            return True, "ролик-карта (сверх основных)", random.randint(0, MAX_SLEEP), "map"
        return False, f"сегодня {len(today)} из {per_day}; план по Баку ≈ {nice}", 0
    if times and (now - max(times)).total_seconds() < MIN_GAP * 60:
        return False, "с прошлого ролика прошло слишком мало времени", 0
    return True, f"публикуем ({len(today) + 1} из {per_day}); план по Баку ≈ {nice}", random.randint(0, MAX_SLEEP), "main"


if __name__ == "__main__":
    due, why, sleep, *mode = is_due()
    print(why + (f"; ждём ещё {sleep // 60} мин {sleep % 60} с" if due else ""))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"due={'true' if due else 'false'}\nsleep={sleep}\nmode={mode[0] if mode else 'main'}\n")
    sys.exit(0)
