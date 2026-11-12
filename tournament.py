"""«World Cup of Countries» (12.11): турнир на 16 стран, кто проходит дальше — решают зрители в комментариях.

Один матч — один ролик, не чаще раза в сутки. Перед следующим матчем считаем голоса под прошлым:
каждый зритель — один голос (первая из двух стран, которую он назвал или поставил флагом). Ничья — решают цифры.
Состояние — data/cup.json.
"""
import datetime, json, os
from catalog import BASE, COUNTRIES, flag_emoji
from duel import duel_rounds
import requests_q

STATE = os.path.join(BASE, "data", "cup.json")
EVERY_H = 22  # матчи не чаще раза в сутки — зрители успевают проголосовать
# 1/8 финала: страны, откуда идут зрители, и пары, где есть за кого болеть (без идущих конфликтов)
FIRST_ROUND = [("US", "GB"), ("IN", "ID"), ("PH", "JP"), ("BR", "MX"), ("TR", "AZ"), ("DE", "FR"), ("KR", "IT"),
               ("NG", "EG")]
STAGES = {8: "ROUND OF 16", 4: "QUARTER-FINAL", 2: "SEMI-FINAL", 1: "FINAL"}


def load():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"no": 1, "rounds": [[{"a": a, "b": b} for a, b in FIRST_ROUND]], "champions": []}


def save(st):
    json.dump(st, open(STATE, "w"), ensure_ascii=False, indent=1)


def _advance(st):
    """Все матчи раунда сыграны — собираем следующий; финал сыгран — чемпион и новый турнир."""
    rnd = st["rounds"][-1]
    if not all(m.get("winner") for m in rnd):
        return
    if len(rnd) == 1:
        st["champions"].append({"no": st["no"], "code": rnd[0]["winner"]})
        st["no"] += 1
        st["rounds"] = [[{"a": a, "b": b} for a, b in FIRST_ROUND]]
        return
    w = [m["winner"] for m in rnd]
    st["rounds"].append([{"a": w[i], "b": w[i + 1]} for i in range(0, len(w), 2)])


def tally(c, st, now=None):
    """Считает голоса под сыгранными матчами без итога (если ролик вышел ≥ EVERY_H часов назад)."""
    import instagram
    now = now or datetime.datetime.utcnow()
    for m in st["rounds"][-1]:
        if m.get("winner") or not m.get("media_id"):
            continue
        if (now - datetime.datetime.fromisoformat(m["at"].rstrip("Z"))).total_seconds() < EVERY_H * 3600:
            continue
        votes, voters, after = {m["a"]: 0, m["b"]: 0}, {}, None
        for _ in range(10):  # постранично, до 1000 комментариев
            p = {"fields": "id,text,username", "limit": 100, "access_token": c["token"]}
            if after:
                p["after"] = after
            r = instagram.http("GET", f"{c['api']}/{m['media_id']}/comments", p)
            for cm in r.get("data", []):
                u = cm.get("username") or cm["id"]
                pick = next((x for x in requests_q.countries_in(cm.get("text", "")) if x in votes), None)
                if pick and u not in voters:
                    voters[u] = pick
                    votes[pick] += 1
            after = r.get("paging", {}).get("cursors", {}).get("after") if r.get("paging", {}).get("next") else None
            if not after:
                break
        total = sum(votes.values())
        if votes[m["a"]] != votes[m["b"]]:
            m["winner"] = max(votes, key=votes.get)
        else:  # ничья или никто не проголосовал — решают цифры
            m["winner"] = m["a"] if m.get("data_winner", 0) == 0 else m["b"]
        m["votes"] = votes
        m["pct"] = round(100 * votes[m["winner"]] / total) if total else None
        m["voters"] = [u for u, x in voters.items() if x == m["winner"]][:5]
        print(f"кубок: {COUNTRIES[m['a']]} {votes[m['a']]} — {votes[m['b']]} {COUNTRIES[m['b']]} → {COUNTRIES[m['winner']]}")
    _advance(st)


def _last_played(st):
    played = [m for r in st["rounds"] for m in r if m.get("winner")]
    return played[-1] if played else None


def next_match(st, now=None):
    """Следующий матч, если пора: прошлый вышел ≥ EVERY_H часов назад и уже подсчитан. Иначе None."""
    now = now or datetime.datetime.utcnow()
    rnd = st["rounds"][-1]
    if any(m.get("media_id") and not m.get("winner") for m in rnd):
        return None  # ждём итогов голосования
    last_at = st.get("last_at")
    if last_at and (now - datetime.datetime.fromisoformat(last_at.rstrip("Z"))).total_seconds() < EVERY_H * 3600:
        return None
    return next((m for m in rnd if not m.get("media_id")), None)


def make_item(st, m):
    """Ролик-матч в формате formats.* (kind="duel", ключ cup:<no>:A-B)."""
    from duel import render_duel
    a, b = m["a"], m["b"]
    rounds = duel_rounds(a, b)
    if not rounds:
        return None
    rnd = st["rounds"][-1]
    n = len(rnd)
    i = rnd.index(m) + 1
    stage = STAGES[n] + (f" · MATCH {i}/{n}" if n > 1 else "")
    prev = _last_played(st)
    if prev and prev.get("pct"):
        prev = {"code": prev["winner"], "name": COUNTRIES[prev["winner"]], "pct": prev["pct"],
                "by": prev.get("voters", [])}
    else:
        prev = None
    if not any(mm.get("winner") for r in st["rounds"] for mm in r) and st["champions"]:
        ch = st["champions"][-1]["code"]
        prev = {"code": ch, "name": f"{COUNTRIES[ch]} (champion)", "pct": 100, "by": []}
    total = [sum(1 for r in rounds if r[4] == s) for s in (0, 1)]
    m["data_winner"] = 0 if total[0] >= total[1] else 1
    na, nb = COUNTRIES[a], COUNTRIES[b]
    fa, fb = flag_emoji(a), flag_emoji(b)
    head = f"World Cup of Countries 🏆 {na} vs {nb} — YOU decide who goes through! {fa}🆚{fb}"
    shout = ""
    if prev and prev.get("by"):
        shout = f"\nLast match: {prev['name']} won with {prev['pct']}% of your votes! Thanks {' '.join('@' + u for u in prev['by'][:3])} 🙌\n"
    ask = f"VOTE in the comments: {fa} {na} or {fb} {nb}? Most votes goes through. Results in the next match!"
    tags = "#shorts #countries #worldcup #vote #geography #comparison"
    return dict(kind="duel", key=f"cup:{st['no']}:{a}-{b}", topic="cup", slug=f"cup{st['no']}_{a.lower()}_{b.lower()}",
                title=head, cup_match=m,
                first_comment=f"🗳️ VOTE HERE: comment {fa} {na} or {fb} {nb}! One vote per person. Results in the next match 🏆",
                description=f"{stage}: {na} vs {nb}.\n3 rounds of real data (World Bank) — then YOU vote.\n{shout}\n{ask}\n\n{tags}",
                short=f"{head}\n{shout}\n{ask}\n\n{tags}",
                render=lambda out, seed, accent: render_duel(a, b, rounds, accent, out, seed=seed,
                                                             pill="WORLD CUP · YOU DECIDE", cup={"stage": stage, "prev": prev}))


def posted(st, m, media_id, at):
    m["media_id"], m["at"] = media_id, at
    st["last_at"] = at


def vote_reply(h, cs, user=None, salt=0):
    """Ответ бота под матчем: «голос засчитан»."""
    import random
    a, b = h["key"].split(":")[2].split("-")
    pick = next((x for x in cs if x in (a, b)), None)
    if not pick:
        return None
    rnd = random.Random(f"{cs}{salt}")
    body = rnd.choice([f"Vote counted for {COUNTRIES[pick]} {flag_emoji(pick)} ✅ Results in the next match!",
                       f"{COUNTRIES[pick]} {flag_emoji(pick)} got your vote ✅ Tell your friends to vote too!",
                       f"Your vote for {COUNTRIES[pick]} {flag_emoji(pick)} is in 🗳️ Can they go through?"])
    return f"@{user} {body}" if user else body
