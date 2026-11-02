"""Недельная пачка роликов: выбор тем, рендер, названия/описания, расписание публикаций.

Запуск:  .venv/bin/python make_batch.py            — 14 роликов (2 в день на неделю)
         .venv/bin/python make_batch.py --count 3  — пробная пачка
"""
import argparse, datetime, json, os, random, subprocess, sys, time
from zoneinfo import ZoneInfo

from catalog import TOPICS, GROUPS, ACCENTS, BASE
from data import ranking
from render import render

USED = os.path.join(BASE, "data", "used.json")
OUTBOX = os.path.join(BASE, "к-публикации")
LOCAL = ZoneInfo("Asia/Baku")
AUDIENCE = ZoneInfo("America/New_York")
POST_TIMES = ["13:00", "19:00"]  # по времени США (восток) — пик просмотров Shorts
BASE_TAGS = "#shorts #countries #geography #comparison #data #ranking"


def notify(msg):
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Рейтинги"'], check=False)


def pick(count, used, rng):
    combos = [(t, g) for t in TOPICS for g in GROUPS if f"{t['id']}:{g}" not in used]
    rng.shuffle(combos)
    chosen, topics_seen, groups_seen = [], set(), {}
    # в одной пачке тема не повторяется, группа — не больше двух раз
    for strict in (True, False):
        for t, g in combos:
            if len(chosen) >= count:
                break
            key = f"{t['id']}:{g}"
            if any(key == c[2] for c in chosen):
                continue
            if strict and (t["id"] in topics_seen or groups_seen.get(g, 0) >= 2):
                continue
            rows = ranking(t, g)
            if not rows:
                used.add(key)  # данных мало — больше не пробуем
                continue
            chosen.append((t, g, key, rows))
            topics_seen.add(t["id"])
            groups_seen[g] = groups_seen.get(g, 0) + 1
    return chosen


def slots(count, start_date):
    out, day = [], start_date
    while len(out) < count:
        for hm in POST_TIMES:
            hh, mm = map(int, hm.split(":"))
            us = datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=AUDIENCE)
            out.append(us)
            if len(out) == count:
                break
        day += datetime.timedelta(days=1)
    return out


def caption(t, gname, rows):
    where = f"among {gname}" if "countries" in gname else f"in {gname}"
    q = t["question"].format(g=where)
    tags = BASE_TAGS + " " + " ".join("#" + x for x in t["tags"].split())
    years = sorted({r[3] for r in rows})
    yrs = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
    title = f"{q} 🌍"
    desc = (f"{t['sub']} — top {len(rows)} in {gname}.\n"
            f"Source: World Bank Open Data (latest available: {yrs}).\n\n"
            f"Is your country on the list? What should we compare next? Comment below 👇\n\n{tags}")
    short = f"{q} 🌍 Where is your country? 👇\n\n{tags}"
    return title, desc, short


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=14)
    args = ap.parse_args()

    used = set(json.load(open(USED))) if os.path.exists(USED) else set()
    today = datetime.date.today()
    rng = random.Random(today.toordinal())
    chosen = pick(args.count, used, rng)
    if not chosen:
        notify("Темы закончились — нужно добавить новые в catalog.py")
        sys.exit("нет свободных тем")

    start = today + datetime.timedelta(days=1)
    folder = os.path.join(OUTBOX, f"{today:%Y-%m-%d}")
    os.makedirs(folder, exist_ok=True)
    plan, meta = [], []
    for i, ((t, g, key, rows), when) in enumerate(zip(chosen, slots(len(chosen), start))):
        gname = GROUPS[g][0]
        fname = f"{i + 1:02d}_{t['id']}_{g}.mp4"
        t0 = time.time()
        render(rows, t, gname, ACCENTS[i % len(ACCENTS)], os.path.join(folder, fname), seed=i)
        print(f"[{i + 1}/{len(chosen)}] {fname}  {time.time() - t0:.0f}s", flush=True)
        used.add(key)
        json.dump(sorted(used), open(USED, "w"), ensure_ascii=False, indent=0)
        title, desc, short = caption(t, gname, rows)
        loc = when.astimezone(LOCAL)
        meta.append({"file": fname, "publish_us_east": when.isoformat(), "publish_baku": loc.isoformat(),
                     "title": title, "description": desc, "caption_tiktok_instagram": short})
        plan.append(f"── {i + 1:02d}. {fname}\n"
                    f"Публикация: {loc:%d.%m %A %H:%M} по Баку  (= {when:%H:%M} в Нью-Йорке)\n\n"
                    f"YouTube — название:\n{title}\n\nYouTube — описание:\n{desc}\n\n"
                    f"TikTok / Instagram — подпись:\n{short}\n")

    json.dump(meta, open(os.path.join(folder, "metadata.json"), "w"), ensure_ascii=False, indent=2)
    with open(os.path.join(folder, "РАСПИСАНИЕ.txt"), "w") as f:
        f.write(f"Пачка от {today:%d.%m.%Y}: {len(chosen)} роликов, публикация с {start:%d.%m}.\n"
                "Как выложить — см. ИНСТРУКЦИЯ.txt в папке проекта.\n\n" + "\n".join(plan))
    left = len(TOPICS) * len(GROUPS) - len(used)
    notify(f"Готово: {len(chosen)} роликов. Свободных тем осталось ~{left}")
    print(folder)


if __name__ == "__main__":
    main()
