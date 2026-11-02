"""Перерендерить готовую пачку с теми же темами (например, после смены звука или дизайна).
  .venv/bin/python rerender.py к-публикации/2026-11-02 [01_babies_americas.mp4 ...]
"""
import os, sys, time
from catalog import TOPICS, GROUPS, ACCENTS
from data import ranking
from render import render

folder = sys.argv[1]
names = sys.argv[2:] or sorted(f for f in os.listdir(folder) if f.endswith(".mp4"))
by_id = {t["id"]: t for t in TOPICS}
for fname in names:
    num, rest = fname[:-4].split("_", 1)
    tid, g = rest.rsplit("_", 1)
    i = int(num) - 1
    t0 = time.time()
    render(ranking(by_id[tid], g), by_id[tid], GROUPS[g][0], ACCENTS[i % len(ACCENTS)], os.path.join(folder, fname), seed=i)
    print(f"{fname}  {time.time() - t0:.0f}s", flush=True)
