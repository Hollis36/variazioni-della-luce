# 《晨光变奏曲》的总谱：钢琴双谱表 + 乐队；同一弦乐组的拨弦、长弓、断弓合并到一行谱上，用 pizz./arco/spicc. 标注。
#   python3 to_score_luce.py <输出目录>
import sys
from pathlib import Path

from music21 import bar as m21bar, clef, dynamics, expressions, instrument, key, layout, metadata, meter, note, stream, tempo
from music21.stream.makeNotation import makeAccidentalsInMeasureStream

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pieces import luce_variazioni as mod  # noqa: E402
from to_score import staff  # noqa: E402

TOTAL = mod.BARS * mod.BEATS_PER_BAR
KS, TS = (lambda: key.KeySignature(2)), (lambda: meter.TimeSignature("4/4"))
generic = instrument.Instrument  # written at sounding pitch, as a score in C
SINGLE = [  # staff id, label, source parts, clef
    ("horn", "圆号 Corno|Cor.", ["horn"], clef.TrebleClef),
    ("bells", "管钟 Campane|Cmp.", ["bells"], clef.TrebleClef),
    ("organ", "管风琴 Organo|Org.", ["organ"], clef.BassClef),
]
STRINGS = [
    ("violin", "小提琴 Violino|Vl.", ["violins", "spic"], clef.TrebleClef),
    ("viola", "中提琴 Viola|Vla.", ["violapizz", "violas"], clef.AltoClef),
    ("cello", "大提琴 Violoncello|Vc.", ["cellopizz", "cello"], clef.BassClef),
    ("bass", "低音提琴 Contrabbasso|Cb.", ["bass"], clef.Bass8vbClef),
]
DYN = {
    "right": [(0, "mp"), (8, "mf"), (16, "mf"), (24, "f"), (32, "ff")],
    "violin": [(16, "p"), (24, "mf"), (32, "f")],
    "viola": [(8, "p"), (16, "p"), (24, "mp"), (32, "f")],
    "cello": [(8, "mp"), (16, "p"), (24, "mf"), (32, "f")],
    "bass": [(24, "mp"), (32, "f")],
    "horn": [(24, "mp"), (32, "f")],
    "organ": [(24, "pp"), (32, "p")],
    "bells": [(33, "mf")],
}
WORDS = {"violin": [(24, "spicc."), (32, "arco")], "viola": [(8, "pizz."), (16, "arco")], "cello": [(8, "pizz."), (16, "arco")]}
STAGES = {8: "", 16: "", 24: ""}


def one(entry, sources):
    name, label, parts, clef_cls = entry
    notes = [x for p in parts for x in sources[p]]
    pulse = 2.0 if name == "violin" else 0.0  # detached notes are written at full value, not as dotted note + rest
    part = staff(name, label, generic, notes, TOTAL, True, None, KS(), TS(), min_len=pulse, roll=0.1)
    part.insert(0, clef_cls())
    return part


def build() -> stream.Score:
    score = stream.Score()
    md = metadata.Metadata()
    md.title, md.movementName, md.composer = mod.TITLE, mod.TITLE, mod.SUBTITLE
    score.insert(0, md)
    sources = {p.name: p.notes for p in mod.PIECE.parts}
    winds = [one(e, sources) for e in SINGLE]
    right, left = mod.piano_hands()
    rh = staff("right", "钢琴 Pianoforte|Pf.", generic, right, TOTAL, True, clef.TrebleClef(), KS(), TS(), min_len=2.0, roll=0.1)
    lh = staff("left", "钢琴 Pianoforte|Pf.", generic, left, TOTAL, True, clef.BassClef(), KS(), TS(), min_len=1.0, roll=0.1)
    strings = [one(e, sources) for e in STRINGS]
    # the piano leads and sits on top, so section marks stay visible when the empty orchestra staves are hidden
    staves = {p.id: p for p in [rh, lh] + winds + strings}
    for p in [rh, lh] + winds + strings:
        score.insert(0, p)
    score.insert(0, layout.StaffGroup([rh, lh], symbol="brace", barTogether=True))
    score.insert(0, layout.StaffGroup(strings, symbol="bracket", barTogether=True))
    top = rh
    opening = tempo.MetronomeMark(number=mod.PIECE.bpm, referent=note.Note(type="quarter"))
    opening.text = "Allegro gioioso"
    rh.insert(0, opening)
    for beat, bpm in mod.PIECE.tempo:
        words = "rit." if beat == 130.0 else None
        mm = tempo.MetronomeMark(text=words, numberSounding=round(bpm), referent=note.Note(type="quarter"))
        if not words:
            mm.style.hideObjectOnPrint = True
        rh.insert(beat, mm)
    for bar, letter, text in mod.SECTIONS:
        if letter:
            top.insert(bar * 4, expressions.RehearsalMark(letter))
        label = expressions.TextExpression(text)
        label.style.fontStyle = "italic"
        label.placement = "above"
        top.insert(bar * 4, label)
    for part, items in DYN.items():
        for bar, dyn in items:
            staves[part].insert(bar * 4, dynamics.Dynamic(dyn))
    for part, items in WORDS.items():
        for bar, text in items:
            staves[part].insert(bar * 4, expressions.TextExpression(text))
    return score


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    score = build().makeNotation()
    for part in score.parts:
        measures = list(part.getElementsByClass(stream.Measure))
        for bar_no, *_ in mod.SECTIONS[1:]:
            if 0 < bar_no < len(measures):
                measures[bar_no - 1].rightBarline = m21bar.Barline("double")
        makeAccidentalsInMeasureStream(part.getElementsByClass(stream.Measure), useKeySignature=key.KeySignature(2),
                                       overrideStatus=True, cautionaryNotImmediateRepeat=False)
    dst = out / "luce_variazioni.musicxml"
    score.write("musicxml", fp=str(dst))
    sys.stdout.write(f"WROTE {dst}\n")


if __name__ == "__main__":
    main()
