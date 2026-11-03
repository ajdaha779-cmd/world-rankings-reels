"""Пора ли публиковать? Запускается каждый час (только стандартная библиотека — быстро).

Правило: в каждом окне последних 24 часов роликов должно быть столько, сколько «слотов» уже наступило.
Если GitHub пропустил запуск — следующий час догонит; между роликами не меньше MIN_GAP минут.
Сколько роликов в день — data/schedule.json → per_day.
"""
import datetime, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
MIN_GAP = 100  # минут между роликами
# время слотов по UTC (Баку = UTC+4); для каждого числа роликов в день — свой набор
SLOT_SETS = {
    1: ["18:07"],
    2: ["15:07", "00:07"],
    3: ["12:07", "18:07", "00:07"],
    4: ["12:07", "15:07", "18:07", "00:07"],
    5: ["03:07", "12:07", "15:07", "18:07", "00:07"],
    6: ["03:07", "12:07", "15:07", "18:07", "21:07", "00:07"],
}


def is_due(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    sched = json.load(open(os.path.join(BASE, "data", "schedule.json")))
    if sched.get("paused"):
        return False, "пауза в data/schedule.json"
    slots = SLOT_SETS[max(1, min(6, int(sched.get("per_day", 3))))]
    occ = []
    for back in (0, 1):
        day = (now - datetime.timedelta(days=back)).date()
        for s in slots:
            hh, mm = map(int, s.split(":"))
            t = datetime.datetime(day.year, day.month, day.day, hh, mm)
            if now - datetime.timedelta(hours=24) < t <= now:
                occ.append(t)
    hist_path = os.path.join(BASE, "data", "history_cloud.json")
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else []
    times = [datetime.datetime.fromisoformat(h["at"].rstrip("Z")) for h in hist if h.get("at")]
    recent = [t for t in times if now - t < datetime.timedelta(hours=24)]
    if len(recent) >= len(occ):
        return False, f"за сутки уже {len(recent)} из {len(occ)}"
    if times and (now - max(times)).total_seconds() < MIN_GAP * 60:
        return False, "прошло меньше 100 минут с прошлого ролика"
    return True, f"за сутки {len(recent)} из {len(occ)} — публикуем"


if __name__ == "__main__":
    due, why = is_due()
    print(why)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"due={'true' if due else 'false'}\n")
    sys.exit(0)
