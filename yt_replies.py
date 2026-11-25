"""Ответы зрителям на YouTube (20.11, просьба пользователя «отвечай на комментарии в ютубе»).

Та же логика, что в Instagram (replies.py): назвал страну → её настоящее место по теме ролика (World Bank).
Тему ролика узнаём по названию (hits.classify). Плюс ответы на «not true / fake» — откуда цифры и где страна на самом деле.
Запускается каждый час из instagram.yml.

  python yt_replies.py           — ответить
  python yt_replies.py --dry     — только показать, что бот ответил бы
"""
import json, os, random, re, sys

import youtube, hits, replies, requests_q, yt_requests
from catalog import BASE, COUNTRIES, flag_emoji

DONE = os.path.join(BASE, "data", "yt_replied.json")
MAX_PER_RUN = 30
DOUBT = re.compile(r"\b(not ?t?rue|ture|fake|wrong|lie|lies|not real|false|bs|cap|nonsense|no way|incorrect)\b|🧢", re.I)
LAUGH = re.compile(r"^[\s😂🤣😆😅🤡💀]+|yeah sure", re.I)


def item_for(title):
    """Псевдо-запись истории для replies.rank_info: ключ «rich:world» / «race:pop:asia» по названию ролика."""
    kind, tid, grp = hits.classify(title)
    if kind == "ranking" and tid and grp:
        return {"kind": "ranking", "key": f"{tid}:{grp}"}
    if kind == "race" and tid and grp:
        return {"kind": "race", "key": f"race:{tid}:{grp}"}
    return {"kind": "duel", "key": ""}  # дуэли и «X vs Y по годам»


def doubt_reply(h, cs, salt):
    rnd = random.Random(salt)
    src = "World Bank Open Data (latest year available)"
    if cs and h["kind"] != "duel":
        r = replies.rank_info(h, cs[0])
        if r:
            name, fl = COUNTRIES[cs[0]], flag_emoji(cs[0])
            topic = r["topic"].replace("gdp", "GDP")
            extra = " By total GDP it's #1 though 😉" if cs[0] == "US" and "per person" in topic else ""
            return (f"Fair question! By {topic}, {name} {fl} is {replies._ord(r['rank'])} in {r['where']} "
                    f"with {r['value']} — numbers from {src}.{extra}")
    return rnd.choice([f"All numbers come straight from {src} 📊 Which country did you expect at the top?",
                       f"It surprised us too! Data: {src}. Which result looks off to you? 🤔"])


VS = re.compile(r"\bvs\.?\b|\bversus\b|\bagainst\b|⚔", re.I)


def request_reply(cs, q, salt):
    """25.11: заказ «A vs B» — в очередь YouTube; ответ: «записали, выйдет скоро»."""
    a, b = cs[:2]
    na, nb = COUNTRIES[a], COUNTRIES[b]
    st = yt_requests.status(q, a, b)
    if st.get("video"):
        return f"Already made it! {na} vs {nb} 👉 youtube.com/shorts/{st['video']}"
    return random.Random(salt).choice([
        f"Great match-up! {na} {flag_emoji(a)} vs {nb} {flag_emoji(b)} is on our list — coming soon 🔥 Subscribe so you don't miss it 🔔",
        f"Noted! {na} vs {nb} {flag_emoji(a)}⚔️{flag_emoji(b)} — the most requested battles go first. Stay tuned 🔔"])


def reply_for(title, text, salt, q=None):
    h = item_for(title)
    cs = requests_q.countries_in(text)
    if cs and len(cs) >= 2 and frozenset(cs[:2]) in requests_q.BLOCKED:
        return None
    if cs and len(cs) >= 2 and q is not None and not DOUBT.search(text):
        return request_reply(cs, q, salt)
    if len(cs) == 1 and VS.search(text):  # «Hong Kong vs Japan» — вторую страну World Bank не знает
        return (f"{COUNTRIES[cs[0]]} {flag_emoji(cs[0])} vs who? We use World Bank countries only — "
                f"comment 2 flags and it goes on our list 👇")
    if DOUBT.search(text):
        return doubt_reply(h, cs, salt)
    if cs:
        lang = replies.lang_of(text)
        if h["kind"] == "duel" and lang == "en" and len(cs) == 1:
            n = COUNTRIES[cs[0]]
            return random.Random(salt).choice([f"{n} {flag_emoji(cs[0])}! Which country should it face next? 👀",
                                               f"Nice! Who should {n} race against next? Comment 2 flags 👇"])
        return replies.reply_text(h, cs, None, salt, lang)
    if LAUGH.search(text):
        tc = requests_q.countries_in(title)
        if h["kind"] == "duel" and len(tc) >= 2:
            return f"😄 So who wins in your opinion — {COUNTRIES[tc[0]]} or {COUNTRIES[tc[1]]}?"
        return random.Random(salt).choice(["😄 Which country would you put at #1?",
                                           "Haha 😄 Comment your country's flag — I'll tell you where it ranks!"])
    return None


def run(dry=False):
    token = youtube.access_token()
    me = youtube.my_channel(token) if hasattr(youtube, "my_channel") else None
    my_id = (me or {}).get("id") if isinstance(me, dict) else None
    done = set(json.load(open(DONE))) if os.path.exists(DONE) else set()
    videos = youtube.channel_stats(token)
    q = yt_requests.load()
    sent = 0
    for p in yt_requests.due_notifications(q):  # 25.11: заказанный ролик вышел — ответить заказчикам ссылкой
        text = (f"Your battle is out! {COUNTRIES[p['a']]} vs {COUNTRIES[p['b']]} 👉 youtube.com/shorts/{p['video']} "
                f"Who should we do next? 🔥")
        print(f"заказ {p['a']}-{p['b']} вышел → {len(p['comments'])} ответов")
        if dry:
            continue
        for cid in p["comments"][:20]:
            try:
                youtube.reply(cid, text, token)
                sent += 1
            except Exception as e:
                print(f"   ответ не отправлен: {str(e)[:160]}")
        p["notified"] = True
    for v in reversed(videos[-60:]):
        if not v["comments"] or sent >= MAX_PER_RUN:
            continue
        _, b = youtube.call("GET", "commentThreads", token,
                            {"part": "snippet,replies", "videoId": v["id"], "maxResults": 100, "textFormat": "plainText"})
        for th in json.loads(b).get("items", []):
            c = th["snippet"]["topLevelComment"]
            s = c["snippet"]
            for r in (th.get("replies") or {}).get("comments", []) + [c]:  # заказы — и в ответах под чужими комментариями
                rs = r["snippet"]
                if my_id and rs.get("authorChannelId", {}).get("value") == my_id:
                    continue
                rc = requests_q.countries_in(rs.get("textOriginal", ""))
                if len(rc) >= 2 and frozenset(rc[:2]) not in requests_q.BLOCKED and not DOUBT.search(rs.get("textOriginal", "")):
                    if yt_requests.add(q, rc[0], rc[1], rs.get("authorDisplayName"), r["id"]):
                        print(f"   заказ: {rc[0]}-{rc[1]} от {rs.get('authorDisplayName')}")
            if c["id"] in done or th["snippet"].get("totalReplyCount", 0) or sent >= MAX_PER_RUN:
                continue
            if my_id and s.get("authorChannelId", {}).get("value") == my_id:
                continue
            text = reply_for(v["title"], s.get("textOriginal") or s.get("textDisplay", ""), c["id"], q)
            print(f"[{v['title'][:40]}] {s.get('authorDisplayName')}: {s.get('textOriginal', '')[:80]}\n   → {text}")
            if dry:
                continue
            done.add(c["id"])
            if not text:
                continue
            try:
                youtube.reply(c["id"], text, token)
                sent += 1
            except Exception as e:
                print(f"   ответ не отправлен: {str(e)[:160]}")
    if not dry:
        json.dump(sorted(done)[-5000:], open(DONE, "w"), indent=0)
        yt_requests.save(q)
    print(f"ответов на YouTube: {sent}")


if __name__ == "__main__":
    run(dry="--dry" in sys.argv)
