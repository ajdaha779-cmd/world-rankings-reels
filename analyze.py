"""Разбор каждого ролика: где уходит зритель и что менять.

Instagram через API не отдаёт график удержания по секундам, но отдаёт:
  • reels_skip_rate — % людей, пролиставших ролик в первые ~3 секунды (сила хука);
  • ig_reels_avg_watch_time — среднее время просмотра.
Раскадровку каждого ролика мы знаем (moments в истории), поэтому видно, на каком моменте
уходит средний зритель. Отчёт пишется в data/АНАЛИЗ.md и в лог запуска.

  python analyze.py   — обновить статистику и отчёт
"""
import datetime, json, os
import instagram

BASE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(BASE, "data", "history_cloud.json")
REPORT = os.path.join(BASE, "data", "АНАЛИЗ.md")
KIND_RU = {"ranking": "рейтинг", "race": "гонка", "duel": "дуэль", "twist": "твист"}


def fetch(c, h):
    r = instagram.http("GET", f"{c['api']}/{h['media_id']}/insights",
                       {"metric": "views,reach,likes,saved,shares,comments,reels_skip_rate,ig_reels_avg_watch_time",
                        "access_token": c["token"]})
    st = {m["name"]: m["values"][0]["value"] for m in r.get("data", [])}
    st["watch"] = st.pop("ig_reels_avg_watch_time", 0) / 1000
    st["skip"] = st.pop("reels_skip_rate", None)
    return st


def moment_at(h, sec):
    ms = h.get("moments") or []
    cur = ms[0][1] if ms else "?"
    for t, name in ms:
        if sec >= t:
            cur = name
    return cur


def verdict(h, st, avg):
    tips = []
    skip, watch, dur = st.get("skip"), st["watch"], h.get("dur") or 25
    if skip is not None:
        if skip >= 70:
            tips.append("хук слабый — 7 из 10 листают в первые 3 с: нужен вопрос/тизер сильнее, крупнее флаги в 1-м кадре")
        elif skip <= 55:
            tips.append("хук сработал — оставить такой тип начала")
    share = watch / dur
    if share < 0.3:
        tips.append(f"уходят на «{moment_at(h, watch)}» — этот участок затянут, ускорить или убрать")
    elif share >= 0.6:
        tips.append("смотрят до развязки — формат и темп удачные")
    eng = st.get("saved", 0) + st.get("shares", 0) + st.get("comments", 0)
    if st.get("views", 0) >= 100 and eng == 0:
        tips.append("нет сохранений/репостов/комментариев — нужен повод: спорный факт, вопрос «а у вас?»")
    if avg and st.get("views", 0) > 1.5 * avg:
        tips.append("тема зашла лучше среднего — делать больше похожих")
    return tips


def run(c=None, history=None, save=True):
    c = c or instagram.conf()
    history = history if history is not None else json.load(open(HISTORY))
    rows = []
    for h in history:
        if not h.get("media_id"):
            continue
        try:
            h["stats"] = fetch(c, h)
            h["stats_at"] = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + "Z"
        except Exception as e:
            print(f"статистика недоступна: {str(e)[:150]}")
            break
        rows.append(h)
    if not rows:
        return history
    avg = sum(h["stats"].get("views", 0) for h in rows) / len(rows)
    lines = [f"# Разбор роликов ({datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=4):%d.%m %H:%M} по Баку)", "",
             f"Роликов: {len(rows)} · средние просмотры: {avg:.0f}", ""]
    by_kind = {}
    for h in rows:
        st = h["stats"]
        by_kind.setdefault(h.get("kind", "ranking"), []).append(st)
        dur = h.get("dur") or 25
        lines.append(f"## {h['title']}")
        lines.append(f"{KIND_RU.get(h.get('kind'), h.get('kind'))} · просмотры {st.get('views', 0)} · "
                     f"пролистали в начале {st.get('skip', 0):.0f}% · смотрят в среднем {st['watch']:.1f} из {dur:.0f} с · "
                     f"лайки {st.get('likes', 0)} · сохранения {st.get('saved', 0)} · репосты {st.get('shares', 0)}")
        for tip in verdict(h, st, avg):
            lines.append(f"- {tip}")
        h["analysis"] = verdict(h, st, avg)
        lines.append("")
    lines.append("## По форматам")
    for k, sts in by_kind.items():
        n = len(sts)
        lines.append(f"- {KIND_RU.get(k, k)}: {n} шт · просмотры {sum(s.get('views', 0) for s in sts) / n:.0f} · "
                     f"пролистали {sum(s.get('skip') or 0 for s in sts) / n:.0f}% · "
                     f"досмотр {sum(s['watch'] for s in sts) / n:.1f} с")
    text = "\n".join(lines) + "\n"
    print(text)
    if save:
        open(REPORT, "w").write(text)
        json.dump(history, open(HISTORY, "w"), ensure_ascii=False, indent=1)
    return history


if __name__ == "__main__":
    run()
