"""보스 디버프 배너가 커스텀 페인팅 파티 패널 안에서 제대로 배치되는지 확인한다.

패널 본체는 위젯 트리 없이 paintEvent로 직접 그린다. 배너만 자식 위젯이라
_relayout에서 직접 setGeometry로 배치하고 높이를 예약해야 하는데, 이게 빠지면
배너가 카드와 겹치거나 패널 밖으로 나간다.
"""

import io
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def render(widget, filename):
    QApplication.processEvents()
    pixmap = QPixmap(widget.size() * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor(58, 62, 72))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    widget.render(painter)
    painter.end()
    pixmap.save(os.path.join(OUT_DIR, filename), "PNG")


def main():
    app = QApplication(sys.argv)
    lines = []
    try:
        import magnifier

        panel = magnifier.PartyPanel()
        panel.player_classes = {"펭구": "홀리나이트", "동료": "버서커"}
        panel.update_states({
            "펭구": {"_class": "홀리나이트",
                     "구원": {"is_ready": True, "cooldown_duration": 0, "timestamp": 0},
                     "천상의 축복": {"is_ready": False, "cooldown_duration": 12, "timestamp": 0}},
            "동료": {"_class": "버서커",
                     "블러디 러스트": {"is_ready": True, "cooldown_duration": 0, "timestamp": 0}},
        })
        panel.show()
        QApplication.processEvents()

        lines.append(f"배너 기본 가시성 (꺼짐이어야 함): {panel.boss_banner.isVisible()}")
        h_without = panel.height()
        lines.append(f"배너 없을 때 패널 높이: {h_without}")
        render(panel, "T_party_no_banner.png")

        # 로컬 감지를 켜면 배너가 나타나고 높이가 늘어나야 한다.
        panel.set_boss_debuff_enabled(True)
        QApplication.processEvents()
        lines.append(f"감지 켠 뒤 가시성: {panel.boss_banner.isVisible()}")
        h_with = panel.height()
        lines.append(f"배너 있을 때 패널 높이: {h_with} (증가폭 {h_with - h_without})")

        geo = panel.boss_banner.geometry()
        lines.append(f"배너 geometry: x={geo.x()} y={geo.y()} w={geo.width()} h={geo.height()}")
        lines.append(f"배너가 패널 안에 있는가: "
                     f"{geo.right() <= panel.width() and geo.bottom() <= panel.height()}")

        # 첫 카드가 배너 아래에서 시작해야 한다(겹치면 안 된다).
        first_card = panel._layout_cache[0]["rect"] if panel._layout_cache else None
        if first_card is not None:
            lines.append(f"첫 카드 top={first_card.top():.0f} / 배너 bottom={geo.bottom()}")
            lines.append(f"겹침 없음: {first_card.top() >= geo.bottom()}")

        # 실제 디버프 상태를 넣어 표시가 바뀌는지 본다.
        panel.update_boss_debuff({"active": True, "remaining": 9.0, "source": "ocr"})
        QApplication.processEvents()
        lines.append(f"값 라벨: '{panel.boss_banner.value_label.text()}' "
                     f"상세: '{panel.boss_banner.detail_label.text()}'")
        render(panel, "T_party_with_banner.png")

        # 테마/배율 변경이 배너까지 전파되는지
        panel.ui_scale = 1.4
        panel.theme_name = list(magnifier.THEMES.keys())[-1]
        panel.apply_theme()
        QApplication.processEvents()
        lines.append(f"배율 1.4 적용 후 배너 높이: {panel.boss_banner.height()}")
        render(panel, "T_party_banner_scaled.png")

        # 감지를 끄면 로컬 보고가 사라져 배너가 숨어야 한다.
        panel.set_boss_debuff_enabled(False)
        QApplication.processEvents()
        lines.append(f"감지 끈 뒤 가시성: {panel.boss_banner.isVisible()}")

        panel.close()
        lines.append("RESULT=OK")
    except Exception:
        lines.append(traceback.format_exc())
        lines.append("RESULT=FAIL")

    report = "\n".join(lines)
    with io.open(os.path.join(OUT_DIR, "verify_boss_banner.log"), "w", encoding="utf-8") as handle:
        handle.write(report)
    print(report)
    sys.stdout.flush()
    os._exit(0 if "RESULT=OK" in report else 1)


if __name__ == "__main__":
    main()
