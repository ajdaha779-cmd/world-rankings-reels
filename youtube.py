"""World in Numbers Uploader — загрузка своих роликов на свой канал YouTube и чтение комментариев под ними (YouTube Data API v3).

Ключи: переменные окружения YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (секреты GitHub) или data/youtube_oauth.json.
Используемые методы: videos.insert (resumable upload), commentThreads.list, comments.insert, channels.list.
Только стандартная библиотека + certifi.

  python youtube.py upload ролик.mp4 "Название" "Описание" [--publish-at 2026-11-20T15:00:00Z]
  python youtube.py comments VIDEO_ID
"""
import json, os, ssl, sys, urllib.parse, urllib.request
import certifi

BASE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(BASE, "data", "youtube_oauth.json")
SSL = ssl.create_default_context(cafile=certifi.where())
API = "https://www.googleapis.com/youtube/v3"


def creds():
    if os.environ.get("YT_REFRESH_TOKEN"):
        return {k: os.environ[f"YT_{k.upper()}"] for k in ("client_id", "client_secret", "refresh_token")}
    return json.load(open(CONF))


def access_token():
    c = creds()
    body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
                                   "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", body, context=SSL))["access_token"]


def call(method, path, token, params=None, body=None, headers=None):
    url = (path if path.startswith("https://") else f"{API}/{path}") + ("?" + urllib.parse.urlencode(params) if params else "")
    h = {"Authorization": f"Bearer {token}", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json; charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, context=SSL, timeout=120) as r:
        return r, r.read()


def upload(path, title, description, tags=(), publish_at=None, token=None):
    """Загружает ролик на свой канал. publish_at (RFC 3339, UTC) — отложенная публикация: до этого времени видео приватное."""
    token = token or access_token()
    status = {"privacyStatus": "private" if publish_at else "public", "selfDeclaredMadeForKids": False}
    if publish_at:
        status["publishAt"] = publish_at
    meta = {"snippet": {"title": title[:100], "description": description[:5000], "tags": list(tags)[:30],
                        "categoryId": "27"},  # 27 — Education
            "status": status}
    size = os.path.getsize(path)
    r, _ = call("POST", "https://www.googleapis.com/upload/youtube/v3/videos", token,
                {"uploadType": "resumable", "part": "snippet,status"}, meta,
                {"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    session = r.headers["Location"]
    with open(path, "rb") as f:
        req = urllib.request.Request(session, data=f.read(), method="PUT",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"})
    with urllib.request.urlopen(req, context=SSL, timeout=600) as r2:
        video = json.load(r2)
    print(f"загружено: https://youtube.com/shorts/{video['id']} ({video['status']['privacyStatus']})")
    return video["id"]


def comments(video_id, token=None):
    """Публичные комментарии под своим видео: [{"id", "author", "text", "published"}]."""
    token = token or access_token()
    out, page = [], None
    while True:
        p = {"part": "snippet", "videoId": video_id, "maxResults": 100, "textFormat": "plainText"}
        if page:
            p["pageToken"] = page
        _, raw = call("GET", "commentThreads", token, p)
        d = json.loads(raw)
        for it in d.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            out.append({"id": it["snippet"]["topLevelComment"]["id"], "author": s.get("authorDisplayName", ""),
                        "text": s.get("textDisplay", ""), "published": s.get("publishedAt", "")})
        page = d.get("nextPageToken")
        if not page:
            return out


def reply(comment_id, text, token=None):
    """Ответ на комментарий под своим видео (например: «Вы на нашей карте мира!»)."""
    token = token or access_token()
    call("POST", "comments", token, {"part": "snippet"}, {"snippet": {"parentId": comment_id, "textOriginal": text}})


def my_channel(token=None):
    token = token or access_token()
    _, raw = call("GET", "channels", token, {"part": "snippet", "mine": "true"})
    return json.loads(raw)["items"][0]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "channel"
    if cmd == "upload":
        pa = sys.argv[sys.argv.index("--publish-at") + 1] if "--publish-at" in sys.argv else None
        upload(sys.argv[2], sys.argv[3], sys.argv[4], publish_at=pa)
    elif cmd == "comments":
        for c in comments(sys.argv[2]):
            print(c["author"], "|", c["text"])
    else:
        ch = my_channel()
        print(ch["snippet"]["title"], ch["snippet"].get("customUrl"))


def channel_stats(token=None, path=None):
    """20.11: просмотры всех роликов канала → data/youtube_stats.json (для hits.py: что залетает на YouTube)."""
    token = token or access_token()
    _, b = call("GET", "channels", token, {"part": "contentDetails", "mine": "true"})
    up = json.loads(b)["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        p = {"part": "contentDetails", "playlistId": up, "maxResults": 50}
        if page:
            p["pageToken"] = page
        _, b = call("GET", "playlistItems", token, p)
        d = json.loads(b)
        ids += [i["contentDetails"]["videoId"] for i in d["items"]]
        page = d.get("nextPageToken")
        if not page:
            break
    out = []
    for i in range(0, len(ids), 50):
        _, b = call("GET", "videos", token, {"part": "snippet,statistics,status", "id": ",".join(ids[i:i + 50])})
        for v in json.loads(b)["items"]:
            if v["status"]["privacyStatus"] != "public":
                continue
            s = v["statistics"]
            out.append({"id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"],
                        "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                        "comments": int(s.get("commentCount", 0))})
    out.sort(key=lambda v: v["published"])
    json.dump(out, open(path or os.path.join(os.path.dirname(CONF), "youtube_stats.json"), "w"), ensure_ascii=False, indent=1)
    return out
