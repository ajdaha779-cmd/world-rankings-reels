"""25.11: проверка ролика по заказу YouTube (JP-PK) — рендер в preview/."""
import os, sys
os.environ["REELS_PLATFORM"] = "youtube"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from formats import request_item
os.makedirs("preview", exist_ok=True)
for a, b in [("JP", "PK"), ("MN", "KR")]:
    it = request_item(a, b, set(), by=["@iampiyara"])
    print(it["kind"], it["key"], "|", it["title"], "\n", it["description"][:300], "\n")
    it["render"](f"preview/{a}_{b}.mp4", 0, (255, 200, 60))
