# 视频用谱页：把总谱工程复制一份、关掉页眉页脚和页码，导出 600 dpi 不裁边的谱页图，
# 以及 MuseScore 的小节坐标（pos.mpos）和音符坐标（pos.spos），供 score_video.py 使用。
#   python3 export_pages.py <score.mscz> <out_dir>
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

MSCORE = shutil.which("mscore") or "/Applications/MuseScore 4.app/Contents/MacOS/mscore"


def without_page_furniture(src: Path, dst: Path) -> None:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith("score_style.mss"):
                text = data.decode()
                for key in ("showPageNumber", "showHeader", "showFooter"):
                    text = re.sub(fr"<{key}>.*?</{key}>", f"<{key}>0</{key}>", text)
                data = text.encode()
            zout.writestr(item, data)


def run(*args: str) -> None:
    subprocess.run([MSCORE, *args], check=True, capture_output=True)


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    clean = out / "video.mscz"
    without_page_furniture(src, clean)
    run("-o", str(out / "page.png"), "-r", "600", str(clean))  # page-1.png, page-2.png, ...
    run("-o", str(out / "pos.mpos"), str(clean))
    run("-o", str(out / "pos.spos"), str(clean))
    pages = sorted(out.glob("page-*.png"))
    if not pages:
        raise SystemExit("MuseScore did not export any page images")
    sys.stdout.write(f"EXPORTED {len(pages)} pages to {out}\n")


if __name__ == "__main__":
    main()
