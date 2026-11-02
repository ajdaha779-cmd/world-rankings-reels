"""Автопубликация Reels в Instagram по расписанию из к-публикации/*/metadata.json.

  .venv/bin/python instagram.py setup   — один раз: вставить токен, проверить аккаунт
  .venv/bin/python instagram.py due     — опубликовать ролик, время которого подошло (запускается каждые 15 мин)
  .venv/bin/python instagram.py now     — опубликовать следующий ролик прямо сейчас (для проверки)
  .venv/bin/python instagram.py status  — что опубликовано и что в очереди
"""
import datetime, glob, json, os, ssl, subprocess, sys, time, urllib.parse, urllib.request, urllib.error
import certifi

BASE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(BASE, "data", "instagram.json")
POSTED = os.path.join(BASE, "data", "posted_instagram.json")
OUTBOX = os.path.join(BASE, "к-публикации")
API = "https://graph.instagram.com/v23.0"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload/v23.0"
SSL = ssl.create_default_context(cafile=certifi.where())
MAX_LATE_HOURS = 48  # ролик, опоздавший больше чем на 2 суток, пропускаем — следующие важнее


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line, flush=True)
    with open(os.path.join(BASE, "data", "instagram.log"), "a") as f:
        f.write(line + "\n")


def notify(msg):
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Instagram"'], check=False)


def http(method, url, params=None, headers=None, body=None, timeout=120):
    if params:
        data = urllib.parse.urlencode(params)
        if method == "GET":
            url, data = f"{url}?{data}", None
        else:
            data = data.encode()
    else:
        data = body
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code}: {e.read().decode(errors='replace')[:500]}") from None


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def save(path, obj):
    json.dump(obj, open(path, "w"), ensure_ascii=False, indent=2)


def conf():
    if os.environ.get("IG_TOKEN"):  # GitHub Actions: токен в секретах, продлевает отдельный workflow
        return {"token": os.environ["IG_TOKEN"], "user_id": os.environ["IG_USER_ID"]}
    c = load(CONF, None)
    if not c:
        sys.exit("Сначала: .venv/bin/python instagram.py setup")
    # долгий токен живёт 60 дней — продлеваем раз в 20 дней
    if time.time() - c.get("refreshed", 0) > 20 * 86400:
        try:
            r = http("GET", "https://graph.instagram.com/refresh_access_token",
                     {"grant_type": "ig_refresh_token", "access_token": c["token"]})
            c["token"], c["refreshed"] = r["access_token"], time.time()
            save(CONF, c)
            log("токен продлён")
        except Exception as e:
            log(f"не удалось продлить токен: {e}")
            notify("Не удалось продлить токен — проверь data/instagram.log")
    return c


def setup():
    token = input("Вставь токен доступа Instagram и нажми Enter:\n> ").strip()
    me = http("GET", f"{API}/me", {"fields": "user_id,username,account_type", "access_token": token})
    save(CONF, {"token": token, "user_id": me["user_id"], "username": me["username"], "refreshed": time.time()})
    print(f"Готово: @{me['username']} ({me.get('account_type')}), id {me['user_id']}")


def queue():
    items = []
    for mf in sorted(glob.glob(os.path.join(OUTBOX, "*", "metadata.json"))):
        folder = os.path.dirname(mf)
        for m in json.load(open(mf)):
            m["path"] = os.path.join(folder, m["file"])
            m["key"] = os.path.relpath(m["path"], OUTBOX)
            m["when"] = datetime.datetime.fromisoformat(m["publish_baku"])
            items.append(m)
    return sorted(items, key=lambda m: m["when"])


def caption(m):
    return m["caption_tiktok_instagram"].replace("#shorts", "#reels")


def publish(c, m):
    size = os.path.getsize(m["path"])
    log(f"публикую {m['key']} ({size // 1024} КБ)")
    cont = http("POST", f"{API}/{c['user_id']}/media",
                {"media_type": "REELS", "upload_type": "resumable", "caption": caption(m),
                 "share_to_feed": "true", "access_token": c["token"]})
    cid = cont["id"]
    with open(m["path"], "rb") as f:
        http("POST", f"{RUPLOAD}/{cid}", body=f.read(), timeout=600,
             headers={"Authorization": f"OAuth {c['token']}", "offset": "0", "file_size": str(size)})
    for _ in range(60):  # Instagram обрабатывает видео — ждём до 10 минут
        st = http("GET", f"{API}/{cid}", {"fields": "status_code,status", "access_token": c["token"]})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram не принял видео: {st}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram слишком долго обрабатывает видео")
    pub = http("POST", f"{API}/{c['user_id']}/media_publish", {"creation_id": cid, "access_token": c["token"]})
    log(f"опубликовано: {m['key']} → media {pub['id']}")
    return pub["id"]


def run(mode):
    c = conf()
    posted = load(POSTED, {})
    now = datetime.datetime.now(datetime.timezone.utc)
    pending = [m for m in queue() if m["key"] not in posted]
    if mode == "due":
        late = [m for m in pending if now - m["when"] > datetime.timedelta(hours=MAX_LATE_HOURS)]
        for m in late:
            posted[m["key"]] = {"skipped": "опоздал больше чем на 48 ч", "at": now.isoformat()}
            log(f"пропущен (сильно опоздал): {m['key']}")
        save(POSTED, posted)
        pending = [m for m in pending if m["when"] <= now and m not in late]
    if not pending:
        return
    m = pending[0]  # один ролик за запуск — чтобы после сна Mac не вывалить всё разом
    try:
        mid = publish(c, m)
        posted[m["key"]] = {"media_id": mid, "at": now.isoformat()}
        save(POSTED, posted)
        notify(f"Опубликован: {m['title'][:60]}")
    except Exception as e:
        log(f"ОШИБКА {m['key']}: {e}")
        notify("Ошибка публикации — см. data/instagram.log")


def status():
    posted = load(POSTED, {})
    for m in queue():
        p = posted.get(m["key"])
        mark = "✓ опубликован" if p and "media_id" in p else ("— пропущен" if p else "  в очереди")
        print(f"{m['when']:%d.%m %H:%M}  {mark}  {m['key']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "due"
    {"setup": setup, "due": lambda: run("due"), "now": lambda: run("now"), "status": status}[cmd]()
