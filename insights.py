"""Статистика роликов → веса форматов. Канал сам делает больше того, что лучше смотрят.

Нужно разрешение instagram_manage_insights; без него всё молча пропускается.
"""
import datetime
import instagram

METRICS = ["views", "reach", "saved", "shares", "likes", "comments", "total_interactions"]
MIN_AGE_H = 20      # раньше суток цифры ещё растут — в веса не берём
MIN_PER_KIND = 2    # меньше замеров на формат — вес нейтральный
REFRESH_LAST = 30   # обновляем статистику последних N роликов


def _fetch(c, media_id):
    for metrics in (METRICS, ["reach", "saved", "shares", "likes", "comments"]):
        try:
            r = instagram.http("GET", f"{c['api']}/{media_id}/insights",
                               {"metric": ",".join(metrics), "access_token": c["token"]})
            return {m["name"]: (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value", 0))
                    for m in r.get("data", [])}
        except RuntimeError as e:
            last = e
    raise last


def update_stats(c, history):
    """Дописывает свежую статистику в записи истории. Возвращает True, если хоть что-то получили."""
    got = False
    for h in history[-REFRESH_LAST:]:
        if not h.get("media_id"):
            continue
        try:
            h["stats"] = _fetch(c, h["media_id"])
            h["stats_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            got = True
        except Exception as e:
            print(f"статистика недоступна: {str(e)[:160]}")
            return got  # скорее всего нет разрешения — дальше не пытаемся
    return got


def score(st):
    views = st.get("views") or st.get("reach") or 0
    eng = 3 * st.get("saved", 0) + 3 * st.get("shares", 0) + 2 * st.get("comments", 0) + st.get("likes", 0)
    return views * (1 + 5 * eng / max(views, 1))


def kind_weights(history):
    """{формат: вес} по средней «силе» роликов; None — если данных пока мало."""
    now = datetime.datetime.utcnow()
    by = {}
    for h in history:
        st, at = h.get("stats"), h.get("at")
        if not st or not at or not h.get("kind"):
            continue
        age = (now - datetime.datetime.fromisoformat(at.rstrip("Z"))).total_seconds() / 3600
        if age >= MIN_AGE_H:
            by.setdefault(h["kind"], []).append(score(st))
    measured = {k: sum(v) / len(v) for k, v in by.items() if len(v) >= MIN_PER_KIND}
    if len(measured) < 2:
        return None
    avg = sum(measured.values()) / len(measured)
    return {k: max(0.4, min(3.0, measured.get(k, avg) / (avg or 1))) for k in ("ranking", "race", "duel")}
