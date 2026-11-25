"""Заказы зрителей YouTube «A vs B» (25.11, пользователь: «а по ютубу комментарии и просьбы»).

yt_replies.py складывает сюда пары из комментариев, make_batch.py --daily делает по самому популярному
заказу первый ролик дня, а после выхода ролика yt_replies.py отвечает заказчикам ссылкой.
  data/yt_requests.json = {"pairs": {"JP-PK": {"a", "b", "votes", "users", "comments", "video", "at", "notified"}}}
"""
import datetime, json, os

from catalog import BASE

PATH = os.path.join(BASE, "data", "yt_requests.json")


def load():
    return json.load(open(PATH)) if os.path.exists(PATH) else {"pairs": {}}


def save(q):
    json.dump(q, open(PATH, "w"), ensure_ascii=False, indent=1)


def add(q, a, b, user, comment_id):
    """Новый голос за пару; True — если пара новая или этот зритель её ещё не просил."""
    key = "-".join(sorted((a, b)))
    p = q["pairs"].setdefault(key, {"a": a, "b": b, "votes": 0, "users": [], "comments": []})
    if comment_id in p["comments"]:
        return False
    p["comments"].append(comment_id)
    if user and user in p["users"]:
        return False
    p["votes"] += 1
    if user:
        p["users"].append(user)
    return True


def status(q, a, b):
    return q["pairs"].get("-".join(sorted((a, b))), {})


def top(used):
    q = load()
    open_ = [p for k, p in q["pairs"].items() if "video" not in p
             and f"h2h:{k}" not in used and f"duel:{k}" not in used]
    return max(open_, key=lambda p: (p["votes"], -len(p["comments"]))) if open_ else None


def mark(req, video_id, at_utc):
    """Ролик по заказу загружен (или сделать его нельзя — video None)."""
    q = load()
    p = q["pairs"].setdefault("-".join(sorted((req["a"], req["b"]))), req)
    p["video"], p["at"] = video_id, at_utc
    save(q)


def due_notifications(q):
    """Пары, чей ролик уже вышел, а заказчикам ещё не ответили."""
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:00Z")
    return [p for p in q["pairs"].values() if p.get("video") and not p.get("notified") and p.get("at", "") <= now]
