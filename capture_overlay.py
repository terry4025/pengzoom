import sys
from PyQt6.QtWidgets import QDialog, QApplication
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor
import mss
import cv2
import numpy as np
import time

class CaptureOverlay(QDialog):
    # Emits (x, y, w, h, template_image_array) -> now template is color (RGB np.ndarray)
    capture_completed = pyqtSignal(int, int, int, int, object)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        # Determine total virtual screen geometry
        total_rect = QRect()
        for screen in QApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)
        
        self.start_pos = None
        self.end_pos = None
        self.is_selecting = False

    def paintEvent(self, event):
        painter = QPainter(self)
        # Matches dark transparent background opacity of SelectionOverlay (RGBA 0,0,0,120)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        if self.is_selecting and self.start_pos and self.end_pos:
            start_local = self.mapFromGlobal(self.start_pos)
            end_local = self.mapFromGlobal(self.end_pos)
            rect = QRect(start_local, end_local).normalized()
            
            # Punch a clear hole so target skill icon is fully visible during selection
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            
            # Draw strong 2px border (exactly matches selection_overlay blue QColor(0, 102, 204))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(0, 102, 204), 2))
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.globalPosition().toPoint()
            self.is_selecting = True

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_pos = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.end_pos = event.globalPosition().toPoint()
            self.is_selecting = False
            self.update()
            
            start_local = self.mapFromGlobal(self.start_pos)
            end_local = self.mapFromGlobal(self.end_pos)
            rect = QRect(start_local, end_local).normalized()
            
            self.hide() # Hide overlay immediately before capturing screen
            QApplication.processEvents()
            # Increase delay to 350ms to ensure Windows minimize/hide animations are fully completed
            time.sleep(0.35) 
            
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            
            if w > 5 and h > 5:
                try:
                    # Get device pixel ratio for correct DPI scaling adjustments
                    screen = QApplication.primaryScreen()
                    ratio = screen.devicePixelRatio()
                    
                    # Convert logical coordinates to physical coordinates for mss
                    px = int(x * ratio)
                    py = int(y * ratio)
                    pw = int(w * ratio)
                    ph = int(h * ratio)
                    
                    with mss.mss() as sct:
                        # Grab using physical screen-space coordinates
                        monitor = {"top": py, "left": px, "width": pw, "height": ph}
                        sct_img = sct.grab(monitor)
                        
                        # Convert raw BGRA from mss to standard RGB matrix
                        raw_np = np.array(sct_img)
                        captured_rgb = cv2.cvtColor(raw_np, cv2.COLOR_BGRA2RGB)
                        self.capture_completed.emit(x, y, w, h, captured_rgb)
                except Exception as e:
                    print(f"Capture error: {e}")
            
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
