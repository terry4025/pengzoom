import sys
import mss
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFrame, QPushButton, QSlider, 
                             QMessageBox, QSizeGrip, QSizePolicy)
from PyQt6.QtCore import QTimer, Qt, QPoint, QRect, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap, QCursor, QPainter, QPen, QColor
from PIL import Image
from pynput import mouse, keyboard

class InputBridge(QObject):
    zoom_changed = pyqtSignal(int)
    toggle_follow = pyqtSignal()
    hotkey_set = pyqtSignal(str)

class SelectionOverlay(QWidget):
    areaSelected = pyqtSignal(QRect)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        # Calculate united geometry for all screens (Dual monitor support)
        total_rect = QRect()
        for screen in QApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)
        self.show()
        
        self.start_pos = None
        self.end_pos = None
        self.is_selecting = False

    def paintEvent(self, event):
        painter = QPainter(self)
        # Fill window with semi-transparent black overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if self.is_selecting and self.start_pos and self.end_pos:
            start_local = self.mapFromGlobal(self.start_pos)
            end_local = self.mapFromGlobal(self.end_pos)
            rect = QRect(start_local, end_local).normalized()
            
            # Clear the selected area to transparent
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            
            # Draw blueish border
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(0, 120, 215), 2))
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
            rect = QRect(self.start_pos, self.end_pos).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.areaSelected.emit(rect)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

class ResizableContainer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContainer")
        self.setStyleSheet("""
            #MainContainer {
                background-color: #1e1e1e;
                border: 2px solid #3d3d3d;
                border-radius: 15px;
            }
        """)
        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background-color: transparent; width: 20px; height: 20px;")

    def resizeEvent(self, event):
        rect = self.rect()
        self.grip.move(rect.right() - 20, rect.bottom() - 20)
        super().resizeEvent(event)

class MagnifierWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Pengu Zoom Pro')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.zoom_factor = 2.0
        self.follow_mouse = True
        self.last_capture_pos = QPoint(0, 0)
        self.custom_hotkey = None
        self.is_setting_hotkey = False
        
        self.bridge = InputBridge()
        self.bridge.zoom_changed.connect(self.handle_global_zoom)
        self.bridge.toggle_follow.connect(self.toggle_follow)
        self.bridge.hotkey_set.connect(self.on_hotkey_set)
        
        self.ctrl_pressed = False
        self.alt_pressed = False
        
        # Start global input listeners using pynput
        self.mouse_listener = mouse.Listener(on_click=self.on_global_click, on_scroll=self.on_global_scroll)
        self.key_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener.start()
        self.key_listener.start()
        
        self.setup_ui()
        
        self.sct = mss.mss()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_magnifier)
        self.timer.start(16)
        
        self.resize(450, 520)
        self.old_pos = None

    def setup_ui(self):
        self.container = ResizableContainer()
        self.setCentralWidget(self.container)
        
        self.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QPushButton#CloseBtn {
                background-color: #c42b1c;
            }
            QPushButton#CloseBtn:hover {
                background-color: #e81123;
            }
            QPushButton#HelpBtn {
                background-color: #0078d7;
            }
            QPushButton#HelpBtn:hover {
                background-color: #0086f1;
            }
            QPushButton#HotkeyBtn {
                background-color: #555;
                border: 1px solid #777;
            }
            QLabel {
                color: white;
            }
        """)
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title/Controls Bar
        self.title_layout = QHBoxLayout()
        
        self.select_btn = QPushButton('Select Area')
        self.select_btn.clicked.connect(self.start_selection)
        self.title_layout.addWidget(self.select_btn)
        
        self.follow_btn = QPushButton('Follow: ON')
        self.follow_btn.clicked.connect(self.toggle_follow)
        self.title_layout.addWidget(self.follow_btn)
        
        self.title_layout.addStretch()
        
        self.help_btn = QPushButton('?')
        self.help_btn.setObjectName('HelpBtn')
        self.help_btn.setFixedSize(25, 25)
        self.help_btn.clicked.connect(self.show_help)
        self.title_layout.addWidget(self.help_btn)
        
        self.close_btn = QPushButton('✕')
        self.close_btn.setObjectName('CloseBtn')
        self.close_btn.setFixedSize(25, 25)
        self.close_btn.clicked.connect(self.close)
        self.title_layout.addWidget(self.close_btn)
        
        self.main_layout.addLayout(self.title_layout)
        
        # Hotkey Configuration Row
        self.hotkey_layout = QHBoxLayout()
        self.hotkey_btn = QPushButton('Set Follow Hotkey (Default: Ctrl+MiddleClick)')
        self.hotkey_btn.setObjectName('HotkeyBtn')
        self.hotkey_btn.clicked.connect(self.start_setting_hotkey)
        self.hotkey_layout.addWidget(self.hotkey_btn)
        self.main_layout.addLayout(self.hotkey_layout)
        
        # Live Magnifier Display Screen
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet('border-radius: 10px; background-color: black; border: 1px solid #333;')
        self.label.setMinimumSize(100, 100)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(self.label)
        
        # Zoom Factor Slider Control
        self.zoom_layout = QHBoxLayout()
        self.zoom_layout.addWidget(QLabel('Zoom:'))
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 100)
        self.zoom_slider.setValue(20)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
        self.zoom_layout.addWidget(self.zoom_slider)
        
        self.zoom_val_label = QLabel('2.0x')
        self.zoom_layout.addWidget(self.zoom_val_label)
        
        self.main_layout.addLayout(self.zoom_layout)

    def start_setting_hotkey(self):
        self.is_setting_hotkey = True
        self.hotkey_btn.setText('Press combination (e.g. Ctrl+F1)...')
        self.hotkey_btn.setStyleSheet('background-color: #d7a000; color: black;')

    def on_hotkey_set(self, key_name):
        self.custom_hotkey = key_name
        self.hotkey_btn.setText(f'Hotkey: {key_name}')
        self.hotkey_btn.setStyleSheet('')
        self.is_setting_hotkey = False

    def on_key_press(self, key):
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            self.ctrl_pressed = True
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = True
            
        try:
            if hasattr(key, 'char') and key.char:
                current_key_name = key.char
            else:
                current_key_name = str(key).replace('Key.', '')
        except Exception:
            current_key_name = str(key)
            
        if self.is_setting_hotkey:
            if current_key_name in ['ctrl_l', 'ctrl_r', 'alt_l', 'alt_r', 'shift', 'shift_r', 'cmd']:
                return
            combo = []
            if self.ctrl_pressed:
                combo.append('Ctrl')
            if self.alt_pressed:
                combo.append('Alt')
            combo.append(current_key_name)
            final_hotkey = '+'.join(combo)
            self.bridge.hotkey_set.emit(final_hotkey)
            return
            
        if self.custom_hotkey:
            parts = self.custom_hotkey.split('+')
            target_key = parts[-1]
            req_ctrl = 'Ctrl' in parts
            req_alt = 'Alt' in parts
            if current_key_name == target_key and self.ctrl_pressed == req_ctrl and self.alt_pressed == req_alt:
                self.bridge.toggle_follow.emit()

    def on_key_release(self, key):
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            self.ctrl_pressed = False
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = False

    def on_global_scroll(self, x, y, dx, dy):
        if self.ctrl_pressed:
            self.bridge.zoom_changed.emit(1 if dy > 0 else -1)

    def on_global_click(self, x, y, button, pressed):
        if not pressed:
            return
        if self.custom_hotkey is None:
            if button == mouse.Button.middle and self.ctrl_pressed:
                self.bridge.toggle_follow.emit()

    def handle_global_zoom(self, direction):
        if direction > 0:
            self.zoom_factor = min(20.0, self.zoom_factor + 0.5)
        else:
            self.zoom_factor = max(1.0, self.zoom_factor - 0.5)
        self.zoom_slider.setValue(int(self.zoom_factor * 10))

    def show_help(self):
        msg = QMessageBox(self)
        msg.setWindowTitle('펭쿠짱을 위한 사용방법')
        msg.setText('')
        msg.setInformativeText(
            "1. 확대/축소: Ctrl + 마우스 휠\n"
            "2. 따라오기 토글: 기본(Ctrl+휠클릭) 또는 설정한 단축키\n"
            "3. 영역 선택: Select Area 버튼 (듀얼모니터 지원)\n"
            "4. 단축키 설정: 버튼 클릭 후 'Ctrl+F1' 처럼 입력\n"
            "5. 창 크기 조절: 우측 하단 모서리 드래그\n"
            "6. 종료: ✕ 버튼 또는 ESC"
        )
        msg.setStyleSheet('QLabel{ color: black; }')
        msg.exec()

    def start_selection(self):
        self.overlay = SelectionOverlay()
        self.overlay.areaSelected.connect(self.on_area_selected)
        self.overlay.show()

    def on_area_selected(self, rect):
        self.follow_mouse = False
        self.follow_btn.setText('Follow: OFF')
        self.last_capture_pos = rect.center()
        
        zw = self.label.width() / rect.width()
        zh = self.label.height() / rect.height()
        new_zoom = min(zw, zh)
        
        self.zoom_factor = max(1.0, min(20.0, new_zoom))
        self.zoom_slider.setValue(int(self.zoom_factor * 10))

    def toggle_follow(self):
        self.follow_mouse = not self.follow_mouse
        self.follow_btn.setText(f'Follow: {"ON" if self.follow_mouse else "OFF"}')
        if self.follow_mouse:
            self.last_capture_pos = QCursor.pos()

    def on_zoom_slider_changed(self, value):
        self.zoom_factor = value / 10.0
        self.zoom_val_label.setText(f'{self.zoom_factor:.1f}x')

    def update_magnifier(self):
        try:
            if self.follow_mouse:
                cursor_pos = QCursor.pos()
                self.last_capture_pos = cursor_pos
                
            x = self.last_capture_pos.x()
            y = self.last_capture_pos.y()
            view_w = self.label.width()
            view_h = self.label.height()
            
            if view_w <= 0 or view_h <= 0:
                return
                
            cap_w = int(view_w / self.zoom_factor)
            cap_h = int(view_h / self.zoom_factor)
            
            monitor = {
                'top': y - cap_h // 2, 
                'left': x - cap_w // 2, 
                'width': cap_w, 
                'height': cap_h
            }
            
            sct_img = self.sct.grab(monitor)
            img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
            img = img.resize((view_w, view_h), Image.Resampling.NEAREST)
            img = img.convert('RGBA')
            data = img.tobytes('raw', 'RGBA')
            
            qimg = QImage(data, view_w, view_h, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)
            
            # Draw cursor crosshair if follow mode is active
            if self.follow_mouse:
                painter = QPainter(pixmap)
                painter.setPen(QPen(QColor(255, 0, 0, 180), 1))
                cx = view_w // 2
                cy = view_h // 2
                painter.drawLine(cx - 15, cy, cx + 15, cy)
                painter.drawLine(cx, cy - 15, cx, cy + 15)
                painter.end()
                
            self.label.setPixmap(pixmap)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Prevent window dragging when clicking the size grip
            if self.container.grip.geometry().contains(event.pos()):
                return
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        # Cleanly stop pynput listeners to avoid hangs
        self.mouse_listener.stop()
        self.key_listener.stop()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MagnifierWindow()
    window.show()
    sys.exit(app.exec())
