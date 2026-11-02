"""Один запуск в GitHub Actions: выбрать следующий ролик (форматы чередуются) → отрендерить → опубликовать Reels.

Состояние (какие ролики уже вышли) хранится в data/used_cloud.json и коммитится обратно в репозиторий.
  python cloud_post.py            — сделать и опубликовать
  python cloud_post.py --dry-run  — только сделать ролик (проверка без публикации)
"""
import argparse, datetime, json, os, random, sys

from catalog import ACCENTS, BASE
from formats import next_item
import instagram

USED = os.path.join(BASE, "data", "used_cloud.json")
HISTORY = os.path.join(BASE, "data", "history_cloud.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    used = set(json.load(open(USED))) if os.path.exists(USED) else set()
    history = json.load(open(HISTORY)) if os.path.exists(HISTORY) else []
    n = len(history)
    rng = random.Random(n * 7919 + datetime.date.today().toordinal())
    item = next_item(n, used, rng, avoid={h["topic"] for h in history[-2:]})
    if not item:
        sys.exit("Ролики закончились — добавь темы в catalog.py")
    out = os.path.join(BASE, "work", f"{item['slug']}.mp4")
    item["render"](out, n, ACCENTS[n % len(ACCENTS)])
    print(f"ролик [{item['kind']}]: {out}\n{item['title']}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"video={out}\n")
    if args.dry_run:
        return

    m = {"path": out, "key": item["key"], "title": item["title"], "caption_tiktok_instagram": item["short"]}
    media_id = instagram.publish(instagram.conf(), m)
    used.add(item["key"])
    history.append({"kind": item["kind"], "topic": item["topic"], "key": item["key"], "title": item["title"],
                    "description": item["description"], "media_id": media_id,
                    "at": datetime.datetime.utcnow().isoformat() + "Z"})
    json.dump(sorted(used), open(USED, "w"), ensure_ascii=False, indent=0)
    json.dump(history, open(HISTORY, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
