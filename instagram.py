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
API_IG = "https://graph.instagram.com/v23.0"  # токен входа через Instagram (IG...), живёт 60 дней
API_FB = "https://graph.facebook.com/v23.0"   # токен системного пользователя (EAA...), бессрочный
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


def api_for(token):
    return API_IG if token.startswith("IG") else API_FB


def conf():
    if os.environ.get("IG_TOKEN"):  # GitHub Actions: токен в секретах
        tok = os.environ["IG_TOKEN"].strip()
        return {"token": tok, "user_id": os.environ["IG_USER_ID"].strip(), "api": api_for(tok)}
    c = load(CONF, None)
    if not c:
        sys.exit("Сначала: .venv/bin/python instagram.py setup")
    c["api"] = api_for(c["token"])
    # токен входа через Instagram живёт 60 дней — продлеваем раз в 20 дней (системный токен бессрочный)
    if c["api"] == API_IG and time.time() - c.get("refreshed", 0) > 20 * 86400:
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
    if api_for(token) == API_IG:
        me = http("GET", f"{API_IG}/me", {"fields": "user_id,username,account_type", "access_token": token})
        ig_id, username = me["user_id"], me["username"]
    else:
        # системный токен: id аккаунта Instagram берём из списка объектов, к которым токен дал доступ
        dbg = http("GET", f"{API_FB}/debug_token", {"input_token": token, "access_token": token})["data"]
        if not dbg.get("is_valid"):
            sys.exit(f"Токен недействителен: {dbg}")
        scopes = {g["scope"]: g.get("target_ids", []) for g in dbg.get("granular_scopes", [])}
        if "instagram_content_publish" not in dbg.get("scopes", []):
            sys.exit("У токена нет разрешения instagram_content_publish — пересоздай его с этим разрешением")
        ids = scopes.get("instagram_content_publish") or scopes.get("instagram_basic") or []
        if not ids:
            pages = http("GET", f"{API_FB}/me/accounts",
                         {"fields": "instagram_business_account", "access_token": token}).get("data", [])
            ids = [p["instagram_business_account"]["id"] for p in pages if p.get("instagram_business_account")]
        if not ids:  # у системных токенов Meta часто не перечисляет объекты — спросим id из настроек портфолио
            ids = [input("id аккаунта Instagram (Настройки портфолио → Аккаунты Instagram):\n> ").strip()]
        ig_id = ids[0]
        username = http("GET", f"{API_FB}/{ig_id}", {"fields": "username", "access_token": token})["username"]
    save(CONF, {"token": token, "user_id": ig_id, "username": username, "refreshed": time.time()})
    print(f"Готово: @{username}, id {ig_id}")


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


def _upload_and_publish(c, path, params, what):
    """Контейнер → загрузка файла (resumable) → ожидание обработки → публикация. Возвращает id медиа."""
    size = os.path.getsize(path)
    cont = http("POST", f"{c['api']}/{c['user_id']}/media",
                {**params, "upload_type": "resumable", "access_token": c["token"]})
    cid = cont["id"]
    with open(path, "rb") as f:
        http("POST", f"{RUPLOAD}/{cid}", body=f.read(), timeout=600,
             headers={"Authorization": f"OAuth {c['token']}", "offset": "0", "file_size": str(size)})
    for _ in range(60):  # Instagram обрабатывает видео — ждём до 10 минут
        st = http("GET", f"{c['api']}/{cid}", {"fields": "status_code,status", "access_token": c["token"]})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram не принял {what}: {st}")
        time.sleep(10)
    else:
        raise RuntimeError(f"Instagram слишком долго обрабатывает {what}")
    pub = http("POST", f"{c['api']}/{c['user_id']}/media_publish", {"creation_id": cid, "access_token": c["token"]})
    return pub["id"]


def publish(c, m):
    log(f"публикую {m['key']} ({os.path.getsize(m['path']) // 1024} КБ)")
    mid = _upload_and_publish(c, m["path"], {"media_type": "REELS", "caption": caption(m), "share_to_feed": "true"},
                              "видео")
    log(f"опубликовано: {m['key']} → media {mid}")
    return mid


def publish_story(c, path):
    """Тот же ролик в Stories — дополнительный охват. Ошибка здесь не мешает Reels."""
    mid = _upload_and_publish(c, path, {"media_type": "STORIES"}, "историю")
    log(f"история опубликована → media {mid}")
    return mid


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
