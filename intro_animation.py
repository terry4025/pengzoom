"""마스코트 인트로 애니메이션.

앱 창이 뜨기 전에 펭구 마스코트가 튀어 올라 손을 흔들고 윙크하는 1.5초짜리
인트로를 투명 창에 그린다.

## 왜 영상이 아니라 프레임 시퀀스인가
Qt의 `QMediaPlayer`/`QVideoWidget` 는 알파를 보존하지 않아 투명 배경 영상을
띄우면 검은 사각형이 남는다. 그래서 알파가 있는 PNG 프레임을 투명 창 위에
`QPainter` 로 직접 그린다(이 프로젝트가 이미 여러 창에서 쓰는 방식).

## 그림 6장으로 어떻게 움직이나
프레임 사이의 중간 동작은 그림이 아니라 변환으로 만든다. 등장 시 스쿼시,
정착 시 스트레치, 퇴장 시 페이드는 모두 코드에서 보간하고, 손 흔들기는
`중립 → 손들기` 두 장을 왕복시켜 두 번 흔든다. 생성 모델에 24장을 요구하면
칸마다 캐릭터가 미세하게 달라져 재생 시 떨림으로 보이는데, 이 구조는 그
위험을 아예 없앤다.

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
FRAME_COUNT = 6

# 화면에 보일 마스코트 높이(논리 픽셀). 원본 캔버스(341px)보다 작게 잡아
# 확대가 일어나지 않게 한다. 확대를 섞으면 선이 흐려진다.
TARGET_HEIGHT = 300
# 팝인 오버슈트(1.06배)와 퇴장 확대가 창 밖으로 잘리지 않도록 두는 여유.
HEADROOM = 1.2

Step = namedtuple(
    "Step",
    "frame duration scale_from scale_to squash_from squash_to "
    "opacity_from opacity_to easing",
)


def _step(frame, duration, scale=(1.0, 1.0), squash=(1.0, 1.0),
          opacity=(1.0, 1.0), easing="out_cubic"):
    return Step(frame, duration, scale[0], scale[1], squash[0], squash[1],
                opacity[0], opacity[1], easing)


# 프레임 번호는 1-based(파일명과 같다).
#   1 눈 감음 · 2 날개 펼침 · 3 중립 · 4 손 들기 · 5 윙크 · 6 윙크(예비)
TIMELINE = (
    # 눈을 감은 채 아래에서 납작하게 튀어 오른다.
    _step(1, 200, scale=(0.55, 1.06), squash=(0.78, 1.0), opacity=(0.0, 1.0)),
    # 날개를 펼치며 살짝 늘어난 뒤 제 크기로 돌아온다.
    _step(2, 150, scale=(1.06, 1.0), squash=(1.06, 1.0), easing="out_quad"),
    _step(3, 130),
    _step(4, 170),
    _step(3, 130),
    _step(4, 170),
    # 윙크로 마무리한 뒤 살짝 커지며 사라진다.
    _step(5, 330),
    _step(5, 240, scale=(1.0, 1.04), opacity=(1.0, 0.0), easing="in_quad"),
)

FrameState = namedtuple("FrameState", "frame scale_x scale_y opacity done")


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
    """타임라인이 만드는 최대 배율(팝인 오버슈트 포함)."""
    return max(max(step.scale_from, step.scale_to) for step in timeline)


def state_at(elapsed_ms, timeline=TIMELINE):
    """경과 시간에 대응하는 프레임과 변환값을 돌려준다.

    Qt에 의존하지 않으므로 타임라인을 단위 테스트할 수 있다.
    """
    total = total_duration_ms(timeline)
    remaining = max(0.0, float(elapsed_ms))
    if remaining >= total:
        last = timeline[-1]
        return FrameState(last.frame, last.scale_to,
                          last.scale_to * last.squash_to, last.opacity_to, True)
    for step in timeline:
        if remaining < step.duration:
            progress = _ease(step.easing,
                             remaining / step.duration if step.duration else 1.0)
            scale = step.scale_from + (step.scale_to - step.scale_from) * progress
            squash = step.squash_from + (step.squash_to - step.squash_from) * progress
            opacity = step.opacity_from + (step.opacity_to - step.opacity_from) * progress
            return FrameState(step.frame, scale, scale * squash, opacity, False)
        remaining -= step.duration
    last = timeline[-1]
    return FrameState(last.frame, last.scale_to, last.scale_to * last.squash_to,
                      last.opacity_to, True)


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
        manifest = load_manifest(self._root) or {"canvas": [340, 341], "anchor": [170, 331]}
        self.canvas_size = manifest["canvas"]
        self.anchor = manifest["anchor"]
        self.device_ratio = self._device_ratio()
        # 원본 캔버스보다 크게 그리면 선이 흐려진다. 고DPI 화면에서는 논리
        # 픽셀 하나가 물리 픽셀 여러 개라, 배율 상한도 그만큼 낮춰야 한다.
        crisp_cap = 1.0 / (max_scale(self.timeline) * max(1.0, self.device_ratio))
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

        width = int(round(self.canvas_size[0] * self.base_scale * HEADROOM))
        height = int(round(self.canvas_size[1] * self.base_scale * HEADROOM))
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
    def paintEvent(self, _event):
        state = self._state
        pixmap = self.frame_pixmap(state.frame)
        if pixmap is None or state.opacity <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing
                               | QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(max(0.0, min(1.0, state.opacity)))

        # 발바닥(앵커)을 창 하단 기준선에 고정한 뒤 그 점을 중심으로 확대/축소한다.
        # 앵커를 고정하지 않으면 스쿼시가 공중에서 눌리는 것처럼 보인다.
        baseline_y = self.height() - (self.height() - self.canvas_size[1] * self.base_scale) / 2.0
        painter.translate(self.width() / 2.0, baseline_y)
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
