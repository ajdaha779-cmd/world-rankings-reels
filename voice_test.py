"""Проба озвучки на сервере: по ролику каждого формата (голос чередуется), без публикации."""
import random, os
import formats
from catalog import ACCENTS
os.makedirs("work/voice", exist_ok=True)
for seed, kind in enumerate(("ranking", "race", "duel")):
    it = next(formats.SOURCES[kind](set(), random.Random(3), set()))
    out = f"work/voice/{seed}_{kind}_{'male' if seed % 2 == 0 else 'female'}.mp4"
    it["render"](out, seed, ACCENTS[seed])
    print(out, "|", it["title"])
