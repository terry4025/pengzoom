"""인트로를 애니메이션 GIF로 렌더링해 실제 속도로 확인한다.

    py design_preview/render_intro_gif.py

`design_preview/intro_preview.gif` 가 생성된다(git에는 넣지 않는다).
정지 컷 시트(`verify_intro.py`)로는 컷 길이를 볼 수 없어서, 타이밍을 손볼 때는
이 GIF로 판단한다.

GIF는 알파가 1비트라 배경을 밝은 회색으로 합성한다. 실제 앱에서는 투명 창에
그려지므로 배경 없이 캐릭터만 보인다.
"""

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PyQt6.QtCore import QBuffer, QByteArray, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import intro_animation  # noqa: E402

STEP_MS = 40           # 25fps. GIF 지연은 10ms 단위로 양자화된다.
BACKGROUND = "#eef1f6"
TAIL_MS = 240          # 끝난 뒤 잠깐 빈 화면을 남겨 반복 경계를 알아보게 한다
SCALE = 0.7            # 파일 크기를 줄이기 위한 표시 축소
PALETTE_COLORS = 64    # 평면 벡터 그림이라 64색으로도 티가 안 난다


def to_pil(pixmap: QPixmap) -> Image.Image:
    if SCALE != 1.0:
        pixmap = pixmap.scaled(
            int(pixmap.width() * SCALE), int(pixmap.height() * SCALE),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return Image.open(io.BytesIO(bytes(data))).convert("RGB")


def render_sequence(timeline):
    """타임라인을 STEP_MS 간격으로 렌더링해 PIL 프레임 목록을 만든다."""
    splash = intro_animation.create_intro(timeline=timeline)
    if splash is None:
        raise SystemExit("인트로 자원을 찾지 못했습니다. py tools/build_intro_frames.py 먼저.")
    total = intro_animation.total_duration_ms(timeline)
    frames = []
    for elapsed in range(0, total + TAIL_MS + 1, STEP_MS):
        splash._state = intro_animation.state_at(min(elapsed, total), timeline)
        tile = QPixmap(splash.size())
        tile.fill(QColor(BACKGROUND))
        splash.render(tile)
        frames.append(to_pil(tile))
    splash.close()
    return frames, total


def save_gif(path: Path, frames):
    # 팔레트는 여러 시점을 이어 붙인 이미지에서 뽑는다. 첫 프레임은 등장 전
    # 빈 화면이라 그것만으로 팔레트를 만들면 배경색 하나로 뭉개진다.
    stride = max(1, len(frames) // 8)
    samples = frames[::stride] or [frames[0]]
    width, height = frames[0].size
    strip = Image.new("RGB", (width * len(samples), height))
    for index, frame in enumerate(samples):
        strip.paste(frame, (index * width, 0))
    palette = strip.quantize(colors=PALETTE_COLORS, method=Image.Quantize.MEDIANCUT)

    converted = [frame.quantize(palette=palette, dither=Image.Dither.NONE)
                 for frame in frames]
    converted[0].save(str(path), save_all=True, append_images=converted[1:],
                      duration=STEP_MS, loop=0, optimize=True)
    print(f"저장: {path} ({path.stat().st_size / 1024:.0f}KB)")


def main():
    # QApplication 참조를 붙잡아 둬야 한다. 임시 객체로 두면 GC 되어
    # 렌더링 중에 프로세스가 그대로 죽는다.
    app = QApplication.instance() or QApplication([])
    frames, total = render_sequence(intro_animation.TIMELINE)
    save_gif(ROOT / "design_preview" / "intro_preview.gif", frames)
    print(f"총 {total}ms, 컷 {len(intro_animation.TIMELINE)}개, "
          f"{len(frames)}프레임({STEP_MS}ms 간격)")
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
