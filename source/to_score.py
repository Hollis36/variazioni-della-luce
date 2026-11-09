# 乐谱层：把一首曲子的音符写成 MusicXML 总谱，交给 MuseScore 打开、排版、演奏（用户：用 MuseScore 4 展示这首）。
# 用作曲时的原始音符（未加人性化抖动），量化到十六分音符网格；钢琴/竖琴的琶音式滚奏合成和弦；
# 每个谱表整理成一条不重叠的和弦序列，休止符、小节线和连线交给 music21 生成。
#   python to_score.py hugo_alpine_long <输出目录>      （需要 music21：pip install music21 mido）
import importlib
import sys
from pathlib import Path

from music21 import (bar as m21bar, chord, clef, dynamics, expressions, harmony, instrument, key, layout, metadata, meter,
                     note, pitch, spanner,
                     stream, tempo)  # noqa: E501

GRID = 0.25  # sixteenth notes
ROLL = 0.26  # notes closer than this inside a piano/harp roll are one chord

# per piece: section names, dynamics and tempo words at bar numbers (0-based), shown in the score
HUGO_MARKS = {
    # 按兰德勒 / 圆舞曲的惯例命名段落：引子—主题—变奏—三声中部（Trio）—再现—尾声
    # 排练字母 + 段落名（意大利文，出版总谱惯例）
    "sections": [(0, "", "Introduzione"), (4, "A", "Tema"), (13, "B", "Variazione"), (22, "C", "Trio"),
                 (38, "D", "Ripresa"), (50, "E", "Coda")],
    "chord_symbols": False,  # 管弦乐总谱一般不写和弦名
    "opening_tempo": "Tempo di Ländler",
    # 乐句连线（起始小节, 结束小节不含）：按旋律的呼吸分句
    "slurs": {
        "violin": [(4, 6), (6, 9), (9, 13), (13, 15), (15, 18), (18, 22), (26, 28), (28, 30), (30, 32), (32, 34),
                   (34, 36), (36, 38), (38, 40), (40, 43), (43, 46), (46, 48), (48, 50), (50, 57)],
        "viola": [(38, 40), (40, 43), (43, 46), (46, 48), (48, 50)],
        "cello": [(22, 24), (24, 26), (38, 40), (40, 43), (43, 46), (46, 50)],
    },
    "dynamics": {
        "violin": [(4, "mp"), (13, "mp"), (22, "mp"), (34, "mf"), (38, "f"), (46, "mf"), (50, "mp"), (52, "p")],
        "viola": [(0, "pp"), (4, "p"), (30, "mp"), (38, "mf"), (46, "mp"), (52, "p")],
        "cello": [(0, "pp"), (4, "p"), (22, "mf"), (26, "p"), (30, "mp"), (38, "mf"), (46, "mp"), (52, "p")],
        "harp": [(0, "p"), (4, "mp"), (22, "p"), (30, "mp"), (38, "mf"), (46, "mp"), (52, "p")],
        "piano": [(4, "p"), (22, "pp"), (30, "p"), (38, "mf"), (46, "mp"), (52, "p")],
    },
    "words": {},
    "hairpins": [("violin", "<", 30, 38), ("viola", "<", 30, 38), ("cello", "<", 30, 38), ("piano", "<", 30, 38),
                 ("violin", ">", 46, 50), ("viola", ">", 46, 50), ("cello", ">", 46, 50), ("piano", ">", 46, 52)],
    "harp_gliss": {"bar": 37, "from": 57, "to": 73},  # A3 up to C#5
    "harp_roll": 52,
    "tempo_words": {37: "poco rit.", 38: "a tempo", 47: "poco a poco rit.", 52: "rit."},
}

INSTRUMENTS = {  # part name -> (music21 instrument, Chinese name, two staves?)
    "harp": (instrument.Harp, "竖琴 Arpa|Arpa", True),  # full name on the first system | abbreviation after
    "piano": (instrument.Piano, "钢琴 Pianoforte|Pf.", True),
    "violin": (instrument.Violin, "小提琴 Violino|Vl.", False),
    "viola": (instrument.Viola, "中提琴 Viola|Vla.", False),
    "cello": (instrument.Violoncello, "大提琴 Violoncello|Vc.", False),
}
ORDER = ["harp", "piano", "violin", "viola", "cello"]


def q(x: float, grid: float = GRID) -> float:
    return round(x / grid) * grid


def events(notes, total: float, merge_rolls: bool, cut_at=None, min_len: float = 0.0, grid: float = GRID,
           roll: float = ROLL) -> list[tuple[float, float, tuple[int, ...]]]:
    """(onset, duration, pitches) with no overlaps: rolls merged, onsets on the grid, each event cut at the next one.
    `cut_at`: onsets of the whole instrument (both staves), so a harp ripple reads as plain eighths instead of ties;
    `min_len`: lengthen short attacks (piano "pah" chords) up to this many beats when the next onset allows"""
    ordered = sorted(notes, key=lambda x: (x.beat, x.pitch))
    groups, last = [], None
    for x in ordered:
        if merge_rolls and groups and x.beat - last <= roll:
            groups[-1].append(x)
        else:
            groups.append([x])
        last = x.beat
    raw = {}
    for g in groups:
        on = q(g[0].beat, grid)
        end = max(q(x.beat + x.dur, grid) for x in g)
        pitches, prev_end = raw.get(on, (set(), on))
        raw[on] = (pitches | {x.pitch for x in g}, max(prev_end, end))
    onsets = sorted(raw)
    out = []
    for i, on in enumerate(onsets):
        nxt = onsets[i + 1] if i + 1 < len(onsets) else total
        if cut_at is not None:
            later = [o for o in cut_at if o > on]
            nxt = min(nxt, later[0]) if later else nxt
        dur = min(max(raw[on][1], on + min_len), nxt, total) - on
        if dur >= GRID:
            out.append((on, dur, tuple(sorted(raw[on][0]))))
    return out


def spelled(midi: int) -> pitch.Pitch:
    """MIDI number -> pitch spelled for D major (sharps), with no explicit natural sign"""
    p = pitch.Pitch(midi=midi)
    if p.accidental is not None and p.accidental.name == "natural":
        p.accidental = None
    return p


def element(dur: float, pitches: tuple[int, ...]):
    if len(pitches) == 1:
        el = note.Note(spelled(pitches[0]))
    else:
        el = chord.Chord([spelled(m) for m in pitches])
    el.quarterLength = dur
    return el


def staff(name: str, label: str, inst_cls, notes, total: float, merge: bool, clef_obj, ks, ts, cut_at=None, min_len=0.0,
          grid=GRID, roll=ROLL) -> stream.Part:
    part = stream.PartStaff() if clef_obj is not None else stream.Part()
    inst = inst_cls()
    inst.partName, inst.partAbbreviation = label.split("|")
    part.insert(0, inst)
    part.insert(0, ks)
    part.insert(0, ts)
    if clef_obj is not None:
        part.insert(0, clef_obj)
    cursor = 0.0
    for on, dur, pitches in events(notes, total, merge, cut_at, min_len, grid, roll):
        if on > cursor:  # write visible rests in the gaps
            part.insert(cursor, note.Rest(quarterLength=on - cursor))
        part.insert(on, element(dur, pitches))
        cursor = on + dur
    if cursor < total:
        part.insert(cursor, note.Rest(quarterLength=total - cursor))
    part.id = name
    return part


def chord_symbol(name: str):
    if "sus" in name:  # music21 spells sus chords out in words; write them as plain text instead
        return expressions.TextExpression(name)
    try:
        cs = harmony.ChordSymbol(name.replace("6/9", "6add9"))
        cs.writeAsChord = False
        root = name.split("/")[0]
        root = root[:2] if len(root) > 1 and root[1] in "#b" else root[:1]
        cs.chordKindStr = name.split("/")[0][len(root):]  # show exactly what was written, e.g. A7sus4, Gmaj7#11
        return cs
    except Exception:  # anything music21 cannot parse is written as plain text above the staff
        return expressions.TextExpression(name)


def build(mod, marks: dict, title: str, subtitle: str) -> stream.Score:
    piece = mod.PIECE
    total = mod.BARS * 3
    raw = {"violin": mod.VIOLIN, "piano": mod.PIANO, "harp": mod.HARP, "cello": mod.CELLO, "viola": mod.VIOLA}
    score = stream.Score()
    md = metadata.Metadata()
    md.title, md.movementName, md.composer = title, title, subtitle
    md.addContributor(metadata.Contributor(role="lyricist", name="调酒小品 No. 37 · 雨果 Hugo Spritz"))
    score.insert(0, md)
    staves = {}
    for name in ORDER:
        cls, label, grand = INSTRUMENTS[name]
        notes = raw[name]
        if grand:
            grid, roll = 0.5, 0.31  # piano and harp move in eighths; rolls and shimmers read as (arpeggiated) chords
            notes = harp_cleanup(notes, marks) if name == "harp" else snap_roll(notes, marks)
            if name == "piano":  # left hand: the "oom" bass (and the lowest notes); right hand: the "pah–pah" chords
                is_low = lambda x: (x.dur >= 0.8 and x.pitch < 57) or x.pitch < 50
                cut, min_len = None, 1.0
            else:  # harp: split at middle C; each ripple note lasts until the next one in either hand
                g = marks.get("harp_gliss") or {}
                is_low = lambda x: x.pitch < 60 and not (x.beat == g.get("bar", -1) * 3 and x.pitch == g.get("from"))
                cut, min_len = sorted({q(x.beat, grid) for x in notes}), 0.0
            up = [x for x in notes if not is_low(x)]
            down = [x for x in notes if is_low(x)]
            ks, ts = key.KeySignature(2), meter.TimeSignature("3/4")
            rh = staff(name + "_rh", label, cls, up, total, True, clef.TrebleClef(), ks, ts, cut, min_len, grid, roll)
            lh = staff(name + "_lh", label, cls, down, total, True, clef.BassClef(), key.KeySignature(2), meter.TimeSignature("3/4"),
                       cut, min_len, grid, roll)
            harp_marks(rh, lh, marks, gliss=(name == "harp"))
            score.insert(0, rh)
            score.insert(0, lh)
            full, abbr = label.split("|")
            score.insert(0, layout.StaffGroup([rh, lh], name=full, abbreviation=abbr, symbol="brace"))
            staves[name] = rh
        else:
            first = {"cello": clef.BassClef(), "viola": clef.AltoClef()}.get(name, clef.TrebleClef())
            p = staff(name, label, cls, notes, total, False, None, key.KeySignature(2), meter.TimeSignature("3/4"))
            p.insert(0, first)
            score.insert(0, p)
            staves[name] = p
    top = staves[ORDER[0]]
    # tempo: the written changes of the piece, with words where the music asks for them
    words = marks["tempo_words"]
    changes = [(0.0, piece.bpm)] + [(b, bpm) for b, bpm in sorted(piece.tempo) if b % 3 == 0]
    for b, bpm in changes:
        bar = int(b // 3)
        if b == 0 or bar in words and words[bar] == "a tempo":  # printed: the opening tempo and its return
            mm = tempo.MetronomeMark(number=round(bpm), referent=note.Note(type="quarter"))
            mm.text = words[bar] if b else marks.get("opening_tempo")
        else:  # every other change plays but is not printed; the words say what is happening
            mm = tempo.MetronomeMark(text=words.get(bar), numberSounding=round(bpm), referent=note.Note(type="quarter"))
            if bar not in words:
                mm.style.hideObjectOnPrint = True
        top.insert(b, mm)
    strings = [staves[k] for k in ("violin", "viola", "cello")]
    score.insert(0, layout.StaffGroup(strings, symbol="bracket", barTogether=True))
    for bar, letter, text in marks["sections"]:
        if letter:
            top.insert(bar * 3, expressions.RehearsalMark(letter))
        label = expressions.TextExpression(text)
        label.style.fontStyle = "italic"
        label.placement = "above"
        top.insert(bar * 3, label)
    if marks.get("chord_symbols", True):
        names = mod.PROG + ["D6/9"]
        for i, name in enumerate(names):
            if i == 0 or name != names[i - 1]:
                staves["violin"].insert(i * 3, chord_symbol(name))
    for part, items in marks["dynamics"].items():
        for bar, dyn in items:
            staves[part].insert(bar * 3, dynamics.Dynamic(dyn))
    for part, items in marks["words"].items():
        for bar, text in items:
            staves[part].insert(bar * 3, expressions.TextExpression(text))
    for part, ranges in marks.get("slurs", {}).items():
        for start, stop in ranges:
            span = [x for x in staves[part].notes if start * 3 <= x.offset < stop * 3 and not isinstance(x, harmony.ChordSymbol)]
            if len(span) >= 2:
                staves[part].insert(0, spanner.Slur(span[0], span[-1]))
    for part, kind, start, stop in marks.get("hairpins", []):
        span = [x for x in staves[part].notes if start * 3 <= x.offset < stop * 3 and not isinstance(x, harmony.ChordSymbol)]
        if span:
            hp = dynamics.Crescendo() if kind == "<" else dynamics.Diminuendo()
            hp.addSpannedElements(span[0], span[-1])
            staves[part].insert(0, hp)
    return score


def harp_cleanup(notes, marks):
    """the glissando bar becomes its two end notes; the closing roll lands on one beat (drawn as an arpeggio)"""
    g = marks.get("harp_gliss")
    out = []
    for x in notes:
        if g and g["bar"] * 3 <= x.beat < g["bar"] * 3 + 3:
            continue
        out.append(x)
    out = snap_roll(out, marks)
    if g:
        out += [type(notes[0])(g["bar"] * 3, 2.0, g["from"], 50), type(notes[0])(g["bar"] * 3 + 2, 1.0, g["to"], 60)]
    return out


def snap_roll(notes, marks):
    """the closing chord was rolled upward note by note; in the score it sits on one beat with an arpeggio sign"""
    at = marks.get("harp_roll")
    if at is None:
        return list(notes)
    return [type(x)(at * 3, x.dur, x.pitch, x.vel) if at * 3 <= x.beat < at * 3 + 2.5 and x.dur > 6 else x for x in notes]


def harp_marks(rh, lh, marks, gliss=True):
    g = marks.get("harp_gliss") if gliss else None
    if g:
        a = [x for x in rh.notes if x.offset == g["bar"] * 3]
        b = [x for x in rh.notes if x.offset == g["bar"] * 3 + 2]
        if a and b:
            rh.insert(0, spanner.Glissando([a[0], b[0]], lineType="wavy", label="gliss."))
    if marks.get("harp_roll") is not None:
        for st in (rh, lh):
            for x in st.notes:
                if x.offset == marks["harp_roll"] * 3 and isinstance(x, chord.Chord):
                    x.expressions.append(expressions.ArpeggioMark("normal"))


def main() -> None:
    key_name, out_dir = sys.argv[1], Path(sys.argv[2])
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    mod = importlib.import_module(f"pieces.{key_name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    score = build(mod, HUGO_MARKS, "云上兰德勒", "Ländler über den Wolken · 为独奏小提琴、竖琴、钢琴与弦乐而作")
    dst = out_dir / f"{key_name}.musicxml"
    score = score.makeNotation()
    for part in score.parts:  # a double bar line where each section begins
        measures = list(part.getElementsByClass(stream.Measure))
        for bar_no, *_ in HUGO_MARKS["sections"][1:]:
            if 0 < bar_no < len(measures):
                measures[bar_no - 1].rightBarline = m21bar.Barline("double")
    from music21.stream.makeNotation import makeAccidentalsInMeasureStream
    for part in score.parts:  # accidentals relative to D major, recomputed measure by measure
        makeAccidentalsInMeasureStream(part.getElementsByClass(stream.Measure), useKeySignature=key.KeySignature(2),
                                       overrideStatus=True, cautionaryNotImmediateRepeat=False)
    score.write("musicxml", fp=str(dst))
    sys.stdout.write(f"WROTE {dst}\n")


if __name__ == "__main__":
    main()
