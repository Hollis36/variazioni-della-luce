# 演奏层：每个声部用自己的采样音色干声渲染（.sfz 走 sfizz，.sf2 走 fluidsynth），再按各自的发送量进
# 同一个房间混响，混音、母带，输出正好 9 秒的配乐。
#   python3 render.py <piece> [<piece> ...]     例：python3 render.py godfather
# 输出 ../成曲/<piece>.wav（48 kHz 24 bit），各声部干声在 ../成曲/分轨/。
import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from room import add_room, impulse
from score import Piece, to_midi

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("RENDER_OUT", HERE.parent / "成曲"))  # 复现时由 reproduce.sh 设为 build/audio
SFIZZ = Path(os.environ.get("SFIZZ", Path.home() / "sfizz-src/build/library/bin/sfizz_render"))
RATE = 48000


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"{Path(cmd[0]).name} failed: {(error.stderr or error.stdout)[-600:]}") from error


def render_part(piece: Piece, part, stems: Path) -> Path:
    font = Path(part.font).expanduser()
    wav = stems / f"{piece.key}_{part.name}.wav"
    with tempfile.TemporaryDirectory() as tmp:
        mid = Path(tmp) / f"{part.name}.mid"
        to_midi(piece, part, str(mid))
        if font.suffix == ".sfz":
            run([str(SFIZZ), "--sfz", str(font), "--midi", str(mid), "--wav", str(wav), "-s", str(RATE), "-q", "3", "--use-eot"])
        else:
            run(["fluidsynth", "-ni", "-q", "-R", "0", "-C", "0", "-F", str(wav), "-r", str(RATE), "-g", "0.5", str(font), str(mid)])
    return wav


def stereo(path: Path) -> np.ndarray:
    audio, rate = sf.read(path, always_2d=True)
    if rate != RATE:
        raise SystemExit(f"{path.name}: expected {RATE} Hz, got {rate}")
    return audio if audio.shape[1] == 2 else np.repeat(audio, 2, axis=1)


def rms_db(audio: np.ndarray, seconds: float, active: bool = False) -> float:
    """level in dB over the piece; with `active`, only over the 0.1 s frames where the part is actually playing"""
    x = audio[: int(RATE * seconds)]
    if active:
        frame = RATE // 10
        power = np.array([(x[i: i + frame] ** 2).mean() for i in range(0, len(x) - frame, frame)])
        power = power[power > power.max() * 1e-4]  # within 40 dB of its loudest moment
        return 10 * np.log10(max(1e-18, float(power.mean())))
    return 20 * np.log10(max(1e-9, float(np.sqrt((x ** 2).mean()))))


def balance(piece: Piece, stems: dict[str, Path]) -> dict[str, float]:
    """each part's gain: its fixed `level`, or — when it has a `target` — whatever puts it `target` dB
    under (or over) the first part, so new pieces sit right without hand-tuning"""
    lead = piece.parts[0]
    lead_db = rms_db(stereo(stems[lead.name]), piece.seconds, piece.balance_active) + 20 * np.log10(lead.level)
    gains = {}
    for part in piece.parts:
        if part.target is None:
            gains[part.name] = part.level
        else:
            gains[part.name] = 10 ** ((lead_db + part.target - rms_db(stereo(stems[part.name]), piece.seconds, piece.balance_active)) / 20)
    return gains


def mix(piece: Piece, stems: dict[str, Path], dst: Path) -> None:
    ir = impulse(RATE, seconds=max(1.8, piece.room * 1.4), rt60=piece.room)
    parts = {part.name: part for part in piece.parts}
    gains = balance(piece, stems)
    layers = [gains[name] * add_room(stereo(path), ir, parts[name].send) for name, path in stems.items()]
    length = int(RATE * piece.seconds)
    bus = np.zeros((length, 2))
    for layer in layers:
        bus[: min(length, len(layer))] += layer[:length]
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "bus.wav"
        sf.write(raw, bus / max(1e-9, np.abs(bus).max()) * 0.7, RATE, subtype="FLOAT")
        tone = piece.meta.get("master_eq") or (  # a piece may ask for its own tone; default unchanged
            "highpass=f=35,"  # clear sub-rumble
            "equalizer=f=300:t=q:w=1.2:g=-1.5,"  # a touch less mud
            "equalizer=f=9000:t=h:w=0.7:g=1.5,"  # a little air on top
        )
        chain = (
            tone
            + f"afade=t=out:st={piece.seconds - piece.fade}:d={piece.fade},"
            "alimiter=limit=0.89:attack=5:release=80:level=false"
        )
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", chain, "-ar", str(RATE), "-c:a", "pcm_s24le", str(dst)])


def loudness(src: Path, target: float = -18.0) -> None:
    """one linear gain so every piece sits at the same loudness (no dynamic squashing)"""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    integrated = float(log.split("I:")[-1].split("LUFS")[0])
    peak = float(log.split("Peak:")[-1].split("dBFS")[0])
    gain = min(target - integrated, -1.0 - peak)
    tmp = src.with_suffix(".tmp.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"volume={gain:.2f}dB", "-c:a", "pcm_s24le", str(tmp)])
    tmp.replace(src)


def render(key: str) -> Path:
    if key.startswith("h_"):  # the hundred drinks are composed by rule, not written one file each
        from hundred import PIECES
        piece: Piece = PIECES[key]
    else:
        piece = importlib.import_module(f"pieces.{key}").PIECE
    stems_dir = OUT / "分轨"
    stems_dir.mkdir(parents=True, exist_ok=True)
    stems = {part.name: render_part(piece, part, stems_dir) for part in piece.parts}
    dst = OUT / f"{piece.key}.wav"
    mix(piece, stems, dst)
    loudness(dst)
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: render.py <piece> [<piece> ...]")
    sys.path.insert(0, str(HERE))
    for key in sys.argv[1:]:
        sys.stdout.write(f"RENDERED {render(key)}\n")
