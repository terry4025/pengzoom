"""설정 → 보스 디버프 탭을 실제로 띄워 설명 문단이 사라졌는지 확인한다.

실행:
    py -3.14 design_preview/verify_boss_tab.py
"""

import os
import sys

os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel

import magnifier

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "M_boss_debuff_tab.png")


def main():
    app = QApplication(sys.argv)
    window = magnifier.MagnifierWindow()
    dialog = magnifier.SettingsModal(window)
    for index in range(dialog.tabs.count()):
        if dialog.tabs.tabText(index) == "보스 디버프":
            dialog.tabs.setCurrentIndex(index)
            break
    dialog.show()
    app.processEvents()

    tab = dialog.tabs.currentWidget()
    texts = [w.text() for w in tab.findChildren(QLabel) if w.text()]
    print("탭에 남은 라벨:")
    for text in texts:
        print("   ", text)

    pixmap = QPixmap(dialog.size())
    painter = QPainter(pixmap)
    dialog.render(painter)
    painter.end()
    pixmap.save(OUT, "PNG")
    print("saved", OUT)

    dialog.close()
    window.boss_debuff_detector.stop_detection()
    window.detector.stop_detection()
    window.party_panel.close()
    window.close()
    del app


if __name__ == "__main__":
    main()
