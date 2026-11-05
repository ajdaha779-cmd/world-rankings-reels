"""Ответ каждому зрителю, назвавшему страну: «🇦🇿 Azerbaijan: #54 of 189 in the world · $7,155».

Ролик просит «напиши флаг своей страны — ответим её местом». Ответ — настоящая цифра Всемирного банка
по теме именно этого ролика. Персональный ответ → человек пишет ещё → Instagram видит живое обсуждение.
Запускается каждый час (даже когда ролик не выходит), чтобы отвечать быстро.

  python replies.py
"""
import json, os
import instagram, requests_q
from catalog import BASE, COUNTRIES, EXCLUDE, GROUPS, TOPICS, RACE_TOPICS, FMT, flag_emoji
from data import indicator

HISTORY = os.path.join(BASE, "data", "history_cloud.json")
QUEUE = os.path.join(BASE, "data", "requests.json")
MAX_PER_RUN = 40  # не больше — чтобы не выглядеть спам-ботом


def _topic(h):
    """(тема, группа, порядок) ролика по ключу истории: «rich:world», «race:pop:asia»."""
    parts = h["key"].split(":")
    if parts[0] == "race":
        t = next((t for t in RACE_TOPICS if t["id"] == parts[1]), None)
        return (t, parts[2], "desc") if t else None
    t = next((t for t in TOPICS if t["id"] == parts[0]), None)
    return (t, parts[1], t["order"]) if t else None


def rank_line(h, iso):
    """Строка ответа с местом страны по теме ролика или None, если данных нет."""
    tg = _topic(h)
    if not tg:
        return None
    t, g, order = tg
    vals = {c: v for c, v in indicator(t["ind"]).items() if c not in EXCLUDE}
    if iso not in vals:
        return None
    members = [c for c in GROUPS[g][1] if c in vals] if iso in GROUPS[g][1] else list(vals)
    gname = GROUPS[g][0] if iso in GROUPS[g][1] else "the world"
    where = f"among {gname}" if "countries" in gname else f"in {gname}"
    ranked = sorted(members, key=lambda c: vals[c][0], reverse=(order == "desc"))
    val, year = vals[iso]
    return (f"{flag_emoji(iso)} {COUNTRIES[iso]}: #{ranked.index(iso) + 1} of {len(ranked)} {where} · "
            f"{FMT[t['fmt']](val)} ({t['sub']}, World Bank {year})")


def reply_text(h, cs):
    if len(cs) >= 2 and frozenset(cs[:2]) in requests_q.BLOCKED:
        return None  # пары с конфликтами не обсуждаем
    if h.get("kind") == "duel" or len(cs) >= 2:
        names = " vs ".join(COUNTRIES[c] for c in cs[:2])
        return f"Added to our battle list: {names} ⚔️ The more votes, the sooner it's out!" if len(cs) >= 2 else \
            f"{flag_emoji(cs[0])} Nice! Which country should {COUNTRIES[cs[0]]} battle next? 👀"
    line = rank_line(h, cs[0])
    return f"{line} 👀 Surprised?" if line else None


def run(c=None, history=None, queue=None):
    c = c or instagram.conf()
    history = history if history is not None else json.load(open(HISTORY))
    queue = queue if queue is not None else (json.load(open(QUEUE)) if os.path.exists(QUEUE) else {})
    replied = set(queue.get("replied", []))
    me = instagram.http("GET", f"{c['api']}/{c['user_id']}", {"fields": "username", "access_token": c["token"]})
    me = me.get("username")
    sent = 0
    for h in reversed(history[-20:]):
        if not h.get("media_id") or sent >= MAX_PER_RUN:
            continue
        try:
            r = instagram.http("GET", f"{c['api']}/{h['media_id']}/comments",
                               {"fields": "id,text,username", "limit": 100, "access_token": c["token"]})
        except Exception as e:
            print(f"комментарии недоступны: {str(e)[:160]}")
            break
        for cm in r.get("data", []):
            if cm["id"] in replied or cm.get("username") == me or sent >= MAX_PER_RUN:
                continue
            replied.add(cm["id"])
            cs = requests_q.countries_in(cm.get("text", ""))
            text = reply_text(h, cs) if cs else None
            if not text:
                continue
            try:
                instagram.http("POST", f"{c['api']}/{cm['id']}/replies", {"message": text, "access_token": c["token"]})
                sent += 1
                print(f"ответ @{cm.get('username')}: {text}")
            except Exception as e:
                print(f"ответ не отправлен: {str(e)[:160]}")
    queue["replied"] = sorted(replied)[-5000:]
    json.dump(queue, open(QUEUE, "w"), ensure_ascii=False, indent=1)
    print(f"ответов: {sent}")
    return queue


if __name__ == "__main__":
    run()
