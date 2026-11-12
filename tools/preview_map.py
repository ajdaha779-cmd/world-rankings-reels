"""Пример ролика «Light Up the World» с голосом (запускается в workflow preview.yml: на старом Mac голоса нет).
Данные — реальные комментарии на 12.11.2026 (первый ролик-карта)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import worldmap

NEW = ['JO', 'RU', 'ZW', 'AZ', 'IN', 'MA', 'IR', 'FR', 'MN', 'KR', 'GB', 'AR']
BY = {'JO': ['omarhammad2016'], 'RU': ['zoktay_16_', 'sardvr'], 'ZW': ['uzanenkosi16'], 'AZ': ['sardvr'], 'IN': ['anurag.kairi'], 'MA': ['mgh_md13'], 'IR': ['saro0onh18', 'ay_han8136'], 'FR': ['saro0onh18'], 'MN': ['sumya__bn910'], 'KR': ['sumya__bn910'], 'GB': ['ay_han8136'], 'AR': ['ay_han8136']}
os.makedirs("preview", exist_ok=True)
worldmap.render_lightup([], NEW, BY, len(NEW), (255, 196, 46), "preview/light-up-day1.mp4", seed=3)
