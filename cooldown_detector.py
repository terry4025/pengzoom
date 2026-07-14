import os
import time
import cv2
import numpy as np
import mss
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal, QRect

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

class CooldownDetector(QThread):
    state_changed = pyqtSignal(str, bool, float)  # (skill_name, is_ready, similarity)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slots = {}  # {name: SkillSlot}
        self.is_running = False
        self.scan_interval = 0.05  # Default 50ms
        self.device_ratio = 1.0    # DPI scale ratio (synced from main window)
        
    def add_slot(self, name, rect, threshold=0.85, template_img=None, template_color=None, cooldown_duration=0):
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
            
        self.slots[name] = slot
        
    def remove_slot(self, name):
        if name in self.slots:
            del self.slots[name]
            
    def trigger_cooldown(self, name):
        slot = self.slots.get(name)
        if slot:
            slot.cooldown_start_time = time.time()
            slot.is_ready = False
            slot._ready_consec_frames = 0
            slot._not_ready_consec_frames = 3
            self.state_changed.emit(name, False, slot.last_similarity)
            
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
            if slot.rect is None or slot.template is None:
                continue
                
            try:
                if isinstance(slot.rect, QRect):
                    x, y, w, h = slot.rect.x(), slot.rect.y(), slot.rect.width(), slot.rect.height()
                else:
                    x, y, w, h = slot.rect
                
                # Convert logical screen coordinates to physical coordinates for mss based on DPI ratio
                ratio = self.device_ratio
                px = int(x * ratio)
                py = int(y * ratio)
                pw = int(w * ratio)
                ph = int(h * ratio)
                
                monitor = {"top": py, "left": px, "width": pw, "height": ph}
                sct_img = sct.grab(monitor)
                
                captured_rgb = np.array(sct_img)[:, :, :3]
                captured_gray = cv2.cvtColor(captured_rgb, cv2.COLOR_RGB2GRAY)
                
                th, tw = slot.template.shape[:2]
                ch, cw = captured_gray.shape[:2]
                
                if th != ch or tw != cw:
                    captured_gray = cv2.resize(captured_gray, (tw, th))
                
                res = cv2.matchTemplate(captured_gray, slot.template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                
                slot.last_similarity = max_val
                
                # 1. Debounce similarity checks (3 consecutive frames to switch states)
                raw_ready = max_val >= slot.threshold
                if raw_ready:
                    slot._ready_consec_frames += 1
                    slot._not_ready_consec_frames = 0
                else:
                    slot._not_ready_consec_frames += 1
                    slot._ready_consec_frames = 0
                    
                new_ready = slot.is_ready
                if slot._ready_consec_frames >= 3:
                    new_ready = True
                elif slot._not_ready_consec_frames >= 3:
                    new_ready = False
                
                # 2. Check active timer
                timer_expired = False
                if slot.cooldown_start_time > 0.0:
                    elapsed = time.time() - slot.cooldown_start_time
                    if elapsed < slot.cooldown_duration:
                        # Timer is active, force ready state to False
                        new_ready = False
                    else:
                        # Timer expired
                        slot.cooldown_start_time = 0.0
                        timer_expired = True
                
                # 3. Update state if changed or timer just expired
                if new_ready != slot.is_ready or timer_expired:
                    slot.is_ready = new_ready
                    self.state_changed.emit(name, new_ready, max_val)
                    
            except Exception:
                pass
