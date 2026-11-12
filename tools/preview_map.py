"""Пример ролика «Light Up the World» с голосом (запускается в workflow preview.yml: на старом Mac голоса нет)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import worldmap

new = ["AZ", "IN", "TR", "BR", "ID", "RU", "FR", "NG"]
nicks = ["ali_baku", "raj_22", "emre34", "lucas.br", "budi.id", "sasha_m", "lea.fr", "tunde_ng"]
os.makedirs("preview", exist_ok=True)
worldmap.render_lightup([], new, dict(zip(new, nicks)), len(new), (255, 196, 46), "preview/light-up-day1.mp4", seed=3)
worldmap.render_lightup(new, ["MA", "KR", "AR", "US"], {"MA": "yassine_ma", "KR": "minji_kr", "AR": "sofi.ar", "US": "johnny_us"},
                        12, (255, 196, 46), "preview/light-up-day2.mp4", seed=4)
