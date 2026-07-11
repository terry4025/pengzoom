import os
import cv2
import numpy as np
import mss
from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRect

class SkillSlot:
    def __init__(self, name="스킬", rect=None, threshold=0.85):
        self.name = name
        self.rect = rect  # QRect or tuple (x, y, w, h)
        self.threshold = threshold
        self.template_path = None
        self.is_ready = True  # Current state
        self.last_similarity = 1.0

class CooldownDetector(QObject):
    state_changed = pyqtSignal(str, bool, float)  # (skill_name, is_ready, similarity)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slots = {}  # {name: SkillSlot}
        self.sct = mss.mss()
        self.timer = QTimer()
        self.timer.timeout.connect(self.scan_all)
        self.scan_interval = 200  # ms
        
    def add_slot(self, name, rect, threshold=0.85, template_img=None):
        slot = SkillSlot(name, rect, threshold)
        if template_img is not None:
            # Convert PIL Image or numpy array to grayscale for matchTemplate
            if isinstance(template_img, Image.Image):
                img_np = np.array(template_img.convert('RGB'))
                slot.template = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            elif isinstance(template_img, np.ndarray):
                if len(template_img.shape) == 3:
                    slot.template = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
                else:
                    slot.template = template_img
            else:
                slot.template = template_img
        else:
            slot.template = None
            
        self.slots[name] = slot
        
    def remove_slot(self, name):
        if name in self.slots:
            del self.slots[name]
            
    def start(self, interval=200):
        self.scan_interval = interval
        self.timer.start(self.scan_interval)
        
    def stop(self):
        self.timer.stop()
        
    def scan_all(self):
        for name, slot in self.slots.items():
            if slot.rect is None or slot.template is None:
                continue
                
            try:
                # Capture target rect
                # slot.rect can be QRect or (x, y, w, h)
                if isinstance(slot.rect, QRect):
                    x, y, w, h = slot.rect.x(), slot.rect.y(), slot.rect.width(), slot.rect.height()
                else:
                    x, y, w, h = slot.rect
                    
                monitor = {"top": y, "left": x, "width": w, "height": h}
                sct_img = self.sct.grab(monitor)
                
                # Convert grab to grayscale numpy array
                captured_rgb = np.array(sct_img)[:, :, :3]  # drop alpha channel
                captured_gray = cv2.cvtColor(captured_rgb, cv2.COLOR_RGB2GRAY)
                
                # Check template dimensions match captured dimensions
                # In template matching, template size must be <= search image size
                # Usually they should match exactly since we capture the exact same rect
                th, tw = slot.template.shape[:2]
                ch, cw = captured_gray.shape[:2]
                
                # Resize if sizes are slightly different to ensure template match executes smoothly
                if th != ch or tw != cw:
                    captured_gray = cv2.resize(captured_gray, (tw, th))
                
                # Run template matching (Normalized Cross-Correlation)
                res = cv2.matchTemplate(captured_gray, slot.template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                
                slot.last_similarity = max_val
                
                # Determine state transitions (Edge Triggering)
                new_ready = max_val >= slot.threshold
                if new_ready != slot.is_ready:
                    slot.is_ready = new_ready
                    self.state_changed.emit(name, new_ready, max_val)
                    
            except Exception as e:
                # Silently catch grab issues if dimensions or positions are invalid during setup
                pass
