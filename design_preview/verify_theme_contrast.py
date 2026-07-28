"""모든 테마 프리셋에서 보스 디버프 배너 글자가 읽히는지 확인한다.

배너의 '암흑 수류탄' 이름은 예전에 색을 지정하지 않아 앱 기본 팔레트(어두운
글자)를 그대로 썼고, 어두운 프리셋에서는 검은 글자가 검은 배경 위에 놓였다.

실행:
    py -3.14 design_preview/verify_theme_contrast.py
"""

import os
import sys
import time

os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

import boss_debuff_panel
import magnifier

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NOW = time.time()

STATES = {
    "펭구": {
        "_class": "테스트",
        "천상의 축복": {"is_ready": True, "cooldown_duration": 0, "timestamp": NOW},
        "심판의 검": {"is_ready": False, "cooldown_duration": 18.0, "timestamp": NOW},
    },
}


def contrast(front: QColor, back: QColor) -> float:
    """WCAG 상대 명도 대비비. 4.5 이상이면 본문 글자로 충분하다."""
    def channel(value):
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    def luminance(color):
        return (0.2126 * channel(color.red())
                + 0.7152 * channel(color.green())
                + 0.0722 * channel(color.blue()))

    first, second = luminance(front), luminance(back)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def blend(front: QColor, back: QColor) -> QColor:
    """알파가 있는 색을 배경 위에 합성한 실제 표시색."""
    alpha = front.alphaF()
    return QColor(
        round(front.red() * alpha + back.red() * (1 - alpha)),
        round(front.green() * alpha + back.green() * (1 - alpha)),
        round(front.blue() * alpha + back.blue() * (1 - alpha)),
    )


def main():
    app = QApplication(sys.argv)
    worst = ("", 99.0)
    rows = []
    for name, theme in magnifier.THEMES.items():
        panel = magnifier.PartyPanel()
        panel.timer.stop()
        panel.theme_name = name
        panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        panel.apply_theme()
        # 패널이 화면에 올라와 있지 않으면 자식 위젯의 isVisible() 이 항상
        # False라, _relayout 이 배너 자리를 잡아 주지 않는다.
        panel.show()
        app.processEvents()
        panel.update_states(STATES)
        panel.tick_timers()
        panel.set_boss_debuff_enabled(True)
        panel.update_boss_debuff({"active": True, "remaining": 7.4, "source": "ocr"})
        app.processEvents()

        banner = panel.boss_banner
        # 배너 카드는 패널 배경 위에 반투명하게 얹힌다. 실제 눈에 보이는 색으로
        # 합성해서 대비를 잰다.
        panel_bg = boss_debuff_panel.parse_theme_color(theme.get("bg"), QColor(18, 18, 23))
        opaque_bg = blend(panel_bg, QColor(58, 62, 72))          # 게임 화면 대신 회색
        card_fill = QColor(banner._accent_active)
        card_fill.setAlphaF(0.12)                                 # _card_style(active=True)
        card_bg = blend(card_fill, opaque_bg)
        ratio_name = contrast(banner._c_text, card_bg)
        ratio_value = contrast(banner._accent_active, card_bg)
        rows.append((name, ratio_name, ratio_value))
        if ratio_name < worst[1]:
            worst = (name, ratio_name)
        if ratio_value < worst[1]:
            worst = (f"{name} (남은시간)", ratio_value)

        pixmap = QPixmap(panel.size() * 2)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(QColor(58, 62, 72))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel.render(painter)
        painter.end()
        safe = name.replace(" ", "_")
        pixmap.save(os.path.join(OUT_DIR, f"TH_{safe}.png"), "PNG")
        panel.close()

    print(f"{'테마':<16} {'이름 대비':>9} {'남은시간 대비':>13}")
    for name, ratio_name, ratio_value in rows:
        flag = "OK" if ratio_name >= 4.5 else "LOW"
        print(f"{name:<16} {ratio_name:>9.2f} {ratio_value:>13.2f}  {flag}")
    print(f"\n최저 대비: {worst[0]} {worst[1]:.2f} (기준 4.5)")
    del app
    return 0 if worst[1] >= 4.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
