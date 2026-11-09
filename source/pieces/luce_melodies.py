# 晨光牧歌 · 第三轮旋律（第二轮 A–D 被否：太平，没有情感）。
# 情感从三处来：旋律大跳后用倚音叹息着落下（不协和 → 解决）；和声有转折；演奏有快慢呼吸和强弱起伏。
from dataclasses import replace

from score import SALAMANDER, VSCO, Note, Part, Piece, humanize, legato, legato_pedal, n, notes

VOICING = {
    "F": "F2 C3 A3 C4", "Dm": "D2 A2 F3 A3", "Bb": "Bb1 F2 D3 F3", "C7": "C2 G2 Bb3 E3", "Am": "A1 E2 C3 E3",
    "D7": "D2 A2 F#3 C4", "Gm": "G1 D2 Bb2 D3", "C": "C2 G2 E3 G3", "G/B": "B1 G2 D3 G3", "Ab": "Ab1 Eb2 C3 Eb3",
    "F/A": "A1 F2 C3 F3", "Gm7": "G1 D2 Bb2 F3", "Eb": "Eb2 Bb2 G3 Bb3", "A7": "A1 E2 C#3 G3", "Bbm": "Bb1 F2 Db3 F3", "F/C": "C2 F2 A2 C3",
    "BbMaj": "Bb1 F2 D3 F3", "G7": "G1 D2 B2 F3", "Em": "E2 B2 G3 B3", "G": "G1 D2 B2 D3", "B7": "B1 F#2 D#3 A3",
}
# E2（用户：E 还可以，但后面情绪没有加强）：前 4 小节不动；5–8 同一个动机抬高一层，经 E♭ 和 A7 把紧张拉起来；
# 9–12 高潮：右手八度、左手十六分音符，第 10 小节到全曲最高的 B♭5，第 11 小节转小 iv（B♭m）是最揪心的一下；13–14 才放下来。
CANDIDATES = {
    "H": dict(title="两声部对话"),
    "J": dict(title="层层欢歌"),
    "K": dict(title="层层欢歌_交响"),
    "E2": dict(title="倚音的渴望_情绪加强", bpm=58, per_bar=4,
               chords=["F", "Dm", "Bb", "C7", "F/A", "Gm7", "Eb", "A7", "Dm", "Bb", "Bbm", "F/C", "Gm,C7", "F"],
               intensity=[0, 0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 2, 1, 0],
               tempo=[0.98, 1.03, 1.05, 0.93, 1.0, 1.04, 1.08, 1.06, 1.08, 1.06, 0.98, 0.9, 0.86, 0.74],
               line=("C5:1 A5:2 G5:1 G5:1.5 F5:0.5 D5:2 Bb4:1 G5:2 F5:1 F5:1.5 E5:0.5 C5:2 "
                     "C5:1 A5:2 Bb5:1 Bb5:1.5 A5:0.5 G5:2 Eb5:1 Bb5:2 G5:1 C#5:1 E5:1 G5:1.5 F5:0.5 "
                     "F5:1 A5:2 G5:1 D5:1 F5:1 Bb5:2 Bb5:1.5 Ab5:0.5 F5:2 A5:1.5 G5:0.5 F5:1 C5:1 "
                     "Bb4:0.5 D5:0.5 G5:1 F5:1 E5:1 G5:1 F5:3")),
    "E": dict(title="倚音的渴望", bpm=58, per_bar=4,
              chords=["F", "Dm", "Bb", "C7", "Am", "D7", "Gm,C7", "F"],
              line=("C5:1 A5:2 G5:1 G5:1.5 F5:0.5 D5:2 Bb4:1 G5:2 F5:1 F5:1.5 E5:0.5 C5:2 "
                    "C5:1 E5:1 A5:1.5 G5:0.5 A5:1.5 G5:0.5 F#5:1 G5:1 Bb4:0.5 D5:0.5 G5:1 F5:1 E5:1 G5:1 F5:3")),
    "F": dict(title="突然照进来的光", bpm=62, per_bar=4,
              chords=["C", "G/B", "Am", "F", "Ab", "BbMaj", "G7", "C"],
              line=("E5:2 G5:1.5 E5:0.5 D5:1 B4:1 D5:1.5 G5:0.5 A5:2 G5:1 E5:1 F5:1.5 E5:0.5 C5:2 "
                    "Eb5:1 C5:1 Ab5:2 G5:1.5 F5:0.5 D5:2 F5:2 D5:2 D5:1 C5:3")),
    "G": dict(title="从小调走进阳光", bpm=54, per_bar=3,
              chords=["Em", "Am", "D7", "G", "Am", "B7", "C", "D7", "G", "G"],
              line=("B4:1 G5:1.5 F#5:0.5 E5:1.5 D5:0.5 C5:1 A4:1 F#5:1.5 E5:0.5 D5:1 B4:2 "
                    "C5:1 E5:1 A5:1 D#5:1 F#5:1 A5:1 G5:1.5 F#5:0.5 E5:1 E5:1 D5:0.5 C5:0.5 A4:1 G4:1 B4:1 G5:1 G5:3")),
}


def melody(line: str, per_bar: int, intensity=None) -> list[Note]:
    raw = notes(0.0, line, 64)
    out = []
    for i, x in enumerate(raw):
        vel = 58 + (x.pitch - 72) * 1.5  # higher notes sing louder, as a voice does
        following = raw[i + 1] if i + 1 < len(raw) else None
        preceding = raw[i - 1] if i else None
        if following and 0 < x.pitch - following.pitch <= 2 and x.dur >= 1:
            vel += 7  # the leaning note
        if preceding and 0 < preceding.pitch - x.pitch <= 2 and preceding.dur >= 1:
            vel -= 9  # its gentle resolution
        level = intensity[int(x.beat // per_bar)] if intensity else 0
        vel = round(max(40, min(104, vel + level * 7)))
        out.append(Note(x.beat, x.dur, x.pitch, vel))
        if level >= 2:  # right-hand octaves at the height of the phrase
            out.append(Note(x.beat, x.dur, x.pitch - 12, vel - 14))
    return out


def accompaniment(chords: list[str], per_bar: int, intensity=None) -> tuple[list[Note], list[float]]:
    out, changes, bar_start = [], [], 0.0
    for bar, spec in enumerate(chords):
        level = intensity[bar] if intensity else 0
        names = spec.split(",")
        span = per_bar / len(names)
        for k, name in enumerate(names):
            start = bar_start + k * span
            changes.append(start)
            low, a, b, c = VOICING[name].split()
            out.append(Note(start, span, n(low), 50 + level * 8))
            if level >= 1:  # octave in the bass as the music grows
                out.append(Note(start, span, n(low) - 12, 42 + level * 8))
            step = 0.25 if level >= 2 else 0.5  # the left hand doubles its motion at the height
            shape = [a, b, c, b, c, b, a, b] * 4
            for i, p in enumerate(shape[: int(span / step) - 1]):
                out.append(Note(start + step * (i + 1), step * 0.96, n(p), 38 + level * 4 - (i % 2) * 3))
        bar_start += per_bar
    return out, changes


def rubato(bpm: float, per_bar: int, bars: int) -> tuple[tuple[float, float], ...]:
    """push gently into the middle of each four-bar phrase, relax at its end; a long breath at the very end"""
    out = []
    for bar in range(bars):
        pos = bar % 4
        factor = {0: 0.98, 1: 1.04, 2: 1.06, 3: 0.92}[pos]
        if bar == bars - 1:
            factor = 0.78
        elif bar == bars - 2:
            factor = 0.88
        out.append((float(bar * per_bar), round(bpm * factor, 1)))
    return tuple(out[1:])


def seconds(bpm: float, tempo, total: float) -> float:
    t, cur, now = 0.0, 0.0, bpm
    for b, v in tempo:
        t, cur, now = t + (b - cur) * 60 / now, b, v
    return t + (total - cur) * 60 / now


def piece(tag: str) -> Piece:
    if tag == "H":
        return h_piece()
    if tag == "J":
        return j_piece()
    if tag == "K":
        return k_piece()
    c = CANDIDATES[tag]
    total = sum(float(t.split(":")[1]) for t in c["line"].split())
    bars = len(c["chords"])
    assert total == bars * c["per_bar"], (tag, total)
    left, changes = accompaniment(c["chords"], c["per_bar"], c.get("intensity"))
    right = legato(melody(c["line"], c["per_bar"], c.get("intensity")), overlap=0.08)
    tempo = (tuple((float(i * c["per_bar"]), round(c["bpm"] * f, 1)) for i, f in enumerate(c["tempo"]))[1:]
             if "tempo" in c else rubato(c["bpm"], c["per_bar"], bars))
    all_notes = humanize(tuple(right + left), 31, timing=0.012, vel=2)
    pedal = legato_pedal(changes, total + 2)
    return Piece(key=f"luce_m{tag}", bpm=c["bpm"], beats=total, swing=0.5, room=1.8, tempo=tempo,
                 seconds=round(seconds(c["bpm"], tempo, total) + 3.0, 2), fade=2.0,
                 parts=(Part("piano", SALAMANDER, 0, 0, all_notes, pedal=pedal, send=0.24),))


# H（用户：还是没有感情，学巴赫/莫扎特的节奏；Codex 评审后的二声部改写）：左手是独立声部，有模仿、延留、问答和休止。
H_RIGHT = ("C5:0.5 A5:1.5 G5:0.5 F5:1.5 | F5:1 E5:1 D5:0.5 E5:0.5 C5:1 | Bb4:1 D5:0.5 F5:0.5 E5:1 D5:1 | E5:0.5 D5:1.5 G5:1 r:1 | "
           "A4:2 C5:1 D5:1 | E5:0.5 F5:0.5 A5:1 G5:0.5 F5:0.5 E5:1 | F5:1 E5:0.5 D5:0.5 C5:1 E5:1 | F5:2 A5:0.5 G5:0.5 F5:0.5 r:0.5 | "
           "C5:0.5 A5:1.5 G5:1 F5:1 | G5:0.5 A5:0.5 Bb5:1.5 A5:0.5 G5:1 | D5:1 F5:3 | F5:1 E5:1 D5:0.5 E5:0.5 G5:1 | F5:2 E5:0.5 F5:0.5 D5:1 | G5:1 F5:3")
H_LEFT = ("F3:2 E3:1 D3:1 | C3:2 G3:1 E3:1 | D3:2 C3:1 Bb2:1 | G2:1 Bb2:1 C3:2 | C3:0.5 A3:2 G3:0.5 F3:1 | D3:2 Bb2:1 C3:1 | C3:2 G2:1 C3:1 | "
          "F3:1 E3:0.5 D3:0.5 C3:1 A2:1 | D3:2 E3:1 F3:1 | Bb2:2 C3:1 Bb2:1 | G2:1 Bb2:1 C3:2 | C3:2 Bb2:2 | A2:1 C3:1 F3:1 Bb2:1 | F3:4")
H_CHANGES = [0, 2, 3, 4, 8, 10, 11, 12, 14, 16, 19, 20, 22, 23, 24, 28, 32, 36, 38, 39, 40, 42, 43, 44, 46, 48, 51, 52]
H_LEVEL = [56, 54, 57, 50, 53, 58, 55, 48, 56, 62, 57, 54, 50, 45]
H_LATE = {5.0: 0.039, 6.0: 0.02, 45.0: 0.039, 46.0: 0.02, 38.5: 0.044}  # the held breath before a resolution, in beats


def h_voice(spec: str) -> list[Note]:
    for bar in spec.split("|"):
        assert sum(float(t.split(":")[1]) for t in bar.split()) == 4, bar
    return notes(0.0, spec.replace("|", " "), 60)


def h_level(b: float) -> float:
    bar, frac = int(b // 4), (b % 4) / 4
    return H_LEVEL[bar] + (H_LEVEL[min(bar + 1, 13)] - H_LEVEL[bar]) * frac


def h_right() -> list[Note]:
    raw = h_voice(H_RIGHT)
    tied = {(2.5, 4.0), (41.0, 44.0)}
    joined, skip = [], set()
    for x in raw:
        if x.beat in skip:
            continue
        for a, b in tied:
            if x.beat == a:
                other = next(y for y in raw if y.beat == b)
                x = Note(x.beat, b - a + other.dur, x.pitch, x.vel)
                skip.add(b)
        joined.append(x)
    out = []
    for i, x in enumerate(joined):
        vel = h_level(x.beat) + (-5 if x.dur <= 0.5 else 0) + (-3 if 16 <= x.beat < 20 else 0)
        nxt = joined[i + 1] if i + 1 < len(joined) else None
        prev = joined[i - 1] if i else None
        if nxt and 0 < x.pitch - nxt.pitch <= 2 and x.dur >= 1:
            vel += 3
        if prev and 0 < prev.pitch - x.pitch <= 2 and prev.dur >= 1:
            vel -= 5
        if x.beat == 0.5:
            vel = 62
        if x.pitch == n("Bb5"):
            vel = 66
        if x.beat == 53.0:
            vel = 42
        ends_before_rest = x.beat + x.dur in (15.0, 31.5)
        offset = H_LATE.get(x.beat, 0.0) + (0.0 if x.beat in (0.0, 16.0, 32.0) else 0.012)
        dur = x.dur * 0.8 if ends_before_rest else x.dur + (0.015 if nxt and nxt.pitch != x.pitch else -0.03 if nxt else 0.0)
        out.append(Note(x.beat + offset, dur, x.pitch, round(vel)))
    return out


def h_left() -> list[Note]:
    return [Note(x.beat, x.dur * 0.93, x.pitch, round(h_level(x.beat) - 12 + (7 if 16 <= x.beat < 20 else 0))) for x in h_voice(H_LEFT)]


def h_piece() -> Piece:
    tempo = ((53.0, 56.3), (54.0, 55.2), (55.0, 54.2))
    pedal = []
    for down, up in legato_pedal(H_CHANGES, 58.0):
        pedal.append((down, 15.0 if up == 16 else 31.5 if up == 32 else up))
    return Piece(key="luce_mH", bpm=58, beats=56.0, swing=0.5, room=1.8, tempo=tempo, seconds=round(seconds(58, tempo, 56.0) + 3.0, 2), fade=2.0,
                 parts=(Part("piano", SALAMANDER, 0, 0, humanize(tuple(h_right() + h_left()), 32, timing=0.003, vel=1), pedal=tuple(pedal), send=0.24),))


# J（用户：没有欢快的感觉，应该层层递进）：D 大调快板，巴洛克"音符越来越密"的变奏。同一主题奏四遍，再加两小节结尾：
#   L1 右手主题，左手四分音符   L2 左手变成八分音符   L3 右手变成十六分音符跑动   L4 右手八度，左手十六分音符
J_THEME = ("A4:0.5 D5:0.5 F#5:0.5 A5:0.5 F#5:1 D5:1 | B4:0.5 D5:0.5 G5:1 E5:0.5 F#5:0.5 G5:0.5 E5:0.5 | "
           "B4:0.5 D5:0.5 F#5:1 C#5:0.5 E5:0.5 A5:1 | G5:0.5 F#5:0.5 E5:0.5 D5:0.5 C#5:1 A4:1 | "
           "A4:0.5 D5:0.5 F#5:0.5 A5:0.5 A5:1 F#5:1 | B4:0.5 D5:0.5 F#5:0.5 B5:0.5 B5:0.5 A5:0.5 G5:1 | "
           "G5:0.5 F#5:0.5 E5:1 E5:0.5 D5:0.5 C#5:1 | D5:2 A4:0.5 B4:0.5 C#5:0.5 E5:0.5")
J_CHORDS = ["D", "D", "G", "A", "Bm", "F#m", "G", "A", "D", "D/F#", "Bm", "G", "Em", "A7", "D", "D"]
J_TONES = {"D": "D2 A2 D3 F#3", "G": "G2 D3 G3 B3", "A": "A2 E3 A3 C#4", "A7": "A2 E3 G3 C#4", "Bm": "B2 F#3 B3 D4",
           "F#m": "F#2 C#3 F#3 A3", "D/F#": "F#2 D3 A3 D4", "Em": "E2 B2 G3 B3"}
J_SCALE = [n(f"{name}{octave}") for octave in range(3, 7) for name in ("D", "E", "F#", "G", "A", "B", "C#")]
J_SCALE = sorted(J_SCALE)
J_BAR_BEATS, J_LAYER_BARS = 4, 8
J_TOP = n("B5")


def j_vel(b: float, base: int) -> int:
    pos = b % 4
    accent = 7 if pos == 0 else 4 if pos == 2 else 1 if pos in (1, 3) else -3
    return base + accent


def j_step(pitch: int, by: int) -> int:
    near = min(range(len(J_SCALE)), key=lambda i: abs(J_SCALE[i] - pitch))
    return J_SCALE[near + by]


def j_theme(start: float, base: int, octave: bool = False) -> list[Note]:
    out = []
    for x in notes(start, J_THEME.replace("|", " "), base):
        vel = j_vel(x.beat, base)
        out.append(Note(x.beat, x.dur * 0.86, x.pitch, vel))
        if octave:
            out.append(Note(x.beat, x.dur * 0.86, x.pitch - 12, vel - 10))
    return out


def j_running(start: float, base: int) -> list[Note]:
    """every theme note becomes running sixteenths around it"""
    out = []
    for x in notes(start, J_THEME.replace("|", " "), base):
        for i in range(int(x.dur / 0.25)):
            shape = (0, 1, 0, -1)[i % 4]
            pitch = j_step(x.pitch, shape) if shape else x.pitch
            if pitch > J_TOP:
                pitch = j_step(x.pitch, -1)
            b = x.beat + i * 0.25
            out.append(Note(b, 0.22, pitch, j_vel(b, base) - (0 if i == 0 else 4)))
    return out


def j_left(start: float, level: int, base: int) -> list[Note]:
    out = []
    for i, name in enumerate(J_CHORDS):
        a, b_, c, d = [n(p) for p in J_TONES[name].split()]
        t0 = start + i * 2
        if level == 1:
            seq, step = (a, b_), 1.0
        elif level == 2:
            seq, step = (a, c, d, c), 0.5
        elif level == 3:
            seq, step = (a, c, d, c), 0.5
            out.append(Note(t0, 0.9, a - 12, base + 2))
        else:
            seq, step = (a, b_, c, d, c, d, c, b_), 0.25
            out.append(Note(t0, 0.9, a - 12, base + 4))
        for k, pitch in enumerate(seq):
            b = t0 + k * step
            out.append(Note(b, step * 0.86, pitch, j_vel(b, base) - (0 if k == 0 else 4)))
    return out


def j_coda(start: float) -> list[Note]:
    run = "D4 F#4 A4 D5 F#5 A5 F#5 D5 C#4 E4 G4 A4 C#5 E5 G5 E5".split()
    out = [Note(start + i * 0.25, 0.22, n(p), 86 + (i % 4 == 0) * 6) for i, p in enumerate(run)]
    out += [Note(start + i * 0.5, 0.45, n(p), 84) for i, p in enumerate("D2 A2 D3 A2 A2 E3 A3 E3".split())]
    final = "D2 D3 A3 D4 F#4 A4 D5 F#5"
    return out + [Note(start + 4 + i * 0.03, 4.5, n(p), 92 - i * 2) for i, p in enumerate(final.split())]


def j_piece() -> Piece:
    for bar in J_THEME.split("|"):
        assert sum(float(t.split(":")[1]) for t in bar.split()) == J_BAR_BEATS, bar
    layer = J_LAYER_BARS * J_BAR_BEATS
    line = (j_theme(0, 62) + j_left(0, 1, 46)
            + j_theme(layer, 70) + j_left(layer, 2, 52)
            + j_running(layer * 2, 72) + j_left(layer * 2, 3, 60)
            + j_theme(layer * 3, 92, octave=True) + j_left(layer * 3, 4, 66)
            + j_coda(layer * 4))
    total = layer * 4 + 8.0
    tempo = ((float(layer), 112.0), (float(layer * 2), 116.0), (float(layer * 3), 120.0), (float(layer * 4 + 2), 108.0), (float(layer * 4 + 4), 92.0))
    return Piece(key="luce_mJ", bpm=108, beats=total, swing=0.5, room=1.4, tempo=tempo, seconds=round(seconds(108, tempo, total) + 1.5, 2), fade=1.5,
                 parts=(Part("piano", SALAMANDER, 0, 0, humanize(tuple(line), 33, timing=0.006, vel=2), send=0.18),))


# K（用户：可以，适当加一点交响）：J 的钢琴一个音不动，乐队跟着分层加入。
#   L1 只有钢琴   L2 大提琴、中提琴拨弦   L3 弦乐长音铺开   L4 小提琴断弓齐奏主题，圆号、低音提琴、管风琴加入   结尾全奏 + 管钟
K_TOP_LINE = "F#5 D5 G5 E5 F#5 C#5 B4 E5 F#5 A5 F#5 G5 G5 E5 F#5 D5".split()


def k_part(name, font, channel, line, seed, target, pan, send=0.3):
    return Part(name, f"{VSCO}/{font}.sfz", 0, channel, humanize(tuple(line), seed, timing=0.008, vel=2), pan=pan, send=send, target=target)


def k_tones(name):
    return [n(x) for x in J_TONES[name].split()]


def k_each(start, fn):
    return [x for i, name in enumerate(J_CHORDS) for x in fn(start + i * 2, name, i)]


def k_piece() -> Piece:
    base = j_piece()
    layer = J_LAYER_BARS * J_BAR_BEATS
    l2, l3, l4, coda = layer, layer * 2, layer * 3, layer * 4
    cello_pizz = k_each(l2, lambda t, c, i: [Note(t, 0.6, k_tones(c)[0], 66), Note(t + 1, 0.6, k_tones(c)[1], 56)])
    viola_pizz = k_each(l2, lambda t, c, i: [Note(t + 0.5, 0.4, k_tones(c)[2], 50), Note(t + 1.5, 0.4, k_tones(c)[2], 46)])
    cello_sus = (k_each(l3, lambda t, c, i: [Note(t, 2.05, k_tones(c)[0], 62)]) + k_each(l4, lambda t, c, i: [Note(t, 2.05, k_tones(c)[0], 78)])
                 + [Note(coda, 2.05, n("D3"), 76), Note(coda + 2, 2.05, n("A2"), 76), Note(coda + 4, 4.5, n("D3"), 82)])
    violas = (k_each(l3, lambda t, c, i: [Note(t, 2.05, k_tones(c)[3], 58)]) + k_each(l4, lambda t, c, i: [Note(t, 2.05, k_tones(c)[3], 72)])
              + [Note(coda, 2.05, n("A3"), 72), Note(coda + 2, 2.05, n("G3"), 72), Note(coda + 4, 4.5, n("A3"), 78)])
    violins = ([Note(l3 + i * 2, 2.05, n(p), 62 + i) for i, p in enumerate(K_TOP_LINE)]
               + [Note(coda, 2.05, n("F#5"), 80), Note(coda + 2, 2.05, n("E5"), 80), Note(coda + 4, 4.5, n("F#5"), 86), Note(coda + 4, 4.5, n("D5"), 82)])
    spic = [Note(x.beat, x.dur, x.pitch, x.vel) for x in j_theme(l4, 84)]
    bass = k_each(l4, lambda t, c, i: [Note(t, 2.05, k_tones(c)[0] - 12 if k_tones(c)[0] - 12 >= 28 else k_tones(c)[0], 70)]) + [Note(coda + 4, 4.5, n("D2"), 76)]
    horn = k_each(l4, lambda t, c, i: [Note(t, 2.05, k_tones(c)[2], 66)]) + [Note(coda + 4, 4.5, n("D4"), 72), Note(coda + 4, 4.5, n("A3"), 70)]
    organ = k_each(l4, lambda t, c, i: [Note(t, 2.0, x, 52) for x in k_tones(c)[1:]]) + [Note(coda + 4, 4.5, n(x), 60) for x in "D3 A3 D4 F#4".split()]
    bells = [Note(coda + 4, 4.0, n("D5"), 62)]
    parts = (
        base.parts[0],
        k_part("violins", "ViolinEnsSusVib", 1, legato(violins, overlap=0.05), 41, -9, 46),
        k_part("spic", "ViolinEnsSpic", 2, spic, 42, -6, 46, 0.24),
        k_part("violas", "ViolaEnsSusVib", 3, legato(violas, overlap=0.05), 43, -12, 76),
        k_part("cello", "CelloEnsSusVib", 4, legato(cello_sus, overlap=0.05), 44, -10, 84),
        k_part("cellopizz", "CelloEnsPizz", 5, cello_pizz, 45, -9, 84, 0.26),
        k_part("violapizz", "ViolaEnsPizz", 6, viola_pizz, 46, -13, 72, 0.26),
        k_part("bass", "ContrabassSusVB", 7, legato(bass, overlap=0.05), 47, -14, 90),
        k_part("horn", "FHornSus", 8, legato(horn, overlap=0.05), 48, -14, 34, 0.4),
        k_part("organ", "OrganQuiet", 10, organ, 49, -17, 64, 0.4),
        k_part("bells", "TubularBells", 11, bells, 50, -12, 54, 0.5),
    )
    return replace(base, key="luce_mK", parts=parts, room=1.7, balance_active=True)
