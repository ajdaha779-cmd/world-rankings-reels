"""Недельная пачка роликов для ручной загрузки (YouTube / TikTok): форматы чередуются,
названия/описания и расписание публикаций пишутся рядом.

Запуск:  .venv/bin/python make_batch.py            — 14 роликов (2 в день на неделю)
         .venv/bin/python make_batch.py --count 3  — пробная пачка
"""
import argparse, datetime, json, os, random, shutil, subprocess, sys, time
from zoneinfo import ZoneInfo

from catalog import ACCENTS, BASE
from formats import next_item

USED = os.path.join(BASE, "data", "used_youtube.json")  # своя очередь тем: YouTube не зависит от Instagram
OUTBOX = os.path.join(BASE, "к-публикации")
LOCAL = ZoneInfo("Asia/Baku")
AUDIENCE = ZoneInfo("America/New_York")
POST_TIMES = ["13:00", "19:00"]  # по времени США (восток) — пик просмотров Shorts


def notify(msg):
    if not shutil.which("osascript"):  # не Mac (GitHub Actions)
        return
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Рейтинги"'], check=False)


def slots(count, start_date):
    out, day = [], start_date
    while len(out) < count:
        for hm in POST_TIMES:
            hh, mm = map(int, hm.split(":"))
            out.append(datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=AUDIENCE))
            if len(out) == count:
                break
        day += datetime.timedelta(days=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=14)
    args = ap.parse_args()

    used = set(json.load(open(USED))) if os.path.exists(USED) else set()
    today = datetime.date.today()
    rng = random.Random(today.toordinal())
    start = today + datetime.timedelta(days=1)
    folder = os.path.join(OUTBOX, f"{today:%Y-%m-%d}")
    os.makedirs(folder, exist_ok=True)
    plan, meta, recent = [], [], []
    for i, when in enumerate(slots(args.count, start)):
        item = next_item(i, used, rng, avoid=recent[-2:])
        if not item:
            notify("Темы закончились — нужно добавить новые в catalog.py")
            break
        fname = f"{i + 1:02d}_{item['slug']}.mp4"
        t0 = time.time()
        item["render"](os.path.join(folder, fname), i, ACCENTS[i % len(ACCENTS)])
        print(f"[{i + 1}/{args.count}] {item['kind']:7s} {fname}  {time.time() - t0:.0f}s", flush=True)
        used.add(item["key"])
        recent.append(item["topic"])
        json.dump(sorted(used), open(USED, "w"), ensure_ascii=False, indent=0)
        loc = when.astimezone(LOCAL)
        meta.append({"file": fname, "kind": item["kind"], "publish_us_east": when.isoformat(),
                     "publish_baku": loc.isoformat(), "title": item["title"], "description": item["description"],
                     "caption_tiktok_instagram": item["short"]})
        plan.append(f"── {i + 1:02d}. {fname}\n"
                    f"Публикация: {loc:%d.%m %A %H:%M} по Баку  (= {when:%H:%M} в Нью-Йорке)\n\n"
                    f"YouTube — название:\n{item['title']}\n\nYouTube — описание:\n{item['description']}\n\n"
                    f"TikTok / Instagram — подпись:\n{item['short']}\n")
    if not meta:
        sys.exit("нет свободных тем")
    json.dump(meta, open(os.path.join(folder, "metadata.json"), "w"), ensure_ascii=False, indent=2)
    with open(os.path.join(folder, "РАСПИСАНИЕ.txt"), "w") as f:
        f.write(f"Пачка от {today:%d.%m.%Y}: {len(meta)} роликов, публикация с {start:%d.%m}.\n"
                "Как выложить — см. ИНСТРУКЦИЯ.txt в папке проекта.\n\n" + "\n".join(plan))
    notify(f"Готово: {len(meta)} роликов")
    print(folder)


if __name__ == "__main__":
    main()
