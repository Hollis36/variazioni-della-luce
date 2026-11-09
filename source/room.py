# 混响：合成一个温暖小厅的脉冲响应（早期反射 + 指数衰减、随时间变暗的尾音，左右声道去相关），
# 所有声部按各自的发送量进同一个房间，听起来像在同一间酒吧里演奏。
import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt


def impulse(rate: int, seconds: float = 1.8, rt60: float = 1.25, seed: int = 7) -> np.ndarray:
    """stereo impulse response, shape (n, 2)"""
    rng = np.random.default_rng(seed)
    count = int(rate * seconds)
    t = np.arange(count) / rate
    decay = np.exp(-6.91 * t / rt60)  # -60 dB at rt60
    out = np.zeros((count, 2))
    for ch in range(2):
        noise = rng.standard_normal(count)
        # darken the tail as it decays: blend a bright and a dark copy over time
        dark = sosfilt(butter(2, 2500, "low", fs=rate, output="sos"), noise)
        bright = sosfilt(butter(2, 7000, "low", fs=rate, output="sos"), noise)
        blend = np.clip(t / 0.6, 0, 1)
        tail = (bright * (1 - blend) + dark * blend) * decay
        tail[: int(0.012 * rate)] = 0  # pre-delay before the diffuse tail
        # a few early reflections off nearby walls
        for delay, gain in ((0.013, 0.5), (0.019, 0.38), (0.027, 0.3), (0.034, 0.24), (0.046, 0.18)):
            d = int((delay + 0.002 * ch) * rate)
            tail[d] += gain * (1 if (d + ch) % 2 else -1)
        out[:, ch] = tail
    return out / np.sqrt((out**2).sum(axis=0)).max()


def add_room(dry: np.ndarray, ir: np.ndarray, send: float) -> np.ndarray:
    """dry (n, 2) + `send` of it through the room; the result is longer by the reverb tail"""
    wet = np.stack([fftconvolve(dry[:, ch], ir[:, ch]) for ch in range(2)], axis=1)
    out = np.zeros_like(wet)
    out[: len(dry)] = dry
    return out + send * wet
