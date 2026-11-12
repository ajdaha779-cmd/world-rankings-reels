"""Ответ каждому зрителю, назвавшему страну: «🇦🇿 Azerbaijan: #54 of 189 in the world · $7,155».

Ролик просит «напиши флаг своей страны — ответим её местом». Ответ — настоящая цифра Всемирного банка
по теме именно этого ролика. Персональный ответ → человек пишет ещё → Instagram видит живое обсуждение.
Запускается каждый час (даже когда ролик не выходит), чтобы отвечать быстро.

  python replies.py
"""
import json, os, random
import instagram, requests_q
from catalog import BASE, COUNTRIES, EXCLUDE, GROUPS, TOPICS, RACE_TOPICS, FMT, flag_emoji
from data import indicator

HISTORY = os.path.join(BASE, "data", "history_cloud.json")
QUEUE = os.path.join(BASE, "data", "requests.json")
MAX_PER_RUN = 40  # не больше — чтобы не выглядеть спам-ботом


def _topic(h):
    """(тема, группа, порядок) ролика по ключу истории: «rich:world», «race:pop:asia»."""
    parts = h.get("key", "").split(":")
    if parts[0] == "race":
        t = next((t for t in RACE_TOPICS if t["id"] == parts[1]), None)
        return (t, parts[2], "desc") if t else None
    t = next((t for t in TOPICS if t["id"] == parts[0]), None)
    return (t, parts[1], t["order"]) if t else None


def _human(fmt, v):
    """Число как в разговоре: «144 million», «$7,411», «73%»."""
    if fmt in ("people", "signed"):
        sign = "+" if fmt == "signed" and v > 0 else ""
        a = abs(v)
        s = f"{a / 1e9:.1f} billion" if a >= 1e9 else f"{a / 1e6:.1f} million" if a >= 1e6 else \
            f"{a / 1e3:.0f} thousand" if a >= 1e4 else f"{a:,.0f}"
        return sign + ("-" if v < 0 else "") + s.replace(".0 ", " ")
    if fmt == "money":
        return f"${v:,.0f}" if v < 1e9 else f"${v / 1e9:,.0f} billion" if v < 1e12 else f"${v / 1e12:.1f} trillion"
    if fmt == "years":
        return f"{v:.0f} years"
    return FMT[fmt](v)


def _ord(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


REGIONS = ["europe", "asia", "americas", "africa", "mideast"]


def rank_info(h, iso):
    """Место страны по теме ролика: в группе ролика или (если её там нет) в мире."""
    tg = _topic(h)
    if not tg:
        return None
    t, g, order = tg
    vals = {c: v for c, v in indicator(t["ind"]).items() if c not in EXCLUDE}
    if iso not in vals:
        return None
    in_group = iso in GROUPS[g][1]
    members = [c for c in GROUPS[g][1] if c in vals] if in_group else list(vals)
    ranked = sorted(members, key=lambda c: vals[c][0], reverse=(order == "desc"))
    home = next((GROUPS[r][0] for r in REGIONS if iso in GROUPS[r][1]), None)
    return dict(rank=ranked.index(iso) + 1, total=len(ranked), where=GROUPS[g][0] if in_group else "the world",
                group=GROUPS[g][0], in_group=in_group, home=home, value=_human(t["fmt"], vals[iso][0]),
                topic=t["sub"].split(" (")[0].lower(), shown=in_group and ranked.index(iso) < 10, group_id=g)


OPENERS = ["", "", "Good question! ", "Ooh, ", "Let me check… ", "Great one! "]
ENDINGS = ["", " Surprised?", " Did you expect higher?", " Is that what you guessed?", " Is that your country? 🙂",
           " Not bad at all!", " 👀"]


def rank_line(h, iso, user=None, salt=0):
    """Живой ответ про место страны: разные формулировки, без «отчёта» в скобках."""
    r = rank_info(h, iso)
    if not r:
        return None
    rnd = random.Random(f"{iso}{salt}")
    name, fl = COUNTRIES[iso], flag_emoji(iso)
    if r["shown"]:
        body = rnd.choice([f"{name} is {_ord(r['rank'])} in {r['where']} — it's right there in the video {fl}",
                           f"{fl} {name} made the top 10 — {_ord(r['rank'])} in {r['where']} with {r['value']}!"])
    elif not r["in_group"] and r["home"] and r["group_id"] in REGIONS:
        home = r["home"].replace("the ", "")
        body = rnd.choice([
            f"we count {name} as part of {r['home']}, so it's not in this list 😉 In the whole world it's "
            f"{_ord(r['rank'])} with {r['value']} {fl}",
            f"{name} {fl} is {_ord(r['rank'])} in the world with {r['value']} — it's in our {home} group, "
            f"that's why it's not here"])
    elif not r["in_group"]:
        body = rnd.choice([f"{name} isn't in {r['group']}, but in the whole world it's {_ord(r['rank'])} with "
                           f"{r['value']} {fl}",
                           f"{fl} {name} is {_ord(r['rank'])} in the world — {r['value']}"])
    else:
        body = rnd.choice([f"{name} {fl} is {_ord(r['rank'])} out of {r['total']} in {r['where']} with {r['value']}",
                           f"{fl} {name} comes {_ord(r['rank'])} in {r['where']} — {r['value']}",
                           f"{name} is number {r['rank']} in {r['where']} {fl} ({r['value']})"])
    good = r["rank"] <= max(3, r["total"] // 3)
    end = rnd.choice([e for e in ENDINGS if good or "Not bad" not in e])
    if end.strip() and end.strip() != "👀" and body[-1].isalnum():
        body += "."
    body = body[0].upper() + body[1:]
    text = rnd.choice(OPENERS) + body + end
    return f"@{user} {text}" if user else text


def reply_text(h, cs, user=None, salt=0):
    rnd = random.Random(f"{cs}{salt}")
    if len(cs) >= 2 and frozenset(cs[:2]) in requests_q.BLOCKED:
        return None  # пары с конфликтами не обсуждаем
    if h.get("key", "").startswith("cup:"):  # матч турнира: «голос засчитан»
        import tournament
        return tournament.vote_reply(h, cs, user, salt)
    if h.get("kind") == "duel" or len(cs) >= 2:
        if len(cs) >= 2:
            a, b = COUNTRIES[cs[0]], COUNTRIES[cs[1]]
            body = rnd.choice([f"{a} vs {b}? Love it, added to our battle list ⚔️",
                               f"Ooh, {a} vs {b} would be a good one! Noted 📝",
                               f"{a} vs {b} — writing it down for a future battle 🔥"])
        else:
            body = rnd.choice([f"{COUNTRIES[cs[0]]} {flag_emoji(cs[0])}! Who should it battle next?",
                               f"Nice! Which country should {COUNTRIES[cs[0]]} face next? 👀"])
        return f"@{user} {body}" if user else body
    return rank_line(h, cs[0], user, salt)


def run(c=None, history=None, queue=None):
    c = c or instagram.conf()
    history = history if history is not None else json.load(open(HISTORY))
    queue = queue if queue is not None else (json.load(open(QUEUE)) if os.path.exists(QUEUE) else {})
    replied = set(queue.get("replied", []))
    import fans
    fans_lit = fans.load().get("lit", {})
    me = instagram.http("GET", f"{c['api']}/{c['user_id']}", {"fields": "username", "access_token": c["token"]})
    me = me.get("username")
    sent = 0
    for h in reversed(history[-20:]):
        if not h.get("media_id") or sent >= MAX_PER_RUN or h.get("key", "").startswith("neutral:"):
            continue  # под роликами о парах с конфликтом бот молчит — не подливаем масла
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
            text = reply_text(h, cs, cm.get("username"), cm["id"]) if cs else None
            if text and len(cs) == 1 and h.get("kind") != "duel":  # карта мира: кто первый — зажигает страну
                lit = fans_lit.get(cs[0])
                if not lit or lit.get("by") == cm.get("username"):
                    text += f" 🌍 You just lit up {COUNTRIES[cs[0]]} on our world map — your name goes on it in the next video!"
                else:
                    text += f" +1 point for {COUNTRIES[cs[0]]} 🏆 (lit by @{lit['by']})"
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
    import fans  # каждый час: сначала зажигаем страны и начисляем очки, чтобы ответ совпадал с картой
    c = instagram.conf()
    hist = json.load(open(HISTORY))
    st = fans.load()
    try:
        me = instagram.http("GET", f"{c['api']}/{c['user_id']}", {"fields": "username", "access_token": c["token"]})
        fans.collect(c, st, hist, me.get("username"))
        fans.save(st)
    except Exception as e:
        print(f"фанаты пропущены: {str(e)[:160]}")
    run(c, hist)
