"""실제 SettingsModal / PartyOverlaySettingsModal / HelpModal 을 PNG로 렌더링한다.

전체 앱을 띄우지 않고 MagnifierWindow만 만들어 모달을 붙인 뒤 각 탭을 그린다.

실행:
    python design_preview/verify_modals.py
"""

import os
import sys
import traceback

# offscreen 은 폰트 DB에 접근하지 못해 글자가 tofu(□)로 나온다.
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def render(widget, filename):
    widget.show()
    QApplication.processEvents()
    pixmap = QPixmap(widget.size() * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor(58, 62, 72))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    widget.render(painter)
    painter.end()
    out = os.path.join(OUT_DIR, filename)
    pixmap.save(out, "PNG")
    print(f"saved {filename}  {widget.width()}x{widget.height()}")


def main():
    app = QApplication(sys.argv)
    try:
        import magnifier

        window = magnifier.MagnifierWindow()

        settings = magnifier.SettingsModal(window)
        for index, name in enumerate(("hotkeys", "skills", "network")):
            settings.tabs.setCurrentIndex(index)
            QApplication.processEvents()
            render(settings, f"M_settings_{index}_{name}.png")

        party = magnifier.PartyOverlaySettingsModal(window)
        render(party, "M_party_settings.png")

        help_modal = magnifier.HelpModal(window)
        render(help_modal, "M_help.png")

        print("OK")
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
