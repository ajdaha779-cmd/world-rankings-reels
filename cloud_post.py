"""Один запуск в GitHub Actions: выбрать тему → отрендерить ролик → опубликовать Reels.

Состояние (какие темы уже вышли) хранится в data/used_cloud.json и коммитится обратно в репозиторий.
  python cloud_post.py            — сделать и опубликовать
  python cloud_post.py --dry-run  — только сделать ролик (проверка без публикации)
"""
import argparse, datetime, json, os, random, sys

from catalog import GROUPS, ACCENTS, BASE
from make_batch import pick, caption
from render import render
import instagram

USED = os.path.join(BASE, "data", "used_cloud.json")
HISTORY = os.path.join(BASE, "data", "history_cloud.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    used = set(json.load(open(USED))) if os.path.exists(USED) else set()
    history = json.load(open(HISTORY)) if os.path.exists(HISTORY) else []
    rng = random.Random(len(used) * 7919 + datetime.date.today().toordinal())
    # не повторяем тему двух последних роликов
    recent = {h["topic"] for h in history[-2:]}
    chosen = [c for c in pick(6, used, rng) if c[0]["id"] not in recent] or pick(1, used, rng)
    if not chosen:
        sys.exit("Темы закончились — добавь новые в catalog.py")
    t, g, key, rows = chosen[0]
    gname = GROUPS[g][0]
    out = os.path.join(BASE, "work", f"{t['id']}_{g}.mp4")
    render(rows, t, gname, ACCENTS[len(used) % len(ACCENTS)], out, seed=len(used))
    title, desc, short = caption(t, gname, rows)
    print(f"ролик: {out}\n{title}")
    # имя файла для шага загрузки артефакта
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"video={out}\n")
    if args.dry_run:
        return

    m = {"path": out, "key": key, "title": title, "caption_tiktok_instagram": short}
    media_id = instagram.publish(instagram.conf(), m)
    used.add(key)
    history.append({"topic": t["id"], "group": g, "title": title, "description": desc,
                    "media_id": media_id, "at": datetime.datetime.utcnow().isoformat() + "Z"})
    json.dump(sorted(used), open(USED, "w"), ensure_ascii=False, indent=0)
    json.dump(history, open(HISTORY, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
