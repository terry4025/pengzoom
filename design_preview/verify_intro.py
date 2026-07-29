"""인트로 애니메이션을 시간축으로 훑어 한 장에 붙여 눈으로 확인한다.

    py design_preview/verify_intro.py

`design_preview/M_intro_timeline.png` 이 생성된다. 실제 창은 투명하므로 여기서는
체커보드 위에 합성해 알파와 정렬을 함께 본다.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QRect, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import intro_animation  # noqa: E402

COLUMNS = 8
SAMPLES = 24


def checkerboard(size, cell=12):
    board = QPixmap(size)
    board.fill(QColor("#f2f4f8"))
    painter = QPainter(board)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#dfe3ec"))
    for y in range(0, size.height(), cell):
        for x in range(0, size.width(), cell):
            if (x // cell + y // cell) % 2 == 0:
                painter.drawRect(x, y, cell, cell)
    painter.end()
    return board


def main():
    app = QApplication.instance() or QApplication([])
    splash = intro_animation.create_intro()
    if splash is None:
        raise SystemExit("인트로 자원을 찾지 못했습니다. py tools/build_intro_frames.py 먼저 실행하세요.")

    total = intro_animation.total_duration_ms()
    times = [round(total * i / (SAMPLES - 1)) for i in range(SAMPLES)]

    tile_w, tile_h = splash.width(), splash.height()
    rows = (len(times) + COLUMNS - 1) // COLUMNS
    sheet = QPixmap(tile_w * COLUMNS, tile_h * rows)
    sheet.fill(QColor("#ffffff"))
    board = checkerboard(splash.size())

    painter = QPainter(sheet)
    for index, elapsed in enumerate(times):
        splash._state = intro_animation.state_at(elapsed)
        tile = QPixmap(board)
        splash.render(tile)
        column, row = index % COLUMNS, index // COLUMNS
        painter.drawPixmap(column * tile_w, row * tile_h, tile)
        painter.setPen(QColor("#334155"))
        painter.drawText(QRect(column * tile_w + 6, row * tile_h + 4, tile_w, 18),
                         Qt.AlignmentFlag.AlignLeft,
                         f"{elapsed}ms  f{splash._state.frame}")
    painter.end()

    out = ROOT / "design_preview" / "M_intro_timeline.png"
    # 눈으로 흐름만 확인하는 자료라 절반 크기로 저장한다(파일 크기 절약).
    sheet.scaled(sheet.width() // 2, sheet.height() // 2,
                 Qt.AspectRatioMode.KeepAspectRatio,
                 Qt.TransformationMode.SmoothTransformation).save(str(out))
    print(f"저장: {out}  ({sheet.width()}x{sheet.height()})")
    print(f"총 길이 {total}ms, 타일 {tile_w}x{tile_h}, base_scale={splash.base_scale:.3f}, "
          f"dpr={splash.device_ratio}")
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
