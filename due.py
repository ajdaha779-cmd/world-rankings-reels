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
WINDOW = 16           # часов в эфирном окне: 15:00–06:59 по Баку — день Европы и США
MAX_SLEEP = 8 * 60    # случайная задержка внутри часа, секунд


def day_start(now):
    start = now.replace(hour=DAY_START_UTC, minute=0, second=0, microsecond=0)
    return start if now >= start else start - datetime.timedelta(days=1)


def plan(start, per_day):
    """Случайные часы публикаций на эти сутки (одинаковые для всех запусков в течение суток)."""
    rng = random.Random(f"plan-{start:%Y-%m-%d}-{per_day}")
    for _ in range(200):  # ищем раскладку, где соседние ролики не ближе 2 часов
        hours = sorted(rng.sample(range(WINDOW), per_day))
        if all(b - a >= 2 for a, b in zip(hours, hours[1:])):
            break
    return [start + datetime.timedelta(hours=h, minutes=17) for h in hours]


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
    today = [t for t in times if t >= start]
    nice = ", ".join(f"{(s + datetime.timedelta(hours=4)):%H:%M}" for s in slots)
    if len(today) >= len(passed):
        return False, f"сегодня {len(today)} из {per_day}; план по Баку ≈ {nice}", 0
    if times and (now - max(times)).total_seconds() < MIN_GAP * 60:
        return False, "с прошлого ролика прошло слишком мало времени", 0
    return True, f"публикуем ({len(today) + 1} из {per_day}); план по Баку ≈ {nice}", random.randint(0, MAX_SLEEP)


if __name__ == "__main__":
    due, why, sleep = is_due()
    print(why + (f"; ждём ещё {sleep // 60} мин {sleep % 60} с" if due else ""))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"due={'true' if due else 'false'}\nsleep={sleep}\n")
    sys.exit(0)
