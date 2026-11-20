"""Движок: кадры через Pillow -> ffmpeg, звук синтезируется numpy."""
import os, math, wave, shutil, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_LOCAL_FF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "ffmpeg")
FF = _LOCAL_FF if os.path.exists(_LOCAL_FF) else shutil.which("ffmpeg")  # на GitHub — системный
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "work")
W, H, FPS, SR = 1080, 1920, 30, 44100
os.makedirs(OUT, exist_ok=True)

# ---------- графика ----------
_fonts, _flags = {}, {}


def font(size, black=True):
    key = (size, black)
    if key not in _fonts:
        name = "Montserrat-Black.ttf" if black else "Montserrat-ExtraBold.ttf"
        _fonts[key] = ImageFont.truetype(os.path.join(FONTS, name), size)
    return _fonts[key]


MAX_FLAG_RATIO = 2.0  # шире 2:1 не бывает — вытянутые флаги (Катар 28:11) становятся ниже, а не шире


def flag(code, h, radius=0.12):
    """Флаг высотой до h. Очень вытянутые флаги вписываются по ширине h·2 и получаются ниже —
    поэтому центрировать нужно по fl.height, а не по h."""
    key = (code, h)
    if key not in _flags:
        im = Image.open(os.path.join(BASE, "assets", "flags", f"{code}.png")).convert("RGBA")
        ratio = im.width / im.height
        w = max(1, round(h * min(ratio, MAX_FLAG_RATIO)))
        h = max(1, round(w / ratio)) if ratio > MAX_FLAG_RATIO else h
        im = im.resize((w, h), Image.LANCZOS)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), int(h * radius), fill=255)
        im.putalpha(mask)
        _flags[key] = im
    return _flags[key]


def gradient(top, bottom):
    t = np.linspace(0, 1, H)[:, None, None]
    a = np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t
    arr = np.repeat(a, W, axis=1)
    # лёгкая виньетка
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W / 2) / W) ** 2 + ((y - H / 2) / H) ** 2)
    arr *= (1 - 0.45 * np.clip(d - 0.2, 0, 1))[:, :, None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def clamp(t, a=0.0, b=1.0):
    return max(a, min(b, t))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = clamp(t)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def mix_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def text(d, xy, s, f, fill=(255, 255, 255), anchor="mm", stroke=0, stroke_fill=(0, 0, 0)):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


def wrap(s, f, max_w):
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if f.getlength(test) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


# ---------- звук ----------
def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _env(n, attack=0.003, decay=8.0):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t * decay)


def _bandnoise(dur, lo, hi, seed=0):
    n = int(dur * SR)
    x = np.random.default_rng(seed).standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(X, n)
    return y / (np.abs(y).max() + 1e-9)


def sfx_wave(kind, **kw):
    if kind == "tick":
        t = _t(0.05)
        return 0.5 * np.sin(2 * np.pi * 1900 * t) * _env(len(t), 0.001, 90)
    if kind == "click":
        return 0.4 * _bandnoise(0.02, 2500, 9000, 3) * _env(int(0.02 * SR), 0.0005, 250)
    if kind == "whoosh":
        dur = kw.get("dur", 0.35)
        n = int(dur * SR)
        env = np.sin(np.linspace(0, np.pi, n)) ** 2
        return 0.55 * _bandnoise(dur, 400, 4000, kw.get("seed", 1)) * env
    if kind == "pop":
        t = _t(0.09)
        f = 700 * np.exp(-t * 25) + 180
        return 0.6 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 40)
    if kind == "boom":
        t = _t(0.9)
        f = 110 * np.exp(-t * 4) + 38
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 4.5)
        hit = _bandnoise(0.9, 60, 3000, 7) * _env(len(t), 0.001, 30)
        return 0.95 * body + 0.35 * hit
    if kind == "ding":
        t = _t(1.4)
        f0 = kw.get("f", 1046.5)
        y = sum(a * np.sin(2 * np.pi * f0 * m * t) * np.exp(-t * (3 + m)) for m, a in ((1, 1), (2, .45), (3, .2), (4.2, .1)))
        return 0.45 * y * np.minimum(1, t / 0.002)
    if kind == "riser":
        dur = kw.get("dur", 1.0)
        t = _t(dur)
        f = 200 + 1400 * (t / dur) ** 2
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
        y = 0.25 * tone + 0.35 * _bandnoise(dur, 1500, 8000, 5)
        return y * (t / dur) ** 2
    if kind == "note":
        f0 = kw["f"]
        t = _t(0.7)
        y = np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * f0 * 4 * t) * np.exp(-t * 18)
        return 0.32 * y * _env(len(t), 0.002, 5)
    if kind == "tada":
        out = np.zeros(int(1.8 * SR))
        for i, f0 in enumerate((523.25, 659.25, 783.99, 1046.5)):
            w_ = sfx_wave("ding", f=f0)
            s = int(i * 0.07 * SR)
            out[s:s + len(w_)] += w_[:len(out) - s] * 0.7
        return out
    if kind == "buzz":
        t = _t(0.25)
        return 0.25 * np.sign(np.sin(2 * np.pi * 110 * t)) * _env(len(t), 0.002, 10)
    raise ValueError(kind)


def music_bed(dur, bpm=118, root=55.0, seed=0):
    """Простой ритмичный бит: бочка, хэт, бас, мягкий пэд."""
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    prog = [0, -4, 3, -2]  # полутона от корня (i–VI–III–VII)
    kick = np.sin(2 * np.pi * np.cumsum(60 * np.exp(-_t(0.3) * 12) + 42) / SR) * _env(int(0.3 * SR), 0.001, 11)
    hat = _bandnoise(0.04, 7000, 15000, 9) * _env(int(0.04 * SR), 0.0005, 120) * 0.25
    k = 0
    while k * beat < dur:
        s = int(k * beat * SR)
        out[s:s + len(kick)] += kick[:max(0, n - s)]
        sh = int((k + 0.5) * beat * SR)
        if sh < n:
            out[sh:sh + len(hat)] += hat[:n - sh]
        bar = (k // 4) % 4
        f = root * 2 ** (prog[bar] / 12)
        bt = _t(beat * 0.9)
        bass = (np.sin(2 * np.pi * f * bt) + 0.3 * np.sin(2 * np.pi * 2 * f * bt)) * _env(len(bt), 0.005, 3) * 0.5
        out[s:s + len(bass)] += bass[:max(0, n - s)]
        if k % 4 == 0:
            pt = _t(beat * 4)
            pad = sum(np.sin(2 * np.pi * f * 4 * r * pt) for r in (1, 1.26, 1.5)) * 0.06
            pad *= np.sin(np.linspace(0, np.pi, len(pt)))
            out[s:s + len(pad)] += pad[:max(0, n - s)]
        k += 1
    return out


# 20.11: в сетке канала YouTube превью Shorts обрезано сверху и снизу (~150 px) — заголовки срезались.
# Для YouTube весь кадр уменьшаем до 82% и ставим по центру на размытый фон из того же кадра.
YT_SAFE = ["-vf", "split[a][b];[a]scale=270:480,boxblur=8,scale=1080:1920,eq=brightness=-0.12[bg];"
                  "[b]scale=886:1576[fg];[bg][fg]overlay=97:172"] \
    if os.environ.get("REELS_PLATFORM") == "youtube" else []


class Video:
    def __init__(self, name, duration, out_path=None):
        self.name, self.duration = name, duration
        self.out_path = out_path
        self.n = int(round(duration * FPS))
        self.events = []
        self.tmp = os.path.join(OUT, f"_{name}_v.mp4")
        self.p = subprocess.Popen(
            [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "-", *YT_SAFE, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", self.tmp], stdin=subprocess.PIPE)

    def sfx(self, t, kind, vol=1.0, **kw):
        self.events.append((t, kind, vol, kw))

    def write(self, img):
        self.p.stdin.write(img.tobytes())

    def finish(self, music=None, music_vol=0.22, audio=None):
        """audio — готовая стереодорожка (n, 2); иначе старое моно-сведение из music и self.events."""
        self.p.stdin.close()
        self.p.wait()
        channels = 2 if audio is not None else 1
        if audio is None:
            n = int(self.duration * SR) + SR
            audio = np.zeros(n)
            if music is not None:
                m = music[:n]
                fade = np.ones(len(m))
                fl = int(0.8 * SR)
                fade[-fl:] = np.linspace(1, 0, fl)
                audio[:len(m)] += m * fade * music_vol
            for t, kind, vol, kw in self.events:
                w_ = sfx_wave(kind, **kw) * vol
                s = int(t * SR)
                if s >= n:
                    continue
                audio[s:s + len(w_)] += w_[:n - s]
            audio = np.tanh(audio * 1.1) * 0.9
        pcm = (np.clip(audio[:int(self.duration * SR)], -1, 1) * 32767).astype(np.int16)
        wav = os.path.join(OUT, f"_{self.name}.wav")
        with wave.open(wav, "wb") as f:
            f.setnchannels(channels)
            f.setsampwidth(2)
            f.setframerate(SR)
            f.writeframes(pcm.tobytes())
        final = self.out_path or os.path.join(OUT, f"{self.name}.mp4")
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", self.tmp, "-i", wav, "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", final], check=True)
        os.remove(self.tmp)
        os.remove(wav)
        return final


_ratios = {}


def flag_box(code, max_w, max_h, radius=0.12):
    """Флаг, вписанный в рамку max_w×max_h — два флага рядом (дуэль) выглядят одного размера."""
    if code not in _ratios:
        with Image.open(os.path.join(BASE, "assets", "flags", f"{code}.png")) as im:
            _ratios[code] = im.width / im.height
    r = min(_ratios[code], MAX_FLAG_RATIO)
    return flag(code, max(1, int(min(max_h, max_w / r))), radius)
