"""Озвучка: нейроголос Kokoro (Apache 2.0, работает локально на сервере, без внешних сервисов).

Голос чередуется: чётные ролики — мужской, нечётные — женский. Озвучиваются только ключевые моменты:
хук в начале, развязка №1 и призыв в конце — голос не спорит с музыкой.
Если библиотека не установлена (например, на старом Mac) — ролик собирается без голоса.
"""
import os, urllib.request
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE, "data", "tts")
REL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
FILES = {"model": "kokoro-v1.0.int8.onnx", "voices": "voices-v1.0.bin"}
VOICES = ["am_michael", "af_heart"]  # мужской, женский
SR = 44100
_engine = None


def _load():
    global _engine
    if _engine is None:
        from kokoro_onnx import Kokoro
        os.makedirs(MODEL_DIR, exist_ok=True)
        for name in FILES.values():
            path = os.path.join(MODEL_DIR, name)
            if not os.path.exists(path):
                urllib.request.urlretrieve(f"{REL}/{name}", path)
        _engine = Kokoro(os.path.join(MODEL_DIR, FILES["model"]), os.path.join(MODEL_DIR, FILES["voices"]))
    return _engine


def available():
    try:
        import kokoro_onnx  # noqa: F401
        return os.environ.get("NO_VOICE") != "1"
    except Exception:
        return False


def voice_for(seed):
    return VOICES[seed % 2]


def say(text, voice, speed=1.08):
    samples, sr = _load().create(text, voice=voice, speed=speed, lang="en-us")
    samples = np.asarray(samples, dtype=np.float64)
    t_new = np.arange(int(len(samples) * SR / sr)) / SR
    out = np.interp(t_new, np.arange(len(samples)) / sr, samples)
    peak = np.abs(out).max() or 1
    return out / peak * 0.9


def spoken(text):
    """Подготовка текста для голоса: «3.0×» → «3 times», «USA» → «U.S.A.» и т. п."""
    rep = {"×": " times", "USA": "the U.S.", "UK": "the U.K.", "UAE": "the U.A.E.", "#1": "number one",
           "→": "to", "ex-USSR": "former Soviet", "GDP": "G.D.P.", "%": " percent"}
    for a, b in rep.items():
        text = text.replace(a, b)
    return text.replace(".0 times", " times")


def lines(plan, seed):
    """plan: [(время, текст)] → [(время, звук)]; реплики не наслаиваются друг на друга."""
    if not available():
        return []
    voice = voice_for(seed)
    out, busy_until = [], 0.0
    for t, txt in plan:
        if not txt:
            continue
        try:
            a = say(spoken(txt), voice)
        except Exception as e:
            print(f"озвучка не получилась: {e}")
            return []
        t = max(t, busy_until + 0.1)
        out.append((t, a))
        busy_until = t + len(a) / SR
    return out
