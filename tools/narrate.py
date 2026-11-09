"""Служебная озвучка для других проектов: строки JSON → WAV-файлы (запускается workflow «Озвучка»).

  python tools/narrate.py '[{"id": "hook", "lang": "en", "text": "..."}, {"id": "hook", "lang": "ru", "text": "..."}]'

en — Kokoro (Apache 2.0, британский мужской голос bm_george), ru — Piper (MIT, голос ru_RU-dmitri-medium).
Результат: work/narration/<lang>_<id>.wav
"""
import json, os, sys, urllib.request, wave
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", "narration")
PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx"


def write(path, samples, sr):
    pcm = (np.clip(np.asarray(samples, dtype=np.float64), -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(pcm.tobytes())


def english(text, path):
    import tts
    eng = tts._load()
    samples, sr = eng.create(text, voice="bm_george", speed=1.05, lang="en-gb")
    write(path, samples / (np.abs(samples).max() or 1) * 0.9, sr)


_piper = None


def russian(text, path):
    global _piper
    if _piper is None:
        from piper import PiperVoice
        model = os.path.join(OUT, "ru.onnx")
        if not os.path.exists(model):
            urllib.request.urlretrieve(PIPER, model)
            urllib.request.urlretrieve(PIPER + ".json", model + ".json")
        _piper = PiperVoice.load(model)
    with wave.open(path, "wb") as f:
        if hasattr(_piper, "synthesize_wav"):
            _piper.synthesize_wav(text, f)
        else:
            _piper.synthesize(text, f)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for ln in json.loads(sys.argv[1]):
        path = os.path.join(OUT, f"{ln['lang']}_{ln['id']}.wav")
        (english if ln["lang"] == "en" else russian)(ln["text"], path)
        print("готово:", path)
