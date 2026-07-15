"""Lost Ark cooldown digit recognition built specifically for the in-game ``Ns`` HUD.

The engine deliberately does not use a general-purpose OCR package.  It detects the
``s`` suffix, segments the one-to-four digits to its left, classifies HOG features
with OpenCV KNN, and then applies a conservative per-slot temporal filter.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np


PROFILE_VERSION = 1
DEFAULT_PROFILE_ID = "lostark_1080p_100"
DEFAULT_DIGIT_ROI = (0.12, 0.24, 0.68, 0.40)
GLYPH_SIZE = (12, 16)  # width, height
SUPPORTED_THRESHOLDS = (145, 160, 175, 190)


def _appdata_dir() -> Path:
    root = Path(os.environ.get("APPDATA", str(Path.home()))) / "PengZoom"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def _encode_png(image: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", image)
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""


def _decode_png(value: str, flags: int = cv2.IMREAD_GRAYSCALE) -> Optional[np.ndarray]:
    if not value:
        return None
    try:
        raw = np.frombuffer(base64.b64decode(value), dtype=np.uint8)
        return cv2.imdecode(raw, flags)
    except Exception:
        return None


def _read_image(path: Path) -> Optional[np.ndarray]:
    try:
        raw = np.fromfile(str(path), dtype=np.uint8)
        return cv2.imdecode(raw, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _write_image(path: Path, image: np.ndarray) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ok, buf = cv2.imencode(path.suffix or ".png", image)
        if ok:
            buf.tofile(str(path))
        return bool(ok)
    except Exception:
        return False


@dataclass
class OcrObservation:
    seconds: Optional[int]
    confidence: float
    accepted: bool
    reject_reason: str = ""
    digit_boxes: list[tuple[int, int, int, int]] = field(default_factory=list)
    suffix_box: Optional[tuple[int, int, int, int]] = None
    raw_seconds: Optional[int] = None
    binary_image: Optional[np.ndarray] = field(default=None, repr=False, compare=False)
    digit_roi_image: Optional[np.ndarray] = field(default=None, repr=False, compare=False)

    def quality_payload(self) -> dict:
        return {
            "seconds": self.seconds,
            "raw_seconds": self.raw_seconds,
            "confidence": float(self.confidence),
            "accepted": bool(self.accepted),
            "reject_reason": self.reject_reason,
            "digit_boxes": [list(box) for box in self.digit_boxes],
            "suffix_box": list(self.suffix_box) if self.suffix_box else None,
        }


@dataclass
class OcrProfile:
    profile_id: str = DEFAULT_PROFILE_ID
    version: int = PROFILE_VERSION
    slot_size: tuple[int, int] = (45, 43)
    digit_height: float = 13.0
    digit_roi: tuple[float, float, float, float] = DEFAULT_DIGIT_ROI
    thresholds: tuple[int, ...] = SUPPORTED_THRESHOLDS
    labels: list[int] = field(default_factory=list)
    glyphs: list[str] = field(default_factory=list)
    suffix_templates: list[str] = field(default_factory=list)
    max_nearest_distance: float = 3.5
    min_margin: float = 0.08
    min_confidence: float = 0.62
    source: str = "user-calibration"

    @property
    def trained(self) -> bool:
        return len(self.labels) >= 10 and len(self.labels) == len(self.glyphs)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "slot_size": list(self.slot_size),
            "digit_height": self.digit_height,
            "digit_roi": list(self.digit_roi),
            "thresholds": list(self.thresholds),
            "labels": self.labels,
            "glyphs": self.glyphs,
            "suffix_templates": self.suffix_templates,
            "max_nearest_distance": self.max_nearest_distance,
            "min_margin": self.min_margin,
            "min_confidence": self.min_confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OcrProfile":
        return cls(
            profile_id=str(data.get("profile_id", DEFAULT_PROFILE_ID)),
            version=int(data.get("version", PROFILE_VERSION)),
            slot_size=tuple(int(v) for v in data.get("slot_size", (45, 43))),
            digit_height=float(data.get("digit_height", 13.0)),
            digit_roi=tuple(float(v) for v in data.get("digit_roi", DEFAULT_DIGIT_ROI)),
            thresholds=tuple(int(v) for v in data.get("thresholds", SUPPORTED_THRESHOLDS)),
            labels=[int(v) for v in data.get("labels", [])],
            glyphs=[str(v) for v in data.get("glyphs", [])],
            suffix_templates=[str(v) for v in data.get("suffix_templates", [])],
            max_nearest_distance=float(data.get("max_nearest_distance", 3.5)),
            min_margin=float(data.get("min_margin", 0.08)),
            min_confidence=float(data.get("min_confidence", 0.62)),
            source=str(data.get("source", "user-calibration")),
        )


class OcrProfileStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else _appdata_dir() / "ocr_profiles"
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, profile_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", profile_id).strip("._") or DEFAULT_PROFILE_ID
        return self.root / f"{safe}.json"

    def save(self, profile: OcrProfile) -> Path:
        path = self.path_for(profile.profile_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        return path

    def load(self, profile_id: str) -> Optional[OcrProfile]:
        candidates = [self.path_for(profile_id), _resource_path(f"ocr_profiles/{profile_id}.json")]
        for path in candidates:
            try:
                if path.exists():
                    profile = OcrProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
                    if profile.version == PROFILE_VERSION and profile.trained:
                        return profile
            except Exception:
                continue
        return None

    def list_profiles(self) -> list[str]:
        names = {p.stem for p in self.root.glob("*.json")}
        bundled = _resource_path("ocr_profiles")
        if bundled.exists():
            names.update(p.stem for p in bundled.glob("*.json"))
        return sorted(names)

    def best_profile_id(self, slot_width: int, slot_height: int) -> Optional[str]:
        best = None
        for profile_id in self.list_profiles():
            profile = self.load(profile_id)
            if profile is None:
                continue
            pw, ph = profile.slot_size
            distance = abs(math.log(max(1, slot_width) / max(1, pw))) + abs(
                math.log(max(1, slot_height) / max(1, ph))
            )
            if best is None or distance < best[0]:
                best = (distance, profile_id)
        return best[1] if best else None


class OcrQualityLogger:
    def __init__(self, enabled: bool = True, save_low_confidence: bool = False):
        self.enabled = enabled
        self.save_low_confidence = save_low_confidence
        self.root = _appdata_dir() / "ocr_logs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "quality.jsonl"
        self.crop_dir = self.root / "low_confidence"

    def log(self, slot_name: str, profile_id: str, observation: OcrObservation,
            interpolated: Optional[float] = None, frame: Optional[np.ndarray] = None) -> None:
        if not self.enabled:
            return
        try:
            self._rotate_log()
            record = {
                "timestamp": time.time(),
                "slot": slot_name,
                "profile_id": profile_id,
                "raw_candidate": observation.raw_seconds,
                "confirmed": observation.seconds,
                "confidence": round(float(observation.confidence), 4),
                "accepted": bool(observation.accepted),
                "reject_reason": observation.reject_reason,
                "interpolated": round(float(interpolated), 3) if interpolated is not None else None,
            }
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            if self.save_low_confidence and frame is not None and not observation.accepted:
                stamp = int(time.time() * 1000)
                _write_image(self.crop_dir / f"{stamp}_{_safe_name(slot_name)}.png", frame)
                self._trim_crops(100 * 1024 * 1024)
        except Exception:
            pass

    def _rotate_log(self) -> None:
        if self.log_path.exists() and self.log_path.stat().st_size > 10 * 1024 * 1024:
            old = self.log_path.with_suffix(".jsonl.1")
            if old.exists():
                old.unlink()
            self.log_path.replace(old)

    def _trim_crops(self, max_bytes: int) -> None:
        if not self.crop_dir.exists():
            return
        files = sorted((p for p in self.crop_dir.glob("*.png") if p.is_file()), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        for path in files:
            if total <= max_bytes:
                break
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            total -= size


def _safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", value)[:60] or "slot"


class OcrDatasetCollector:
    """Local-only 15 FPS slot recorder used for calibration and diagnostics."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else _appdata_dir() / "ocr_datasets"
        self.active = False
        self.session_dir: Optional[Path] = None
        self.slot_name = ""
        self.start_seconds = 0
        self.started_at = 0.0
        self.last_saved_at = 0.0
        self.next_save_at = 0.0
        self.frame_count = 0
        self.metadata: dict = {}

    def start(self, slot_name: str, start_seconds: int, metadata: Optional[dict] = None) -> Path:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.root / f"{stamp}_{_safe_name(slot_name)}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.slot_name = slot_name
        self.start_seconds = max(1, int(start_seconds))
        self.started_at = time.monotonic()
        self.last_saved_at = 0.0
        self.next_save_at = self.started_at
        self.frame_count = 0
        self.metadata = dict(metadata or {})
        self.metadata.update({
            "slot": slot_name,
            "start_seconds": self.start_seconds,
            "capture_fps": 15,
            "created_at": time.time(),
            "full_screen_saved": False,
        })
        self.active = True
        return self.session_dir

    def add_frame(self, frame_rgb: np.ndarray, now: Optional[float] = None) -> bool:
        if not self.active or self.session_dir is None:
            return False
        now = time.monotonic() if now is None else now
        if now + 1e-6 < self.next_save_at:
            return False
        elapsed = max(0.0, now - self.started_at)
        seconds = max(0, int(math.ceil(self.start_seconds - elapsed)))
        self.frame_count += 1
        name = f"frame_{self.frame_count:06d}_{seconds:04d}s.png"
        bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR) if frame_rgb.ndim == 3 else frame_rgb
        saved = _write_image(self.session_dir / name, bgr)
        if saved:
            self.last_saved_at = now
            interval = 1.0 / 15.0
            self.next_save_at = max(self.next_save_at + interval, now - interval)
        if seconds <= 0:
            self.stop()
        return saved

    def stop(self) -> Optional[Path]:
        if self.session_dir is None:
            self.active = False
            return None
        self.metadata.update({"frame_count": self.frame_count, "finished_at": time.time()})
        try:
            (self.session_dir / "metadata.json").write_text(
                json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        path = self.session_dir
        self.active = False
        return path


class _TemporalState:
    def __init__(self):
        self.last_seconds: Optional[int] = None
        self.last_confirmed_at = 0.0
        self.ready = True
        self.drop_candidate: Optional[int] = None
        self.drop_count = 0

    def mark_ready(self) -> None:
        self.ready = True
        self.last_seconds = None
        self.drop_candidate = None
        self.drop_count = 0

    def filter(self, observation: OcrObservation, now: float) -> OcrObservation:
        candidate = observation.raw_seconds
        if not observation.accepted or candidate is None:
            return observation
        if candidate < 1 or candidate > 9999:
            observation.accepted = False
            observation.seconds = None
            observation.reject_reason = "out_of_range"
            return observation

        if self.last_seconds is None or self.ready:
            return self._accept(observation, candidate, now)

        delta = self.last_seconds - candidate
        if delta in (0, 1):
            return self._accept(observation, candidate, now)
        if delta > 1:
            if observation.confidence < 0.82:
                return self._reject(observation, "large_drop_low_confidence")
            if self.drop_candidate == candidate:
                self.drop_count += 1
            else:
                self.drop_candidate = candidate
                self.drop_count = 1
            if self.drop_count >= 2:
                return self._accept(observation, candidate, now)
            return self._reject(observation, "large_drop_needs_confirmation")

        return self._reject(observation, "increase_while_active")

    def _accept(self, observation: OcrObservation, candidate: int, now: float) -> OcrObservation:
        self.last_seconds = candidate
        self.last_confirmed_at = now
        self.ready = False
        self.drop_candidate = None
        self.drop_count = 0
        observation.seconds = candidate
        observation.accepted = True
        observation.reject_reason = ""
        return observation

    @staticmethod
    def _reject(observation: OcrObservation, reason: str) -> OcrObservation:
        observation.seconds = None
        observation.accepted = False
        observation.reject_reason = reason
        return observation


def _crop_normalized(image: np.ndarray, roi: Iterable[float]) -> tuple[np.ndarray, tuple[int, int]]:
    rx, ry, rw, rh = [float(v) for v in roi]
    h, w = image.shape[:2]
    x0 = max(0, min(w - 1, int(round(rx * w))))
    y0 = max(0, min(h - 1, int(round(ry * h))))
    x1 = max(x0 + 1, min(w, int(round((rx + rw) * w))))
    y1 = max(y0 + 1, min(h, int(round((ry + rh) * h))))
    return image[y0:y1, x0:x1], (x0, y0)


def _make_binary(image_bgr: np.ndarray, threshold: int) -> np.ndarray:
    if image_bgr.ndim == 2:
        gray = image_bgr
        saturation = np.zeros_like(gray)
    else:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        saturation = hsv[:, :, 1]
    # Cooldown glyphs are nearly white; saturation gating removes most icon art.
    mask = ((gray >= threshold) & (saturation <= 145)).astype(np.uint8) * 255
    kernel = np.ones((2, 2), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _components(binary: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    result = []
    for x, y, w, h, area in stats[1:count]:
        if area >= 4:
            result.append((int(x), int(y), int(w), int(h), int(area)))
    return result


def _normalize_glyph(binary: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = box
    crop = binary[max(0, y):y + h, max(0, x):x + w]
    if crop.size == 0:
        return np.zeros((GLYPH_SIZE[1], GLYPH_SIZE[0]), np.uint8)
    canvas = np.zeros((GLYPH_SIZE[1], GLYPH_SIZE[0]), np.uint8)
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


def _hog(glyph: np.ndarray) -> np.ndarray:
    return _HOG.compute(glyph).reshape(-1).astype(np.float32)


def _suffix_and_digit_boxes(binary: np.ndarray, expected_digits: Optional[int] = None):
    comps = _components(binary)
    rh, rw = binary.shape[:2]
    # The suffix is the right-most text-sized component. Its upper edge may merge
    # with the download overlay, so only its x anchor is used for digit splitting.
    suffix_candidates = [
        c for c in comps
        if c[0] >= int(rw * 0.38) and c[2] <= max(14, int(rw * 0.45))
        and c[3] >= max(6, int(rh * 0.38)) and c[1] <= int(rh * 0.65)
    ]
    if not suffix_candidates:
        return None, []
    sx, sy, sw, sh, _ = max(suffix_candidates, key=lambda c: c[0])
    suffix_box = (sx, max(sy, int(rh * 0.24)), min(sw, rw - sx), min(sh, rh - max(sy, int(rh * 0.24))))

    candidates = []
    for x, y, w, h, area in comps:
        if x + w > sx + 1:
            continue
        if h < max(8, int(math.ceil(rh * 0.58))) or h > rh:
            continue
        if w > max(11, int(rw * 0.35)):
            continue
        if y > int(rh * 0.45):
            continue
        candidates.append((x, y, w, h))
    candidates.sort(key=lambda b: b[0])
    if expected_digits is not None and len(candidates) > expected_digits:
        candidates = candidates[-expected_digits:]
    return suffix_box, candidates


class CooldownOcrEngine:
    def __init__(self, profile_store: Optional[OcrProfileStore] = None,
                 logger: Optional[OcrQualityLogger] = None):
        self.profile_store = profile_store or OcrProfileStore()
        self.logger = logger or OcrQualityLogger()
        self._profiles: dict[str, OcrProfile] = {}
        self._models: dict[str, cv2.ml_KNearest] = {}
        self._training_features: dict[str, np.ndarray] = {}
        self._training_labels: dict[str, np.ndarray] = {}
        self._states: dict[str, _TemporalState] = {}

    def available_profiles(self) -> list[str]:
        return self.profile_store.list_profiles()

    def best_profile_id(self, slot_width: int, slot_height: int) -> str:
        return self.profile_store.best_profile_id(slot_width, slot_height) or DEFAULT_PROFILE_ID

    def load_profile(self, profile_id: str) -> Optional[OcrProfile]:
        if profile_id in self._profiles:
            return self._profiles[profile_id]
        profile = self.profile_store.load(profile_id)
        if profile is None:
            return None
        features, labels = [], []
        for label, encoded in zip(profile.labels, profile.glyphs):
            glyph = _decode_png(encoded)
            if glyph is not None:
                features.append(_hog(glyph))
                labels.append(float(label))
        if len(features) < 10:
            return None
        feature_matrix = np.asarray(features, np.float32)
        model = cv2.ml.KNearest_create()
        model.setDefaultK(3)
        model.setIsClassifier(True)
        model.train(feature_matrix, cv2.ml.ROW_SAMPLE, np.asarray(labels, np.float32))
        self._profiles[profile_id] = profile
        self._models[profile_id] = model
        self._training_features[profile_id] = feature_matrix
        self._training_labels[profile_id] = np.asarray(labels, np.int32)
        return profile

    def recognize(self, slot_id: str, frame_rgb: np.ndarray, profile_id: str = DEFAULT_PROFILE_ID,
                  digit_roi: Optional[Iterable[float]] = None, now: Optional[float] = None) -> OcrObservation:
        profile = self.load_profile(profile_id)
        if profile is None:
            return OcrObservation(None, 0.0, False, "profile_not_trained")
        now = time.monotonic() if now is None else now
        bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR) if frame_rgb.ndim == 3 else frame_rgb
        target_size = tuple(profile.slot_size)
        if (bgr.shape[1], bgr.shape[0]) != target_size:
            bgr = cv2.resize(bgr, target_size, interpolation=cv2.INTER_CUBIC)
        roi, _ = _crop_normalized(bgr, digit_roi or profile.digit_roi)
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB) if roi.ndim == 3 else roi

        best: Optional[OcrObservation] = None
        for threshold in profile.thresholds:
            binary = _make_binary(roi, threshold)
            observation = self._recognize_binary(profile, binary, roi_rgb)
            if best is None or observation.confidence > best.confidence:
                best = observation
            if observation.accepted and observation.confidence >= 0.98:
                break
        if best is None:
            best = OcrObservation(None, 0.0, False, "preprocess_failed", digit_roi_image=roi)

        state = self._states.setdefault(slot_id, _TemporalState())
        return state.filter(best, now)

    def _recognize_binary(self, profile: OcrProfile, binary: np.ndarray,
                          roi: np.ndarray) -> OcrObservation:
        suffix_box, digit_boxes = _suffix_and_digit_boxes(binary)
        if suffix_box is None:
            return OcrObservation(None, 0.0, False, "suffix_not_found",
                                  binary_image=binary, digit_roi_image=roi)
        if not 1 <= len(digit_boxes) <= 4:
            return OcrObservation(None, 0.0, False, "digit_count",
                                  digit_boxes=digit_boxes, suffix_box=suffix_box,
                                  binary_image=binary, digit_roi_image=roi)

        values, confidences = [], []
        for box in digit_boxes:
            feature = _hog(_normalize_glyph(binary, box))
            model = self._models[profile.profile_id]
            _, result, _, _ = model.findNearest(feature.reshape(1, -1), k=1)
            digit = int(round(float(result[0, 0])))
            training = self._training_features[profile.profile_id]
            training_labels = self._training_labels[profile.profile_id]
            all_distances = np.linalg.norm(training - feature, axis=1)
            class_distances = {
                value: float(np.min(all_distances[training_labels == value]))
                for value in range(10) if np.any(training_labels == value)
            }
            ranked = sorted(class_distances.items(), key=lambda item: item[1])
            nearest = class_distances[digit]
            competitors = [distance for value, distance in ranked if value != digit]
            second = competitors[0] if competitors else nearest + 1.0
            margin = max(0.0, (second - nearest) / max(second, 1e-6))
            distance_score = max(0.0, 1.0 - nearest / max(profile.max_nearest_distance, 1e-6))
            confidence = 0.72 * distance_score + 0.28 * min(1.0, margin / max(profile.min_margin, 1e-6))
            if nearest > profile.max_nearest_distance or margin < profile.min_margin:
                confidence *= 0.65
            values.append(digit)
            confidences.append(confidence)

        seconds = int("".join(str(v) for v in values))
        confidence = float(min(confidences)) if confidences else 0.0
        accepted = confidence >= profile.min_confidence
        return OcrObservation(
            seconds if accepted else None,
            confidence,
            accepted,
            "" if accepted else "ambiguous_digit",
            digit_boxes=digit_boxes,
            suffix_box=suffix_box,
            raw_seconds=seconds,
            binary_image=binary,
            digit_roi_image=roi,
        )

    def mark_ready(self, slot_id: str) -> None:
        self._states.setdefault(slot_id, _TemporalState()).mark_ready()

    def reset_slot(self, slot_id: str) -> None:
        self._states.pop(slot_id, None)


def _parse_label(path: Path) -> Optional[int]:
    match = re.search(r"(?:_|^)(\d+)s(?:\.|$)", path.name, re.IGNORECASE)
    if not match:
        match = re.fullmatch(r"(\d+)\.png", path.name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def build_profile_from_images(image_paths: Iterable[Path], output_path: Path,
                              profile_id: str = DEFAULT_PROFILE_ID,
                              digit_roi: Iterable[float] = DEFAULT_DIGIT_ROI,
                              source: str = "seed-captures",
                              base_profile: Optional[OcrProfile] = None) -> tuple[OcrProfile, dict]:
    glyphs: list[str] = list(base_profile.glyphs) if base_profile else []
    labels: list[int] = list(base_profile.labels) if base_profile else []
    suffixes: list[str] = list(base_profile.suffix_templates) if base_profile else []
    digit_heights: list[float] = [base_profile.digit_height] if base_profile else []
    known_glyphs = set(zip(labels, glyphs))
    known_suffixes = set(suffixes)
    loaded_images: list[tuple[Path, int, np.ndarray]] = []
    for path in image_paths:
        label = _parse_label(Path(path))
        image = _read_image(Path(path))
        if label is not None and label > 0 and image is not None:
            loaded_images.append((Path(path), label, image))

    image_count = len(loaded_images)
    segmented_count = 0
    slot_sizes = [(image.shape[1], image.shape[0]) for _, _, image in loaded_images]
    if not slot_sizes:
        raise ValueError("학습할 PNG 이미지를 찾지 못했습니다.")
    median_w = int(np.median([s[0] for s in slot_sizes]))
    median_h = int(np.median([s[1] for s in slot_sizes]))

    for path, label, image in loaded_images:
        if (image.shape[1], image.shape[0]) != (median_w, median_h):
            image = cv2.resize(image, (median_w, median_h), interpolation=cv2.INTER_CUBIC)
        roi, _ = _crop_normalized(image, digit_roi)
        expected = len(str(label))
        found_for_image = False
        for threshold in SUPPORTED_THRESHOLDS:
            binary = _make_binary(roi, threshold)
            suffix_box, boxes = _suffix_and_digit_boxes(binary, expected)
            if suffix_box is None or len(boxes) != expected:
                continue
            found_for_image = True
            for digit, box in zip(str(label), boxes):
                digit_value = int(digit)
                encoded_glyph = _encode_png(_normalize_glyph(binary, box))
                if (digit_value, encoded_glyph) not in known_glyphs:
                    glyphs.append(encoded_glyph)
                    labels.append(digit_value)
                    known_glyphs.add((digit_value, encoded_glyph))
                digit_heights.append(int(box[3]))
            sx, sy, sw, sh = suffix_box
            encoded_suffix = _encode_png(_normalize_glyph(binary, (sx, sy, sw, sh)))
            if encoded_suffix not in known_suffixes:
                suffixes.append(encoded_suffix)
                known_suffixes.add(encoded_suffix)
        if found_for_image:
            segmented_count += 1

    if len(set(labels)) < 10:
        raise ValueError(f"숫자 0~9 학습 표본이 부족합니다: {sorted(set(labels))}")
    profile = OcrProfile(
        profile_id=profile_id,
        slot_size=(median_w, median_h),
        digit_height=float(np.median(digit_heights)) if digit_heights else 13.0,
        digit_roi=tuple(float(v) for v in digit_roi),
        labels=labels,
        glyphs=glyphs,
        suffix_templates=suffixes[:64],
        source=source,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return profile, {
        "images": image_count,
        "segmented_images": segmented_count,
        "glyphs": len(glyphs),
        "added_glyphs": len(glyphs) - (len(base_profile.glyphs) if base_profile else 0),
        "digits": sorted(set(labels)),
        "output": str(output_path),
    }


def benchmark_profile(profile_path: Path, image_paths: Iterable[Path]) -> dict:
    store = OcrProfileStore(profile_path.parent)
    profile = OcrProfile.from_dict(json.loads(profile_path.read_text(encoding="utf-8")))
    if store.path_for(profile.profile_id).resolve() != profile_path.resolve():
        store.save(profile)
    engine = CooldownOcrEngine(store, OcrQualityLogger(enabled=False))
    total = correct = accepted = false_confirm = unknown = 0
    rows = []
    for index, path in enumerate(image_paths):
        expected = _parse_label(Path(path))
        image = _read_image(Path(path))
        if expected is None or image is None:
            continue
        total += 1
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        obs = engine.recognize(f"bench_{index}", rgb, profile.profile_id)
        if obs.accepted:
            accepted += 1
            if obs.seconds == expected:
                correct += 1
            else:
                false_confirm += 1
        else:
            unknown += 1
        rows.append({
            "file": Path(path).name,
            "expected": expected,
            "observed": obs.seconds,
            "raw": obs.raw_seconds,
            "confidence": round(obs.confidence, 4),
            "accepted": obs.accepted,
            "reason": obs.reject_reason,
        })
    return {
        "total": total,
        "accepted": accepted,
        "correct": correct,
        "false_confirm": false_confirm,
        "unknown": unknown,
        "confirmed_accuracy": (correct / accepted) if accepted else 0.0,
        "unknown_rate": (unknown / total) if total else 0.0,
        "rows": rows,
    }


def _image_paths(root: Path) -> list[Path]:
    return sorted(root.rglob("*.png"), key=lambda p: p.name)


def main() -> int:
    parser = argparse.ArgumentParser(description="PengZoom Lost Ark cooldown OCR profile tools")
    parser.add_argument("--train", type=Path, help="Directory containing labeled *_<seconds>s.png captures")
    parser.add_argument("--output", type=Path, default=Path("ocr_profiles") / f"{DEFAULT_PROFILE_ID}.json")
    parser.add_argument("--benchmark", type=Path, help="Benchmark directory (defaults to --train)")
    args = parser.parse_args()
    if not args.train:
        parser.error("--train is required")
    paths = _image_paths(args.train)
    _, stats = build_profile_from_images(paths, args.output)
    print(json.dumps({"training": stats}, ensure_ascii=False, indent=2))
    bench_dir = args.benchmark or args.train
    result = benchmark_profile(args.output, _image_paths(bench_dir))
    print(json.dumps({"benchmark": result}, ensure_ascii=False, indent=2))
    return 0 if result["false_confirm"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
