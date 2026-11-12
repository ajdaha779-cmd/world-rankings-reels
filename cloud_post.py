"""Один запуск в GitHub Actions:
  1. статистика прошлых роликов → веса форматов (канал делает больше того, что лучше смотрят);
  2. комментарии → заказы дуэлей от зрителей («Azerbaijan vs Turkey!»);
  3. выбор и рендер ролика → Reels → Stories → первый комментарий → ответ заказчикам.

Состояние хранится в data/*.json и коммитится обратно в репозиторий.
  python cloud_post.py            — сделать и опубликовать
  python cloud_post.py --dry-run  — только сделать ролик (проверка без публикации)
"""
import argparse, datetime, json, os, random, sys

from catalog import ACCENTS, BASE
from formats import next_item, pick_kind, make_duel, next_neutral
import instagram, insights, requests_q, analyze, replies
import render, race, duel, twists, tournament, fans

USED = os.path.join(BASE, "data", "used_cloud.json")
HISTORY = os.path.join(BASE, "data", "history_cloud.json")
QUEUE = os.path.join(BASE, "data", "requests.json")
FIRST_COMMENT = {"duel": "Which 2 countries should battle next? Comment below ⚔️👇",
                 "default": "Drop your country's flag 👇 Every comment = +1 point for your country on our Fan Table 🏆 Top fans appear in the next video!"}


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def save(path, obj, indent=1):
    json.dump(obj, open(path, "w"), ensure_ascii=False, indent=indent)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    used = set(load(USED, []))
    history = load(HISTORY, [])
    queue = load(QUEUE, {})
    n = len(history)
    rng = random.Random(n * 7919 + datetime.date.today().toordinal())
    conf = instagram.conf() if (os.environ.get("IG_TOKEN") or os.path.exists(instagram.CONF)) else None

    weights = None
    if conf:
        analyze.run(conf, history, save=False)  # разбор каждого ролика → лог и data/АНАЛИЗ.md
        if any(h.get("stats") for h in history):
            weights = insights.kind_weights(history)
            print(f"веса форматов по статистике: {weights}")
        requests_q.collect(conf, history, queue)

    kind = pick_kind(n, weights, [h.get("kind") for h in history[-2:]], rng)
    item, req = None, None
    cup = tournament.load()
    if conf:  # турнир: итоги голосования под прошлым матчем и, если пора, следующий матч — вне очереди
        try:
            tournament.tally(conf, cup)
            m = tournament.next_match(cup)
            item = tournament.make_item(cup, m) if m else None
        except Exception as e:
            print(f"турнир пропущен: {str(e)[:200]}")
            item = None
    fan = fans.load()
    if conf:  # очки стран за комментарии и ники для строки «Thanks for commenting»
        try:
            me = instagram.http("GET", f"{conf['api']}/{conf['user_id']}", {"fields": "username", "access_token": conf["token"]})
            fans.collect(conf, fan, history, me.get("username"))
            render.SHOUTS = fans.shoutouts(fan, 4)
            if not item and fans.due(fan):
                item = fans.make_item(fan)
        except Exception as e:
            print(f"фанаты пропущены: {str(e)[:200]}")
    if kind == "duel" and not item:
        req = requests_q.top_request(queue, used)
        if req:
            item = make_duel(req["a"], req["b"], by=req["users"])
            print(f"дуэль по заказу зрителей ({req['votes']} голосов)")
    if kind == "duel" and not item and rng.random() < 0.5:
        item = next_neutral(used, history)  # редко и нейтрально: пары с идущим конфликтом
    item = item or next_item(n, used, rng, avoid={h["topic"] for h in history[-2:]}, kind=kind)
    if not item:
        sys.exit("Ролики закончились — добавь темы в catalog.py")

    out = os.path.join(BASE, "work", f"{item['slug']}.mp4")
    item["render"](out, n, ACCENTS[n % len(ACCENTS)])
    timeline = {"ranking": render, "race": race, "duel": duel, "twist": twists, "fans": fans}[item["kind"]].LAST
    print(f"ролик [{item['kind']}]: {out}\n{item['title']}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"video={out}\n")
    if args.dry_run:
        return

    m = {"path": out, "key": item["key"], "title": item["title"], "caption_tiktok_instagram": item["short"]}
    media_id = instagram.publish(conf, m)
    story_id = None
    try:
        story_id = instagram.publish_story(conf, out)
    except Exception as e:  # история — бонус, Reels уже вышел
        print(f"история не опубликована: {str(e)[:200]}")
    if item.get("neutral"):
        requests_q.first_comment(conf, media_id, "Data only — no winners here. Please keep it respectful 🙏")
    else:
        requests_q.first_comment(conf, media_id, item.get("first_comment") or FIRST_COMMENT.get(item["kind"], FIRST_COMMENT["default"]))
    if req:
        requests_q.reply_all(conf, req, "Your battle is out! Check our latest reel 🔥⚔️")

    if item.get("cup_match"):
        tournament.posted(cup, item["cup_match"], media_id, datetime.datetime.utcnow().isoformat() + "Z")
    tournament.save(cup)
    if item["kind"] == "fans":
        fans.posted(fan, datetime.datetime.utcnow().isoformat() + "Z")
    fans.save(fan)
    used.add(item["key"])
    history.append({"kind": item["kind"], "topic": item["topic"], "key": item["key"], "title": item["title"],
                    "description": item["description"], "media_id": media_id, "story_id": story_id,
                    "requested": bool(req), "dur": timeline.get("dur"), "moments": timeline.get("moments"),
                    "at": datetime.datetime.utcnow().isoformat() + "Z"})
    save(USED, sorted(used), indent=0)
    save(HISTORY, history)
    save(QUEUE, queue)
    try:
        replies.run(conf, history, queue)
    except Exception as e:
        print(f"ответы на комментарии не отправлены: {e}")
    try:
        analyze.run(conf, history, save=True)
    except Exception as e:
        print(f"отчёт не обновлён: {e}")


if __name__ == "__main__":
    main()
