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
  smaller than the skill cooldown digits, so glyph classification alone is not
  trusted.  Seconds are resolved by the first source that is actually reliable:
  trained OCR -> the 2-digit/1-digit transition anchor -> learned duration.
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


PROFILE_VERSION = 1
DEFAULT_DEBUFF_ID = "dark_grenade"
DEBUFF_DISPLAY_NAMES = {DEFAULT_DEBUFF_ID: "암흑 수류탄"}

GLYPH_SIZE = (12, 16)  # width, height of the normalized glyph canvas

# Timer text is drawn in a warm salmon tone (RGB 216,139,111 at 1080p) with a
# dark outline.  A white top-hat keeps those thin strokes and suppresses large
# bright areas of the game world behind the strip.
TIMER_TOPHAT_KERNEL = (7, 7)
TIMER_THRESHOLDS = (40, 55, 70, 30)

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

MAX_NEAREST_DISTANCE = 3.2
MIN_MARGIN = 0.10
MIN_OCR_CONFIDENCE = 0.70
MIN_TRAINED_DIGITS = 8     # digits 0-9 coverage required before OCR is trusted


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
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, TIMER_TOPHAT_KERNEL)
    return cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)


def binarize_timer_text(image_bgr: np.ndarray, threshold: Optional[int] = None) -> tuple[np.ndarray, int]:
    """Return (binary, used_threshold).

    Without an explicit threshold the sweep stops at the first value that
    segments into a suffix plus 1-3 digits, which is what a valid ``N초`` looks
    like.  Otherwise the middle threshold is returned so callers can still
    inspect a best-effort binary image.
    """
    tophat = timer_tophat(image_bgr)
    if threshold is not None:
        return (tophat >= threshold).astype(np.uint8) * 255, int(threshold)

    fallback = None
    for value in TIMER_THRESHOLDS:
        binary = (tophat >= value).astype(np.uint8) * 255
        suffix_box, digit_boxes = segment_timer_glyphs(binary)
        if suffix_box is not None and 1 <= len(digit_boxes) <= 3:
            return binary, value
        if fallback is None:
            fallback = (binary, value)
    return fallback if fallback else ((tophat >= 55).astype(np.uint8) * 255, 55)


def _components(binary: np.ndarray, min_area: int = 3) -> list[tuple[int, int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    result = []
    for x, y, w, h, area in stats[1:count]:
        if area >= min_area:
            result.append((int(x), int(y), int(w), int(h), int(area)))
    return result


def segment_timer_glyphs(binary: np.ndarray) -> tuple[Optional[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    """Locate the ``초`` suffix and the digits to its left.

    The suffix is the widest text-height component nearest the horizontal
    centre of the ROI: the ROI is centred on the debuff cell, so a neighbouring
    cell's text can only ever appear at the far left/right edge.
    """
    height, width = binary.shape[:2]
    comps = _components(binary)
    if not comps:
        return None, []

    text_h = max(4, int(round(height * 0.45)))
    centre = width / 2.0
    # ``초`` is wider than any digit at this scale (10px vs 5-6px at 1080p).
    suffix_candidates = [
        c for c in comps
        if c[3] >= text_h * 0.55 and c[2] >= 6 and c[0] > centre - width * 0.30
        and c[0] > 0 and (c[0] + c[2]) < width
    ]
    if not suffix_candidates:
        return None, []
    suffix = max(suffix_candidates, key=lambda c: (c[2] * c[3], -abs(c[0] - centre)))
    sx, sy, sw, sh, _ = suffix
    suffix_box = (sx, sy, sw, sh)

    digits = []
    for x, y, w, h, _area in comps:
        if x + w > sx + 1:
            continue
        if x <= 0:  # clipped by the ROI edge -> belongs to the neighbour cell
            continue
        if h < text_h * 0.55 or h > height:
            continue
        if w > max(8, int(width * 0.30)):
            continue
        digits.append((x, y, w, h))
    digits.sort(key=lambda b: b[0])
    # Keep only the run that is adjacent to the suffix; anything separated by a
    # gap wider than one glyph belongs to the neighbouring debuff cell.
    if digits:
        kept = [digits[-1]]
        for box in reversed(digits[:-1]):
            previous = kept[0]
            if previous[0] - (box[0] + box[2]) <= max(3, int(round(previous[2] * 0.9))):
                kept.insert(0, box)
            else:
                break
        digits = kept[-3:]
    return suffix_box, digits


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
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_NEAREST)
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
    source: str = "bootstrap"
    _features: Optional[np.ndarray] = field(default=None, repr=False, compare=False)
    _labels_np: Optional[np.ndarray] = field(default=None, repr=False, compare=False)

    # -- persistence --------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "text_height": self.text_height,
            "labels": self.labels,
            "glyphs": self.glyphs,
            "suffix_glyphs": self.suffix_glyphs,
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
        """User-trained profile first, bundled seed second, empty last."""
        for path in (user_data_root() / "timer_profiles" / f"{debuff_id}.json",
                     assets_root() / "timer_profiles" / f"{debuff_id}.json"):
            profile = cls.load(path)
            if profile is not None and profile.version == PROFILE_VERSION:
                return profile
        return cls(profile_id=debuff_id)

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
        return True

    def add_suffix(self, glyph: np.ndarray) -> bool:
        encoded = encode_png(glyph)
        if not encoded or encoded in self.suffix_glyphs:
            return False
        self.suffix_glyphs.append(encoded)
        return True

    # -- inference ----------------------------------------------------------
    @property
    def digit_coverage(self) -> list[int]:
        return sorted(set(self.labels))

    @property
    def trusted(self) -> bool:
        return len(self.digit_coverage) >= MIN_TRAINED_DIGITS

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
        self._anchor_value = None
        self._anchor_at = 0.0
        self._anchor_source = ""
        self._last_signature = None
        self.tick_count = 0
        self.last_tick_at = 0.0
        self.last_ocr_seconds = None
        self.last_ocr_confidence = 0.0

    # -- helpers ------------------------------------------------------------
    @property
    def total_duration(self) -> float:
        return self.configured_duration or self.learned_duration

    def set_anchor(self, value: float, now: float, source: str = "manual") -> None:
        """Pin the countdown to an exactly known remaining value."""
        self._anchor_value = float(value)
        self._anchor_at = now
        self._anchor_source = source
        if self.appeared_at > 0.0:
            candidate = float(value) + (now - self.appeared_at)
            # Only widen the learned total: an early anchor sees the largest
            # remaining value, later anchors can only under-estimate it.
            if candidate > self.learned_duration:
                self.learned_duration = round(candidate, 1)

    def _remaining(self, now: float) -> tuple[Optional[float], str]:
        if self._anchor_value is not None:
            remaining = self._anchor_value - (now - self._anchor_at)
            return max(0.0, remaining), self._anchor_source
        total = self.total_duration
        if total > 0.0 and self.appeared_at > 0.0:
            return max(0.0, total - (now - self.appeared_at)), "duration"
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
            self._last_signature = None
            self._pending_glyph_count = 0
            self._glyph_count_streak = 0
            self.glyph_count = 0
        elif self.active and self._miss_streak >= DEACTIVATE_FRAMES:
            self.active = False
            self.cell = None
            self.score = frame.score
            self._anchor_value = None
            self._anchor_source = ""
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
        # when the remaining time goes 10s -> 9s.
        if frame.glyph_count > 0:
            if frame.glyph_count == self._pending_glyph_count:
                self._glyph_count_streak += 1
            else:
                self._pending_glyph_count = frame.glyph_count
                self._glyph_count_streak = 1
            if self._glyph_count_streak >= GLYPH_COUNT_FRAMES:
                previous = self.glyph_count
                self.glyph_count = frame.glyph_count
                if previous == 2 and frame.glyph_count == 1:
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
            previous, _ = self._remaining(now)
            # OCR may only move the countdown forward (down in seconds) unless
            # nothing is known yet; a jump upwards means a misread.
            if previous is None or frame.ocr_seconds <= math.ceil(previous) + 1:
                self.set_anchor(float(frame.ocr_seconds), now, "ocr")

        return self.snapshot(now)

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
        self.is_running = False
        self._locked_size = None
        self._last_emit = 0.0
        self._last_state = None
        self._last_sample_at = 0.0
        self._sample_buffer: list[tuple[float, np.ndarray]] = []
        self._sample_seq = 0
        self.sample_root = user_data_root() / "samples" / debuff_id
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
            # already show a countdown instead of a bare "ON".
            self.tracker.learned_duration = max(self.tracker.learned_duration,
                                                max(0.0, float(learned_duration)))
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

    def reload_assets(self):
        self.templates = load_icon_templates(self.debuff_id)
        self.profile = TimerGlyphProfile.load_for(self.debuff_id)
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
                binary, _threshold = binarize_timer_text(timer_roi)
                suffix_box, digit_boxes = segment_timer_glyphs(binary)
                if suffix_box is not None and digit_boxes:
                    frame.glyph_count = len(digit_boxes)
                    frame.digit_signature = digit_signature(binary, digit_boxes)
                    seconds, confidence = self.profile.read_seconds(binary, digit_boxes)
                    frame.ocr_seconds = seconds
                    frame.ocr_confidence = confidence
                else:
                    timer_roi = None
        elif match is not None and match.score < self.match_threshold * 0.75:
            # A long miss streak means the strip moved or the boss changed;
            # unlock the scale so the next search covers the full range again.
            self._locked_size = None

        was_active = self.tracker.active
        state = self.tracker.update(frame, now)
        if self.collect_samples and state.get("active") and timer_roi is not None:
            self._save_sample(timer_roi, None, None, None, now)
        elif was_active and not state.get("active"):
            self._sample_buffer.clear()
        self._last_state = state
        self._emit_state(state)
        return state

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
    def _save_sample(self, roi_bgr, binary, suffix_box, digit_boxes, now: float) -> None:
        """Store timer-ROI crops for calibration.

        Labels must be exact, so a crop is only named ``*_09s.png`` once an OCR
        or 2->1 digit anchor is available.  Everything captured before that is
        buffered and labelled backwards from the anchor, which turns a single
        12s cast into samples for 12,11,10,9...1 - full 0-9 digit coverage.
        """
        if now - self._last_sample_at < 0.45:
            return
        self._last_sample_at = now
        state = self.tracker.snapshot(now)
        remaining = state.get("remaining")
        exact = state.get("source") in ("ocr", "anchor") and remaining is not None

        if not exact:
            self._sample_buffer.append((now, roi_bgr.copy()))
            del self._sample_buffer[:-60]
            return

        pending = self._sample_buffer
        self._sample_buffer = []
        pending.append((now, roi_bgr))
        for stamp, crop in pending:
            label = int(math.ceil(float(remaining) + (now - stamp) - 1e-6))
            if label < 1 or label > 999:
                continue
            self._write_sample(crop, label)

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


def train_timer_profile(sample_paths: Iterable[Path], debuff_id: str = DEFAULT_DEBUFF_ID,
                        base_profile: Optional[TimerGlyphProfile] = None,
                        output_path: Optional[Path] = None) -> dict:
    """Build the glyph profile from labelled ``*_09s.png`` timer-ROI crops."""
    profile = base_profile or TimerGlyphProfile.load_for(debuff_id)
    profile.profile_id = debuff_id
    added = 0
    used = 0
    skipped: list[str] = []
    heights: list[int] = []
    for path in sample_paths:
        path = Path(path)
        label = parse_sample_label(path)
        image = read_image(path)
        if label is None or label <= 0 or image is None:
            skipped.append(f"{path.name}: 라벨/이미지 없음")
            continue
        binary, _ = binarize_timer_text(image)
        suffix_box, digit_boxes = segment_timer_glyphs(binary)
        text = str(label)
        if suffix_box is None or len(digit_boxes) != len(text):
            skipped.append(f"{path.name}: 글리프 {len(digit_boxes)}개 / 기대 {len(text)}개")
            continue
        for char, box in zip(text, digit_boxes):
            if profile.add_digit(int(char), normalize_glyph(binary, box)):
                added += 1
            heights.append(int(box[3]))
        profile.add_suffix(normalize_glyph(binary, suffix_box))
        used += 1
    if heights:
        profile.text_height = int(np.median(heights))
    profile.source = "calibration"
    path = Path(output_path) if output_path else user_data_root() / "timer_profiles" / f"{debuff_id}.json"
    profile.save(path)
    return {
        "ok": profile.trusted,
        "used_images": used,
        "added_glyphs": added,
        "digits": profile.digit_coverage,
        "trusted": profile.trusted,
        "missing_digits": [d for d in range(10) if d not in profile.digit_coverage],
        "skipped": skipped[:20],
        "output": str(path),
    }
