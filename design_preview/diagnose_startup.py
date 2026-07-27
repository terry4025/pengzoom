"""앱이 즉시 종료되는 원인을 추적한다.

magnifier.__main__ 과 동일한 순서로 기동하면서 lastWindowClosed /
aboutToQuit 시그널과 각 최상위 창의 가시성을 기록한다.

실행:
    python design_preview/diagnose_startup.py
"""

import os
import sys
import traceback

os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


def dump_windows(app, tag):
    print(f"[{tag}] topLevelWidgets:")
    for widget in app.topLevelWidgets():
        print(f"    {type(widget).__name__:<24} visible={widget.isVisible()} "
              f"size={widget.width()}x{widget.height()} "
              f"opacity={widget.windowOpacity():.2f}")


def main():
    import magnifier

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    app.lastWindowClosed.connect(
        lambda: print("[signal] lastWindowClosed fired\n"
                      + "".join(traceback.format_stack())))
    app.aboutToQuit.connect(lambda: print("[signal] aboutToQuit fired"))

    try:
        window = magnifier.MagnifierWindow()
    except Exception:
        print("[FAIL] MagnifierWindow() raised:")
        traceback.print_exc()
        os._exit(2)

    dump_windows(app, "after init")
    window.show()
    app.processEvents()
    dump_windows(app, "after show")

    ticks = {"n": 0}

    def probe():
        ticks["n"] += 1
        print(f"[probe {ticks['n']}] main visible={window.isVisible()} "
              f"minimized={window.isMinimized()} "
              f"panel visible={window.party_panel.isVisible()}")

    probe_timer = QTimer()
    probe_timer.timeout.connect(probe)
    probe_timer.start(700)

    def stop():
        probe_timer.stop()
        print("[result] event loop survived 4s -> no early exit")
        dump_windows(app, "before quit")
        window.close()
        app.quit()

    QTimer.singleShot(4000, stop)
    code = app.exec()
    print(f"[result] app.exec() returned {code}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
