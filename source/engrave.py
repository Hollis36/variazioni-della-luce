# 排版层：给 MuseScore 工程套上出版总谱的版式（用户：乐谱排版更专业、更美观）。
# 改 .mscz 里的样式（A4、谱表大小、行距、字体）和标题框文字，其余内容不动。
#   python3 engrave.py <score.mscz>
import os
import re
import sys
import zipfile
from pathlib import Path

A4_W, A4_H, MARGIN = 8.2677, 11.6929, 0.6299  # inches; 16 mm margins
STYLE = {
    "pageWidth": A4_W, "pageHeight": A4_H, "pagePrintableWidth": round(A4_W - 2 * MARGIN, 4),
    "pageEvenLeftMargin": MARGIN, "pageOddLeftMargin": MARGIN,
    "pageEvenTopMargin": 0.55, "pageOddTopMargin": 0.55, "pageEvenBottomMargin": 0.6, "pageOddBottomMargin": 0.6,
    "spatium": 1.45,  # mm per staff space: a 5.8 mm staff, usual for a small ensemble full score
    "minSystemDistance": 7.5, "maxSystemDistance": 14, "minStaffSpread": 3.2, "maxStaffSpread": 6,
    "akkoladeDistance": 5.5, "staffUpperBorder": 6,
    "firstSystemIndentationValue": 7.5,
    "lastSystemFillLimit": 0.0,  # stretch the last system across the page
    "measureNumberInterval": 5, "measureNumberSystem": 1,
    "titleFontFace": "Songti SC", "titleFontSize": 26, "titleFontStyle": 1,
    "subTitleFontFace": "Songti SC", "subTitleFontSize": 13, "subTitleFontStyle": 2,
    "composerFontFace": "Songti SC", "composerFontSize": 10.5, "lyricistFontFace": "Songti SC", "lyricistFontSize": 10.5,
    "longInstrumentFontFace": "Songti SC", "longInstrumentFontSize": 10,
    "shortInstrumentFontFace": "Edwin", "shortInstrumentFontSize": 10,
    "rehearsalMarkFontSize": 13, "rehearsalMarkFrameRound": 0,
    "expressionFontSize": 10.5, "tempoFontSize": 11, "tempoChangeFontSize": 11,
    "footerFirstPage": 0,
}
if os.environ.get("SCORE_HIDE_EMPTY"):  # staves appear only where their instruments play
    STYLE.update({"hideEmptyStaves": 1, "dontHideStavesInFirstSystem": 0})
HEADER = [  # (style, text) for the title frame; each piece passes its own
    ("title", os.environ.get("SCORE_TITLE", "云上兰德勒")),
    ("subtitle", os.environ.get("SCORE_SUBTITLE", "Ländler über den Wolken")),
]


def restyle(mss: str) -> str:
    for k, v in STYLE.items():
        tag = f"<{k}>{v}</{k}>"
        if re.search(fr"<{k}>.*?</{k}>", mss):
            mss = re.sub(fr"<{k}>.*?</{k}>", tag, mss, count=1)
        else:
            mss = mss.replace("</Style>", f"    {tag}\n  </Style>", 1)
    return mss


DEDICATION = os.environ.get("SCORE_DEDICATION", "Für CN")  # 题献：标题上方单独一行，小号斜体居中


def retitle(mscx: str) -> str:
    if DEDICATION:  # a slim frame of its own above the title frame
        frame = (f"<VBox>\n        <height>2.5</height>\n        <bottomGap>0</bottomGap>\n        <Text>\n          <style>subtitle</style>\n"
                 f"          <text><font size=\"11\"/>{DEDICATION}</text>\n          </Text>\n        </VBox>\n      ")
        mscx = mscx.replace("<VBox>", frame + "<VBox>", 1)
        return _retitle(mscx, skip=1)
    return _retitle(mscx)


def _retitle(mscx: str, skip: int = 0) -> str:
    if skip:
        i = mscx.index("</VBox>") + len("</VBox>")
        head, tail = mscx[:i], mscx[i:]
        return head + _retitle(tail)
    texts = "".join(f"\n        <Text>\n          <style>{st}</style>\n          <text>{tx}</text>\n          </Text>"
                    for st, tx in HEADER)
    return re.sub(r"(<VBox>\s*<height>)[\d.]+(</height>.*?)(<Text>.*</Text>)(\s*</VBox>)",
                  lambda m: "<VBox>\n        <topGap>0</topGap>\n        <height>" + "13" + re.sub(r"<Text>.*", "", m.group(2), flags=re.S) + texts.strip() + m.group(4),
                  mscx, count=1, flags=re.S)


def merge_tempo(mscx: str) -> str:
    """出版谱写法：速度文字和节拍器数字写在同一行，例如 Tempo di Ländler (♩ = 180)；回原速只写 a tempo"""
    note = "<sym>metNoteQuarterUp</sym>"
    for i, words in enumerate(re.findall(r"<StaffText>\s*<eid>[^<]*</eid>\s*<text><b>(Tempo di [^<]*|Allegro [^<]*|a tempo)</b></text>\s*</StaffText>", mscx)):
        mscx = re.sub(r"\s*<StaffText>\s*<eid>[^<]*</eid>\s*<text><b>" + re.escape(words) + r"</b></text>\s*</StaffText>", "", mscx, count=1)
        shown = list(re.finditer(r"(<Tempo>(?:(?!</Tempo>).)*?)<text>" + re.escape(note) + r" = (\d+)</text>", mscx, flags=re.S))
        visible = [m for m in shown if "<visible>0</visible>" not in m.group(1) and "<b>" not in m.group(0)]
        if visible:
            m = visible[0]
            text = f"<b>{words}</b> ({note} = {m.group(2)})" if words != "a tempo" else f"<b>{words}</b>"
            mscx = mscx[:m.start()] + m.group(1) + f"<text>{text}</text>" + mscx[m.end():]
    return mscx


def main() -> None:
    src = Path(sys.argv[1])
    tmp = src.with_suffix(".tmp.mscz")
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith("score_style.mss"):
                data = restyle(data.decode()).encode()
            elif item.filename.endswith(".mscx"):
                data = merge_tempo(retitle(data.decode())).encode()
            zout.writestr(item, data)
    tmp.replace(src)
    sys.stdout.write(f"ENGRAVED {src}\n")


if __name__ == "__main__":
    main()
