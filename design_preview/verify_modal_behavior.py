"""재구성한 파티 설정 / 도움말 모달의 시그널 연결이 살아있는지 확인한다.

레이아웃을 카드 구조로 바꾸면서 위젯 생성 순서가 달라졌기 때문에,
콤보/슬라이더/버튼이 실제로 오버레이 상태를 바꾸는지 눌러 본다.
"""

import io
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "verify_modal_behavior.log")


def main():
    app = QApplication(sys.argv)
    lines = []
    try:
        import magnifier

        window = magnifier.MagnifierWindow()
        overlay = window.party_panel
        dlg = magnifier.PartyOverlaySettingsModal(window)

        # 1. 슬라이더 -> 오버레이 값 + 값 라벨 동시 반영
        dlg.scale_slider.setValue(13)
        lines.append(f"scale  overlay={overlay.ui_scale:.1f} label={dlg.lbl_scale_val.text()}")
        dlg.opacity_slider.setValue(55)
        lines.append(f"opacity overlay={overlay.panel_opacity} label={dlg.lbl_opacity_val.text()}")
        dlg.speed_slider.setValue(17)
        lines.append(f"speed  overlay={overlay.speed:.1f} label={dlg.lbl_speed_val.text()}")

        # 2. 콤보 -> 오버레이 모드 반영
        dlg.layout_combo.setCurrentText("컴팩트")
        lines.append(f"layout_mode={overlay.layout_mode}")
        dlg.display_combo.setCurrentText("아이콘만")
        lines.append(f"display_mode={overlay.display_mode}")
        theme_names = list(magnifier.THEMES.keys())
        dlg.theme_combo.setCurrentText(theme_names[-1])
        lines.append(f"theme={overlay.theme_name}")

        # 3. 직업 콤보 -> player_class 반영
        player = window.player_name
        dlg.class_combos[player].setCurrentText("버서커")
        lines.append(f"player_class={window.player_class}")

        # 4. 클릭 투과 토글 -> 오버레이 + 버튼 톤 반영
        before = overlay.panel_click_through
        dlg.btn_panel_click_through.click()
        lines.append(f"click_through {before} -> {overlay.panel_click_through}"
                     f" tone='{dlg.btn_panel_click_through.objectName()}'")
        dlg.btn_panel_click_through.click()
        lines.append(f"click_through back -> {overlay.panel_click_through}"
                     f" tone='{dlg.btn_panel_click_through.objectName()}'")

        # 5. 헤더 닫기 버튼이 살아 있는지 (close_and_save 호출)
        dlg.close_and_save()
        lines.append("close_and_save OK")

        # 6. 도움말 모달
        help_modal = magnifier.HelpModal(window)
        help_modal.accept()
        lines.append("help modal build/accept OK")

        lines.append("RESULT=OK")
    except Exception:
        lines.append(traceback.format_exc())
        lines.append("RESULT=FAIL")

    report = "\n".join(lines)
    with io.open(OUT, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(report)
    sys.stdout.flush()
    os._exit(0 if "RESULT=OK" in report else 1)


if __name__ == "__main__":
    main()
