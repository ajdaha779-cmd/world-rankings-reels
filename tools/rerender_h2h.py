"""Перерендерить h2h-ролики готовой пачки (16.11: исправлены заголовки и подпись разрыва).
  python tools/rerender_h2h.py 01_h2h_us_cn 15_h2h_kr_it ...   → preview/<имя>.mp4 + preview/titles.txt
Слева та же страна, что в имени файла; сид и цвет — как в make_batch (по номеру).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import h2h
from catalog import ACCENTS, COUNTRIES

os.makedirs("preview", exist_ok=True)
out = []
for name in sys.argv[1:]:
    num, _, a, b = name.split("_")
    a, b, i = a.upper(), b.upper(), int(num) - 1
    best = h2h.best_stat(a, b)
    ind, what, label, fmt_id, (years, va, vb, flips) = best
    # best_stat считает от (a, b) в этом порядке — порядок в имени файла уже тот, что был в ролике
    head = h2h.title_for(a, b, ind, what, (years, va, vb, flips))
    h2h.render_h2h(a, b, years, va, vb, flips, label, fmt_id, ACCENTS[i % len(ACCENTS)], f"preview/{name}.mp4",
                   seed=i, what=what)
    out.append(f"{name}\n{head}\n{label}: {COUNTRIES[a]} vs {COUNTRIES[b]}, every year {years[0]}–{years[-1]}.\n")
    print(out[-1], flush=True)
open("preview/titles.txt", "w").write("\n".join(out))
