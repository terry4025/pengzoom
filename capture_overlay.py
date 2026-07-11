import sys
from PyQt6.QtWidgets import QDialog, QRubberBand, QApplication
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
import mss
import cv2
import numpy as np
import time

class CaptureOverlay(QDialog):
    # Emits (x, y, w, h, template_image_array)
    capture_completed = pyqtSignal(int, int, int, int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        
        # Semi-transparent dark background
        self.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        
        self.origin = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            self.rubberBand.setGeometry(QRect(self.origin, self.origin))
            self.rubberBand.show()
            
    def mouseMoveEvent(self, event):
        if not self.origin.isNull():
            self.rubberBand.setGeometry(QRect(self.origin, event.pos()).normalized())
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.rubberBand.geometry()
            self.rubberBand.hide()
            self.hide() # Hide immediately
            
            QApplication.processEvents() # Wait for UI to update and overlay to disappear
            time.sleep(0.1) # Small sleep to ensure screen is clean before grabbing
            
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            
            if w > 10 and h > 10:
                try:
                    with mss.mss() as sct:
                        monitor = {"top": y, "left": x, "width": w, "height": h}
                        sct_img = sct.grab(monitor)
                        captured_rgb = np.array(sct_img)[:, :, :3]
                        captured_gray = cv2.cvtColor(captured_rgb, cv2.COLOR_RGB2GRAY)
                        
                        self.capture_completed.emit(x, y, w, h, captured_gray)
                except Exception as e:
                    print(f"Capture error: {e}")
            
            self.close()
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
