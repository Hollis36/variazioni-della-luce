# 作曲层：把一首 9 秒小曲写成 MIDI（用户：从底层思考怎么做出好听的音乐 → 先按乐理作曲，再用真实采样演奏）。
# 曲子以“拍”为单位写，120 BPM 时一拍 0.5 秒，视频的四段（2 s / 3 s / 2 s / 2 s）正好落在第 0、4、10、14 拍，
# 和弦在镜头切换处换，最后一个和弦在第 14 拍（7.0 s，小柠递杯）落下并一直响到结束。
from dataclasses import dataclass, field
import random

import mido

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
TPB = 960  # ticks per beat


def n(name: str) -> int:
    """'C#4' / 'Bb2' -> MIDI number (C4 = 60)."""
    pitch, octave = name[:-1], int(name[-1])
    return 12 * (octave + 1) + NOTE[pitch[0]] + pitch[1:].count("#") - pitch[1:].count("b")


@dataclass(frozen=True)
class Note:
    beat: float
    dur: float
    pitch: int
    vel: int


@dataclass(frozen=True)
class Part:
    """one instrument: a General MIDI program on its own channel, rendered from `font`"""
    name: str
    font: str
    program: int
    channel: int
    notes: tuple[Note, ...]
    pedal: tuple[tuple[float, float], ...] = ()  # sustain pedal (down, up) in beats
    volume: int = 100
    pan: int = 64
    send: float = 0.2  # how much of the part goes into the shared room
    level: float = 1.0  # trim after rendering, linear
    expression: tuple[tuple[float, int], ...] = ()  # CC11 swells (beat, 0–127), interpolated; strings breathe with it
    target: float | None = None  # if set, the mix sets this part's level to `target` dB relative to the first part


@dataclass(frozen=True)
class Piece:
    key: str
    bpm: float
    beats: float
    parts: tuple[Part, ...]
    swing: float = 2 / 3  # where the off-beat eighth lands inside the beat (0.5 = straight)
    meta: dict = field(default_factory=dict)
    tempo: tuple[tuple[float, float], ...] = ()  # later tempo changes (beat, bpm), e.g. a ritardando at the end
    room: float = 1.25  # reverb time (RT60, seconds) of the shared room
    seconds: float = 9.0  # rendered length (the video slot); longer pieces set their own
    fade: float = 0.6  # fade at the very end, so the last chord's ring lands exactly on `seconds`
    balance_active: bool = False  # balance parts by their level while playing (for pieces where parts enter and leave)


def chord(beat: float, dur: float, names: str, vel: int, roll: float = 0.0) -> list[Note]:
    """a voicing, lowest note first; `roll` spreads the notes upward like a gentle arpeggio (in beats)"""
    return [Note(beat + i * roll, dur - i * roll, n(name), vel - 2 * i) for i, name in enumerate(names.split())]


def notes(beat0: float, spec: str, vel: int) -> list[Note]:
    """a line written as 'D5:0.5 F5:0.5 A5:1 r:0.5 ...' (pitch:beats, r = rest), starting at beat0"""
    out, beat = [], beat0
    for token in spec.split():
        name, dur = token.split(":")
        if name != "r":
            out.append(Note(beat, float(dur), n(name), vel))
        beat += float(dur)
    return out


SIGNATURE_TOP = 83  # B5: the bell stays bright without turning shrill on phone speakers


def legato_pedal(changes: list[float], end: float) -> tuple[tuple[float, float], ...]:
    """syncopated pedalling: lift exactly on each chord change and press again just after it, so the
    harmonies connect without blurring into each other"""
    edges = list(changes) + [end]
    return tuple((max(0.0, a + (0.08 if i else 0.0)), b) for i, (a, b) in enumerate(zip(edges, edges[1:])))


def signature(beat: float, tonic: str, vel: int = 46, minor: bool = False, per_second: float = 1.0) -> list[Note]:
    """the series' sonic logo on the hand-off: scale degrees 5–2–3 high above the final chord, like a soft bell
    (a minor third in a minor key); `per_second` is beats per second, so the motif keeps its pace at any tempo"""
    root = n(tonic)
    steps = (7, 14, 15 if minor else 16)
    while root + steps[-1] > SIGNATURE_TOP:  # 用户：最高音不要太尖锐
        root -= 12
    return [Note(beat + i / 3 * per_second, (2.0 - i / 3) * per_second, root + step, vel - 3 * i) for i, step in enumerate(steps)]


def swung(beat: float, swing: float) -> float:
    """move written off-beat eighths (x.5) to the swing position"""
    whole = int(beat)
    frac = beat - whole
    return whole + swing if abs(frac - 0.5) < 1e-6 else beat


def humanize(notes: tuple[Note, ...], seed: int, timing: float = 0.02, vel: int = 5) -> tuple[Note, ...]:
    """small, repeatable timing and velocity variation so the playing doesn't sound quantized"""
    rng = random.Random(seed)
    return tuple(
        Note(max(0.0, x.beat + rng.uniform(-timing, timing)), x.dur, x.pitch, max(1, min(127, x.vel + rng.randint(-vel, vel))))
        for x in notes
    )


def expression_curve(points: tuple[tuple[float, int], ...], step: float = 0.125) -> list[tuple[float, int]]:
    """CC11 values every `step` beats, linear between the given (beat, value) points"""
    out = []
    for (b0, v0), (b1, v1) in zip(points, points[1:]):
        count = max(1, round((b1 - b0) / step))
        out += [(b0 + (b1 - b0) * i / count, round(v0 + (v1 - v0) * i / count)) for i in range(count)]
    return out + list(points[-1:])


def to_midi(piece: Piece, part: Part, path: str) -> None:
    """write one part as its own MIDI file (each part is rendered from its own SoundFont)"""
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(piece.bpm), time=0))
    ch = part.channel
    events = [(round(beat * TPB), mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))) for beat, bpm in piece.tempo] + [
        (0, mido.Message("program_change", channel=ch, program=part.program)),
        (0, mido.Message("control_change", channel=ch, control=7, value=part.volume)),
        (0, mido.Message("control_change", channel=ch, control=10, value=part.pan)),
    ]
    for x in part.notes:
        start = round(swung(x.beat, piece.swing) * TPB)
        end = round((swung(x.beat, piece.swing) + x.dur) * TPB)
        events.append((start, mido.Message("note_on", channel=ch, note=x.pitch, velocity=x.vel)))
        events.append((end, mido.Message("note_off", channel=ch, note=x.pitch, velocity=0)))
    for beat, value in expression_curve(part.expression):
        events.append((round(beat * TPB), mido.Message("control_change", channel=ch, control=11, value=value)))
    for down, up in part.pedal:
        events.append((round(down * TPB), mido.Message("control_change", channel=ch, control=64, value=127)))
        events.append((round(up * TPB), mido.Message("control_change", channel=ch, control=64, value=0)))
    # note-offs before note-ons at the same tick, so repeated notes retrigger cleanly
    events.sort(key=lambda e: (e[0], 0 if e[1].type in ("note_off", "control_change", "set_tempo") else 1))
    now = 0
    for tick, msg in events:
        track.append(msg.copy(time=tick - now))
        now = tick
    # keep the file running past the last beat so the reverb tail is rendered
    track.append(mido.MetaMessage("end_of_track", time=max(0, round((piece.beats + 2) * TPB) - now)))
    mid = mido.MidiFile(ticks_per_beat=TPB)
    mid.tracks.append(track)
    mid.save(path)


# the sample sets (see 配乐/compose/README in memory): Salamander for piano, GeneralUser GS for the rest
SOUNDFONTS = __import__("os").environ.get("SOUNDFONTS", "~/soundfonts")  # where the sample libraries live
SALAMANDER = f"{SOUNDFONTS}/SalamanderGrandPiano-SFZ+FLAC-V3+20200602/SalamanderGrandPiano-V3+20200602.sfz"
GU = f"{SOUNDFONTS}/GeneralUser-GS.sf2"


def legato(line: list[Note], overlap: float = 0.06) -> list[Note]:
    """let each note run a hair into the next, as a bowed line connects (the last note is left as written)"""
    return [Note(x.beat, x.dur + (overlap if i < len(line) - 1 else 0), x.pitch, x.vel) for i, x in enumerate(line)]


VSCO = f"{SOUNDFONTS}/VSCO-2-CE"
