"""파티 패널의 스킬 이름 상태 표시를 실제 페인팅으로 확인한다.

RDY/CD 약어 대신 사용자가 설정한 스킬 이름이 초록/빨강으로 나오는지,
남은 초를 아는 스킬은 숫자를 유지하는지 눈으로 검증한다.

실행:
    py -3.14 design_preview/verify_skill_names.py
"""

import os
import sys
import time

os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

import magnifier

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NOW = time.time()

STATES = {
    "펭구": {
        "_class": "홀리나이트",
        "천상의 축복": {"is_ready": True, "cooldown_duration": 0, "timestamp": NOW},
        "심판의 검": {"is_ready": False, "cooldown_duration": 18.0, "timestamp": NOW},
        "구원": {"is_ready": False, "cooldown_duration": 0, "timestamp": NOW},
    },
    "테리4025": {
        "_class": "바드",
        "천상의 하모니": {"is_ready": True, "cooldown_duration": 0, "timestamp": NOW},
        "사운드홀릭": {"is_ready": False, "cooldown_duration": 3.4, "timestamp": NOW},
    },
}


def render(theme, density, display, filename):
    panel = magnifier.PartyPanel()
    panel.timer.stop()
    panel.theme_name = theme
    panel.layout_mode = density
    panel.display_mode = display
    panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    panel.apply_theme()
    panel.update_states(STATES)
    panel.tick_timers()

    pixmap = QPixmap(panel.size() * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor(58, 62, 72))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    panel.render(painter)
    painter.end()
    pixmap.save(os.path.join(OUT_DIR, filename), "PNG")
    print(f"saved {filename}  {panel.width()}x{panel.height()}")
    panel.close()


def main():
    app = QApplication(sys.argv)
    render("옵시디언 글래스", "표준", "상세 정보", "N_names_standard.png")
    render("옵시디언 글래스", "컴팩트", "상세 정보", "N_names_compact.png")
    render("옵시디언 글래스", "표준", "아이콘만", "N_names_iconsonly.png")
    del app


if __name__ == "__main__":
    main()
