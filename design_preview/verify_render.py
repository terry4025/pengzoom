"""실제 magnifier.PartyPanel 구현을 PNG로 렌더링해 시각 검증한다.

목업(render_concepts.py)이 아니라 앱에 들어간 진짜 코드를 그린다.

실행:
    python design_preview/verify_render.py
"""

import os
import sys
import time

# 주의: QT_QPA_PLATFORM=offscreen 은 시스템 폰트 DB에 접근하지 못해 모든 글자가
# tofu(□)로 렌더링된다. 시각 검증은 반드시 네이티브 플랫폼에서 해야 한다.
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

import magnifier

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

NOW = time.time()
# (플레이어, 클래스, [(스킬, 준비여부, 쿨타임 총량, 경과초)])
FIXTURE = [
    ("펭구", "홀리나이트", [("헤븐리블레싱", True, 60, 0), ("소드오브저지먼트", False, 36, 18)]),
    ("테리4025", "바드", [("천상의 하모니", True, 45, 0), ("사운드홀릭", False, 24, 21), ("하베스트송", False, 60, 19)]),
    ("붓칼", "도화가", [("문양: 해", True, 48, 0), ("색채의 마술", False, 30, 20)]),
    ("불꽃마법사", "소서리스", [("점화", False, 40, 12)]),
]


def build_states(stale_last=False):
    states = {}
    for index, (player, cls, skills) in enumerate(FIXTURE):
        # 마지막 파티원만 오프라인(갱신 끊김) 상태로 만들어 표시를 확인한다.
        offline = stale_last and index == len(FIXTURE) - 1
        base_ts = NOW - (30.0 if offline else 0.0)
        entry = {"_class": cls}
        for name, ready, total, elapsed in skills:
            entry[name] = {
                "is_ready": ready,
                "cooldown_duration": 0 if ready else max(0.1, total - elapsed),
                "timestamp": base_ts,
            }
        states[player] = entry
    return states


def render(panel, filename):
    pixmap = QPixmap(panel.size() * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor(58, 62, 72))  # 게임 화면 대신 중간 회색 (반투명 확인용)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    panel.render(painter)
    painter.end()
    out = os.path.join(OUT_DIR, filename)
    pixmap.save(out, "PNG")
    print(f"saved {filename}  {panel.width()}x{panel.height()}")


def make_panel(theme, density, display, stale_last=False):
    panel = magnifier.PartyPanel()
    panel.timer.stop()
    panel.theme_name = theme
    panel.layout_mode = density
    panel.display_mode = display
    panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    panel.apply_theme()
    panel.update_states(build_states(stale_last))
    panel.tick_timers()
    return panel


def audit_hot_path():
    """핫 패스에 QSS 호출이 없고 위젯/타이머가 증식하지 않는지 검증한다."""
    import inspect

    source = inspect.getsource(magnifier.PartyPanel)
    qss_hits = [line.strip() for line in source.splitlines()
                if "setStyleSheet" in line]
    print("\n[정적 검사] PartyPanel 전체 소스의 setStyleSheet 호출: "
          f"{len(qss_hits)}건")
    for hit in qss_hits:
        print(f"   {hit}")

    panel = make_panel("옵시디언 글래스", "표준", "상세 정보")
    players = len(panel.widgets)
    skills = sum(len(p["skill_widgets"]) for p in panel.widgets.values())
    children = panel.findChildren(magnifier.QWidget)
    timers = panel.findChildren(magnifier.QTimer)
    print(f"\n[구조 검사] 파티원 {players}명 / 스킬 {skills}개")
    print(f"   자식 위젯 수: {len(children)}  (구버전: 파티원·스킬마다 생성)")
    print(f"   QTimer 수: {len(timers)}      (구버전: 1 + GlowDot 개수)")

    frames = 300
    started = time.perf_counter()
    for _ in range(frames):
        panel.tick_timers()
    elapsed = time.perf_counter() - started
    print(f"\n[성능] tick_timers {frames}회: {elapsed * 1000:.1f}ms "
          f"(프레임당 {elapsed / frames * 1000:.3f}ms)")
    panel.close()
    return len(qss_hits), len(children), len(timers)


def main():
    app = QApplication(sys.argv)
    jobs = [
        ("옵시디언 글래스", "표준", "상세 정보", False, "V_obsidian_standard.png"),
        ("옵시디언 글래스", "컴팩트", "상세 정보", False, "V_obsidian_compact.png"),
        ("옵시디언 글래스", "표준", "아이콘만", False, "V_obsidian_iconsonly.png"),
        ("옵시디언 글래스", "표준", "상세 정보", True, "V_obsidian_offline.png"),
        ("노르딕 라이트", "표준", "상세 정보", False, "V_nordic_standard.png"),
        ("크림슨 벨벳", "컴팩트", "상세 정보", False, "V_crimson_compact.png"),
    ]
    panels = []
    for theme, density, display, stale, name in jobs:
        panel = make_panel(theme, density, display, stale)
        render(panel, name)
        panels.append(panel)

    # 핫 패스 계측은 design_preview/audit_hot_path.py 에서 따로 실행한다.
    for panel in panels:
        panel.close()
    del app


if __name__ == "__main__":
    main()
