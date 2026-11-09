# 复现

在 macOS 上准备好环境，运行 `./reproduce.sh`，即可在 `build/` 中重新生成母带、MP3、总谱、4K 随谱视频、封面版和 1080p 网页版。随机演奏偏差使用固定种子，同一环境下结果相同。

| 组件 | 验证过的版本 |
|---|---|
| macOS | 26（视频用到系统字体 Songti SC、Georgia Italic、DIN Alternate） |
| Python | 3.13，`pip install -r requirements.txt` |
| MuseScore Studio | 4.7.6，命令行 `mscore` |
| ffmpeg | 8.0，带 libx264、libmp3lame |
| sfizz | git f5c6e29，需要 `sfizz_render`（`cmake -B build -DCMAKE_BUILD_TYPE=Release -DSFIZZ_RENDER=ON`） |

## 采样

| 采样 | 获取 | 放置位置 |
|---|---|---|
| VSCO 2 Community Edition（git 6dd651d） | https://github.com/sgossner/VSCO-2-CE | `~/soundfonts/VSCO-2-CE` |
| Salamander Grand Piano V3（2020-06-02，SFZ+FLAC） | https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html | `~/soundfonts/SalamanderGrandPiano-SFZ+FLAC-V3+20200602` |

可用环境变量 `SOUNDFONTS`、`SFIZZ` 改位置。

## 步骤

| 步骤 | 脚本 |
|---|---|
| 作曲 | `source/pieces/luce_melodies.py`（J、K）、`source/pieces/luce_variazioni.py` |
| 音频 | `source/render.py`（`score.py`、`room.py`） |
| 总谱 | `source/to_score_luce.py` → MuseScore → `source/engrave.py` |
| 视频 | `source/export_pages.py` → `source/score_video.py` |
