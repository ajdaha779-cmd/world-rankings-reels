"""Заказы зрителей из комментариев: «Azerbaijan vs Turkey!», «🇧🇷🇦🇷» → следующие дуэли.

Нужно разрешение instagram_manage_comments; без него всё молча пропускается.
"""
import difflib, re
import instagram
from catalog import COUNTRIES, EXCLUDE

# пары, между которыми войны или острые конфликты — такие «дуэли» не делаем никогда
BLOCKED = {frozenset(p) for p in [("RU", "UA"), ("AM", "AZ"), ("IN", "PK"), ("IL", "IR"), ("IL", "LB"), ("IL", "SY"),
                                  ("SA", "YE"), ("ET", "ER"), ("SD", "SS"), ("CD", "RW"), ("KR", "KP"), ("AF", "PK"),
                                  ("VE", "GY"), ("MA", "DZ"), ("RS", "XK"), ("CN", "TW"), ("RU", "GE"), ("IR", "SA"),
                                  ("TH", "KH"), ("KG", "TJ")]}
ALIASES = {"usa": "US", "america": "US", "united states": "US", "uk": "GB", "england": "GB",
           "britain": "GB", "great britain": "GB", "korea": "KR", "south korea": "KR", "uae": "AE", "emirates": "AE",
           "turkiye": "TR", "türkiye": "TR", "holland": "NL", "czech": "CZ", "czech republic": "CZ",
           "russia": "RU", "россия": "RU", "азербайджан": "AZ", "турция": "TR", "казахстан": "KZ", "грузия": "GE",
           "узбекистан": "UZ", "германия": "DE", "франция": "FR", "сша": "US", "китай": "CN", "япония": "JP",
           "бразилия": "BR", "испания": "ES", "италия": "IT", "индия": "IN", "англия": "GB", "украина": "UA",
           "ivory coast": "CI", "dr congo": "CD", "vietnam": "VN", "viet nam": "VN"}
# 14.11: самая активная аудитория — иранская; названия стран по-персидски и по-турецки
ALIASES.update({"ایران": "IR", "انگلیس": "GB", "انگلستان": "GB", "بریتانیا": "GB", "فرانسه": "FR", "آلمان": "DE",
                "ترکیه": "TR", "آمریکا": "US", "امریکا": "US", "روسیه": "RU", "عراق": "IQ", "افغانستان": "AF",
                "آذربایجان": "AZ", "چین": "CN", "ژاپن": "JP", "هند": "IN", "هندوستان": "IN", "پاکستان": "PK", "عربستان": "SA",
                "ایتالیا": "IT", "اسپانیا": "ES", "برزیل": "BR", "آرژانتین": "AR", "کانادا": "CA", "مصر": "EG",
                "امارات": "AE", "قطر": "QA", "کره": "KR", "کره جنوبی": "KR", "مغولستان": "MN", "ارمنستان": "AM",
                "گرجستان": "GE", "تاجیکستان": "TJ", "ازبکستان": "UZ", "قزاقستان": "KZ", "سوئد": "SE", "هلند": "NL",
                "almanya": "DE", "fransa": "FR", "ingiltere": "GB", "rusya": "RU", "amerika": "US", "azerbaycan": "AZ",
                "iran": "IR", "japonya": "JP", "çin": "CN", "italya": "IT", "ispanya": "ES", "yunanistan": "GR"})
NAMES = {n.lower(): c for c, n in COUNTRIES.items()}
NAMES.update(ALIASES)
_PATTERN = re.compile(r"(?<![a-zа-яё\u0600-\u06FF])(" + "|".join(sorted(map(re.escape, NAMES), key=len, reverse=True)) + r")(?![a-zа-яё\u0600-\u06FF])")


_CYR_STEMS = [(re.escape(n[:-1] if n[-1] in "аяйь" else n), c) for n, c in ALIASES.items() if re.search("[а-яё]", n)]


def countries_in(text):
    """Страны в порядке упоминания: по названиям и по эмодзи флагов."""
    found = []
    low = text.lower()
    for m in _PATTERN.finditer(low):
        found.append((m.start(), NAMES[m.group(1)]))
    for stem, c in _CYR_STEMS:  # русские падежи: «Казахстана», «Турцией»
        for m in re.finditer(r"(?<![а-яё])" + stem + r"[а-яё]{0,3}(?![а-яё])", low):
            found.append((m.start(), c))
    for m in re.finditer("\U0001F3F4[\U000E0061-\U000E007A]+\U000E007F", text):  # 🏴 Англия/Шотландия/Уэльс → UK
        found.append((m.start(), "GB"))
    for m in re.finditer(r"[\U0001F1E6-\U0001F1FF]{2}", text):
        iso = "".join(chr(ord(ch) - 0x1F1E6 + 65) for ch in m.group(0))
        found.append((m.start(), iso))
    if not found:  # опечатки: «Jordain» → Jordan, «Azerbajan» → Azerbaijan (только латиница, слова от 5 букв)
        for m in re.finditer(r"[a-z]{5,}", low):
            close = difflib.get_close_matches(m.group(0), [n for n in NAMES if " " not in n and len(n) >= 5], 1, 0.8)
            if close:
                found.append((m.start(), NAMES[close[0]]))
    out = []
    for _, c in sorted(found):
        if c in COUNTRIES and c not in EXCLUDE and c not in out:
            out.append(c)
    return out


def collect(c, history, queue):
    """Читает комментарии последних роликов и копит заказы дуэлей: queue = {"seen": [...], "pairs": {...}}."""
    seen = set(queue.get("seen", []))
    pairs = queue.setdefault("pairs", {})
    for h in history[-15:]:
        if not h.get("media_id"):
            continue
        try:
            r = instagram.http("GET", f"{c['api']}/{h['media_id']}/comments",
                               {"fields": "id,text,username", "limit": 100, "access_token": c["token"]})
        except Exception as e:
            print(f"комментарии недоступны: {str(e)[:160]}")
            break
        for cm in r.get("data", []):
            if cm["id"] in seen:
                continue
            seen.add(cm["id"])
            cs = countries_in(cm.get("text", ""))
            if len(cs) >= 2 and frozenset(cs[:2]) not in BLOCKED:
                key = "-".join(sorted(cs[:2]))
                p = pairs.setdefault(key, {"a": cs[0], "b": cs[1], "votes": 0, "users": [], "comments": []})
                p["votes"] += 1
                if cm.get("username") and cm["username"] not in p["users"]:
                    p["users"].append(cm["username"])
                p["comments"].append(cm["id"])
    queue["seen"] = sorted(seen)[-3000:]
    return queue


def top_request(queue, used):
    pairs = [p for k, p in queue.get("pairs", {}).items() if f"duel:{k}" not in used]
    return max(pairs, key=lambda p: p["votes"]) if pairs else None


def reply_all(c, req, text):
    for cid in req.get("comments", [])[:20]:
        try:
            instagram.http("POST", f"{c['api']}/{cid}/replies", {"message": text, "access_token": c["token"]})
        except Exception as e:
            print(f"ответ на комментарий не отправлен: {str(e)[:120]}")
            return


def first_comment(c, media_id, text):
    try:
        instagram.http("POST", f"{c['api']}/{media_id}/comments", {"message": text, "access_token": c["token"]})
    except Exception as e:
        print(f"первый комментарий не опубликован: {str(e)[:120]}")
