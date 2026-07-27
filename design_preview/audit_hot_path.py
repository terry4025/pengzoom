"""PartyPanel 핫 패스 감사 (렌더링과 분리 실행).

실행: python design_preview/audit_hot_path.py
"""

import inspect
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QTimer

import magnifier

NOW = time.time()
FIXTURE = [
    ("pengu", "\ud5f4\ub9ac\ub098\uc774\ud2b8", [("s1", True, 60, 0), ("s2", False, 36, 18)]),
    ("terry", "\ubc14\ub4dc", [("s1", True, 45, 0), ("s2", False, 24, 21), ("s3", False, 60, 19)]),
    ("brush", "\ub3c4\ud654\uac00", [("s1", True, 48, 0), ("s2", False, 30, 20)]),
    ("mage", "\uc18c\uc11c\ub9ac\uc2a4", [("s1", False, 40, 12)]),
]


def build_states():
    states = {}
    for player, cls, skills in FIXTURE:
        entry = {"_class": cls}
        for name, ready, total, elapsed in skills:
            entry[name] = {
                "is_ready": ready,
                "cooldown_duration": 0 if ready else max(0.1, total - elapsed),
                "timestamp": NOW,
            }
        states[player] = entry
    return states


def main():
    app = QApplication(sys.argv)

    source = inspect.getsource(magnifier.PartyPanel)
    qss_hits = [line.strip() for line in source.splitlines() if "setStyleSheet" in line]
    print("[static] setStyleSheet occurrences in PartyPanel source:", len(qss_hits))
    for hit in qss_hits:
        print("   ", hit.encode("ascii", "replace").decode("ascii"))

    panel = magnifier.PartyPanel()
    panel.timer.stop()
    panel.update_states(build_states())
    panel.tick_timers()

    players = len(panel.widgets)
    skills = sum(len(p["skill_widgets"]) for p in panel.widgets.values())
    children = panel.findChildren(QWidget)
    timers = panel.findChildren(QTimer)
    print(f"[structure] players={players} skills={skills}")
    print(f"[structure] child widgets={len(children)}")
    print(f"[structure] QTimer count={len(timers)}")

    frames = 300
    started = time.perf_counter()
    for _ in range(frames):
        panel.tick_timers()
    elapsed = time.perf_counter() - started
    print(f"[perf] tick_timers x{frames} = {elapsed * 1000:.1f}ms "
          f"({elapsed / frames * 1000:.4f}ms per frame)")

    panel.close()
    print("[done]")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
