import os
import time
import math
import queue
import re
from pathlib import Path
import cv2
import numpy as np
import mss
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal, QRect
from cooldown_ocr import (
    CAPTURE_PROFILE_ID,
    CAPTURE_PROFILE_PREFIX,
    DEFAULT_DIGIT_ROI,
    DEFAULT_PROFILE_ID,
    CooldownOcrEngine,
    OcrDatasetCollector,
    build_profile_from_images,
    train_capture_profile,
)

class SkillSlot:
    def __init__(self, name="스킬", rect=None, threshold=0.85, cooldown_duration=0):
        self.name = name
        self.rect = rect  # QRect or tuple (x, y, w, h)
        self.threshold = threshold
        self.template_path = None
        # Ready is never assumed.  The saved Ready template must be confirmed.
        self.is_ready = False
        self.last_similarity = 0.0
        self.last_appearance_similarity = 0.0
        self.last_brightness_ratio = 0.0
        self.last_saturation_ratio = 0.0
        self.template = None        # Grayscale matrix for cv2 matchTemplate
        self.template_color = None  # RGB color matrix for UI Preview
        self.cooldown_duration = cooldown_duration
        self.trigger_key = None
        self.cooldown_start_time = 0.0
        self.cooldown_seen_unready = False
        self._ready_consec_frames = 0
        self._not_ready_consec_frames = 0
        self.device_ratio = None

        # Cooldown seconds are manual-only. OCR fields remain as dormant
        # compatibility state so older config files can be loaded safely.
        self.ocr_enabled = False
        self.ocr_mode = "off"  # legacy compatibility: off | shadow | primary
        self.ocr_profile_id = DEFAULT_PROFILE_ID
        self.digit_roi = list(DEFAULT_DIGIT_ROI)
        self.ocr_last_seconds = None
        self.ocr_last_confidence = 0.0
        self.ocr_last_confirmed_at = 0.0
        self.ocr_active = False
        self.ocr_last_scan_at = 0.0
        self.ocr_next_scan_at = 0.0
        self.ocr_save_diagnostics = False
        self.last_ocr_quality = {}
        self.last_ocr_frame = None
        self.last_ocr_binary = None

class CooldownDetector(QThread):
    state_changed = pyqtSignal(str, bool, float)  # (skill_name, is_ready, similarity)
    cooldown_observed = pyqtSignal(str, int, float)  # (skill_name, seconds, confidence)
    ocr_quality = pyqtSignal(str, object)  # (skill_name, diagnostic dictionary)
    calibration_finished = pyqtSignal(str, object)  # (skill_name, result dictionary)
    developer_capture_status = pyqtSignal(str, object)  # (skill_name, capture status)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slots = {}  # {name: SkillSlot}
        self.is_running = False
        self.scan_interval = 0.05  # Default 50ms
        self.device_ratio = 1.0    # DPI scale ratio (synced from main window)
        self.ocr_interval = 1.0 / 15.0
        self.ocr_engine = CooldownOcrEngine()
        self.dataset_collector = OcrDatasetCollector()
        self.collecting_slot_name = None
        self.developer_capture_enabled = False
        self.developer_capture_root = Path(
            os.environ.get("APPDATA", str(Path.home()))
        ) / "PengZoom" / "cooldown_captures"
        self._trigger_queue = queue.Queue()
        self._developer_sessions = {}
        self.capture_import_result = {}

    def import_developer_captures(self, force=False):
        result = train_capture_profile(
            self.developer_capture_root,
            self.ocr_engine.profile_store,
            force=force,
        )
        if result.get("ok"):
            cached_ids = set(self.ocr_engine._profiles) | {CAPTURE_PROFILE_ID}
            for profile_id in cached_ids:
                if profile_id == CAPTURE_PROFILE_ID or profile_id.startswith(CAPTURE_PROFILE_PREFIX):
                    self.ocr_engine._profiles.pop(profile_id, None)
                    self.ocr_engine._models.pop(profile_id, None)
                    self.ocr_engine._training_features.pop(profile_id, None)
                    self.ocr_engine._training_labels.pop(profile_id, None)
            for profile_id in result.get("profile_ids", []):
                self.ocr_engine.reload_profile(profile_id)
        self.capture_import_result = result
        return result

    def best_profile_for_slot(self, slot):
        rect = self._rect_values(slot.rect) if slot else None
        if not rect:
            return DEFAULT_PROFILE_ID
        ratio = getattr(slot, "device_ratio", None) or self.device_ratio
        return self.ocr_engine.best_profile_id(
            max(1, int(rect[2] * ratio)),
            max(1, int(rect[3] * ratio)),
        ) or DEFAULT_PROFILE_ID
        
    def add_slot(self, name, rect, threshold=0.85, template_img=None, template_color=None, cooldown_duration=0):
        previous = self.slots.get(name)
        slot = SkillSlot(name, rect, threshold, cooldown_duration)
        
        # Load grayscale and color template matrices
        if template_img is not None:
            if isinstance(template_img, Image.Image):
                img_np = np.array(template_img.convert('RGB'))
                slot.template_color = img_np
                slot.template = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            elif isinstance(template_img, np.ndarray):
                if len(template_img.shape) == 3:
                    # RGB color image received
                    slot.template_color = template_img
                    slot.template = cv2.cvtColor(template_img, cv2.COLOR_RGB2GRAY)
                else:
                    slot.template = template_img
                    slot.template_color = None
            else:
                slot.template = template_img
                slot.template_color = None
        else:
            slot.template = None
            slot.template_color = None
            
        if template_color is not None:
            slot.template_color = template_color

        if previous is not None:
            slot.trigger_key = previous.trigger_key
            slot.device_ratio = previous.device_ratio
            slot.ocr_enabled = previous.ocr_enabled
            slot.ocr_mode = previous.ocr_mode
            slot.ocr_profile_id = previous.ocr_profile_id
            slot.digit_roi = list(previous.digit_roi)
            slot.ocr_save_diagnostics = previous.ocr_save_diagnostics
            slot.cooldown_seen_unready = previous.cooldown_seen_unready
            if cooldown_duration == 0:
                slot.cooldown_duration = previous.cooldown_duration
            
        self.slots[name] = slot
        
    def remove_slot(self, name):
        if name in self.slots:
            self.ocr_engine.reset_slot(name)
            del self.slots[name]

    def configure_ocr(self, name, mode=None, profile_id=None, digit_roi=None,
                      device_ratio=None, save_diagnostics=None):
        slot = self.slots.get(name)
        if not slot:
            return False
        # v2.46 retired cooldown-number OCR. Keep accepting this legacy API so
        # old callers/config migrations do not crash, but never enable scans.
        slot.ocr_mode = "off"
        slot.ocr_enabled = False
        if profile_id:
            slot.ocr_profile_id = str(profile_id)
        if digit_roi is not None and len(digit_roi) == 4:
            slot.digit_roi = [float(v) for v in digit_roi]
        if device_ratio is not None:
            slot.device_ratio = max(0.5, float(device_ratio))
        if save_diagnostics is not None:
            slot.ocr_save_diagnostics = False
        return True

    def start_calibration_collection(self, name, start_seconds):
        slot = self.slots.get(name)
        if not slot or slot.rect is None:
            raise ValueError("먼저 슬롯 영역을 지정해 주세요.")
        self.collecting_slot_name = name
        return self.dataset_collector.start(
            name,
            start_seconds,
            {
                "profile_id": slot.ocr_profile_id,
                "slot_rect": self._rect_values(slot.rect),
                "digit_roi": list(slot.digit_roi),
                "device_ratio": slot.device_ratio,
            },
        )

    def stop_calibration_collection(self, train=True):
        name = self.collecting_slot_name
        session_dir = self.dataset_collector.stop()
        self.collecting_slot_name = None
        if not name or session_dir is None:
            return {"ok": False, "error": "진행 중인 녹화가 없습니다."}
        if not train:
            return {"ok": True, "session_dir": str(session_dir), "trained": False}
        slot = self.slots.get(name)
        if not slot:
            return {"ok": False, "error": "슬롯이 삭제되었습니다.", "session_dir": str(session_dir)}
        try:
            paths = sorted(session_dir.glob("*.png"))
            output = self.ocr_engine.profile_store.path_for(slot.ocr_profile_id)
            base_profile = self.ocr_engine.load_profile(slot.ocr_profile_id)
            _, stats = build_profile_from_images(
                paths,
                output,
                profile_id=slot.ocr_profile_id,
                digit_roi=slot.digit_roi,
                source=f"calibration:{session_dir.name}",
                base_profile=base_profile,
            )
            self.ocr_engine._profiles.pop(slot.ocr_profile_id, None)
            self.ocr_engine._models.pop(slot.ocr_profile_id, None)
            self.ocr_engine._training_features.pop(slot.ocr_profile_id, None)
            self.ocr_engine._training_labels.pop(slot.ocr_profile_id, None)
            loaded = self.ocr_engine.load_profile(slot.ocr_profile_id)
            result = {"ok": loaded is not None, "trained": loaded is not None,
                      "session_dir": str(session_dir), **stats}
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "session_dir": str(session_dir)}
        self.calibration_finished.emit(name, result)
        return result

    @staticmethod
    def _rect_values(rect):
        if isinstance(rect, QRect):
            return [rect.x(), rect.y(), rect.width(), rect.height()]
        return list(rect) if rect else None
            
    def request_trigger(self, name, trigger_monotonic=None):
        """Queue a global-key trigger for detector-thread processing."""
        if trigger_monotonic is None:
            trigger_monotonic = time.monotonic()
        self._trigger_queue.put((name, trigger_monotonic, time.time()))

    def trigger_cooldown(self, name):
        # Backwards-compatible entry point used by older callers.
        self.request_trigger(name)

    def _drain_trigger_requests(self, now_mono=None):
        now_mono = time.monotonic() if now_mono is None else now_mono
        while True:
            try:
                name, trigger_mono, trigger_wall = self._trigger_queue.get_nowait()
            except queue.Empty:
                break
            slot = self.slots.get(name)
            if slot is None:
                continue

            # pynput may repeat a held key.  Never restart an active capture or
            # move its one-second labels forward.
            if self.developer_capture_enabled and name in self._developer_sessions:
                continue

            # Manual time owns the displayed/broadcast remaining seconds.
            # Ready still requires the saved skill template to be confirmed.
            if slot.cooldown_duration > 0:
                slot.cooldown_start_time = trigger_wall
                slot.cooldown_seen_unready = False

            if self.developer_capture_enabled:
                self._start_developer_capture(name, slot, trigger_mono, now_mono)

    @staticmethod
    def _safe_capture_name(name):
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name)).strip(" .")
        return safe[:80] or "skill"

    def _start_developer_capture(self, name, slot, trigger_mono, now_mono):
        if name in self._developer_sessions:
            return
        if slot.rect is None or slot.cooldown_duration <= 0:
            self.developer_capture_status.emit(name, {
                "event": "rejected",
                "reason": "영역과 쿨타임(1초 이상)을 먼저 설정해 주세요.",
            })
            return

        safe_name = self._safe_capture_name(name)
        stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int((time.time() % 1) * 1000):03d}"
        session_dir = self.developer_capture_root / f"{stamp}_{safe_name}"
        suffix = 1
        while session_dir.exists():
            session_dir = self.developer_capture_root / f"{stamp}_{safe_name}_{suffix}"
            suffix += 1
        try:
            session_dir.mkdir(parents=True, exist_ok=False)
        except Exception as exc:
            self.developer_capture_status.emit(name, {
                "event": "error",
                "reason": f"캡처 폴더 생성 실패: {exc}",
                "directory": str(session_dir),
            })
            return
        duration = max(1, int(math.ceil(slot.cooldown_duration)))
        self._developer_sessions[name] = {
            "directory": session_dir,
            "safe_name": safe_name,
            "duration": duration,
            # Labels are anchored to the actual key event.  If the detector is
            # delayed, elapsed labels are skipped instead of being shifted.
            "capture_origin": trigger_mono + 0.25,
            "last_label": None,
            "saved": 0,
        }
        self.developer_capture_status.emit(name, {
            "event": "started",
            "directory": str(session_dir),
            "expected": duration,
        })

    def _capture_developer_frame(self, name, frame_rgb, now_mono):
        session = self._developer_sessions.get(name)
        if session is None or now_mono < session["capture_origin"]:
            return
        elapsed = now_mono - session["capture_origin"]
        label = session["duration"] - int(math.floor(elapsed))
        if label <= 0:
            self._finish_developer_capture(name)
            return
        if session["last_label"] == label:
            return

        # If the detector was delayed, save only the currently visible second;
        # never duplicate one late frame under several labels.
        output = session["directory"] / f"{session['safe_name']}_{label}s.png"
        try:
            bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR) if frame_rgb.ndim == 3 else frame_rgb
            ok, encoded = cv2.imencode(".png", bgr)
            if not ok:
                raise OSError("PNG 인코딩 실패")
            encoded.tofile(str(output))
            session["last_label"] = label
            session["saved"] += 1
            self.developer_capture_status.emit(name, {
                "event": "saved",
                "seconds": label,
                "saved": session["saved"],
                "file": str(output),
                "directory": str(session["directory"]),
            })
            if label == 1:
                self._finish_developer_capture(name)
        except Exception as exc:
            self.developer_capture_status.emit(name, {
                "event": "error",
                "reason": str(exc),
                "directory": str(session["directory"]),
            })
            self._developer_sessions.pop(name, None)

    def _finish_developer_capture(self, name):
        session = self._developer_sessions.pop(name, None)
        if session is not None:
            self.developer_capture_status.emit(name, {
                "event": "finished",
                "saved": session["saved"],
                "directory": str(session["directory"]),
            })

    @staticmethod
    def _resolve_skill_recognition(slot, raw_ready):
        """Return Ready using only the saved skill-template recognizer."""
        if raw_ready:
            slot._ready_consec_frames += 1
            slot._not_ready_consec_frames = 0
        else:
            slot._not_ready_consec_frames += 1
            slot._ready_consec_frames = 0
        if slot._ready_consec_frames >= 3:
            return True
        if slot._not_ready_consec_frames >= 3:
            return False
        return slot.is_ready

    @staticmethod
    def _ready_appearance_matches(slot, captured_rgb, match_gray):
        """Reject darkened/desaturated cooldown icons that correlate as Ready."""
        template_gray = slot.template
        if template_gray is None:
            return False
        th, tw = template_gray.shape[:2]

        current_gray = cv2.GaussianBlur(match_gray, (3, 3), 0)
        reference_gray = cv2.GaussianBlur(template_gray, (3, 3), 0)
        gray_delta = np.mean(cv2.absdiff(current_gray, reference_gray)) / 255.0
        appearance_similarity = 1.0 - float(gray_delta)

        reference_mean = float(np.mean(reference_gray))
        current_mean = float(np.mean(current_gray))
        brightness_ratio = current_mean / max(1.0, reference_mean)
        saturation_ratio = 1.0

        if slot.template_color is not None:
            current_color = cv2.resize(captured_rgb, (tw, th), interpolation=cv2.INTER_AREA)
            reference_color = slot.template_color
            if reference_color.shape[:2] != (th, tw):
                reference_color = cv2.resize(reference_color, (tw, th), interpolation=cv2.INTER_AREA)
            current_color = cv2.GaussianBlur(current_color, (3, 3), 0)
            reference_color = cv2.GaussianBlur(reference_color, (3, 3), 0)
            color_delta = np.mean(
                np.abs(current_color.astype(np.float32) - reference_color.astype(np.float32))
            ) / 255.0
            appearance_similarity = min(appearance_similarity, 1.0 - float(color_delta))

            current_sat = float(np.mean(cv2.cvtColor(current_color, cv2.COLOR_RGB2HSV)[:, :, 1]))
            reference_sat = float(np.mean(cv2.cvtColor(reference_color, cv2.COLOR_RGB2HSV)[:, :, 1]))
            if reference_sat >= 12.0:
                saturation_ratio = current_sat / reference_sat

        slot.last_appearance_similarity = appearance_similarity
        slot.last_brightness_ratio = brightness_ratio
        slot.last_saturation_ratio = saturation_ratio
        return (
            appearance_similarity >= 0.82
            and brightness_ratio >= 0.72
            and saturation_ratio >= 0.55
        )

    def get_remaining_seconds(self, name):
        slot = self.slots.get(name)
        if not slot:
            return 0
        if slot.cooldown_start_time > 0.0:
            return max(0, int(np.ceil(slot.cooldown_duration - (time.time() - slot.cooldown_start_time))))
        return 0

    def get_ocr_remaining_seconds(self, name):
        slot = self.slots.get(name)
        if not slot or not slot.ocr_active or slot.ocr_last_seconds is None:
            return 0
        elapsed = max(0.0, time.monotonic() - slot.ocr_last_confirmed_at)
        return max(0, int(np.ceil(slot.ocr_last_seconds - elapsed)))
            
    def start_detection(self, interval_ms=100):
        self.scan_interval = interval_ms / 1000.0
        if not self.isRunning():
            self.start()
        
    def stop_detection(self):
        self.is_running = False
        self.wait()  # Wait for thread loop to exit safely
        
    def run(self):
        self.is_running = True
        # Create mss instance inside the run loop (QThread local) to avoid cross-thread context issues
        with mss.mss() as sct:
            while self.is_running:
                loop_start = time.time()
                self.scan_all(sct)
                
                # Dynamic sleep calculation to keep precise tick rate
                elapsed = time.time() - loop_start
                sleep_time = max(0.01, self.scan_interval - elapsed)
                time.sleep(sleep_time)
                
    def scan_all(self, sct):
        self._drain_trigger_requests()
        for name, slot in list(self.slots.items()):
            capture_active = name in self._developer_sessions
            if slot.rect is None or (
                slot.template is None and not slot.ocr_enabled and not capture_active
            ):
                continue

            skill_recognition_updated = False
            try:
                if isinstance(slot.rect, QRect):
                    x, y, w, h = slot.rect.x(), slot.rect.y(), slot.rect.width(), slot.rect.height()
                else:
                    x, y, w, h = slot.rect
                
                # Convert logical screen coordinates to physical coordinates for mss based on DPI ratio
                ratio = getattr(slot, "device_ratio", None) or self.device_ratio
                px = int(x * ratio)
                py = int(y * ratio)
                pw = int(w * ratio)
                ph = int(h * ratio)
                
                monitor = {"top": py, "left": px, "width": pw, "height": ph}
                sct_img = sct.grab(monitor)
                
                raw_capture = np.array(sct_img)
                captured_rgb = cv2.cvtColor(raw_capture, cv2.COLOR_BGRA2RGB)
                captured_gray = cv2.cvtColor(raw_capture, cv2.COLOR_BGRA2GRAY)
                now_mono = time.monotonic()
                self._capture_developer_frame(name, captured_rgb, now_mono)

                max_val = slot.last_similarity
                raw_ready = False
                if slot.template is not None:
                    th, tw = slot.template.shape[:2]
                    ch, cw = captured_gray.shape[:2]
                    match_gray = captured_gray if (th == ch and tw == cw) else cv2.resize(captured_gray, (tw, th))
                    res = cv2.matchTemplate(match_gray, slot.template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    slot.last_similarity = max_val
                    appearance_ready = self._ready_appearance_matches(
                        slot, captured_rgb, match_gray
                    )
                else:
                    appearance_ready = False
                
                # 1. Skill recognition OpenCV — the sole Ready/Cooldown authority.
                raw_ready = (
                    slot.template is not None
                    and max_val >= slot.threshold
                    and appearance_ready
                )
                template_ready = self._resolve_skill_recognition(slot, raw_ready)
                skill_recognition_updated = True
                # Commit skill recognition before manual timer bookkeeping.
                if template_ready != slot.is_ready:
                    slot.is_ready = template_ready
                    self.state_changed.emit(name, template_ready, max_val)

                # Manual timer expiry cannot create Ready. Some skills remain
                # unavailable after cooldown until their resource is restored.
                if slot.cooldown_start_time > 0.0:
                    if not raw_ready:
                        slot.cooldown_seen_unready = True
                    if slot._ready_consec_frames >= 3 and slot.cooldown_seen_unready:
                        slot.cooldown_start_time = 0.0
                    else:
                        elapsed = time.time() - slot.cooldown_start_time
                        if elapsed >= slot.cooldown_duration:
                            slot.cooldown_start_time = 0.0

            except Exception:
                if not skill_recognition_updated:
                    failed_ready = self._resolve_skill_recognition(slot, False)
                    if failed_ready != slot.is_ready:
                        slot.is_ready = failed_ready
                        self.state_changed.emit(name, failed_ready, slot.last_similarity)
