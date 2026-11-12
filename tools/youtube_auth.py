"""Одноразовое подключение YouTube: окно входа Google → разрешение «загружать видео и отвечать на комментарии» →
refresh-токен в data/youtube_oauth.json (на этом Mac) и в секретах GitHub (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN).

Клиент OAuth — файл client_secret_*.json, скачанный из Google Cloud (тип «Приложение для ПК»), ищется в ~/Downloads.
Только стандартная библиотека + certifi. Пароль Google никуда не передаётся — вход идёт на сайте Google.
"""
import base64, glob, hashlib, http.server, json, os, secrets, ssl, subprocess, sys, urllib.parse, urllib.request, webbrowser
import certifi

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "youtube_oauth.json")
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"
SSL = ssl.create_default_context(cafile=certifi.where())


def client():
    files = sorted(glob.glob(os.path.expanduser("~/Downloads/client_secret_*.json")), key=os.path.getmtime)
    if not files:
        sys.exit("Не нашёл файл client_secret_….json в «Загрузках». Скачай его в Google Cloud (Учётные данные → OAuth-клиент → скачать JSON).")
    c = json.load(open(files[-1]))
    c = c.get("installed") or c.get("web")
    return c["client_id"], c["client_secret"]


def main():
    cid, csec = client()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if q.get("state") == state and "code" in q:
                got["code"] = q["code"]
                msg = "Готово! YouTube подключён — окно можно закрыть."
            else:
                got["error"] = q.get("error", "нет кода")
                msg = "Что-то пошло не так: " + got["error"]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent"})
    print("Открываю окно входа Google… Выбери аккаунт канала World in Numbers и разреши доступ.")
    print("Если появится «Google не проверил это приложение» — нажми «Дополнительно» → «Перейти на страницу…». Это наше приложение.")
    webbrowser.open(url)
    while not got:
        srv.handle_request()
    if "code" not in got:
        sys.exit("Доступ не получен: " + got["error"])
    body = urllib.parse.urlencode({"code": got["code"], "client_id": cid, "client_secret": csec, "redirect_uri": redirect,
                                   "grant_type": "authorization_code", "code_verifier": verifier}).encode()
    tok = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", body, context=SSL))
    if "refresh_token" not in tok:
        sys.exit("Google не выдал долгий ключ. Запусти ещё раз.")
    old = os.umask(0o077)
    json.dump({"client_id": cid, "client_secret": csec, "refresh_token": tok["refresh_token"]}, open(OUT, "w"))
    os.umask(old)
    # какой канал подключили — для проверки
    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                                 headers={"Authorization": f"Bearer {tok['access_token']}"})
    ch = json.load(urllib.request.urlopen(req, context=SSL)).get("items", [{}])[0].get("snippet", {})
    print(f"Подключён канал: {ch.get('title')} ({ch.get('customUrl')})")
    gh = os.path.join(BASE, "bin", "gh")
    for name, val in (("YT_CLIENT_ID", cid), ("YT_CLIENT_SECRET", csec), ("YT_REFRESH_TOKEN", tok["refresh_token"])):
        subprocess.run([gh, "secret", "set", name], input=val.encode(), check=True, cwd=BASE)
    print("Ключи сохранены в GitHub. Готово — окно можно закрыть.")


if __name__ == "__main__":
    main()
