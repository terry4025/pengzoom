"""마스코트 인트로 애니메이션.

앱 창이 뜨기 전에 펭구 마스코트가 점프해 등장하고, 손을 두 번 흔들고, 눈을
깜빡이고, 인사한 뒤 사라지는 2초 남짓한 인트로를 투명 창에 그린다.

## 왜 영상이 아니라 프레임 시퀀스인가
Qt의 `QMediaPlayer`/`QVideoWidget` 는 알파를 보존하지 않아 투명 배경 영상을
띄우면 검은 사각형이 남는다. 그래서 알파가 있는 PNG 프레임을 투명 창 위에
`QPainter` 로 직접 그린다(이 프로젝트가 이미 여러 창에서 쓰는 방식).

## 그림 12장으로 어떻게 움직이나
그림은 **실루엣이 바뀌는 순간만** 담는다(날개 각도 3단, 눈 3단, 입 모양, 인사).
나머지는 변환으로 만든다.

  * 점프 궤적 — `dy`(표시 높이 비율)를 올렸다 내린다. 상승은 out_cubic,
    하강은 in_quad 라 실제 중력처럼 위에서 느려지고 아래에서 빨라진다.
  * 웅크림·착지 반동 — `squash`(세로 배율)로 누르고 늘린다. 발바닥을 앵커로
    잡아 눌릴 때 땅에 붙어 보인다.
  * 몸 기울기 — 손을 들 때 `rot` 로 몇 도만 기울여 무게를 싣는다.

생성 모델에 24장을 요구하면 칸마다 캐릭터가 미세하게 달라져 재생 시 떨림으로
보이는데, 이 구조는 그 위험을 없앤다.

`state_at()` 은 Qt 없이 동작하는 순수 함수라 타임라인 자체를 테스트할 수 있고,
`IntroSplash` 는 그 결과를 그리기만 한다.
"""

import json
import os
import sys
from collections import namedtuple
from pathlib import Path

from PyQt6.QtCore import QElapsedTimer, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

FRAMES_DIRNAME = "frames"
ASSETS_DIRNAME = "intro_assets"
MANIFEST_NAME = "manifest.json"
FRAME_COUNT = 12

# 화면에 보일 마스코트 높이(논리 픽셀). 원본 캔버스(286px)보다 크게 잡으면
# 확대가 섞여 선이 흐려진다.
TARGET_HEIGHT = 280
# 창 여백. 점프 높이와 오버슈트를 담고도 남을 만큼만 둔다.
SIDE_PAD = 0.14

Step = namedtuple(
    "Step",
    "frame duration scale_from scale_to squash_from squash_to "
    "dy_from dy_to rot_from rot_to opacity_from opacity_to easing",
)


def _step(frame, duration, scale=(1.0, 1.0), squash=(1.0, 1.0), dy=(0.0, 0.0),
          rot=(0.0, 0.0), opacity=(1.0, 1.0), easing="out_cubic"):
    return Step(frame, duration, scale[0], scale[1], squash[0], squash[1],
                dy[0], dy[1], rot[0], rot[1], opacity[0], opacity[1], easing)


# 프레임 번호는 1-based(파일명과 같다). 12장 시트의 포즈:
#   1 웅크림 · 2 도약(날개 아래) · 3 날개 활짝 · 4 중립 · 5 날개 45°
#   6 날개 최대 + 벌린 입 · 7 날개 최대 + 손끝 꺾임 · 8 반쯤 감은 눈
#   9 감은 눈 · 10 윙크 · 11 날개 모음 · 12 인사
TIMELINE = (
    # 등장: 웅크린 자세로 나타나 더 깊게 눌린다(도약 예비 동작).
    _step(1, 110, scale=(0.92, 0.94), squash=(0.90, 0.84), opacity=(0.0, 1.0),
          easing="out_quad"),
    _step(1, 110, scale=(0.94, 0.96), squash=(0.84, 0.74), easing="in_out_quad"),
    # 도약: 몸이 늘어나며 떠오른다.
    _step(2, 110, scale=(0.96, 1.0), squash=(0.74, 1.12), dy=(0.0, -0.06),
          easing="out_quad"),
    # 공중: 날개를 펼치고 정점까지 올라간 뒤 떨어진다.
    _step(3, 130, squash=(1.08, 1.0), dy=(-0.06, -0.20), rot=(0.0, -2.0),
          easing="out_cubic"),
    _step(3, 120, squash=(1.0, 0.98), dy=(-0.20, -0.06), rot=(-2.0, 1.0),
          easing="in_quad"),
    # 착지: 눌렸다가 반동으로 살짝 늘어난 뒤 정착한다.
    _step(1, 90, squash=(0.98, 0.80), dy=(-0.06, 0.0), easing="in_quad"),
    _step(4, 110, squash=(0.80, 1.06), rot=(1.0, 0.0), easing="out_cubic"),
    _step(4, 80, squash=(1.06, 1.0), easing="out_quad"),
    # 손 흔들기 1회차: 45° → 최대 → 손끝 꺾임 → 내려옴.
    _step(5, 90, rot=(0.0, -1.5), easing="out_quad"),
    _step(6, 90, rot=(-1.5, -3.0), easing="out_quad"),
    _step(7, 80, rot=(-3.0, -3.5), easing="linear"),
    _step(5, 80, rot=(-3.5, -1.0), easing="out_quad"),
    # 2회차.
    _step(6, 90, rot=(-1.0, -3.0), easing="out_quad"),
    _step(7, 80, rot=(-3.0, -3.5), easing="linear"),
    _step(5, 90, rot=(-3.5, 0.0), easing="out_quad"),
    _step(4, 60),
    # 눈 깜빡임(반쯤 → 완전 → 반쯤)과 윙크.
    _step(8, 60, easing="linear"),
    _step(9, 90, easing="linear"),
    _step(8, 60, easing="linear"),
    _step(10, 130),
    # 마무리: 날개를 모으고 고개를 숙여 인사한 뒤 사라진다.
    _step(11, 140, squash=(1.0, 0.99)),
    _step(12, 150, rot=(0.0, 3.0), dy=(0.0, 0.01), easing="out_quad"),
    _step(12, 200, scale=(1.0, 1.03), dy=(0.01, -0.02), opacity=(1.0, 0.0),
          easing="in_quad"),
)

FrameState = namedtuple("FrameState", "frame scale_x scale_y dy rotation opacity done")


def _ease(name, t):
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    if name == "linear":
        return t
    if name == "out_quad":
        return 1.0 - (1.0 - t) ** 2
    if name == "in_quad":
        return t * t
    if name == "in_out_quad":
        return 2 * t * t if t < 0.5 else 1.0 - ((-2 * t + 2) ** 2) / 2.0
    # 기본값: out_cubic
    return 1.0 - (1.0 - t) ** 3


def total_duration_ms(timeline=TIMELINE):
    return sum(step.duration for step in timeline)


def max_scale(timeline=TIMELINE):
    """타임라인이 만드는 최대 배율(스트레치·퇴장 확대 포함)."""
    return max(max(step.scale_from * step.squash_from,
                   step.scale_to * step.squash_to,
                   step.scale_from, step.scale_to) for step in timeline)


def max_rise(timeline=TIMELINE):
    """점프 최고 높이(표시 높이에 대한 비율)."""
    return max(0.0, max(-min(step.dy_from, step.dy_to) for step in timeline))


def max_drop(timeline=TIMELINE):
    """기준선 아래로 내려가는 최대 폭(비율)."""
    return max(0.0, max(max(step.dy_from, step.dy_to) for step in timeline))


def _final_state(timeline):
    last = timeline[-1]
    return FrameState(last.frame, last.scale_to, last.scale_to * last.squash_to,
                      last.dy_to, last.rot_to, last.opacity_to, True)


def state_at(elapsed_ms, timeline=TIMELINE):
    """경과 시간에 대응하는 프레임과 변환값을 돌려준다.

    Qt에 의존하지 않으므로 타임라인을 단위 테스트할 수 있다.
    """
    remaining = max(0.0, float(elapsed_ms))
    if remaining >= total_duration_ms(timeline):
        return _final_state(timeline)
    for step in timeline:
        if remaining < step.duration:
            progress = _ease(step.easing,
                             remaining / step.duration if step.duration else 1.0)

            def lerp(start, end):
                return start + (end - start) * progress

            scale = lerp(step.scale_from, step.scale_to)
            squash = lerp(step.squash_from, step.squash_to)
            return FrameState(step.frame, scale, scale * squash,
                              lerp(step.dy_from, step.dy_to),
                              lerp(step.rot_from, step.rot_to),
                              lerp(step.opacity_from, step.opacity_to), False)
        remaining -= step.duration
    return _final_state(timeline)


def assets_root():
    """번들(exe)과 소스 실행 모두에서 프레임 폴더를 찾는다."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / ASSETS_DIRNAME / FRAMES_DIRNAME


def frame_paths(root=None):
    root = Path(root) if root is not None else assets_root()
    return [root / f"frame_{index}.png" for index in range(1, FRAME_COUNT + 1)]


def load_manifest(root=None):
    root = Path(root) if root is not None else assets_root()
    try:
        data = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    canvas = data.get("canvas")
    anchor = data.get("anchor")
    if not (isinstance(canvas, list) and len(canvas) == 2):
        return None
    if not (isinstance(anchor, list) and len(anchor) == 2):
        anchor = [canvas[0] // 2, canvas[1]]
    return {"canvas": [int(canvas[0]), int(canvas[1])],
            "anchor": [int(anchor[0]), int(anchor[1])]}


def assets_available(root=None):
    return all(path.exists() for path in frame_paths(root)) and load_manifest(root) is not None


def config_path():
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return Path(appdata) / "PengZoom" / "config.json"


def intro_enabled(path=None):
    """설정 파일의 `show_intro` 값. 창이 만들어지기 전에 읽어야 하므로 직접 읽는다."""
    path = Path(path) if path is not None else config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(data, dict):
        return True
    return bool(data.get("show_intro", True))


class IntroSplash(QWidget):
    """프레임리스·투명 창에 인트로를 재생하고 끝나면 `finished` 를 낸다."""

    finished = pyqtSignal()

    def __init__(self, root=None, timeline=TIMELINE, parent=None):
        super().__init__(parent)
        self.timeline = timeline
        self._root = Path(root) if root is not None else assets_root()
        manifest = load_manifest(self._root) or {"canvas": [316, 286], "anchor": [158, 276]}
        self.canvas_size = manifest["canvas"]
        self.anchor = manifest["anchor"]
        self.device_ratio = self._device_ratio()

        # 원본 캔버스보다 크게 그리면 선이 흐려진다. 고DPI 화면에서는 논리
        # 픽셀 하나가 물리 픽셀 여러 개라, 배율 상한도 그만큼 낮춰야 한다.
        peak = max_scale(self.timeline)
        crisp_cap = 1.0 / (peak * max(1.0, self.device_ratio))
        self.base_scale = min(TARGET_HEIGHT / float(self.canvas_size[1]), crisp_cap)

        self._frames = {}
        self._state = state_at(0, self.timeline)
        self._emitted = False
        self._elapsed = QElapsedTimer()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setToolTip("클릭하거나 ESC를 누르면 건너뜁니다")

        # 표시 크기와 창 크기. 창은 점프 최고점과 최대 배율을 모두 담아야 한다.
        self.display_w = self.canvas_size[0] * self.base_scale
        self.display_h = self.canvas_size[1] * self.base_scale
        self.bottom_pad = self.display_h * (0.04 + max_drop(self.timeline))
        width = int(round(self.display_w * (peak + SIDE_PAD)))
        height = int(round(self.display_h * (peak + max_rise(self.timeline)) + self.bottom_pad))
        self.resize(width, height)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------ 자원
    @staticmethod
    def _device_ratio():
        screen = None
        if QApplication.instance() is not None:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        try:
            return float(screen.devicePixelRatio()) if screen is not None else 1.0
        except Exception:
            return 1.0

    def frame_pixmap(self, number):
        """프레임을 지연 로딩한다. 없으면 None(그 프레임은 건너뛴다)."""
        if number in self._frames:
            return self._frames[number]
        pixmap = QPixmap(str(self._root / f"frame_{number}.png"))
        self._frames[number] = None if pixmap.isNull() else pixmap
        return self._frames[number]

    # ------------------------------------------------------------------ 재생
    def start(self):
        self.center_on_cursor_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._elapsed.start()
        self._timer.start()
        self.update()

    def center_on_cursor_screen(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.center().x() - self.width() // 2,
                  area.center().y() - self.height() // 2)

    def render_at(self, elapsed_ms):
        """지정한 경과 시간의 상태로 갱신한다(테스트에서도 쓴다)."""
        self._state = state_at(elapsed_ms, self.timeline)
        self.update()
        if self._state.done:
            self._finish()
        return self._state

    def _tick(self):
        self.render_at(self._elapsed.elapsed())

    def skip(self):
        self._finish()

    def _finish(self):
        if self._emitted:
            return
        self._emitted = True
        self._timer.stop()
        self.hide()
        self.finished.emit()

    # ------------------------------------------------------------------ 입력
    def mousePressEvent(self, event):
        self.skip()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.skip()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ 그리기
    def baseline_y(self):
        """발바닥이 놓이는 창 안의 y 좌표."""
        return self.height() - self.bottom_pad

    def paintEvent(self, _event):
        state = self._state
        pixmap = self.frame_pixmap(state.frame)
        if pixmap is None or state.opacity <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing
                               | QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(max(0.0, min(1.0, state.opacity)))

        # 발바닥(앵커)을 기준선에 놓고 그 점을 중심으로 기울이고 확대/축소한다.
        # 앵커를 고정하지 않으면 스쿼시가 공중에서 눌리는 것처럼 보인다.
        painter.translate(self.width() / 2.0,
                          self.baseline_y() + state.dy * self.display_h)
        if state.rotation:
            painter.rotate(state.rotation)
        painter.scale(self.base_scale * state.scale_x, self.base_scale * state.scale_y)
        painter.drawPixmap(
            QRectF(-self.anchor[0], -self.anchor[1],
                   self.canvas_size[0], self.canvas_size[1]),
            pixmap,
            QRectF(0, 0, pixmap.width(), pixmap.height()),
        )
        painter.end()


def create_intro(root=None, timeline=TIMELINE):
    """자원이 갖춰져 있으면 인트로 위젯을, 아니면 None을 준다."""
    root = Path(root) if root is not None else assets_root()
    if not assets_available(root):
        return None
    return IntroSplash(root=root, timeline=timeline)
