#!/bin/zsh
# 从源码完整复现《晨光变奏曲》的全部成品，输出到 build/。环境要求见 REPRODUCE.md。
#   ./reproduce.sh [all|audio|score|video]
set -euo pipefail
cd "${0:a:h}"
B=$PWD/build; N=Variazioni-della-Luce; K=luce_variazioni
PY=${PYTHON:-python3}
MSCORE=${MSCORE:-$(command -v mscore || echo "/Applications/MuseScore 4.app/Contents/MacOS/mscore")}
export SCORE_TITLE=晨光变奏曲 SCORE_SUBTITLE="Variazioni della Luce" SCORE_DEDICATION="Für eine schöne Welt" SCORE_HIDE_EMPTY=1
mkdir -p $B
audio() {
  RENDER_OUT=$B/audio $PY source/render.py $K
  cp $B/audio/$K.wav $B/${N}_24bit-48kHz.wav
  ffmpeg -loglevel error -y -i $B/${N}_24bit-48kHz.wav -c:a libmp3lame -b:a 320k -ar 48000 $B/${N}_320k.mp3
}
score() {
  $PY source/to_score_luce.py $B/score
  "$MSCORE" -o $B/$N.mscz $B/score/$K.musicxml >/dev/null 2>&1
  $PY source/engrave.py $B/$N.mscz
  "$MSCORE" -o $B/${N}_score.pdf $B/$N.mscz >/dev/null 2>&1
}
video() {
  $PY source/export_pages.py $B/$N.mscz $B/pages
  PIECE=$K CRF=10 PRESET=slow $PY source/score_video.py $B/pages $B/${N}_24bit-48kHz.wav $B/video all
  mv $B/video/晨光变奏曲_演奏过程_4K.mp4 $B/${N}_4K-master.mp4
  mv $B/video/晨光变奏曲.mp4 $B/${N}_cover.mp4
  ffmpeg -loglevel error -y -i $B/${N}_4K-master.mp4 -vf "scale=1920:1080:flags=lanczos" -c:v libx264 -preset veryslow -tune stillimage \
    -crf 26 -maxrate 700k -bufsize 1400k -g 240 -profile:v high -level 4.1 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart -map_metadata -1 $B/${N}_1080p-light.mp4
}
case ${1:-all} in audio) audio;; score) score;; video) video;; all) audio; score; video;; *) echo "usage: $0 [all|audio|score|video]" >&2; exit 1;; esac
ls -la $B
