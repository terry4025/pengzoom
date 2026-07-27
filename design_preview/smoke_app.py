"""MagnifierWindow의 실제 초기화 -> 프레임 렌더 -> 종료 경로를 짧게 검증한다.

setup_ui만 떼어 보는 harness와 달리 탐지 스레드, 전역 훅, mss 캡처, 파티 패널까지
전부 붙은 상태로 돌려 본 뒤 closeEvent 정리가 예외 없이 끝나는지 확인한다.

실행:
    python design_preview/smoke_app.py
"""

import os
import sys
import traceback

os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import magnifier

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    app = QApplication(sys.argv)
    result = {"frames": 0, "error": None}

    try:
        window = magnifier.MagnifierWindow()
        window.show()
        print(f"[init] window created  {window.width()}x{window.height()}")
        print(f"[init] party panel     {window.party_panel.width()}x{window.party_panel.height()}")
        print(f"[init] follow_btn      {window.follow_btn.text()!r}")
        print(f"[init] click_thru_btn  {window.click_through_btn.text()!r}")
        print(f"[init] density mode    {window.party_panel.layout_mode!r}")

        # 실제 update_magnifier(numpy 파이프라인)를 여러 프레임 돌린다.
        def pump():
            window.update_magnifier()
            result["frames"] += 1

        pump_timer = QTimer()
        pump_timer.timeout.connect(pump)
        pump_timer.start(16)

        def finish():
            pump_timer.stop()
            has_pixmap = (window.label.pixmap() is not None
                          and not window.label.pixmap().isNull())
            print(f"[render] update_magnifier frames = {result['frames']}")
            print(f"[render] viewport pixmap set     = {has_pixmap}")
            # 핫 패스 예외는 삼켜지므로 카운터로 확인한다.
            print(f"[render] frame_error_count       = {window.frame_error_count}")
            if window.last_frame_error:
                print("[render] first frame error:")
                print(window.last_frame_error)
                result["error"] = window.last_frame_error
            if has_pixmap:
                out = os.path.join(OUT_DIR, "V_smoke_viewport.png")
                window.label.pixmap().save(out, "PNG")
                print(f"[render] saved V_smoke_viewport.png "
                      f"{window.label.pixmap().width()}x{window.label.pixmap().height()}")
            window.close()
            app.quit()

        QTimer.singleShot(1200, finish)
        app.exec()
        print("[close] closeEvent completed without exception")
    except Exception:
        result["error"] = traceback.format_exc()
        print("[FAIL]")
        print(result["error"])

    sys.stdout.flush()
    os._exit(1 if result["error"] else 0)


if __name__ == "__main__":
    main()
