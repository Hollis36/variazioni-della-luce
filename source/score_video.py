# 成品视频层（用户：最后提交 PDF 曲谱、高质量 mp4、4K 演奏过程）。
#   PIECE=<曲名模块> python3 score_video.py <pages_dir> <audio.wav> <out_dir> [all|cover|follow]
# 曲子模块（pieces/<曲名模块>.py）除 PIECE 外还要提供：BARS（总小节数）、TITLE、SUBTITLE、DEDICATION、
# INSTRUMENTATION（封面乐器行）、BEATS_PER_BAR、SECTIONS（[(起始小节, 字母, 段落名), ...]）。
# pages_dir 里要有 MuseScore 导出的 page-N.png（600 dpi、不裁边）、pos.mpos（小节框）、pos.spos（音符位置）。
#   cover  → <TITLE>.mp4：4K 封面 + 原始 24 bit 混音转 AAC 320k
#   follow → <TITLE>_演奏过程_4K.mp4：一次显示一行总谱，播放线沿音符走，当前小节淡淡高亮
import importlib
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
if not os.environ.get("PIECE"):
    raise SystemExit("set PIECE to a module name in pieces/, e.g. PIECE=my_piece")
piece_mod = importlib.import_module(f"pieces.{os.environ['PIECE']}")

W, H, FPS = 3840, 2160, 30
# 编码质量：默认 CRF 16；母带级用 CRF=10 PRESET=slow（用户：一定要最高质量）
CRF, PRESET = __import__("os").environ.get("CRF", "16"), __import__("os").environ.get("PRESET", "medium")
DPI, POS_DPI = 600, 14400  # page images / MuseScore position files
# 配色（用户：底色用珠光白）：珠光白底 + 墨色标题 + 暖灰辅助文字 + 香槟金强调
PAPER, INK, STONE, HAIR, ACCENT = (247, 245, 241), (34, 32, 36), (150, 144, 136), (226, 221, 213), (176, 146, 98)
PEARL_CENTER, PEARL_EDGE = (252, 251, 248), (239, 237, 233)
SUP = "/System/Library/Fonts/Supplemental/"
SECTIONS = piece_mod.SECTIONS
TITLE, SUBTITLE, DEDICATION = piece_mod.TITLE, piece_mod.SUBTITLE, piece_mod.DEDICATION
FADE = 0.6  # seconds of cross-fade when the next line of the score comes in
TITLE_HOLD, TITLE_FADE, END_FADE = 2.6, 1.2, 1.8  # opening title card, its fade into the score, fade back at the end
MARGIN_X, MARGIN_Y = 190, 110


def songti(size: int) -> ImageFont.FreeTypeFont:
    for i in range(12):  # pick the bold Simplified-Chinese face inside the collection
        try:
            f = ImageFont.truetype(SUP + "Songti.ttc", size, index=i)
        except OSError:
            break
        if f.getname() == ("Songti SC", "Bold"):
            return f
    return ImageFont.truetype(SUP + "Songti.ttc", size)


@lru_cache(maxsize=None)
def font(kind: str, size: int):
    return {"song": lambda: songti(size), "ital": lambda: ImageFont.truetype(SUP + "Georgia Italic.ttf", size),
            "num": lambda: ImageFont.truetype(SUP + "DIN Alternate Bold.ttf", size)}[kind]()


def bar_times() -> list[float]:
    """seconds at the start of every bar, from the same tempo map the audio was rendered with"""
    p = piece_mod.PIECE
    changes = sorted(p.tempo)

    def b2s(b: float) -> float:
        t, cur, bpm = 0.0, 0.0, p.bpm
        for cb, v in changes:
            if cb >= b:
                break
            t, cur, bpm = t + (cb - cur) * 60 / bpm, cb, v
        return t + (b - cur) * 60 / bpm
    return [b2s(piece_mod.BEATS_PER_BAR * i) for i in range(piece_mod.BARS + 1)]


def read_pos(path: Path):
    text = path.read_text()
    els = {int(m[0]): (float(m[1]), float(m[2]), float(m[3]), float(m[4]), int(m[5])) for m in
           re.findall(r'id="(\d+)" x="([\d.]+)" y="([\d.]+)" sx="([\d.]+)" sy="([\d.]+)" page="(\d+)"', text)}
    ms = {int(a): int(b) for a, b in re.findall(r'elid="(\d+)" position="(\d+)"', text)}
    k = DPI / POS_DPI
    return [(ms[i], x * k, y * k, sx * k, sy * k, pg) for i, (x, y, sx, sy, pg) in sorted(els.items())]


def measure_paths(measures, segments):
    """for every bar: (fractions of the bar, x positions) so the playhead sits on each note as it sounds"""
    out = []
    for i, (ms0, x, y, sx, sy, pg) in enumerate(measures):
        ms1 = measures[i + 1][0] if i + 1 < len(measures) else ms0 + (ms0 - measures[i - 1][0])
        segs = sorted((ms, sxx) for ms, sxx, _, _, _, spg in segments if spg == pg and ms0 <= ms < ms1 and x <= sxx <= x + sx)
        fr = [(ms - ms0) / (ms1 - ms0) for ms, _ in segs] + [1.0]
        xs = [sxx for _, sxx in segs] + [x + sx]
        out.append((fr, xs))
    return out


@lru_cache(maxsize=1)
def pearl() -> np.ndarray:
    """pearl white: brighter in the middle, softer to the edges, a breath of warm rose top-left and cool blue
    bottom-right, plus a fine grain so the gradient never bands after compression"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - 0.48 * W) / (0.75 * W)) ** 2 + ((yy - 0.42 * H) / (0.75 * H)) ** 2).clip(0, 1)
    r = r ** 1.6
    c, e = np.array(PEARL_CENTER, np.float32), np.array(PEARL_EDGE, np.float32)
    bg = c * (1 - r[..., None]) + e * r[..., None]
    diag = (xx / W + yy / H) / 2  # 0 top-left .. 1 bottom-right
    bg += np.stack([1.6 * (1 - diag), 0.4 * np.ones_like(diag), 1.8 * diag], axis=-1) - 0.9  # rose -> blue sheen
    bg += np.random.default_rng(7).normal(0, 0.55, (H, W, 1)).astype(np.float32)
    return bg.clip(0, 255)


def tinted(img: Image.Image) -> np.ndarray:
    """white paper -> warm paper, black ink stays black (multiply)"""
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    return (a * np.array(PAPER, dtype=np.float32)).clip(0, 255)


def text_patch(s: str, kind: str, size: int, color) -> tuple[np.ndarray, np.ndarray]:
    f = font(kind, size)
    l, t, r, b = f.getbbox(s)
    im = Image.new("L", (r - l + 4, b - t + 4), 0)
    ImageDraw.Draw(im).text((2 - l, 2 - t), s, font=f, fill=255)
    return np.asarray(im, dtype=np.float32)[..., None] / 255.0, np.array(color, dtype=np.float32)


def paste(frame: np.ndarray, patch, x: int, y: int, anchor: str = "la") -> None:
    alpha, col = patch
    h, w = alpha.shape[:2]
    if anchor[0] == "r":
        x -= w
    region = frame[y:y + h, x:x + w]
    region[:] = region * (1 - alpha) + col * alpha


def ink_edge(inked: np.ndarray, start: int, step: int, reach: float = 0.55, gap: float = 0.05) -> int:
    """walk away from a staff until a blank band `gap` inches tall; everything before it belongs to this line"""
    last, blank = start, 0
    for row in range(start, int(np.clip(start + step * reach * DPI, 0, len(inked) - 1)), step):
        if inked[row]:
            last, blank = row, 0
        else:
            blank += 1
            if blank >= gap * DPI:
                break
    return last


def system_frames(pages_dir: Path, measures):
    """one prepared background per line of the score, plus where its bars land on screen"""
    systems = []
    for i, (_, x, y, sx, sy, pg) in enumerate(measures):
        if not systems or systems[-1]["key"] != (pg, round(y)):
            systems.append({"key": (pg, round(y)), "bars": []})
        systems[-1]["bars"].append(i)
    pages = {}
    box_w, box_h = W - 2 * MARGIN_X, H - 2 * MARGIN_Y - 40  # no header: the score gets the whole stage
    for s in systems:
        pg, _ = s["key"]
        if pg not in pages:
            pages[pg] = Image.open(pages_dir / f"page-{pg + 1}.png")
        page = pages[pg]
        ys = [measures[b][2] for b in s["bars"]]
        x0, x1 = 0.42 * DPI, page.width - 0.42 * DPI
        top, bottom = min(ys), max(measures[b][2] + measures[b][4] for b in s["bars"])
        inked = (np.asarray(page.convert("L").crop((int(x0), 0, int(x1), page.height))) < 200).any(axis=1)
        y0 = ink_edge(inked, int(top), -1) - 0.03 * DPI  # stop at the blank band, so a neighbouring line's marks stay out
        y1 = ink_edge(inked, int(bottom), 1) + 0.03 * DPI
        crop = page.crop((int(x0), int(y0), int(x1), int(y1)))
        scale = min(box_w / crop.width, box_h / crop.height)
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
        ox, oy = (W - crop.width) // 2, MARGIN_Y - 10 + (box_h - crop.height) // 2
        base = np.empty((H, W, 3), dtype=np.float32)
        base[:] = pearl()
        ink = np.asarray(crop.convert("RGB"), dtype=np.float32) / 255.0  # the score printed onto the pearl paper
        base[oy:oy + crop.height, ox:ox + crop.width] *= ink
        s.update(base=base.clip(0, 255).astype(np.uint8), map=lambda px, py, ox=ox, oy=oy, x0=x0, y0=y0, k=scale: (ox + (px - x0) * k, oy + (py - y0) * k))
    return systems


def footer(frame: np.ndarray, t: float, dur: float, section: str) -> None:
    """one quiet line: the piece on the left, the section on the right, a hairline of progress beneath"""
    y = H - 64
    frame[y:y + 2, MARGIN_X:W - MARGIN_X] = HAIR
    frame[y:y + 2, MARGIN_X:MARGIN_X + int((W - 2 * MARGIN_X) * min(1.0, t / dur))] = ACCENT
    ded = text_patch(DEDICATION + "   ·   ", "ital", 32, STONE)
    paste(frame, ded, MARGIN_X, y - 62)
    paste(frame, text_patch(TITLE, "song", 32, STONE), MARGIN_X + ded[0].shape[1], y - 64)
    paste(frame, text_patch(section, "ital", 32, STONE), W - MARGIN_X, y - 62, "ra")


def title_card() -> np.ndarray:
    frame = pearl().copy()
    cx = W // 2
    for patch, y in [(text_patch(DEDICATION, "ital", 52, STONE), 720), (text_patch(TITLE, "song", 200, INK), 830),
                     (text_patch(SUBTITLE, "ital", 72, STONE), 1110)]:
        paste(frame, patch, cx - patch[0].shape[1] // 2, y)
    frame[1260:1264, cx - 90:cx + 90] = ACCENT
    line = text_patch(piece_mod.INSTRUMENTATION, "ital", 44, STONE)
    paste(frame, line, cx - line[0].shape[1] // 2, 1320)
    return frame.clip(0, 255).astype(np.uint8)


def dip(a: np.ndarray, b: np.ndarray, k: float, paper: np.ndarray) -> np.ndarray:
    """fade a out to plain paper, then b in from it, so title and score never overlap"""
    return blend(a, paper, 2 * k) if k < 0.5 else blend(paper, b, 2 * k - 1)


def blend(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    k = 0.5 - 0.5 * np.cos(np.pi * min(1.0, max(0.0, k)))  # ease in and out
    return (a.astype(np.float32) * (1 - k) + b.astype(np.float32) * k).astype(np.uint8)


SHOW_PLAYHEAD = False
BAR_TINT, BAR_FADE = 0.13, 0.18
GLOW = (232, 205, 150)  # light warm champagne for the bar being played (a darker gold would read grey on pearl)  # how strongly the current bar is tinted; seconds to hand over to the next bar
SMOOTH_SIGMA = 4.0  # frames (~0.13 s): the playhead glides instead of hopping from note to note


def smooth_track(raw: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Gaussian-smooth the playhead within each line of the score, then keep it from ever stepping back"""
    r = int(3 * SMOOTH_SIGMA)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / SMOOTH_SIGMA) ** 2)
    k /= k.sum()
    out = raw.copy()
    edges = np.flatnonzero(np.diff(groups)) + 1
    for a, b in zip(np.r_[0, edges], np.r_[edges, len(raw)]):
        seg = np.pad(raw[a:b], r, mode="edge")
        out[a:b] = np.maximum.accumulate(np.convolve(seg, k, mode="valid"))
    return out


def draw_playhead(frame: np.ndarray, x: float, y0: int, y1: int, accent: np.ndarray) -> None:
    """an anti-aliased 4 px line with a faint 24 px halo, placed at a fractional pixel position"""
    cols = np.arange(int(x) - 14, int(x) + 15)

    def cover(half: float) -> np.ndarray:  # how much of each pixel column the band [x-half, x+half] covers
        return np.clip(np.minimum(cols + 1, x + half) - np.maximum(cols, x - half), 0, 1)
    alpha = cover(2.0) + (1 - cover(2.0)) * 0.1 * cover(12.0)
    region = frame[y0 - 16:y1 + 16, cols[0]:cols[-1] + 1].astype(np.float32)
    a = alpha[None, :, None]
    frame[y0 - 16:y1 + 16, cols[0]:cols[-1] + 1] = (region * (1 - a) + accent * a).astype(np.uint8)


def follow_video(pages_dir: Path, audio: Path, out: Path, dur: float) -> None:
    measures = read_pos(pages_dir / "pos.mpos")
    paths = measure_paths(measures, read_pos(pages_dir / "pos.spos"))
    systems = system_frames(pages_dir, measures)
    sys_of = {b: i for i, s in enumerate(systems) for b in s["bars"]}
    bars_t = bar_times()
    n_bars = len(measures)
    preview = [float(x) for x in __import__("os").environ.get("PREVIEW_TIMES", "").split(",") if x]
    ff = None if preview else subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a",
                           "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-tune", "stillimage", "-pix_fmt", "yuv420p",
                           "-profile:v", "high", "-level", "5.2", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", "-map_metadata", "-1",
                           str(out)], stdin=subprocess.PIPE)
    accent = np.array(ACCENT, dtype=np.float32)
    card = title_card()
    paper = pearl().astype(np.uint8)
    n_frames = int(dur * FPS)
    bars, raw_x = np.zeros(n_frames, dtype=int), np.zeros(n_frames)
    for f in range(n_frames):  # first pass: where the playhead should be, frame by frame
        t = f / FPS
        bar = min(n_bars - 1, int(np.searchsorted(bars_t, t, side="right")) - 1)
        frac = min(1.0, (t - bars_t[bar]) / (bars_t[bar + 1] - bars_t[bar])) if bar + 1 < len(bars_t) else 1.0
        bars[f], raw_x[f] = bar, systems[sys_of[bar]]["map"](float(np.interp(frac, *paths[bar])), 0)[0]
    track = smooth_track(raw_x, np.array([sys_of[b] for b in bars]))
    prev_sys, changed_at = 0, -10.0
    for f in range(n_frames):
        t = f / FPS
        bar = int(bars[f])
        si = sys_of[bar]
        if si != prev_sys:
            prev_sys, changed_at, old = si, t, frame_base_prev
        s = systems[si]
        frame = s["base"].copy()
        # 不画播放线（用户：可以不要红线）：只把正在演奏的小节轻轻染色，换小节时柔和交接
        ease = min(1.0, (t - bars_t[bar]) / BAR_FADE)
        tints = [(bar, ease)]
        if bar > 0 and sys_of[bar - 1] == si and ease < 1.0:
            tints.append((bar - 1, 1.0 - ease))
        for b_, k in tints:
            _, mx, my, msx, msy, _ = measures[b_]
            (x0, y0), (x1, y1) = s["map"](mx, my), s["map"](mx + msx, my + msy)
            hl = frame[int(y0):int(y1), int(x0):int(x1)]
            a_ = BAR_TINT * k
            hl[:] = (hl * (1 - a_) + np.array(GLOW, np.float32) * a_).astype(np.uint8)
        if SHOW_PLAYHEAD:
            draw_playhead(frame, float(track[f]), int(y0), int(y1), accent)
        section = next(f"{l}  ·  {n}" if l else n for b, l, n in reversed(SECTIONS) if bar >= b)
        footer(frame, t, dur, section)
        if t - changed_at < FADE:  # cross-fade from the previous line of the score
            frame = blend(old, frame, (t - changed_at) / FADE)
        frame_base_prev = frame
        if t < TITLE_HOLD + TITLE_FADE:  # open on the title, then let the score come in under the harp
            frame = dip(card, frame, (t - TITLE_HOLD) / TITLE_FADE, paper)
        if t > dur - END_FADE - 1.0:  # as the last chord rings, return to the title
            frame = dip(frame, card, (t - (dur - END_FADE - 1.0)) / END_FADE, paper)
        if preview:
            if any(abs(t - p) < 0.5 / FPS for p in preview):
                Image.fromarray(frame).save(out.with_name(f"preview_{t:05.1f}.png"))
            continue
        ff.stdin.write(frame.tobytes())
    if ff:
        ff.stdin.close()
        ff.wait()


def cover_video(audio: Path, out: Path, still: Path, dur: float) -> None:
    Image.fromarray(title_card()).save(still)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", str(still), "-i", str(audio),
                    "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-tune", "stillimage", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "320k", "-t", f"{dur:.3f}", "-movflags", "+faststart", "-map_metadata", "-1", str(out)],
                   check=True)


def main() -> None:
    pages_dir, audio, out_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
                               capture_output=True, text=True, check=True).stdout)
    what = sys.argv[4] if len(sys.argv) > 4 else "all"
    if what in ("all", "cover"):
        cover_video(audio, out_dir / f"{TITLE}.mp4", out_dir / f"{TITLE}_封面.png", dur)
    if what in ("all", "follow"):
        follow_video(pages_dir, audio, out_dir / f"{TITLE}_演奏过程_4K.mp4", dur)
    sys.stdout.write(f"DONE {out_dir}\n")


if __name__ == "__main__":
    main()
