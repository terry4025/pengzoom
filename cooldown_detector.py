import os
import time
import cv2
import numpy as np
import mss
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal, QRect
from cooldown_ocr import (
    DEFAULT_DIGIT_ROI,
    DEFAULT_PROFILE_ID,
    CooldownOcrEngine,
    OcrDatasetCollector,
    build_profile_from_images,
)

class SkillSlot:
    def __init__(self, name="스킬", rect=None, threshold=0.85, cooldown_duration=0):
        self.name = name
        self.rect = rect  # QRect or tuple (x, y, w, h)
        self.threshold = threshold
        self.template_path = None
        self.is_ready = True  # Current state
        self.last_similarity = 1.0
        self.template = None        # Grayscale matrix for cv2 matchTemplate
        self.template_color = None  # RGB color matrix for UI Preview
        self.cooldown_duration = cooldown_duration
        self.trigger_key = None
        self.cooldown_start_time = 0.0
        self._ready_consec_frames = 0
        self._not_ready_consec_frames = 0
        self.device_ratio = None

        # OCR starts in Shadow mode so existing users can compare it with the
        # manual timer before explicitly promoting a slot to OCR authority.
        self.ocr_enabled = True
        self.ocr_mode = "shadow"  # off | shadow | primary
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
        if mode is not None:
            slot.ocr_mode = mode if mode in ("off", "shadow", "primary") else "shadow"
            slot.ocr_enabled = slot.ocr_mode != "off"
        if profile_id:
            slot.ocr_profile_id = str(profile_id)
        if digit_roi is not None and len(digit_roi) == 4:
            slot.digit_roi = [float(v) for v in digit_roi]
        if device_ratio is not None:
            slot.device_ratio = max(0.5, float(device_ratio))
        if save_diagnostics is not None:
            slot.ocr_save_diagnostics = bool(save_diagnostics)
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
            
    def trigger_cooldown(self, name):
        slot = self.slots.get(name)
        if slot and slot.ocr_mode != "primary":
            slot.cooldown_start_time = time.time()
            slot.is_ready = False
            slot._ready_consec_frames = 0
            slot._not_ready_consec_frames = 3
            self.state_changed.emit(name, False, slot.last_similarity)

    def get_remaining_seconds(self, name):
        slot = self.slots.get(name)
        if not slot:
            return 0
        if slot.ocr_mode == "primary" and slot.ocr_active and slot.ocr_last_seconds is not None:
            elapsed = max(0.0, time.monotonic() - slot.ocr_last_confirmed_at)
            return max(0, int(np.ceil(slot.ocr_last_seconds - elapsed)))
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
        for name, slot in list(self.slots.items()):
            if slot.rect is None or (slot.template is None and not slot.ocr_enabled):
                continue
                
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

                max_val = slot.last_similarity
                raw_ready = False
                if slot.template is not None:
                    th, tw = slot.template.shape[:2]
                    ch, cw = captured_gray.shape[:2]
                    match_gray = captured_gray if (th == ch and tw == cw) else cv2.resize(captured_gray, (tw, th))
                    res = cv2.matchTemplate(match_gray, slot.template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    slot.last_similarity = max_val
                
                # 1. Debounce similarity checks (3 consecutive frames to switch states)
                raw_ready = slot.template is not None and max_val >= slot.threshold
                if raw_ready:
                    slot._ready_consec_frames += 1
                    slot._not_ready_consec_frames = 0
                else:
                    slot._not_ready_consec_frames += 1
                    slot._ready_consec_frames = 0
                    
                debounced_ready = slot.is_ready
                if slot._ready_consec_frames >= 3:
                    debounced_ready = True
                elif slot._not_ready_consec_frames >= 3:
                    debounced_ready = False
                
                new_ready = debounced_ready

                now_mono = time.monotonic()
                if self.collecting_slot_name == name and self.dataset_collector.active:
                    self.dataset_collector.add_frame(captured_rgb, now_mono)

                # OCR is intentionally throttled to 15 FPS even though template
                # matching keeps its 50 ms loop for sub-200 ms Ready detection.
                observation = None
                if slot.ocr_enabled and now_mono + 1e-6 >= slot.ocr_next_scan_at:
                    slot.ocr_last_scan_at = now_mono
                    if slot.ocr_next_scan_at <= 0.0:
                        slot.ocr_next_scan_at = now_mono + self.ocr_interval
                    else:
                        while slot.ocr_next_scan_at <= now_mono:
                            slot.ocr_next_scan_at += self.ocr_interval
                    observation = self.ocr_engine.recognize(
                        name,
                        captured_rgb,
                        slot.ocr_profile_id,
                        slot.digit_roi,
                        now_mono,
                    )
                    if observation.accepted and observation.seconds is not None:
                        slot.ocr_last_seconds = int(observation.seconds)
                        slot.ocr_last_confidence = float(observation.confidence)
                        slot.ocr_last_confirmed_at = now_mono
                        slot.ocr_active = True
                        self.cooldown_observed.emit(name, slot.ocr_last_seconds, slot.ocr_last_confidence)

                    payload = observation.quality_payload()
                    payload["profile_id"] = slot.ocr_profile_id
                    payload["mode"] = slot.ocr_mode
                    payload["remaining"] = self.get_ocr_remaining_seconds(name)
                    payload["collecting"] = self.collecting_slot_name == name
                    payload["frame_count"] = self.dataset_collector.frame_count if payload["collecting"] else 0
                    payload["frame"] = captured_rgb.copy()
                    payload["digit_roi_image"] = observation.digit_roi_image.copy() if observation.digit_roi_image is not None else None
                    payload["binary_image"] = observation.binary_image.copy() if observation.binary_image is not None else None
                    slot.last_ocr_quality = payload
                    slot.last_ocr_frame = payload["frame"]
                    slot.last_ocr_binary = payload["binary_image"]
                    self.ocr_quality.emit(name, payload)
                    self.ocr_engine.logger.save_low_confidence = slot.ocr_save_diagnostics
                    self.ocr_engine.logger.log(
                        name, slot.ocr_profile_id, observation,
                        interpolated=payload["remaining"],
                        frame=captured_rgb if slot.ocr_save_diagnostics else None,
                    )
                
                # 2. Check active timer
                timer_expired = False
                if slot.cooldown_start_time > 0.0:
                    # OpenCV active recognition takes priority: if the current frame matches (raw_ready),
                    # immediately cancel the timer and override to Ready status!
                    if raw_ready:
                        slot.cooldown_start_time = 0.0
                        slot._ready_consec_frames = 3
                        slot._not_ready_consec_frames = 0
                        new_ready = True
                        debounced_ready = True
                    else:
                        elapsed = time.time() - slot.cooldown_start_time
                        if elapsed < slot.cooldown_duration:
                            # Timer is active, force ready state to False
                            new_ready = False
                        else:
                            # Timer expired
                            slot.cooldown_start_time = 0.0
                            timer_expired = True

                # In primary mode the accepted game number is authoritative.
                # The timer above remains only as a Shadow comparison source.
                ocr_ready_confirmed = (
                    slot.ocr_active
                    and slot._ready_consec_frames >= 3
                    and (observation is None or not observation.accepted)
                )
                if ocr_ready_confirmed:
                    slot.ocr_active = False
                    slot.ocr_last_seconds = None
                    slot.ocr_last_confirmed_at = 0.0
                    self.ocr_engine.mark_ready(name)

                if slot.ocr_mode == "primary":
                    if observation is not None and observation.accepted:
                        slot.cooldown_start_time = 0.0
                        new_ready = False
                    elif ocr_ready_confirmed:
                        new_ready = True
                
                # 3. Update state if changed or timer just expired
                if new_ready != slot.is_ready or timer_expired:
                    slot.is_ready = new_ready
                    self.state_changed.emit(name, new_ready, max_val)
                    
            except Exception as exc:
                payload = {"accepted": False, "reject_reason": f"detector_error:{type(exc).__name__}"}
                slot.last_ocr_quality = payload
                self.ocr_quality.emit(name, payload)
