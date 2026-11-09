# 晨光变奏曲 Variazioni della Luce · Für eine schöne Welt（定稿：试听版 K）。
# 用户的要求一路收敛为：欢快、层层递进、钢琴为主、适当加一点交响。音符写在 luce_melodies.py 的 J/K。
from dataclasses import replace

from pieces.luce_melodies import j_coda, j_left, j_running, j_theme, k_piece

BARS, BEATS_PER_BAR = 34, 4
TITLE, SUBTITLE, DEDICATION = "晨光变奏曲", "Variazioni della Luce", "Für eine schöne Welt"
INSTRUMENTATION = "Pianoforte  ·  Archi  ·  Corno  ·  Organo  ·  Campane"
SECTIONS = [(0, "A", "Tema"), (8, "B", "Variazione I"), (16, "C", "Variazione II"), (24, "D", "Variazione III"), (32, "", "Finale")]
PIECE = replace(k_piece(), key="luce_variazioni")


def piano_hands():
    """the piano's right and left hand separately, for the score"""
    layer = 32
    right = j_theme(0, 62) + j_theme(layer, 70) + j_running(layer * 2, 72) + j_theme(layer * 3, 92, octave=True)
    left = j_left(0, 1, 46) + j_left(layer, 2, 52) + j_left(layer * 2, 3, 60) + j_left(layer * 3, 4, 66)
    for x in j_coda(layer * 4):
        (left if x.pitch < 60 else right).append(x)
    return right, left
