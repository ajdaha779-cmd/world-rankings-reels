"""Звук роликов: синтезированный бит (808, хлопки, хэты, пэд, мелодия) + саунд-дизайн рейтинга. Стерео."""
import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
_rng = np.random.default_rng(11)


# ---------- базовые блоки ----------
def _sos(kind, f):
    return butter(4, f, btype=kind, fs=SR, output="sos")


def lp(x, f):
    return sosfilt(_sos("lowpass", f), x, axis=0)


def hp(x, f):
    return sosfilt(_sos("highpass", f), x, axis=0)


def bp(x, lo, hi):
    return sosfilt(_sos("bandpass", (lo, hi)), x, axis=0)


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def noise(dur):
    return _rng.standard_normal(int(dur * SR))


def decay(n, tau, attack=0.002):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / tau)


def osc_sine(freq):
    return np.sin(2 * np.pi * np.cumsum(freq) / SR)


def saw(f, dur, detune_cents=0.0, phase=0.0):
    t = t_(dur)
    ff = f * 2 ** (detune_cents / 1200)
    return 2 * ((t * ff + phase) % 1) - 1


def note_hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def place(buf, sig, t, gain=1.0, pan=0.0):
    """Положить моно/стерео сигнал в стерео-буфер с панорамой (-1..1)."""
    s = int(t * SR)
    if s >= len(buf) or s + len(sig) <= 0:
        return
    if sig.ndim == 1:
        a = np.pi / 4 * (pan + 1)
        sig = np.stack([sig * np.cos(a), sig * np.sin(a)], axis=1) * np.sqrt(2)
    if s < 0:
        sig, s = sig[-s:], 0
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[:e - s] * gain


def feedback_delay(x, delay_s, fb, mix):
    """Эхо с обратной связью; считается блоками длиной в задержку (быстро)."""
    d = int(delay_s * SR)
    y = x.copy()
    for k in range(d, len(x), d):
        e = min(len(x), k + d)
        y[k:e] += fb * y[k - d:e - d]
    return x * (1 - mix) + (y - x) * mix + x * mix


def reverb(x, mix=0.25, size=1.0):
    """Простая реверберация Шрёдера: 4 гребенчатых фильтра на канал."""
    out = np.zeros_like(x)
    for ch, offs in ((0, 0), (1, 23)):
        src = x[:, ch] if x.ndim == 2 else x
        acc = np.zeros(len(src))
        for D in (1116, 1188, 1277, 1356):
            D = int((D + offs) * size)
            y = src.copy()
            for k in range(D, len(src), D):
                e = min(len(src), k + D)
                y[k:e] += 0.78 * y[k - D:e - D]
            acc += y
        acc = lp(acc, 6000) / 4
        if x.ndim == 2:
            out[:, ch] = acc
        else:
            return src * (1 - mix) + acc * mix
    return x * (1 - mix) + out * mix


def stereo(x):
    return np.stack([x, x], axis=1)


# ---------- инструменты ----------
def kick():
    t = t_(0.45)
    body = osc_sine(48 + 120 * np.exp(-t * 35)) * decay(len(t), 0.16)
    click = hp(noise(0.006), 3000) * 0.4
    body[:len(click)] += click
    return np.tanh(body * 1.8) * 0.9


def clap():
    out = np.zeros(int(0.35 * SR))
    for i, off in enumerate((0, 0.011, 0.022)):
        b = bp(noise(0.3), 900, 6000) * decay(int(0.3 * SR), 0.012 if i < 2 else 0.09)
        s = int(off * SR)
        out[s:s + len(b)] += b[:len(out) - s]
    return out * 0.55


def hat(open_=False):
    dur = 0.25 if open_ else 0.06
    return hp(noise(dur), 7500) * decay(int(dur * SR), 0.09 if open_ else 0.018) * 0.35


def sub808(f, dur):
    t = t_(dur)
    freq = f * (1 + 0.6 * np.exp(-t * 60))
    y = osc_sine(freq) * decay(len(t), dur * 0.6, 0.004)
    y = np.tanh(y * 2.2) * 0.7
    return lp(y, 500)


def pad(midis, dur):
    """Широкий пэд из расстроенных пил: левый/правый канал звучат чуть по-разному."""
    L = np.zeros(int(dur * SR))
    R = np.zeros_like(L)
    for m in midis:
        f = note_hz(m)
        L += saw(f, dur, -9, 0.1) + saw(f, dur, 4, 0.6)
        R += saw(f, dur, 9, 0.3) + saw(f, dur, -4, 0.8)
    env = np.minimum(1, t_(dur) / 0.08) * np.minimum(1, (dur - t_(dur)) / 0.15)
    y = np.stack([L, R], axis=1) * env[:, None] / (2 * len(midis))
    return lp(y, 1600)


def pluck(midi, dur=0.5, bright=3500):
    f = note_hz(midi)
    t = t_(dur)
    tri = 2 * np.abs(2 * ((t * f) % 1) - 1) - 1
    sq = np.sign(np.sin(2 * np.pi * f * t)) * 0.25
    return lp((tri + sq) * decay(len(t), 0.12), bright) * 0.5


def bell(midi, dur=1.6):
    f = note_hz(midi)
    t = t_(dur)
    y = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * (2.5 + 2 * m)) for m, a in
            ((1, 1.0), (2.0, 0.5), (3.01, 0.25), (4.2, 0.12)))
    return y * np.minimum(1, t / 0.002) * 0.45


def whoosh(dur=0.32, up=True):
    n = int(dur * SR)
    k = np.linspace(0, 1, n) if up else np.linspace(1, 0, n)
    lo, hi = bp(noise(dur), 300, 1500), bp(noise(dur), 2000, 9000)
    y = lo * (1 - k) + hi * k
    return y * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.5


def riser(dur):
    t = t_(dur)
    k = t / dur
    tone = osc_sine(180 + 1500 * k ** 2) * 0.25
    hiss = hp(noise(dur), 2500) * 0.45 * k
    return (tone + hiss) * k ** 1.6


def impact():
    t = t_(2.2)
    sub = np.tanh(osc_sine(30 + 90 * np.exp(-t * 6)) * decay(len(t), 0.7) * 2) * 0.9
    crash = hp(noise(2.2), 4000) * decay(len(t), 0.55) * 0.5
    snap = bp(noise(2.2), 800, 5000) * decay(len(t), 0.03) * 0.8
    return sub, crash + snap


# ---------- аранжировка ----------
KEYS = [57, 60, 55, 62]  # A, C, G, D (минор)
PROG = [(0, 3, 7), (-4, 0, 3), (3, 7, 10), (-2, 2, 5)]  # i – VI – III – VII


def beat(dur, bpm, root):
    """Бит на всю длину. Возвращает (музыка, время каждого удара бочки)."""
    n = int(dur * SR) + SR
    drums, bass, music = np.zeros((n, 2)), np.zeros((n, 2)), np.zeros((n, 2))
    b = 60 / bpm
    bar = 4 * b
    K, C, Ho, Hc = kick(), clap(), hat(True), hat(False)
    kicks = []
    nbars = int(dur / bar) + 1
    for bi in range(nbars):
        t0 = bi * bar
        chord = PROG[bi % 4]
        r = root + chord[0]
        for kb in (0, 1.5, 2.5) if bi % 2 else (0, 2.5):
            place(drums, K, t0 + kb * b, 1.0)
            kicks.append(t0 + kb * b)
        place(bass, sub808(note_hz(r - 24), 1.5 * b), t0, 0.9)
        place(bass, sub808(note_hz(r - 24), b), t0 + 2.5 * b, 0.8)
        for cb in (1, 3):
            place(drums, C, t0 + cb * b, 0.8)
        steps = 16 if bi % 4 == 3 else 8  # каждый 4-й такт — дробь хэтов
        for s in range(steps):
            st = t0 + s * bar / steps
            v = 0.55 + 0.45 * (s % 2 == 0)
            place(drums, Ho if (steps == 8 and s == 7) else Hc, st, v, pan=0.35 if s % 2 else -0.25)
        place(music, pad([root + x for x in chord] + [root + chord[0] + 12], bar), t0, 0.5)
        arp = [0, 1, 2, 1, 2, 0, 1, 2]
        for s, a in enumerate(arp):
            place(music, pluck(root + 12 + chord[a]), t0 + s * b / 2, 0.45, pan=-0.3 if s % 2 else 0.3)
    # сайдчейн: пэд и мелодия «приседают» на бочку — даёт качающийся ритм
    duck = np.ones(n)
    tk = np.arange(int(0.25 * SR)) / SR
    shape = 1 - 0.55 * np.exp(-tk / 0.09)
    for kt in kicks:
        s = int(kt * SR)
        e = min(n, s + len(shape))
        duck[s:e] = np.minimum(duck[s:e], shape[:e - s])
    music = feedback_delay(music, 3 * b / 4, 0.3, 0.25) * duck[:, None]
    return drums * 0.75 + bass * 0.85 + music * 0.5, kicks


def master(x, target_rms=0.16):
    rms = np.sqrt(np.mean(x ** 2)) + 1e-9
    x = x * (target_rms / rms)
    return np.tanh(x * 1.2) * 0.95


def bpm_for(seed):
    return (96, 100, 104)[seed % 3]


def ranking_track(dur, reveal, n, pause_start, top_t, end_t, seed=0, whooshes=()):
    """Полная звуковая дорожка ролика-рейтинга.
    reveal: {место: время}, pause_start..top_t — пауза перед №1."""
    root = KEYS[seed % len(KEYS)]
    bpm = bpm_for(seed)
    music, _ = beat(dur + 1, bpm, root)
    N = int(dur * SR)
    music = music[:N]

    # пауза перед №1: музыка уходит «под воду» и почти стихает, перед ударом — тишина
    s, e = int(pause_start * SR), int(top_t * SR)
    seg = music[s:e]
    if len(seg):
        k = np.linspace(0, 1, len(seg))[:, None]
        under = lp(seg, 500)
        mixd = seg * (1 - k) ** 2 + under * (1 - (1 - k) ** 2)
        gate = np.ones(len(seg))
        gate[-int(0.18 * SR):] = 0  # 0.18 с тишины перед ударом
        music[s:e] = mixd * (1 - 0.6 * k) * gate[:, None]

    # хвост: плавное затухание
    fl = int(0.9 * SR)
    music[-fl:] *= np.linspace(1, 0, fl)[:, None]

    fx = np.zeros((N + SR, 2))
    penta = [0, 3, 5, 7, 10]
    steps = sorted(reveal.items(), key=lambda kv: -kv[0])  # с последнего места к первому
    for i, (rank, t) in enumerate(steps):
        if rank == 1:
            continue
        place(fx, whoosh(0.3), t - 0.05, 0.35, pan=0.4)
        midi = root + 12 * (i // 5) + penta[i % 5]  # каждое следующее место — нота выше
        place(fx, bell(midi), t + 0.08, 0.5, pan=-0.15)
    place(fx, riser(top_t - pause_start - 0.18), pause_start, 0.7)  # обрывается вместе с музыкой
    sub, crash = impact()
    place(fx, sub, top_t, 0.85)
    place(fx, reverb(stereo(crash), 0.35), top_t, 0.8)
    place(fx, pad([root + 12, root + 15, root + 19, root + 24], 1.4) * 2.2, top_t, 0.6)
    place(fx, bell(root + 24, 2.0), top_t + 0.05, 0.45)
    for wt in whooshes:
        place(fx, whoosh(0.4, up=False), wt - 0.05, 0.35, pan=0.3)
    place(fx, whoosh(0.45, up=False), end_t - 0.05, 0.4, pan=-0.3)
    place(fx, bell(root + 19), end_t + 0.25, 0.35)
    place(fx, bell(root + 24), end_t + 0.4, 0.3)

    fx = reverb(fx[:N], 0.12)
    return master(music * 0.8 + fx)
