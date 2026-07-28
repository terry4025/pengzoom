"""Boss debuff (암흑 수류탄) recognition for the boss HP bar debuff strip.

Why this is not just another cooldown slot
------------------------------------------
* The boss debuff cells are re-centred under the boss HP bar every time a
  debuff is added or removed, so a fixed slot rectangle never works.  The strip
  is scanned as one wide band and the icon is located inside it every frame.
* The same item icon is also visible in the bottom-right battle-item hotkey
  bar.  Only the user-selected band above the boss HP bar is ever captured, and
  the match threshold is high enough to reject the hotkey-bar rendering
  (measured 0.52~0.61 there against 1.00 on the real debuff cell).
* The remaining-time text under the cell is only ~8 px tall at 1080p, far
  smaller than the skill cooldown digits.  It is magnified 4x and segmented on
  the warm (R-B) channel, which separates the salmon text from any background
  the arena shows; the digits are then matched against a trained glyph set.
  Seconds are resolved by the first source that is actually reliable:
  trained OCR -> the 2-digit/1-digit transition anchor -> learned duration.
* Training samples are labelled backwards from the moment the debuff
  *disappears*, never from the live estimate.  Labelling from the estimate is
  self-referential: one wrong guess is written to disk, trained on, and then
  confirms itself forever (the "always 8 seconds" failure).
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np

try:  # Qt is optional so the tracker can be unit-tested headless.
    import mss
    from PyQt6.QtCore import QRect, QThread, pyqtSignal
    _QT_AVAILABLE = True
except Exception:  # pragma: no cover - only hit on a broken install
    mss = None
    QRect = None
    QThread = object
    _QT_AVAILABLE = False

    def pyqtSignal(*_args, **_kwargs):  # type: ignore
        return None


PROFILE_VERSION = 3  # v3: adds appearance patches for correlation reading (v2 lacks them)
DEFAULT_DEBUFF_ID = "dark_grenade"
DEBUFF_DISPLAY_NAMES = {DEFAULT_DEBUFF_ID: "암흑 수류탄"}

GLYPH_SIZE = (12, 16)  # width, height of the normalized glyph canvas

# Timer text is drawn in a warm salmon tone (RGB 216,139,111 at 1080p) over an
# arbitrary game background.  R-B separates it from the (mostly blue/grey)
# world far better than luminance does: the text scores ~+105 while blue water
# scores 0 after clipping.  A top-hat on that channel then removes any large
# warm area (fire, blood, UI tint) and keeps only thin strokes.
TIMER_TOPHAT_KERNEL = (7, 7)     # in *source* pixels, scaled by TIMER_UPSCALE
TIMER_UPSCALE = 4                # 8px tall text is segmented far more stably at 32px
TIMER_MIN_PEAK = 12              # below this the ROI holds no timer text at all
TIMER_SCORE_FRACTION = 0.42      # binarize at this fraction of the strongest stroke

# Cell geometry measured on the reference 1080p capture:
#   cell 26x26 at (930,155);  text "9초" at x 936..950, y 185..192
# Everything below is expressed relative to the matched cell so it survives UI
# scale changes and the constant horizontal re-centring of the strip.
DIGIT_ROI_LEFT = -0.35     # * cell width, from the cell left edge
DIGIT_ROI_WIDTH = 1.70     # * cell width
DIGIT_ROI_TOP = 0.04       # * cell height, from the cell bottom edge
DIGIT_ROI_HEIGHT = 0.62    # * cell height

DEFAULT_MATCH_THRESHOLD = 0.80
DEFAULT_MIN_ICON_PX = 16
DEFAULT_MAX_ICON_PX = 46
DEFAULT_SCAN_INTERVAL = 0.1

ACTIVATE_FRAMES = 2        # consecutive hits required before reporting active
DEACTIVATE_FRAMES = 3      # consecutive misses required before clearing
GLYPH_COUNT_FRAMES = 2     # debounce for the digit-count anchor
TICK_DIFF_RATIO = 0.14     # normalized pixel change that counts as a 1s tick

# The 2-digit -> 1-digit anchor is only trustworthy if the two-digit state was
# actually held for a while.  A single flickering frame must never re-pin the
# countdown to 9s: that was the cause of the "always 8 seconds" readout.
ANCHOR_MIN_TWO_DIGIT_SEC = 0.8
OCR_AGREE_TOLERANCE = 1.2  # seconds two consecutive reads may disagree by
OCR_CONFIRM_WINDOW = 2.5   # a pending first read expires after this long
OCR_GRACE_SEC = 0.7        # hold "ON" this long before falling back to an estimate
REFRESH_JUMP_SEC = 2.5     # a confirmed reading this far above the estimate = re-applied
MAX_LEARNED_DURATION = 60.0  # sanity cap for an auto-learned total

MAX_NEAREST_DISTANCE = 3.2
MIN_MARGIN = 0.10
MIN_OCR_CONFIDENCE = 0.70
MIN_SUFFIX_SIMILARITY = 0.45   # '초' 글리프 모양 확인 하한
MIN_TRAINED_DIGITS = 8     # digits 0-9 coverage required before OCR is trusted
MIN_TRAINED_ACCURACY = 0.90  # leave-one-out accuracy required before OCR is trusted

# --- 상관 정합(NCC) 경로 ---------------------------------------------------
# 이진화 -> 덩어리 분리 -> 분류 대신, 학습된 숫자 모양을 회색 점수 이미지에
# 정규화 상관으로 직접 맞춘다. 정규화 상관은 밝기·대비 변화에 불변이라 배경이
# 글자와 같은 색조로 물들어도(용암·석양) 분리 실패로 무너지지 않는다.
NCC_HEIGHT_RATIOS = (0.42, 0.50, 0.58)   # * ROI 높이. 8px 텍스트 = ROI의 약 0.5
NCC_MIN_SUFFIX = 0.50      # '초' 정합 하한. 이보다 낮으면 타이머 줄이 아니다
NCC_MIN_DIGIT = 0.60       # 숫자 정합 하한. 실측 정답 위치는 0.90 을 넘는다
NCC_MAX_DIGITS = 2         # 표시되는 남은 초는 두 자리를 넘지 않는다
# 외형 템플릿은 실측 점수 이미지에서 그대로 잘라 보관한다. 정규화된 12x16 이진
# 캔버스를 되키운 템플릿은 획 모양이 어긋나 '초' 정합이 0.60 에 머물렀고, 그
# 어긋난 위치가 '14초' 를 '1초' 로 읽는 원인이었다. 실측 외형은 0.95 를 넘는다.
PATCH_HEIGHT = 32          # 글자(잉크) 높이 기준 정규화 높이
PATCH_MARGIN = 0.18        # * 글자 높이. 템플릿에 함께 담는 실제 배경 여백

SAMPLE_MIN_INTERVAL = 0.4  # two crops per displayed second is plenty
SAMPLE_BUFFER_FRAMES = 240  # ~96s of a single cast at the interval above


def assets_root() -> Path:
    """Bundled asset folder (PyInstaller aware)."""
    import sys
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "boss_debuff_assets"


def user_data_root() -> Path:
    root = Path(os.environ.get("APPDATA", str(Path.home()))) / "PengZoom" / "boss_debuff"
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_image(path: Path, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
    """Read a PNG through numpy so non-ASCII (Korean) paths keep working."""
    try:
        return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), flags)
    except Exception:
        return None


def write_image(path: Path, image: np.ndarray) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ok, buf = cv2.imencode(".png", image)
        if ok:
            buf.tofile(str(path))
        return bool(ok)
    except Exception:
        return False


def encode_png(image: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", image)
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""


def decode_png(value: str) -> Optional[np.ndarray]:
    if not value:
        return None
    try:
        raw = np.frombuffer(base64.b64decode(value), dtype=np.uint8)
        return cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Timer text pipeline
# ---------------------------------------------------------------------------

def digit_roi_from_cell(cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> tuple[int, int, int, int]:
    """Timer-text rectangle directly under a matched debuff cell."""
    x = int(round(cell_x + DIGIT_ROI_LEFT * cell_w))
    y = int(round(cell_y + cell_h + DIGIT_ROI_TOP * cell_h))
    w = max(6, int(round(DIGIT_ROI_WIDTH * cell_w)))
    h = max(5, int(round(DIGIT_ROI_HEIGHT * cell_h)))
    return x, y, w, h


def timer_tophat(image_bgr: np.ndarray) -> np.ndarray:
    """Legacy grayscale top-hat, kept for callers that want a luminance view."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, TIMER_TOPHAT_KERNEL)
    return cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)


def upscale_roi(image_bgr: np.ndarray, upscale: int = TIMER_UPSCALE) -> np.ndarray:
    """8px 텍스트를 세그먼테이션이 안정적인 크기로 키운다."""
    upscale = max(1, int(upscale))
    if upscale == 1:
        return image_bgr
    return cv2.resize(image_bgr, None, fx=upscale, fy=upscale,
                      interpolation=cv2.INTER_CUBIC)


def _tophat_kernel(upscale: int) -> np.ndarray:
    return cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(3, TIMER_TOPHAT_KERNEL[0] * upscale), max(3, TIMER_TOPHAT_KERNEL[1] * upscale)))


def text_chroma(color_bgr: Iterable[int]) -> tuple[float, float]:
    """BGR 색의 Lab 색상 좌표(a*, b*). 밝기는 버린다."""
    patch = np.zeros((1, 1, 3), np.uint8)
    patch[0, 0] = [int(v) for v in color_bgr]
    lab = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)[0, 0]
    return float(lab[1]), float(lab[2])


DEFAULT_TEXT_BGR = (111, 139, 216)     # 1080p 실측 살몬색 (RGB 216,139,111)
DEFAULT_TEXT_CHROMA = text_chroma(DEFAULT_TEXT_BGR)

# 서로 다른 배경에서 각각 강한 채널들. 한 채널로는 모든 보스방을 덮을 수 없다.
#   warm   : R-B. 파랑/회색 배경에서 압도적으로 강하다.
#   chroma : 글자 색조와의 거리. 배경이 따뜻하지만 색조가 다를 때 유효하다.
#   bright : 밝기 top-hat. 배경이 글자와 같은 색조일 때 어두운 외곽선 덕에 남는다.
#   dark   : 밝기 bottom-hat. 배경이 글자보다 밝을 때(설원·백색 아레나) 유효하다.
TIMER_SCORE_MODES = ("warm", "chroma", "bright", "dark")
# 검증된 기본 분리 지점(0.42)을 먼저 쓰고, 실패할 때만 더 관대한/엄격한 값을 본다.
TIMER_SCORE_FRACTIONS = (0.42, 0.33, 0.55)


def timer_score(big_bgr: np.ndarray, mode: str,
                chroma: tuple[float, float] = None,
                upscale: int = TIMER_UPSCALE) -> np.ndarray:
    """업스케일된 ROI에서 글자 획만 남기는 점수 이미지."""
    kernel = _tophat_kernel(upscale)
    if big_bgr.ndim == 2:
        gray = big_bgr
    else:
        gray = cv2.cvtColor(big_bgr, cv2.COLOR_BGR2GRAY)

    if mode == "warm":
        if big_bgr.ndim == 2:
            base = gray
        else:
            channels = big_bgr.astype(np.int16)
            base = np.clip(channels[:, :, 2] - channels[:, :, 0], 0, 255).astype(np.uint8)
        return cv2.morphologyEx(base, cv2.MORPH_TOPHAT, kernel)
    if mode == "chroma":
        if big_bgr.ndim == 2:
            return np.zeros_like(gray)
        target = chroma or DEFAULT_TEXT_CHROMA
        lab = cv2.cvtColor(big_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        distance = np.hypot(lab[:, :, 1] - target[0], lab[:, :, 2] - target[1])
        closeness = np.clip(255.0 - distance * 3.0, 0, 255).astype(np.uint8)
        return cv2.morphologyEx(closeness, cv2.MORPH_TOPHAT, kernel)
    if mode == "bright":
        return cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    if mode == "dark":
        return cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    raise ValueError(f"unknown timer score mode: {mode}")


def timer_text_score(image_bgr: np.ndarray,
                     upscale: int = TIMER_UPSCALE) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(upscaled_bgr, score)`` for the default (warm) channel."""
    big = upscale_roi(image_bgr, upscale)
    return big, timer_score(big, "warm", upscale=upscale)


def binarize_timer_text(image_bgr: np.ndarray, threshold: Optional[int] = None,
                        upscale: int = TIMER_UPSCALE, mode: str = "warm",
                        chroma: tuple[float, float] = None) -> tuple[np.ndarray, int]:
    """Return ``(binary, used_threshold)`` for one hypothesis of the timer ROI.

    A single deterministic threshold is derived from the strongest stroke in the
    ROI instead of sweeping fixed values.  The old sweep picked a different
    threshold nearly every frame, so the same ``17초`` segmented as 1, 2 or 3
    glyphs from one frame to the next.
    """
    big = upscale_roi(image_bgr, upscale)
    score = timer_score(big, mode, chroma, upscale)
    peak = int(score.max()) if score.size else 0
    if threshold is None:
        if peak < TIMER_MIN_PEAK:
            return np.zeros(score.shape, np.uint8), 0
        threshold = max(10, int(round(peak * TIMER_SCORE_FRACTION)))
    binary = (score >= int(threshold)).astype(np.uint8) * 255
    if upscale > 1:
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    return binary, int(threshold)


def _components(binary: np.ndarray, min_area: int = 3) -> list[tuple[int, int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    result = []
    for x, y, w, h, area in stats[1:count]:
        if area >= min_area:
            result.append((int(x), int(y), int(w), int(h), int(area)))
    return result


def _merge_split_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Join boxes that are two halves of one glyph.

    Only boxes whose x ranges genuinely overlap are merged (a ``9`` can break
    into bowl + tail).  Merging by proximity instead would glue the ``1`` and
    the ``7`` of ``17초`` into a single box.
    """
    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda b: b[0]):
        for index, previous in enumerate(merged):
            overlap = (min(previous[0] + previous[2], box[0] + box[2])
                       - max(previous[0], box[0]))
            if overlap >= 0.45 * min(previous[2], box[2]):
                x0 = min(previous[0], box[0])
                y0 = min(previous[1], box[1])
                x1 = max(previous[0] + previous[2], box[0] + box[2])
                y1 = max(previous[1] + previous[3], box[1] + box[3])
                merged[index] = (x0, y0, x1 - x0, y1 - y0)
                break
        else:
            merged.append(tuple(int(v) for v in box))
    merged.sort(key=lambda b: b[0])
    return merged


def segment_timer_glyphs(binary: np.ndarray) -> tuple[Optional[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    """Locate the ``초`` suffix and the digits to its left.

    Every rule is expressed as a fraction of the ROI height, so the same code
    works on a raw 16px ROI and on the 4x upscaled binary.  The suffix is the
    widest text-height component nearest the horizontal centre: the ROI is
    centred on the debuff cell, so a neighbouring cell's text can only ever
    appear at the far left/right edge.
    """
    height, width = binary.shape[:2]
    comps = _components(binary, min_area=3 if height <= 24 else 6)
    if not comps:
        return None, []

    boxes = _merge_split_boxes([(c[0], c[1], c[2], c[3]) for c in comps])
    text_h = max(4.0, height * 0.38)
    tall = [b for b in boxes if b[3] >= text_h]
    if not tall:
        return None, []

    centre = width / 2.0
    # ``초`` is wider than any digit at this scale (10px vs 3-6px at 1080p).
    suffix_candidates = [
        b for b in tall
        if b[2] >= height * 0.40 and b[0] > centre - width * 0.32
        and b[0] > 0 and (b[0] + b[2]) < width
    ]
    if not suffix_candidates:
        return None, []
    suffix = max(suffix_candidates, key=lambda b: (b[2] * b[3], -abs(b[0] - centre)))
    sx, sy, sw, sh, = suffix
    suffix_box = (sx, sy, sw, sh)

    slack = max(1, int(round(height * 0.05)))
    digits = [b for b in tall
              if b[0] + b[2] <= sx + slack        # left of the suffix
              and b[0] > 0                        # not clipped -> not a neighbour
              and b[2] <= max(4, int(round(height * 0.45)))]
    digits.sort(key=lambda b: b[0])
    # Keep only the run adjacent to the suffix.  One glyph advance is ~0.85 of
    # the text height, a neighbouring cell sits a whole cell width away.
    if digits:
        gap_limit = max(2, int(round(sh * 0.85)))
        kept = [digits[-1]]
        for box in reversed(digits[:-1]):
            previous = kept[0]
            if previous[0] - (box[0] + box[2]) <= gap_limit:
                kept.insert(0, box)
            else:
                break
        digits = kept[-3:]
    return suffix_box, [tuple(int(v) for v in b) for b in digits]


def has_decimal_point(binary: np.ndarray, suffix_box, digit_boxes) -> bool:
    """True when the timer shows a sub-second value such as ``0.4초``.

    Below one second the game switches to one decimal place.  The dot is too
    short to pass the digit height filter, so ``0.4초`` would otherwise be read
    as the two-digit number 04 and re-trigger the 2->1 digit anchor.
    """
    if suffix_box is None or len(digit_boxes) < 2:
        return False
    height = binary.shape[0]
    left = min(b[0] for b in digit_boxes)
    right = suffix_box[0]
    baseline = min(b[1] + b[3] for b in digit_boxes)
    for x, y, w, h, _area in _components(binary, min_area=1):
        if h >= height * 0.38 or w > height * 0.30:
            continue
        if x <= left or x + w > right:
            continue
        if y + h >= baseline - height * 0.12:
            return True
    return False


def normalize_glyph(binary: np.ndarray, box: Iterable[int]) -> np.ndarray:
    x, y, w, h = (int(v) for v in box)
    crop = binary[max(0, y):y + h, max(0, x):x + w]
    canvas = np.zeros((GLYPH_SIZE[1], GLYPH_SIZE[0]), np.uint8)
    if crop.size == 0:
        return canvas
    max_w, max_h = GLYPH_SIZE[0] - 2, GLYPH_SIZE[1] - 2
    scale = min(max_w / max(1, crop.shape[1]), max_h / max(1, crop.shape[0]))
    nw = max(1, int(round(crop.shape[1] * scale)))
    nh = max(1, int(round(crop.shape[0] * scale)))
    # Averaging on the way down keeps a 32px stroke recognizable; nearest
    # neighbour would alias it into a different shape every frame.
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_NEAREST
    resized = cv2.resize(crop, (nw, nh), interpolation=interpolation)
    resized = (resized >= 110).astype(np.uint8) * 255
    ox = (GLYPH_SIZE[0] - nw) // 2
    oy = (GLYPH_SIZE[1] - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas


_HOG = cv2.HOGDescriptor(
    _winSize=GLYPH_SIZE,
    _blockSize=(4, 4),
    _blockStride=(2, 2),
    _cellSize=(2, 2),
    _nbins=9,
)


def glyph_features(glyph: np.ndarray) -> np.ndarray:
    return _HOG.compute(glyph).reshape(-1).astype(np.float32)


@dataclass
class TimerGlyphProfile:
    """Nearest-neighbour glyph set for the 8px ``N초`` debuff timer."""

    profile_id: str = DEFAULT_DEBUFF_ID
    version: int = PROFILE_VERSION
    text_height: int = 8
    labels: list[int] = field(default_factory=list)
    glyphs: list[str] = field(default_factory=list)
    suffix_glyphs: list[str] = field(default_factory=list)
    patch_labels: list[int] = field(default_factory=list)
    patch_modes: list[str] = field(default_factory=list)
    patches: list[str] = field(default_factory=list)
    accuracy: float = 0.0
    source: str = "bootstrap"
    _features: Optional[np.ndarray] = field(default=None, repr=False, compare=False)
    _labels_np: Optional[np.ndarray] = field(default=None, repr=False, compare=False)
    _suffix_features: Optional[np.ndarray] = field(default=None, repr=False, compare=False)
    _loo: Optional[float] = field(default=None, repr=False, compare=False)
    _stencils: Optional[tuple] = field(default=None, repr=False, compare=False)
    _patch_stencils: Optional[tuple] = field(default=None, repr=False, compare=False)

    # -- persistence --------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "text_height": self.text_height,
            "labels": self.labels,
            "glyphs": self.glyphs,
            "suffix_glyphs": self.suffix_glyphs,
            "patch_labels": self.patch_labels,
            "patch_modes": self.patch_modes,
            "patches": self.patches,
            "accuracy": round(float(self.accuracy), 4),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimerGlyphProfile":
        return cls(
            profile_id=str(data.get("profile_id", DEFAULT_DEBUFF_ID)),
            version=int(data.get("version", PROFILE_VERSION)),
            text_height=int(data.get("text_height", 8)),
            labels=[int(v) for v in data.get("labels", [])],
            glyphs=[str(v) for v in data.get("glyphs", [])],
            suffix_glyphs=[str(v) for v in data.get("suffix_glyphs", [])],
            patch_labels=[int(v) for v in data.get("patch_labels", [])],
            patch_modes=[str(v) for v in data.get("patch_modes", [])],
            patches=[str(v) for v in data.get("patches", [])],
            accuracy=float(data.get("accuracy", 0.0) or 0.0),
            source=str(data.get("source", "bootstrap")),
        )

    @classmethod
    def load(cls, path: Path) -> Optional["TimerGlyphProfile"]:
        try:
            if Path(path).exists():
                return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        except Exception:
            pass
        return None

    @classmethod
    def load_for(cls, debuff_id: str = DEFAULT_DEBUFF_ID) -> "TimerGlyphProfile":
        """Pick the best usable profile: user-trained first, bundled seed next.

        A user profile that cannot separate its own digits (trained from a bad
        sample round) must not shadow the verified bundled seed, so an untrusted
        user profile loses to a trusted bundled one.  Profiles from an older
        ``PROFILE_VERSION`` are ignored: their glyphs were produced by a
        different binarization and no longer describe the same shapes.
        """
        candidates = []
        for path in (user_data_root() / "timer_profiles" / f"{debuff_id}.json",
                     assets_root() / "timer_profiles" / f"{debuff_id}.json"):
            profile = cls.load(path)
            if profile is not None and profile.version == PROFILE_VERSION:
                candidates.append(profile)
        for profile in candidates:
            if profile.trusted:
                return profile
        return candidates[0] if candidates else cls(profile_id=debuff_id)

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        return path

    # -- training -----------------------------------------------------------
    def add_digit(self, digit: int, glyph: np.ndarray) -> bool:
        encoded = encode_png(glyph)
        if not encoded or (digit, encoded) in set(zip(self.labels, self.glyphs)):
            return False
        self.labels.append(int(digit))
        self.glyphs.append(encoded)
        self._features = None
        self._loo = None
        self._stencils = None
        return True

    def add_suffix(self, glyph: np.ndarray) -> bool:
        encoded = encode_png(glyph)
        if not encoded or encoded in self.suffix_glyphs:
            return False
        self.suffix_glyphs.append(encoded)
        self._suffix_features = None
        self._stencils = None
        return True

    def stencils(self) -> tuple[dict, Optional[np.ndarray]]:
        """숫자별 평균 글리프와 '초' 평균 글리프 (정규화 캔버스 기준).

        여러 프레임·여러 채널에서 잘라낸 같은 숫자를 평균하면 획 두께와
        안티에일리어싱이 자연히 섞여, 한 장에서 뜬 템플릿보다 안정적이다.
        """
        if self._stencils is not None:
            return self._stencils
        collected: dict[int, list] = {}
        for label, encoded in zip(self.labels, self.glyphs):
            glyph = decode_png(encoded)
            if glyph is None or glyph.shape[:2] != (GLYPH_SIZE[1], GLYPH_SIZE[0]):
                continue
            collected.setdefault(int(label), []).append(glyph.astype(np.float32))
        digits = {digit: np.mean(frames, axis=0)
                  for digit, frames in collected.items() if frames}
        suffix_frames = []
        for encoded in self.suffix_glyphs:
            glyph = decode_png(encoded)
            if glyph is not None and glyph.shape[:2] == (GLYPH_SIZE[1], GLYPH_SIZE[0]):
                suffix_frames.append(glyph.astype(np.float32))
        suffix = np.mean(suffix_frames, axis=0) if suffix_frames else None
        self._stencils = (digits, suffix)
        return self._stencils

    def add_patch(self, digit: Optional[int], patch: np.ndarray,
                  mode: str = "warm") -> bool:
        """Store an appearance template cut straight out of a score image.

        ``digit`` is ``None`` for the ``초`` suffix.  These are what the
        correlation reader matches with: a glyph rebuilt from the normalized
        12x16 canvas has the wrong stroke shape, and the resulting ``초``
        template only correlated at 0.60, which put the suffix in the wrong
        place and turned ``14초`` into ``1초``.

        Patches are kept per colour channel: a stroke cut out of a luminance
        top-hat is thicker than the same stroke cut out of the warm channel, and
        averaging the two together blurs both.
        """
        if patch is None or patch.size == 0:
            return False
        encoded = encode_png(patch)
        if not encoded:
            return False
        label = -1 if digit is None else int(digit)
        if (label, str(mode), encoded) in set(zip(self.patch_labels, self.patch_modes,
                                                 self.patches)):
            return False
        self.patch_labels.append(label)
        self.patch_modes.append(str(mode))
        self.patches.append(encoded)
        self._patch_stencils = None
        return True

    @staticmethod
    def _average(frames: list) -> Optional[np.ndarray]:
        frames = [f for f in frames if f is not None and f.shape[0] > 4]
        if not frames:
            return None
        width = max(3, int(np.median([f.shape[1] for f in frames])))
        height = int(np.median([f.shape[0] for f in frames]))
        resized = [cv2.resize(f.astype(np.float32), (width, height),
                              interpolation=cv2.INTER_AREA) for f in frames]
        return np.mean(resized, axis=0).astype(np.float32)

    def compact_patches(self) -> int:
        """Collapse the collected patches into one mean per (glyph, channel).

        Only the mean is ever matched against, so keeping every crop would make
        the profile grow without bound (502 digit crops from 57 frames was
        already 1.2MB).
        """
        grouped: dict[tuple, list] = {}
        for label, mode, encoded in zip(self.patch_labels, self.patch_modes, self.patches):
            decoded = decode_png(encoded)
            if decoded is not None:
                grouped.setdefault((int(label), str(mode)), []).append(decoded)
        self.patch_labels, self.patch_modes, self.patches = [], [], []
        self._patch_stencils = None
        for (label, mode), frames in sorted(grouped.items()):
            mean = self._average(frames)
            if mean is None:
                continue
            encoded = encode_png(np.clip(mean, 0, 255).astype(np.uint8))
            if not encoded:
                continue
            self.patch_labels.append(int(label))
            self.patch_modes.append(str(mode))
            self.patches.append(encoded)
        return len(self.patches)

    def patch_stencils(self, mode: str = "warm") -> tuple[dict, Optional[np.ndarray]]:
        """숫자별/접미사 평균 외형 템플릿. 잉크 높이는 :data:`PATCH_HEIGHT`.

        요청한 채널의 템플릿이 없으면 가지고 있는 채널을 모두 평균해서 쓴다.
        """
        if self._patch_stencils is None:
            self._patch_stencils = {}
        cached = self._patch_stencils.get(mode)
        if cached is not None:
            return cached

        collected: dict[int, list] = {}
        for label, patch_mode, encoded in zip(self.patch_labels, self.patch_modes,
                                              self.patches):
            if mode and patch_mode != mode:
                continue
            decoded = decode_png(encoded)
            if decoded is not None:
                collected.setdefault(int(label), []).append(decoded.astype(np.float32))
        if not collected and mode:
            return self.patch_stencils("")      # 채널 구분 없이 다시 시도
        digits = {}
        for label, frames in collected.items():
            mean = self._average(frames)
            if mean is None:
                continue
            if label < 0:
                continue
            digits[label] = mean
        suffix = self._average(collected.get(-1, []))
        result = (digits, suffix)
        self._patch_stencils[mode] = result
        return result

    # -- inference ----------------------------------------------------------
    @property
    def digit_coverage(self) -> list[int]:
        return sorted(set(self.labels))

    @property
    def trusted(self) -> bool:
        """OCR is only used once the glyph set is both complete and verified.

        A profile trained from mislabelled samples covers every digit yet cannot
        tell them apart, and used to be trusted on coverage alone.  The stored
        (or lazily measured) leave-one-out score now has to agree.
        """
        if len(self.digit_coverage) < MIN_TRAINED_DIGITS:
            return False
        score = float(self.accuracy or 0.0)
        if score <= 0.0:
            if self._loo is None:
                self._loo = self.self_accuracy()
            score = self._loo
        return score >= MIN_TRAINED_ACCURACY

    def self_accuracy(self) -> float:
        """Leave-one-out accuracy over the stored glyphs.

        Only glyphs whose digit has at least one sibling can be scored: with a
        single sample per class the nearest *other* glyph is always a different
        digit, which would report 0% for a perfectly usable seed profile.
        """
        if not self._ensure_features():
            return 1.0
        features, labels = self._features, self._labels_np
        counts = {int(v): int((labels == v).sum()) for v in np.unique(labels)}
        scorable = [i for i in range(features.shape[0]) if counts[int(labels[i])] >= 2]
        if len(scorable) < 4:
            return 1.0
        correct = 0
        for index in scorable:
            distances = np.linalg.norm(features - features[index], axis=1)
            distances[index] = np.inf
            correct += int(labels[int(np.argmin(distances))] == labels[index])
        return correct / float(len(scorable))

    def _ensure_features(self) -> bool:
        if self._features is not None:
            return self._features.size > 0
        features, labels = [], []
        for label, encoded in zip(self.labels, self.glyphs):
            glyph = decode_png(encoded)
            if glyph is not None and glyph.shape[:2] == (GLYPH_SIZE[1], GLYPH_SIZE[0]):
                features.append(glyph_features(glyph))
                labels.append(int(label))
        self._features = np.asarray(features, np.float32) if features else np.zeros((0, 1), np.float32)
        self._labels_np = np.asarray(labels, np.int32)
        return self._features.size > 0

    def classify(self, glyph: np.ndarray) -> tuple[Optional[int], float]:
        """Return (digit, confidence). Confidence is 0.0 when untrained."""
        if not self._ensure_features():
            return None, 0.0
        feature = glyph_features(glyph)
        distances = np.linalg.norm(self._features - feature, axis=1)
        per_class = {
            int(value): float(np.min(distances[self._labels_np == value]))
            for value in np.unique(self._labels_np)
        }
        ranked = sorted(per_class.items(), key=lambda item: item[1])
        digit, nearest = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else nearest + 1.0
        margin = max(0.0, (second - nearest) / max(second, 1e-6))
        distance_score = max(0.0, 1.0 - nearest / MAX_NEAREST_DISTANCE)
        confidence = 0.65 * distance_score + 0.35 * min(1.0, margin / MIN_MARGIN)
        if nearest > MAX_NEAREST_DISTANCE or margin < MIN_MARGIN:
            confidence *= 0.55
        return digit, float(min(1.0, confidence))

    def suffix_similarity(self, glyph: np.ndarray) -> float:
        """학습된 '초' 글리프와의 유사도(0~1).

        숫자 하나를 함께 삼킨 덩어리를 '초' 로 착각하면 '19초' 가 '1초' 로
        읽힌다. 접미사 모양 자체를 확인해 그 후보를 버린다.
        """
        if not self.suffix_glyphs:
            return 1.0
        if self._suffix_features is None:
            features = []
            for encoded in self.suffix_glyphs:
                decoded = decode_png(encoded)
                if decoded is not None and decoded.shape[:2] == (GLYPH_SIZE[1], GLYPH_SIZE[0]):
                    features.append(glyph_features(decoded))
            self._suffix_features = (np.asarray(features, np.float32) if features
                                     else np.zeros((0, 1), np.float32))
        if self._suffix_features.size == 0:
            return 1.0
        distances = np.linalg.norm(self._suffix_features - glyph_features(glyph), axis=1)
        nearest = float(np.min(distances))
        return max(0.0, 1.0 - nearest / MAX_NEAREST_DISTANCE)

    def read_seconds(self, binary: np.ndarray,
                     digit_boxes: list[tuple[int, int, int, int]]) -> tuple[Optional[int], float]:
        if not digit_boxes or not self.trusted:
            return None, 0.0
        values, confidences = [], []
        for box in digit_boxes:
            digit, confidence = self.classify(normalize_glyph(binary, box))
            if digit is None:
                return None, 0.0
            values.append(digit)
            confidences.append(confidence)
        confidence = float(min(confidences))
        if confidence < MIN_OCR_CONFIDENCE:
            return None, confidence
        return int("".join(str(v) for v in values)), confidence


# ---------------------------------------------------------------------------
# Multi-hypothesis reading
# ---------------------------------------------------------------------------

@dataclass
class TimerReading:
    """One frame's timer readout with everything the tracker needs."""
    value: Optional[int] = None
    confidence: float = 0.0
    glyph_count: int = 0
    signature: Optional[np.ndarray] = None
    sub_second: bool = False
    mode: str = ""
    threshold: int = 0
    binary: Optional[np.ndarray] = field(default=None, repr=False)
    digit_boxes: list = field(default_factory=list, repr=False)
    suffix_box: Optional[tuple] = None
    candidates: int = 0


def glyph_layout_ok(binary: np.ndarray, suffix_box, digit_boxes) -> bool:
    """Does this segmentation actually look like ``N초``?

    The glyph classifier always returns *some* nearest neighbour, so its
    confidence alone cannot tell a real digit from a lump of background.  These
    geometric rules can: the game renders the digits and the suffix on one
    baseline, at one size, with sparse strokes.
    """
    if suffix_box is None or not digit_boxes:
        return False
    height, width = binary.shape[:2]
    ink = float(np.count_nonzero(binary)) / float(height * width)
    if ink > 0.32:                      # 배경이 덩어리째 켜진 후보
        return False
    sx, sy, sw, sh = suffix_box
    if sh <= 0 or sw <= 0:
        return False
    if sw > 1.35 * sh:
        # '초' 는 거의 정사각형이다. 이보다 넓으면 옆 숫자를 함께 삼킨 덩어리다.
        # 그 상태로 읽으면 '19초' 가 '1초' 로 읽힌다.
        return False
    widths = [b[2] for b in digit_boxes]
    if sw < 1.15 * float(np.median(widths)):
        return False                    # 초 글리프는 숫자보다 넓다
    suffix_baseline = sy + sh
    for x, y, w, h in digit_boxes:
        if not (0.70 * sh <= h <= 1.30 * sh):
            return False                # 글자 높이가 한 줄로 맞지 않는다
        if abs((y + h) - suffix_baseline) > 0.28 * sh:
            return False                # 베이스라인이 어긋난다
        crop = binary[max(0, y):y + h, max(0, x):x + w]
        if crop.size == 0:
            return False
        fill = float(np.count_nonzero(crop)) / float(crop.size)
        if not (0.18 <= fill <= 0.90):
            return False                # 획 밀도가 숫자답지 않다

    # 잘려나간 자리 검사. '18초' 에서 8을 놓치면 마지막 숫자와 초 사이가
    # 한 글자만큼 벌어지고, 1을 놓치면 첫 숫자 왼쪽에 글자 잉크가 남는다.
    # 이런 후보는 18을 1로 읽는 위험한 오독이 되므로 버린다.
    rightmost = max(b[0] + b[2] for b in digit_boxes)
    if sx - rightmost > 0.55 * sh:
        return False
    leftmost = min(b[0] for b in digit_boxes)
    band_left = max(0, int(leftmost - 0.9 * sh))
    if leftmost - band_left >= 4:
        band = binary[max(0, sy):suffix_baseline, band_left:leftmost]
        if band.size and float(np.count_nonzero(band)) / float(band.size) > 0.10:
            return False
    return True


def timer_hypotheses(roi_bgr: np.ndarray, chroma: tuple[float, float] = None,
                     upscale: int = TIMER_UPSCALE):
    """Yield every plausible ``(binary, suffix, digits, mode, threshold)``.

    A frame is separated once per colour channel and threshold; only the
    combinations that look like ``N초`` are handed back.
    """
    if roi_bgr is None or roi_bgr.size == 0:
        return
    big = upscale_roi(roi_bgr, upscale)
    for priority, mode in enumerate(TIMER_SCORE_MODES):
        score_image = timer_score(big, mode, chroma, upscale)
        peak = int(score_image.max()) if score_image.size else 0
        if peak < TIMER_MIN_PEAK:
            continue
        for fraction in TIMER_SCORE_FRACTIONS:
            threshold = max(10, int(round(peak * fraction)))
            binary = (score_image >= threshold).astype(np.uint8) * 255
            if upscale > 1:
                binary = cv2.morphologyEx(
                    binary, cv2.MORPH_CLOSE,
                    cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
            suffix_box, digit_boxes = segment_timer_glyphs(binary)
            if not glyph_layout_ok(binary, suffix_box, digit_boxes):
                continue
            yield binary, suffix_box, digit_boxes, mode, threshold, priority


def read_timer_value(roi_bgr: np.ndarray, profile: "TimerGlyphProfile",
                     predicted: Optional[float] = None,
                     chroma: tuple[float, float] = None,
                     upscale: int = TIMER_UPSCALE) -> TimerReading:
    """Read ``N초`` from the timer ROI, trying several separations.

    No single colour channel survives every boss arena.  The warm (R-B) channel
    is unbeatable over the blue/grey arenas it was tuned on, but a *warm* arena
    (lava, sand, sunset) scores higher than the text itself and the readout dies
    - which is exactly the "works on this boss, not on that one" report.  The
    luminance top-hat still finds the glyphs there, because the game draws a dark
    outline around them, so the stroke stays a local maximum whatever colour the
    background is.

    Candidates are ranked, not taken first-come:

    1. agreement with where the countdown should already be (strongest signal),
    2. more digits wins - dropping the leading ``1`` of ``17초`` is the common
       failure, while inventing a digit is already blocked by the layout gate,
    3. classifier confidence, then the channel's own reliability order.
    """
    best = TimerReading()
    fallback: Optional[TimerReading] = None
    ranked: list[tuple[tuple, TimerReading]] = []

    for binary, suffix_box, digit_boxes, mode, threshold, priority in timer_hypotheses(
            roi_bgr, chroma, upscale):
        sub_second = has_decimal_point(binary, suffix_box, digit_boxes)
        reading = TimerReading(
            glyph_count=0 if sub_second else len(digit_boxes),
            sub_second=sub_second, mode=mode, threshold=threshold,
            binary=binary, digit_boxes=digit_boxes, suffix_box=suffix_box,
            signature=None if sub_second else digit_signature(binary, digit_boxes),
        )
        if sub_second:
            if fallback is None:
                fallback = reading
            continue
        if profile.suffix_similarity(normalize_glyph(binary, suffix_box)) < MIN_SUFFIX_SIMILARITY:
            continue                    # '초' 모양이 아니면 자리수부터 믿을 수 없다
        seconds, confidence = profile.read_seconds(binary, digit_boxes)
        reading.value = seconds
        reading.confidence = confidence
        if seconds is None or confidence < MIN_OCR_CONFIDENCE:
            if fallback is None or confidence > fallback.confidence:
                fallback = reading
            continue
        agrees = (predicted is not None
                  and abs(float(seconds) - float(predicted)) <= 2.5)
        ranked.append(((0 if agrees else 1, -len(digit_boxes),
                        -round(confidence, 3), priority), reading))
        if agrees and confidence >= 0.95:
            reading.candidates = len(ranked)
            return reading

    if ranked:
        ranked.sort(key=lambda item: item[0])
        winner = ranked[0][1]
        winner.candidates = len(ranked)
        return winner
    # 분리에 실패한 프레임은 상관 정합으로 한 번 더 본다. 배경이 글자와 같은
    # 계열로 물든 보스방에서는 이 경로만 살아남는다.
    correlated = read_timer_by_correlation(roi_bgr, profile, predicted, chroma, upscale)
    if correlated.value is not None and correlated.confidence >= MIN_OCR_CONFIDENCE:
        return correlated
    if fallback is not None:
        return fallback
    return correlated if correlated.suffix_box is not None else best


# ---------------------------------------------------------------------------
# Correlation reading (no segmentation)
# ---------------------------------------------------------------------------

def _crop_ink(canvas: np.ndarray, threshold: float = 40.0) -> Optional[np.ndarray]:
    """Trim the normalized canvas down to the glyph itself.

    ``normalize_glyph`` pads every glyph into the same 12x16 box, so a raw
    canvas template is far wider than a narrow digit.  Correlating with that
    padding made the tens digit fail the adjacency check (``19초`` read as
    ``9초``), because the template box overlapped its neighbour.
    """
    mask = canvas >= threshold
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    return canvas[int(ys.min()):int(ys.max()) + 1, int(xs.min()):int(xs.max()) + 1]


def appearance_patch(field: np.ndarray, box, height: int = PATCH_HEIGHT,
                     margin_ratio: float = PATCH_MARGIN) -> Optional[np.ndarray]:
    """Cut a glyph out of a score image, with its real surroundings.

    Normalized to a fixed ink height so templates from different resolutions
    stay comparable.  The margin is deliberately real background rather than
    zero padding: it is what lets correlation reject a ``1`` that sits on the
    left stroke of a ``4``.
    """
    if field is None or field.size == 0:
        return None
    x, y, w, h = (int(v) for v in box)
    if h < 4 or w < 2:
        return None
    pad = int(round(h * margin_ratio))
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(field.shape[1], x + w + pad), min(field.shape[0], y + h + pad)
    crop = field[y0:y1, x0:x1]
    if crop.shape[0] < 6 or crop.shape[1] < 4:
        return None
    # 잘린 여백만큼 되메워 항상 같은 비율로 맞춘다.
    top, bottom = pad - (y - y0), pad - (y1 - (y + h))
    left, right = pad - (x - x0), pad - (x1 - (x + w))
    if any(v > 0 for v in (top, bottom, left, right)):
        crop = cv2.copyMakeBorder(crop, max(0, top), max(0, bottom),
                                  max(0, left), max(0, right), cv2.BORDER_REPLICATE)
    scale = float(height) / float(h)
    out_h = max(6, int(round(crop.shape[0] * scale)))
    out_w = max(4, int(round(crop.shape[1] * scale)))
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(crop.astype(np.float32), (out_w, out_h),
                         interpolation=interpolation)
    return np.clip(resized, 0, 255).astype(np.uint8)


def _stencil_at(canvas: np.ndarray, scale: float,
                margin: int = 0) -> Optional[np.ndarray]:
    """Scale a cropped stencil, soften it, and surround it with background.

    The in-game text is 8px and heavily anti-aliased; a hard-edged template
    correlates poorly with it.  The empty margin matters just as much: a bare
    ``1`` is a vertical bar that correlates strongly with part of a ``4`` or
    with the left stroke of ``초``, and every misread in the first correlation
    build was exactly that (``14초`` read as ``1초``).  Requiring the
    surrounding pixels to be background removes those matches.
    """
    width = int(round(canvas.shape[1] * scale))
    height = int(round(canvas.shape[0] * scale))
    if width < 3 or height < 5:
        return None
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(canvas, (width, height), interpolation=interpolation)
    softened = cv2.GaussianBlur(resized, (0, 0), max(0.6, scale * 0.4))
    if margin > 0:
        softened = cv2.copyMakeBorder(softened, margin, margin, margin, margin,
                                      cv2.BORDER_CONSTANT, value=0.0)
    return softened


def _correlate_timer(field: np.ndarray, digit_stencils: dict,
                     suffix_stencil: np.ndarray, glyph_height: float,
                     mode: str) -> Optional[TimerReading]:
    """Find ``N초`` in one score image by template correlation.

    The suffix is located first: it is the widest, most distinctive shape in the
    strip, and it fixes both the baseline and the scale.  Digits are then taken
    from the band left of it, right to left, and each one has to sit on that
    baseline and touch the previous glyph.  Nothing is binarized, so a warm
    background cannot merge into a glyph or cut one in half.

    Templates are appearance patches (:func:`appearance_patch`) whose ink height
    is :data:`PATCH_HEIGHT` and which carry a :data:`PATCH_MARGIN` band of real
    background around the glyph.
    """
    scale = float(glyph_height) / float(PATCH_HEIGHT)
    margin = int(round(PATCH_MARGIN * glyph_height))
    suffix_template = _stencil_at(suffix_stencil, scale)
    if suffix_template is None:
        return None
    sh = suffix_template.shape[0] - 2 * margin
    sw = suffix_template.shape[1] - 2 * margin
    if sh < 5 or sw < 5 or field.shape[0] <= suffix_template.shape[0] \
            or field.shape[1] <= suffix_template.shape[1]:
        return None
    response = cv2.matchTemplate(field, suffix_template, cv2.TM_CCOEFF_NORMED)
    _lo, suffix_score, _lo_at, suffix_at = cv2.minMaxLoc(response)
    if suffix_score < NCC_MIN_SUFFIX:
        return None
    sx, sy = int(suffix_at[0]) + margin, int(suffix_at[1]) + margin
    baseline = sy + sh

    templates = {}
    for digit, canvas in digit_stencils.items():
        template = _stencil_at(canvas, scale)
        if template is not None and template.shape[0] > 2 * margin + 3:
            templates[int(digit)] = template
    if len(templates) < MIN_TRAINED_DIGITS:
        return None

    pad = int(round(0.30 * sh))
    y0, y1 = max(0, sy - pad - margin), min(field.shape[0], baseline + pad + margin)
    x0 = max(0, sx - int(round(2.8 * sh)) - margin)
    x1 = min(field.shape[1], sx + int(round(0.20 * sh)))
    band = field[y0:y1, x0:x1]

    # 자리마다 폭이 다르므로(1 은 좁다) 숫자별로 따로 정합한 뒤 모아서 겨룬다.
    found = []
    for digit, template in templates.items():
        if band.shape[0] <= template.shape[0] or band.shape[1] <= template.shape[1]:
            continue
        ink_h = template.shape[0] - 2 * margin
        ink_w = template.shape[1] - 2 * margin
        digit_response = cv2.matchTemplate(band, template, cv2.TM_CCOEFF_NORMED)
        work = digit_response.copy()
        for _ in range(NCC_MAX_DIGITS):
            flat = int(np.argmax(work))
            y, x = np.unravel_index(flat, work.shape)
            value = float(work[y, x])
            if value < NCC_MIN_DIGIT:
                break
            ax = x0 + int(x) + margin
            ay = y0 + int(y) + margin
            if abs((ay + ink_h) - baseline) <= 0.28 * sh:
                found.append((ax, ay, ink_w, ink_h, value, digit))
            span = max(2, int(round(0.35 * sh)))
            work[:, max(0, int(x) - span):int(x) + span + 1] = -2.0
    if not found:
        return None

    # 같은 자리를 여러 숫자가 주장하면 가장 잘 맞는 하나만 남긴다.
    found.sort(key=lambda item: -item[4])
    kept: list[tuple] = []
    for candidate in found:
        centre = candidate[0] + candidate[2] * 0.5
        if any(abs(centre - (k[0] + k[2] * 0.5)) < 0.35 * sh for k in kept):
            continue
        kept.append(candidate)

    # 오른쪽(1의 자리)부터, 서로 붙어 있는 숫자만 받아들인다. 떨어져 있는 피크는
    # 옆 칸 글자나 배경 무늬다.
    kept.sort(key=lambda item: -item[0])
    accepted: list[tuple] = []
    for candidate in kept:
        ax, _ay, tw, _th, _value, _digit = candidate
        right = ax + tw
        if not accepted:
            if not (-0.10 * sh <= sx - right <= 0.55 * sh):
                continue
        else:
            gap = accepted[-1][0] - right
            if not (-0.10 * sh <= gap <= 0.40 * sh):
                continue
        accepted.append(candidate)
        if len(accepted) >= NCC_MAX_DIGITS:
            break
    if not accepted:
        return None
    accepted.reverse()

    digit_boxes = [(ax, ay, tw, th) for ax, ay, tw, th, _value, _digit in accepted]
    suffix_box = (sx, sy, sw, sh)
    peak = float(field.max())
    binary = (field >= max(10.0, peak * TIMER_SCORE_FRACTION)).astype(np.uint8) * 255

    # 앞자리를 놓친 후보는 버린다. '15초' 에서 1 을 못 찾으면 5초로 읽히는데,
    # 그것이 상관 경로에 남아 있던 오독 전부였다. 맨 왼쪽 숫자의 왼쪽에 글자
    # 두께의 잉크가 남아 있으면 아직 숫자가 하나 더 있다는 뜻이다.
    if len(accepted) < NCC_MAX_DIGITS:
        leftmost = min(box[0] for box in digit_boxes)
        left_from = max(0, int(leftmost - round(0.95 * sh)))
        if leftmost - left_from >= 4:
            band_left = binary[max(0, sy):baseline, left_from:leftmost]
            if band_left.size and float(np.count_nonzero(band_left)) / band_left.size > 0.05:
                return None

    sub_second = has_decimal_point(binary, suffix_box, digit_boxes)
    weakest = min(item[4] for item in accepted)
    # 신뢰도는 숫자 정합만으로 낸다. '초' 템플릿은 정규화 캔버스에서 복원한
    # 것이라 실측 정합이 0.60 근처에 머무는데(숫자는 0.93), 그 값을 신뢰도에
    # 섞으면 제대로 읽은 프레임까지 임계 아래로 끌려 내려간다. 접미사는 위치와
    # 배율을 잡는 역할만 하고, 통과 여부는 NCC_MIN_SUFFIX 가 판단한다.
    confidence = float(min(1.0, max(0.0, (weakest - 0.60) / 0.37)))
    seconds = None if sub_second else int("".join(str(item[5]) for item in accepted))
    return TimerReading(
        value=seconds, confidence=0.0 if sub_second else confidence,
        glyph_count=0 if sub_second else len(digit_boxes), sub_second=sub_second,
        mode=f"ncc-{mode}", threshold=int(round(weakest * 100)),
        binary=binary, digit_boxes=digit_boxes, suffix_box=suffix_box,
        signature=None if sub_second else digit_signature(binary, digit_boxes),
    )


def read_timer_by_correlation(roi_bgr: np.ndarray, profile: "TimerGlyphProfile",
                              predicted: Optional[float] = None,
                              chroma: tuple[float, float] = None,
                              upscale: int = TIMER_UPSCALE) -> TimerReading:
    """Read the timer without segmenting anything.

    Used when the segmentation path found no usable candidate at all, which is
    what happens over a boss arena whose background is as warm as the text.
    Ranking follows the same rules as :func:`read_timer_value`.
    """
    best = TimerReading()
    if roi_bgr is None or roi_bgr.size == 0 or not profile.trusted:
        return best
    if not getattr(profile, "patches", None):
        return best

    big = upscale_roi(roi_bgr, upscale)
    ranked: list[tuple[tuple, TimerReading]] = []
    fallback: Optional[TimerReading] = None
    for priority, mode in enumerate(TIMER_SCORE_MODES):
        digit_stencils, suffix_stencil = profile.patch_stencils(mode)
        if len(digit_stencils) < MIN_TRAINED_DIGITS or suffix_stencil is None:
            continue
        score_image = timer_score(big, mode, chroma, upscale)
        if score_image.size == 0 or int(score_image.max()) < TIMER_MIN_PEAK:
            continue
        field = score_image.astype(np.float32)
        for ratio in NCC_HEIGHT_RATIOS:
            reading = _correlate_timer(field, digit_stencils, suffix_stencil,
                                       big.shape[0] * ratio, mode)
            if reading is None:
                continue
            if reading.value is None or reading.confidence < MIN_OCR_CONFIDENCE:
                if fallback is None or reading.confidence > fallback.confidence:
                    fallback = reading
                continue
            agrees = (predicted is not None
                      and abs(float(reading.value) - float(predicted)) <= 2.5)
            ranked.append(((0 if agrees else 1, -reading.glyph_count,
                            -round(reading.confidence, 3), priority), reading))
    if ranked:
        ranked.sort(key=lambda item: item[0])
        winner = ranked[0][1]
        winner.candidates = len(ranked)
        return winner
    return fallback if fallback is not None else best


def sample_text_color(roi_bgr: np.ndarray, binary: np.ndarray,
                      digit_boxes, upscale: int = TIMER_UPSCALE) -> Optional[tuple[float, float]]:
    """Chroma of the pixels that were actually classified as digits.

    Lets the detector re-calibrate the target colour per raid: UI filters, HDR
    and arena lighting all shift the rendered salmon a little.
    """
    if binary is None or not digit_boxes or roi_bgr is None:
        return None
    big = upscale_roi(roi_bgr, upscale)
    if big.ndim != 3 or big.shape[:2] != binary.shape[:2]:
        return None
    mask = np.zeros(binary.shape, np.uint8)
    for x, y, w, h in digit_boxes:
        mask[max(0, y):y + h, max(0, x):x + w] = binary[max(0, y):y + h, max(0, x):x + w]
    # 획 가장자리(안티에일리어싱)를 빼고 안쪽만 본다.
    mask = cv2.erode(mask, np.ones((2, 2), np.uint8))
    pixels = big[mask > 0]
    if pixels.shape[0] < 12:
        return None
    median = np.median(pixels.reshape(-1, 3), axis=0)
    return text_chroma(median)


# ---------------------------------------------------------------------------
# Icon templates
# ---------------------------------------------------------------------------

@dataclass
class IconTemplate:
    name: str
    gray: np.ndarray
    color: Optional[np.ndarray] = None

    @property
    def size(self) -> int:
        return int(self.gray.shape[0])


def load_icon_templates(debuff_id: str = DEFAULT_DEBUFF_ID) -> list[IconTemplate]:
    """Bundled cell crops first, then any user-provided crops."""
    templates: list[IconTemplate] = []
    seen: set[bytes] = set()
    for root in (assets_root() / "icons" / debuff_id, user_data_root() / "icons" / debuff_id):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.png")):
            image = read_image(path)
            if image is None or image.shape[0] < 8 or image.shape[1] < 8:
                continue
            # Square the crop so a single scale parameter describes the match.
            side = min(image.shape[0], image.shape[1])
            image = image[:side, :side]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            digest = gray.tobytes()[:512]
            if digest in seen:
                continue
            seen.add(digest)
            templates.append(IconTemplate(path.stem, gray, cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
    return templates


@dataclass
class IconMatch:
    score: float
    x: int
    y: int
    size: int
    template: str = ""


def match_icon(band_gray: np.ndarray, templates: list[IconTemplate],
               min_px: int = DEFAULT_MIN_ICON_PX, max_px: int = DEFAULT_MAX_ICON_PX,
               locked_size: Optional[int] = None) -> Optional[IconMatch]:
    """Multi-scale search for the debuff cell inside the strip band."""
    if band_gray is None or band_gray.size == 0 or not templates:
        return None
    if locked_size:
        sizes = [s for s in range(locked_size - 2, locked_size + 3) if min_px <= s <= max_px]
    else:
        sizes = list(range(int(min_px), int(max_px) + 1))
    best: Optional[IconMatch] = None
    bh, bw = band_gray.shape[:2]
    for template in templates:
        for size in sizes:
            if size > bh or size > bw:
                continue
            resized = cv2.resize(template.gray, (size, size), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(band_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if best is None or max_val > best.score:
                best = IconMatch(float(max_val), int(max_loc[0]), int(max_loc[1]), int(size), template.name)
    return best


# ---------------------------------------------------------------------------
# Tracking state machine (pure logic, unit testable without Qt)
# ---------------------------------------------------------------------------

@dataclass
class DebuffFrame:
    """One scan result handed to the tracker."""
    matched: bool
    score: float = 0.0
    cell: Optional[tuple[int, int, int, int]] = None
    glyph_count: int = 0
    ocr_seconds: Optional[int] = None
    ocr_confidence: float = 0.0
    digit_signature: Optional[np.ndarray] = None


class BossDebuffTracker:
    """Turns per-frame observations into a stable remaining-seconds readout.

    Priority of the seconds source:
        ``ocr``      trained glyph profile read this second
        ``anchor``   the 2-digit -> 1-digit transition means exactly 9s left
        ``duration`` configured or previously learned total minus elapsed
        ``unknown``  active, but never guess a number
    """

    def __init__(self, debuff_id: str = DEFAULT_DEBUFF_ID, configured_duration: float = 0.0):
        self.debuff_id = debuff_id
        self.configured_duration = float(configured_duration or 0.0)
        self.learned_duration = 0.0
        self.observed_max = 0.0     # 지금까지 OCR 로 확실히 읽은 가장 큰 숫자
        self.expect_ocr = False     # 신뢰할 수 있는 글리프 세트가 있는가
        self.reset()

    def reset(self) -> None:
        self.active = False
        self._hit_streak = 0
        self._miss_streak = 0
        self.appeared_at = 0.0
        self.last_seen_at = 0.0
        self.score = 0.0
        self.cell = None
        self.glyph_count = 0
        self._glyph_count_streak = 0
        self._pending_glyph_count = 0
        self._glyph_count_since = 0.0
        self._anchor_fired = False
        self._anchor_value = None
        self._anchor_at = 0.0
        self._anchor_source = ""
        self._last_signature = None
        self._ocr_pending = None
        self._refresh_pending = None
        self.tick_count = 0
        self.last_tick_at = 0.0
        self.last_ocr_seconds = None
        self.last_ocr_confidence = 0.0

    # -- helpers ------------------------------------------------------------
    @property
    def total_duration(self) -> float:
        return self.configured_duration or self.learned_duration

    def reset_learned_duration(self) -> None:
        """Forget the auto-learned total.

        A value learned by an older build could be inflated (a mid-cast refresh
        used to add the elapsed time on top of the reading, so a 20s debuff was
        stored as 28.8s) and there was no way back: the value only ever grew and
        was written to the config file.  Clearing ``observed_max`` too means the
        next confirmed reading re-learns it from scratch.
        """
        self.observed_max = 0.0
        self.learned_duration = 0.0

    def set_anchor(self, value: float, now: float, source: str = "manual") -> None:
        """Pin the countdown to an exactly known remaining value."""
        self._anchor_value = float(value)
        self._anchor_at = now
        self._anchor_source = source
        if source == "ocr":
            # 총 지속시간은 '여태 본 가장 큰 숫자'로 배운다.  예전에는
            # 읽은 값 + 감지 시작 이후 경과 로 계산했는데, 디버프가 만료 전에
            # 다시 걸리면(리프레시) 경과가 그대로 누적되어 20초 디버프가 28.8초로
            # 굳었고, 매번 28초부터 세는 것처럼 보였다.
            if float(value) > self.observed_max:
                self.observed_max = float(value)
            self.learned_duration = round(self.observed_max, 1)
            return
        if self.appeared_at > 0.0:
            candidate = float(value) + max(0.0, now - self.appeared_at)
            if self.observed_max > 0.0:
                # OCR 로 본 최대값이 있으면 그 이상으로는 늘리지 않는다.
                candidate = min(candidate, self.observed_max)
            if candidate > self.learned_duration:
                self.learned_duration = round(candidate, 1)

    def _accepts_anchor(self, value: float, now: float) -> bool:
        """A measured countdown may never jump back up.

        ``duration`` is only an estimate, so a real measurement is allowed to
        correct it in either direction.  Once the value came from OCR or the
        digit-count anchor, though, a higher number means a misread.
        """
        current, source = self._remaining(now)
        if current is None or source == "duration":
            return True
        return value <= math.ceil(current) + 1

    def _remaining(self, now: float) -> tuple[Optional[float], str]:
        # 경과 시간은 음수가 될 수 없다. 시계가 뒤로 간 것처럼 보이는 상태
        # (스레드 재시작, 서로 다른 시간축 혼입)에서 음수 경과를 그대로 빼면
        # 남은 시간이 총 지속시간보다 커지는 엉뚱한 값이 나온다.
        if self._anchor_value is not None:
            remaining = self._anchor_value - max(0.0, now - self._anchor_at)
            return max(0.0, remaining), self._anchor_source
        total = self.total_duration
        if total > 0.0 and self.appeared_at > 0.0:
            elapsed = max(0.0, now - self.appeared_at)
            if self.expect_ocr and elapsed < OCR_GRACE_SEC:
                # 숫자를 읽을 수 있는 상태라면, 첫 몇 프레임은 추정값을 내보내지
                # 않는다. 학습된 총 지속시간이 조금이라도 어긋나 있으면 캐스트
                # 시작마다 틀린 숫자가 한 번 스쳐 지나간다.
                return None, "unknown"
            return max(0.0, total - elapsed), "duration"
        return None, "unknown"

    # -- main entry ---------------------------------------------------------
    def update(self, frame: DebuffFrame, now: Optional[float] = None) -> dict:
        now = time.monotonic() if now is None else float(now)

        if frame.matched:
            self._hit_streak += 1
            self._miss_streak = 0
        else:
            self._miss_streak += 1
            self._hit_streak = 0

        if not self.active and self._hit_streak >= ACTIVATE_FRAMES:
            self.active = True
            self.appeared_at = now
            self.tick_count = 0
            self._anchor_value = None
            self._anchor_at = 0.0
            self._anchor_source = ""
            self._anchor_fired = False
            self._last_signature = None
            self._pending_glyph_count = 0
            self._glyph_count_streak = 0
            self._glyph_count_since = 0.0
            self._ocr_pending = None
            self._refresh_pending = None
            self.glyph_count = 0
        elif self.active and self._miss_streak >= DEACTIVATE_FRAMES:
            self.active = False
            self.cell = None
            self.score = frame.score
            self._anchor_value = None
            self._anchor_source = ""
            self._ocr_pending = None
            self._refresh_pending = None
            self.glyph_count = 0
            return self.snapshot(now)

        if frame.matched:
            self.score = frame.score
            self.cell = frame.cell
            self.last_seen_at = now

        if not self.active:
            self.score = frame.score
            return self.snapshot(now)

        # Digit-count anchor: the strip switches from two glyphs to one exactly
        # when the remaining time goes 10s -> 9s.  It fires at most once per
        # cast and only after the two-digit state was actually held, because a
        # single dropped digit used to re-pin the countdown to 9s forever.
        if frame.glyph_count > 0:
            if frame.glyph_count == self._pending_glyph_count:
                self._glyph_count_streak += 1
            else:
                self._pending_glyph_count = frame.glyph_count
                self._glyph_count_streak = 1
            if self._glyph_count_streak >= GLYPH_COUNT_FRAMES:
                previous = self.glyph_count
                if frame.glyph_count != previous:
                    self.glyph_count = frame.glyph_count
                    held = now - self._glyph_count_since if self._glyph_count_since else 0.0
                    self._glyph_count_since = now
                    if (previous == 2 and frame.glyph_count == 1
                            and not self._anchor_fired
                            and self._anchor_source != "ocr"
                            and held >= ANCHOR_MIN_TWO_DIGIT_SEC
                            and self._accepts_anchor(9.0, now)):
                        self._anchor_fired = True
                        self.set_anchor(9.0, now, "anchor")

        # 1s tick detection keeps the displayed integer in step with the game.
        if frame.digit_signature is not None:
            if self._last_signature is not None and self._last_signature.shape == frame.digit_signature.shape:
                diff = float(np.mean(self._last_signature != frame.digit_signature))
                if diff >= TICK_DIFF_RATIO:
                    self.tick_count += 1
                    self.last_tick_at = now
                    if self._anchor_value is not None and self._anchor_source == "anchor":
                        # Re-align the fractional part to the observed tick.
                        remaining = self._anchor_value - (now - self._anchor_at)
                        snapped = float(max(0, math.floor(remaining + 0.5)))
                        if abs(snapped - remaining) <= 0.5:
                            self._anchor_value = snapped
                            self._anchor_at = now
            self._last_signature = frame.digit_signature

        if frame.ocr_seconds is not None and frame.ocr_confidence >= MIN_OCR_CONFIDENCE:
            self.last_ocr_seconds = int(frame.ocr_seconds)
            self.last_ocr_confidence = float(frame.ocr_confidence)
            self._ingest_ocr(float(frame.ocr_seconds), now)

        return self.snapshot(now)

    def _ingest_ocr(self, value: float, now: float) -> None:
        """Anchor on OCR, but only after two mutually consistent reads.

        A single frame can be misread (background junk merging into a glyph).
        Two reads that agree once the elapsed time is taken into account cannot
        both be wrong in the same direction, so that pair is what pins the
        countdown.  Afterwards each further read has to stay consistent.
        """
        if self._anchor_source == "ocr" and self._anchor_value is not None:
            predicted = self._anchor_value - max(0.0, now - self._anchor_at)
            if abs(value - predicted) <= OCR_AGREE_TOLERANCE:
                self.set_anchor(value, now, "ocr")
                return
            if value > predicted + REFRESH_JUMP_SEC:
                # 값이 크게 올라갔다 = 만료 전에 다시 걸렸다(리프레시).
                # 확인용으로 한 프레임 더 본 뒤 새 캐스트로 처리한다.
                pending = self._refresh_pending
                self._refresh_pending = (value, now)
                if pending is not None and now - pending[1] <= OCR_CONFIRM_WINDOW \
                        and abs(value - (pending[0] - (now - pending[1]))) <= OCR_AGREE_TOLERANCE:
                    self._refresh_pending = None
                    self.appeared_at = now
                    self._anchor_fired = False
                    self.set_anchor(value, now, "ocr")
            return

        pending = self._ocr_pending
        self._ocr_pending = (value, now)
        if pending is None:
            return
        previous_value, previous_at = pending
        if now - previous_at > OCR_CONFIRM_WINDOW:
            return
        predicted = previous_value - (now - previous_at)
        if abs(value - predicted) > OCR_AGREE_TOLERANCE:
            return
        if not self._accepts_anchor(value, now):
            return
        self.set_anchor(value, now, "ocr")

    def snapshot(self, now: Optional[float] = None) -> dict:
        now = time.monotonic() if now is None else float(now)
        remaining, source = self._remaining(now) if self.active else (None, "")
        return {
            "debuff_id": self.debuff_id,
            "name": DEBUFF_DISPLAY_NAMES.get(self.debuff_id, self.debuff_id),
            "active": bool(self.active),
            "remaining": None if remaining is None else round(float(remaining), 2),
            "source": source if self.active else "",
            "score": round(float(self.score), 4),
            "cell": list(self.cell) if self.cell else None,
            "glyph_count": int(self.glyph_count),
            "tick_count": int(self.tick_count),
            "total_duration": round(float(self.total_duration), 1),
            "learned_duration": round(float(self.learned_duration), 1),
            "ocr_seconds": self.last_ocr_seconds,
            "ocr_confidence": round(float(self.last_ocr_confidence), 3),
            "updated_at": now,
        }


def digit_signature(binary: np.ndarray, digit_boxes: list[tuple[int, int, int, int]]) -> Optional[np.ndarray]:
    """Small canonical bitmap of the digits only, used for 1s tick detection."""
    if not digit_boxes:
        return None
    x0 = min(b[0] for b in digit_boxes)
    y0 = min(b[1] for b in digit_boxes)
    x1 = max(b[0] + b[2] for b in digit_boxes)
    y1 = max(b[1] + b[3] for b in digit_boxes)
    crop = binary[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return None
    return (cv2.resize(crop, (16, 12), interpolation=cv2.INTER_AREA) >= 110)


# ---------------------------------------------------------------------------
# Screen scanning thread
# ---------------------------------------------------------------------------

class BossDebuffDetector(QThread):
    """Scans the boss debuff strip band and reports 암흑 수류탄 state."""

    if _QT_AVAILABLE:
        debuff_updated = pyqtSignal(str, object)   # (debuff_id, state dict)
        sample_saved = pyqtSignal(str, object)     # (debuff_id, info dict)

    def __init__(self, parent=None, debuff_id: str = DEFAULT_DEBUFF_ID):
        super().__init__(parent)
        self.debuff_id = debuff_id
        self.enabled = False
        self.region = None                  # (x, y, w, h) in logical screen coords
        self.device_ratio = 1.0
        self.match_threshold = DEFAULT_MATCH_THRESHOLD
        self.min_icon_px = DEFAULT_MIN_ICON_PX
        self.max_icon_px = DEFAULT_MAX_ICON_PX
        self.scan_interval = DEFAULT_SCAN_INTERVAL
        self.collect_samples = False

        self.templates = load_icon_templates(debuff_id)
        self.profile = TimerGlyphProfile.load_for(debuff_id)
        self.tracker = BossDebuffTracker(debuff_id)
        self.tracker.expect_ocr = bool(self.profile.trusted)
        self.is_running = False
        self._locked_size = None
        self._last_emit = 0.0
        self._last_state = None
        self._last_sample_at = 0.0
        self._sample_buffer: list[tuple[float, np.ndarray]] = []
        self._sample_seq = 0
        self.sample_root = user_data_root() / "samples" / debuff_id
        self.text_chroma = DEFAULT_TEXT_CHROMA
        self.last_error = ""

    # -- configuration ------------------------------------------------------
    def configure(self, enabled=None, region=None, device_ratio=None, match_threshold=None,
                  duration=None, learned_duration=None, min_icon_px=None, max_icon_px=None,
                  collect_samples=None):
        if enabled is not None:
            self.enabled = bool(enabled)
        if region is not None:
            self.region = self._rect_values(region)
            self._locked_size = None
            self.tracker.reset()
        if device_ratio is not None:
            self.device_ratio = max(0.5, float(device_ratio))
        if match_threshold is not None:
            self.match_threshold = max(0.4, min(0.99, float(match_threshold)))
        if duration is not None:
            self.tracker.configured_duration = max(0.0, float(duration))
        if learned_duration is not None:
            # Restored from config so the very first cast after a restart can
            # already show a countdown instead of a bare "ON".  A stored value
            # from an older build could be inflated by a mid-cast refresh, so it
            # is capped: no debuff in the strip runs longer than this.
            restored = max(0.0, min(float(learned_duration), MAX_LEARNED_DURATION))
            if self.tracker.observed_max <= 0.0:
                # 이 세션에서 아직 숫자를 읽지 못했으면 설정값이 유일한 근거다.
                # 예전에는 max() 로 합쳐서 한 번 부풀려진 값이 영원히 남았다.
                self.tracker.learned_duration = restored
        if min_icon_px is not None:
            self.min_icon_px = max(8, int(min_icon_px))
        if max_icon_px is not None:
            self.max_icon_px = max(self.min_icon_px + 1, int(max_icon_px))
        if collect_samples is not None:
            self.collect_samples = bool(collect_samples)

    @staticmethod
    def _rect_values(rect):
        if rect is None:
            return None
        if QRect is not None and isinstance(rect, QRect):
            return [rect.x(), rect.y(), rect.width(), rect.height()]
        return [int(v) for v in rect]

    def reset_learned_duration(self) -> dict:
        """Drop the auto-learned total and report the fresh state."""
        self.tracker.reset_learned_duration()
        state = self.tracker.snapshot()
        self._last_state = state
        self._emit_state(state)
        return state

    def reload_assets(self):
        self.templates = load_icon_templates(self.debuff_id)
        self.profile = TimerGlyphProfile.load_for(self.debuff_id)
        self.tracker.expect_ocr = bool(self.profile.trusted)
        self._locked_size = None

    def auto_region_for_screen(self, screen_width: int, screen_height: int) -> list[int]:
        """Default strip band: centred under the boss HP bar near the top.

        Measured on the 1080p reference capture the cells sit at y 155..181 with
        the timer text down to y 193, horizontally centred around x 943.
        """
        width = int(screen_width * 0.42)
        height = int(screen_height * 0.075)
        x = int(screen_width / 2 - width / 2)
        y = int(screen_height * 0.128)
        return [x, y, width, height]

    def status(self) -> dict:
        state = dict(self._last_state or self.tracker.snapshot())
        state.update({
            "enabled": self.enabled,
            "region": list(self.region) if self.region else None,
            "templates": [t.name for t in self.templates],
            "template_sizes": [t.size for t in self.templates],
            "locked_size": self._locked_size,
            "threshold": self.match_threshold,
            "profile_digits": self.profile.digit_coverage,
            "profile_trusted": self.profile.trusted,
            "last_error": self.last_error,
        })
        return state

    # -- thread ------------------------------------------------------------
    def start_detection(self, interval_ms: Optional[int] = None):
        if interval_ms:
            self.scan_interval = max(0.02, interval_ms / 1000.0)
        if not self.isRunning():
            self.start()

    def stop_detection(self):
        self.is_running = False
        self.wait(2000)

    def run(self):  # pragma: no cover - needs a live screen
        self.is_running = True
        with mss.mss() as sct:
            while self.is_running:
                started = time.time()
                try:
                    self.scan_once(sct)
                except Exception as exc:
                    self.last_error = str(exc)
                elapsed = time.time() - started
                time.sleep(max(0.01, self.scan_interval - elapsed))

    def grab_band(self, sct) -> Optional[np.ndarray]:
        if not self.region:
            return None
        x, y, w, h = self.region
        ratio = self.device_ratio or 1.0
        monitor = {
            "left": int(x * ratio), "top": int(y * ratio),
            "width": max(1, int(w * ratio)), "height": max(1, int(h * ratio)),
        }
        raw = np.array(sct.grab(monitor))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def scan_once(self, sct) -> Optional[dict]:
        if not self.enabled or not self.region or not self.templates:
            return None
        band = self.grab_band(sct)
        if band is None:
            return None
        return self.analyze_band(band)

    def analyze_band(self, band_bgr: np.ndarray, now: Optional[float] = None) -> dict:
        """Locate the icon inside a captured band and update the tracker."""
        now = time.monotonic() if now is None else float(now)
        gray = cv2.cvtColor(band_bgr, cv2.COLOR_BGR2GRAY) if band_bgr.ndim == 3 else band_bgr
        match = match_icon(gray, self.templates, self.min_icon_px, self.max_icon_px, self._locked_size)
        frame = DebuffFrame(matched=False, score=match.score if match else 0.0)
        timer_roi = None

        if match is not None and match.score >= self.match_threshold:
            self._locked_size = match.size
            frame.matched = True
            frame.cell = (match.x, match.y, match.size, match.size)
            dx, dy, dw, dh = digit_roi_from_cell(*frame.cell)
            x0, y0 = max(0, dx), max(0, dy)
            x1 = min(band_bgr.shape[1], dx + dw)
            y1 = min(band_bgr.shape[0], dy + dh)
            if x1 - x0 >= 6 and y1 - y0 >= 5:
                timer_roi = band_bgr[y0:y1, x0:x1]
                predicted, _source = self.tracker._remaining(now) if self.tracker.active \
                    else (None, "")
                reading = read_timer_value(timer_roi, self.profile, predicted,
                                           self.text_chroma)
                if reading.suffix_box is None:
                    timer_roi = None
                else:
                    frame.glyph_count = reading.glyph_count
                    frame.digit_signature = reading.signature
                    frame.ocr_seconds = reading.value
                    frame.ocr_confidence = reading.confidence
                    if reading.value is not None and reading.confidence >= MIN_OCR_CONFIDENCE:
                        self._calibrate_text_chroma(timer_roi, reading)
        elif match is not None and match.score < self.match_threshold * 0.75:
            # A long miss streak means the strip moved or the boss changed;
            # unlock the scale so the next search covers the full range again.
            self._locked_size = None

        was_active = self.tracker.active
        state = self.tracker.update(frame, now)
        if self.collect_samples:
            if state.get("active") and timer_roi is not None:
                self._buffer_sample(timer_roi, now)
            elif was_active and not state.get("active"):
                self._flush_samples(now)
        elif self._sample_buffer:
            self._sample_buffer.clear()
        self._last_state = state
        self._emit_state(state)
        return state

    def _calibrate_text_chroma(self, timer_roi, reading: "TimerReading") -> None:
        """확정된 읽기에서 글자 색을 다시 배운다.

        보스방마다 조명·UI 필터·HDR 때문에 렌더된 살몬색이 조금씩 다르다. 확실히
        읽은 프레임에서 실제 글자 픽셀의 색조를 표본으로 삼아 목표색을 천천히
        따라가게 하면, 한 보스에서 학습해도 다른 보스방에서 색 기준이 맞는다.
        """
        sampled = sample_text_color(timer_roi, reading.binary, reading.digit_boxes)
        if sampled is None:
            return
        current = self.text_chroma or DEFAULT_TEXT_CHROMA
        # 급격히 흔들리지 않게 지수 이동 평균으로 섞는다.
        blend = 0.15
        self.text_chroma = (current[0] * (1 - blend) + sampled[0] * blend,
                            current[1] * (1 - blend) + sampled[1] * blend)

    def _emit_state(self, state: dict) -> None:
        if not _QT_AVAILABLE:
            return
        now = time.monotonic()
        previous = getattr(self, "_emitted", None)
        changed = (
            previous is None
            or previous.get("active") != state.get("active")
            or previous.get("source") != state.get("source")
            or (state.get("remaining") is None) != (previous.get("remaining") is None)
            or (state.get("remaining") is not None
                and abs(float(state["remaining"]) - float(previous.get("remaining") or 0.0)) >= 0.5)
        )
        if changed or now - self._last_emit >= 1.0:
            self._last_emit = now
            self._emitted = dict(state)
            try:
                self.debuff_updated.emit(self.debuff_id, state)
            except Exception:
                pass

    # -- sample collection --------------------------------------------------
    def _buffer_sample(self, roi_bgr, now: float) -> None:
        """Keep timer-ROI crops of the running cast in memory.

        Nothing is written while the debuff is up: the only label source that
        cannot be wrong is the moment the debuff *disappears*.  Labelling from
        the live estimate is what produced the mislabelled sample set (a real
        ``17초`` frame stored as ``09s``) and, once trained on, locked the
        readout onto a single wrong number.
        """
        if now - self._last_sample_at < SAMPLE_MIN_INTERVAL:
            return
        self._last_sample_at = now
        self._sample_buffer.append((now, roi_bgr.copy()))
        del self._sample_buffer[:-SAMPLE_BUFFER_FRAMES]

    def _flush_samples(self, now: float) -> dict:
        """Label the buffered cast backwards from its expiry and write it out.

        The game prints ``ceil(remaining)``, so with an expiry time ``T`` every
        buffered frame has an exact label ``ceil(T - t)``.  ``T`` itself is only
        known to within one scan, so it is fitted: the digit count of each frame
        must match the number of digits of its label, and the 2 -> 1 digit switch
        happens exactly at 9s.  That single degree of freedom is pinned by the
        observed switch, and the fit score doubles as a validity check for casts
        that were lost instead of expiring (boss died, region scrolled away).
        """
        pending, self._sample_buffer = self._sample_buffer, []
        result = {"written": 0, "skipped": len(pending), "reason": "", "fit": 0.0}
        if len(pending) < 4:
            result["reason"] = "관측 프레임이 너무 적습니다 (최소 4프레임)"
            return result

        observations = []
        for stamp, crop in pending:
            binary, _ = binarize_timer_text(crop)
            suffix_box, digit_boxes = segment_timer_glyphs(binary)
            if suffix_box is None or not digit_boxes:
                observations.append((stamp, crop, 0, False))
                continue
            decimal = has_decimal_point(binary, suffix_box, digit_boxes)
            observations.append((stamp, crop, 0 if decimal else len(digit_boxes), decimal))

        scorable = [o for o in observations if o[2] > 0]
        if len(scorable) < 4:
            result["reason"] = "숫자를 읽을 수 있는 프레임이 부족합니다"
            return result

        base = observations[-1][0]
        best_fit, best_expiry = -1.0, base
        for step in range(0, 22):
            expiry = base + step * 0.05
            hits = 0
            for stamp, _crop, count, decimal in observations:
                label = math.ceil(expiry - stamp - 1e-6)
                if decimal:
                    # A sub-second frame can only sit in the final second.
                    hits += 1 if label <= 1 else -2
                elif count > 0:
                    hits += 1 if count == len(str(max(1, label))) else -1
            score = hits / float(len(scorable))
            if score > best_fit:
                best_fit, best_expiry = score, expiry

        result["fit"] = round(best_fit, 3)
        if best_fit < 0.75:
            result["reason"] = f"카운트다운 정렬 실패 (일치율 {best_fit:.2f})"
            return result

        written = 0
        for stamp, crop, count, decimal in observations:
            label = int(math.ceil(best_expiry - stamp - 1e-6))
            if decimal or count <= 0 or not (1 <= label <= 999):
                continue
            if count != len(str(label)):
                continue
            self._write_sample(crop, label)
            written += 1
        result["written"] = written
        result["skipped"] = len(pending) - written
        if not written:
            result["reason"] = "라벨과 글리프 수가 맞는 프레임이 없습니다"
        if _QT_AVAILABLE:
            try:
                self.sample_saved.emit(self.debuff_id, {"summary": result})
            except Exception:
                pass
        return result

    def _write_sample(self, roi_bgr, label: Optional[int]) -> None:
        self._sample_seq += 1
        stamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{self._sample_seq:05d}"
        # The label suffix must stay at the end of the name: the calibration
        # loader parses ``*_09s.png`` and a de-duplication suffix would hide it.
        name = f"{stamp}_{label:02d}s.png" if label else f"{stamp}_unknown.png"
        path = self.sample_root / name
        if write_image(path, roi_bgr) and _QT_AVAILABLE:
            try:
                self.sample_saved.emit(self.debuff_id, {"file": str(path), "label": label})
            except Exception:
                pass

    # -- preview ------------------------------------------------------------
    def render_preview(self, band_bgr: np.ndarray, state: dict) -> np.ndarray:
        preview = band_bgr.copy()
        cell = state.get("cell")
        if cell:
            x, y, w, h = cell
            colour = (0, 255, 120) if state.get("active") else (0, 180, 255)
            cv2.rectangle(preview, (x, y), (x + w, y + h), colour, 1)
            dx, dy, dw, dh = digit_roi_from_cell(x, y, w, h)
            cv2.rectangle(preview, (dx, dy), (dx + dw, dy + dh), (0, 210, 255), 1)
        return cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# Calibration from collected samples
# ---------------------------------------------------------------------------

_LABEL_RE = re.compile(r"(?:^|[_-])(\d{1,3})s(?:[_-]|\.|$)", re.IGNORECASE)


def parse_sample_label(path: Path) -> Optional[int]:
    match = _LABEL_RE.search(Path(path).name)
    if match:
        return int(match.group(1))
    match = re.fullmatch(r"(\d{1,3})\.png", Path(path).name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def glyph_variants(binary: np.ndarray, box: Iterable[int]) -> list[np.ndarray]:
    """정규화 글리프 + 획 두께를 한 단계 얇게/두껍게 한 변형.

    같은 숫자라도 어느 채널로 분리했는지에 따라 획 두께가 달라진다. HOG는 두께에
    민감해서, 한 두께만 배운 프로파일은 다른 채널로 잘라낸 자기 글자를 낮은
    신뢰도로 밀어낸다(예측은 맞는데 0.6에서 걸림). 두께 변형을 함께 학습하면
    어느 채널로 읽어도 같은 글자로 붙는다.
    """
    x, y, w, h = (int(v) for v in box)
    crop = binary[max(0, y):y + h, max(0, x):x + w]
    if crop.size == 0:
        return []
    kernel = np.ones((3, 3), np.uint8)
    shapes = [crop, cv2.erode(crop, kernel), cv2.dilate(crop, kernel)]
    glyphs = []
    for shape in shapes:
        if not shape.any():
            continue
        padded = np.zeros_like(binary)
        padded[max(0, y):y + shape.shape[0], max(0, x):x + shape.shape[1]] = shape
        glyphs.append(normalize_glyph(padded, (x, y, w, h)))
    return glyphs


def train_timer_profile(sample_paths: Iterable[Path], debuff_id: str = DEFAULT_DEBUFF_ID,
                        base_profile: Optional[TimerGlyphProfile] = None,
                        output_path: Optional[Path] = None,
                        progress=None) -> dict:
    """Build the glyph profile from labelled ``*_09s.png`` timer-ROI crops.

    The profile is rebuilt from the sample folder every time instead of being
    appended to the previous one: a single mislabelled training round used to
    stay in the profile forever.  Training ends with a leave-one-out check, and
    the score is stored so :attr:`TimerGlyphProfile.trusted` can refuse to use
    a glyph set that cannot separate its own digits.

    Every sample is learned through *all* colour separations that resolve it,
    not just the warm channel.  A glyph cut out of a luminance top-hat has
    slightly thicker strokes than the same glyph cut out of the warm channel, so
    a profile that only ever saw one channel rejects its own digits the moment a
    warm boss arena forces the reader onto another channel.
    """
    profile = base_profile if base_profile is not None else TimerGlyphProfile(profile_id=debuff_id)
    profile.profile_id = debuff_id
    added = 0
    used = 0
    skipped: list[str] = []
    heights: list[int] = []
    paths = list(sample_paths)
    for index, path in enumerate(paths):
        if progress is not None and not progress(index, len(paths), path):
            skipped.append("사용자 취소")
            break
        path = Path(path)
        label = parse_sample_label(path)
        image = read_image(path)
        if label is None or label <= 0 or image is None:
            skipped.append(f"{path.name}: 라벨/이미지 없음")
            continue
        text = str(label)
        variants = 0
        fields: dict[str, np.ndarray] = {}
        big = upscale_roi(image, TIMER_UPSCALE)
        for binary, suffix_box, digit_boxes, mode, _thr, _priority in timer_hypotheses(image):
            if len(digit_boxes) != len(text):
                continue
            if has_decimal_point(binary, suffix_box, digit_boxes):
                continue
            if mode not in fields:
                fields[mode] = timer_score(big, mode, None, TIMER_UPSCALE)
            field_image = fields[mode]
            for char, box in zip(text, digit_boxes):
                for glyph in glyph_variants(binary, box):
                    if profile.add_digit(int(char), glyph):
                        added += 1
                # 상관 정합용 외형 템플릿. 이진화 이전의 점수 이미지에서 딴다.
                profile.add_patch(int(char), appearance_patch(field_image, box), mode)
                heights.append(int(box[3]))
            profile.add_suffix(normalize_glyph(binary, suffix_box))
            profile.add_patch(None, appearance_patch(field_image, suffix_box), mode)
            variants += 1
        if variants:
            used += 1
        else:
            skipped.append(f"{path.name}: 라벨과 맞는 분리 결과가 없음")
    if heights:
        profile.text_height = int(np.median(heights))
    templates = profile.compact_patches()
    profile.accuracy = profile.self_accuracy()
    profile._loo = profile.accuracy
    profile.source = "calibration"
    path = Path(output_path) if output_path else user_data_root() / "timer_profiles" / f"{debuff_id}.json"
    profile.save(path)
    return {
        "ok": profile.trusted,
        "used_images": used,
        "added_glyphs": added,
        "templates": templates,
        "digits": profile.digit_coverage,
        "trusted": profile.trusted,
        "accuracy": round(float(profile.accuracy), 3),
        "missing_digits": [d for d in range(10) if d not in profile.digit_coverage],
        "skipped": skipped[:20],
        "output": str(path),
    }
