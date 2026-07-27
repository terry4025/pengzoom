"""실제 magnifier.MagnifierWindow의 setup_ui 결과를 PNG로 렌더링한다.

전체 창을 띄우면 탐지 스레드/전역 훅/mss가 함께 붙으므로, setup_ui가 만드는
위젯 트리만 떼어내 독립 컨테이너에 담아 렌더링한다.

실행:
    python design_preview/verify_main_window.py
"""

import os
import sys

# offscreen 플랫폼은 폰트 DB에 접근하지 못해 글자가 tofu(□)로 나온다.
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow

import magnifier

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


class UiHarness(QMainWindow):
    """MagnifierWindow.setup_ui만 그대로 실행하는 최소 껍데기."""

    def __init__(self):
        super().__init__()
        self.click_through = False
        self.hide_ui_on_transparent = False
        # setup_ui가 연결하는 슬롯들. 렌더링만 하므로 동작은 필요 없다.
        for name in ("start_selection", "toggle_follow", "toggle_click_through",
                     "show_settings", "show_help", "on_zoom_slider_changed",
                     "on_opacity_slider_changed"):
            setattr(self, name, lambda *_: None)
        magnifier.MagnifierWindow.setup_ui(self)


def fake_viewport(width, height):
    """확대 화면 자리에 게임 화면 느낌의 더미 이미지를 채운다."""
    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor(30, 41, 59))
    gradient.setColorAt(0.5, QColor(15, 23, 42))
    gradient.setColorAt(1.0, QColor(38, 24, 44))
    painter.fillRect(0, 0, width, height, gradient)
    painter.setPen(QColor(255, 255, 255, 14))
    for x in range(0, width, 22):
        painter.drawLine(x, 0, x, height)
    for y in range(0, height, 22):
        painter.drawLine(0, y, width, y)
    painter.setPen(QColor(255, 69, 58, 200))
    cx, cy = width // 2, height // 2
    painter.drawLine(cx - 15, cy, cx + 15, cy)
    painter.drawLine(cx, cy - 15, cx, cy + 15)
    painter.end()
    return pixmap


def render(window, filename):
    window.resize(420, 540)
    window.show()
    QApplication.processEvents()
    label = window.label
    label.setPixmap(fake_viewport(label.width(), label.height()))
    QApplication.processEvents()

    pixmap = QPixmap(window.size() * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor(58, 62, 72))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    window.render(painter)
    painter.end()
    out = os.path.join(OUT_DIR, filename)
    pixmap.save(out, "PNG")
    print(f"saved {filename}  {window.width()}x{window.height()}")


def main():
    app = QApplication(sys.argv)

    window = UiHarness()
    render(window, "V_main_default.png")

    # 마우스 투과 ON 상태(액센트 채움 2개)도 확인한다.
    window.click_through_btn.setText('마우스 투과 켬')
    window.click_through_btn.setProperty("class", "PrimaryActive")
    window.click_through_btn.style().unpolish(window.click_through_btn)
    window.click_through_btn.style().polish(window.click_through_btn)
    window.zoom_slider.setValue(85)
    window.zoom_val_label.setText("8.5x")
    window.opacity_slider.setValue(70)
    window.opacity_val_label.setText("70%")
    render(window, "V_main_active.png")

    window.close()
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
