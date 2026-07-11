import sys
import mss
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFrame, QPushButton, QSlider, 
                             QDialog, QSizeGrip, QSizePolicy)
from PyQt6.QtCore import QTimer, Qt, QPoint, QRect, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap, QCursor, QPainter, QPen, QColor
from PIL import Image
from pynput import mouse, keyboard

class InputBridge(QObject):
    zoom_changed = pyqtSignal(int)
    toggle_follow = pyqtSignal()
    toggle_click_through = pyqtSignal()
    hotkey_set = pyqtSignal(str)

class HelpModal(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("도움말")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setStyleSheet("""
            #ModalContainer {
                background-color: rgba(28, 28, 30, 0.95);
                border: 1.5px solid rgba(255, 255, 255, 0.15);
                border-radius: 16px;
            }
            QLabel {
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0071e3;
            }
            QPushButton:pressed {
                transform: scale(0.96);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setObjectName("ModalContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(16)
        
        title_label = QLabel("🐧 펭구 줌인 Pro 사용 가이드")
        title_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #ffffff;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title_label)
        
        content_label = QLabel(
            "🍎 <b>주요 단축키 및 조작법</b><br><br>"
            "1. <b>확대/축소</b>: <span style='color: #0088ff;'>Ctrl + 마우스 휠</span><br>"
            "2. <b>따라오기 토글</b>: <span style='color: #0088ff;'>Ctrl + 휠 클릭</span> (또는 지정된 키)<br>"
            "3. <b>영역 지정</b>: [영역 지정] 클릭 후 화면 드래그<br>"
            "4. <b>투명도 설정</b>: 하단 투명도 슬라이더 사용 (15% ~ 100%)<br>"
            "5. <b>마우스 투과 토글</b>: <span style='color: #0088ff;'>Ctrl + Alt + T</span><br>"
            "   <i>※ 투과 모드가 켜지면 마우스 클릭이 창을 통과해 뒤쪽 게임을 조작할 수 있습니다. 다시 일반 모드로 돌아오려면 단축키를 누르세요.</i><br>"
            "6. <b>프로그램 종료</b>: ✕ 버튼 또는 ESC 키"
        )
        content_label.setStyleSheet("font-size: 13px; line-height: 1.5; color: #cccccc;")
        content_label.setWordWrap(True)
        container_layout.addWidget(content_label)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("확인")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        container_layout.addLayout(btn_layout)
        
        layout.addWidget(container)
        self.resize(340, 380)
        self.old_pos = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
            
    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
            
    def mouseReleaseEvent(self, event):
        self.old_pos = None

class SelectionOverlay(QWidget):
    areaSelected = pyqtSignal(QRect)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
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
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        if self.is_selecting and self.start_pos and self.end_pos:
            start_local = self.mapFromGlobal(self.start_pos)
            end_local = self.mapFromGlobal(self.end_pos)
            rect = QRect(start_local, end_local).normalized()
            
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            
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
                background-color: rgba(28, 28, 30, 0.90);
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 18px;
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
        self.setWindowTitle('펭구 줌인 Pro v2.0')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.zoom_factor = 2.0
        self.follow_mouse = True
        self.click_through = False
        self.last_capture_pos = QPoint(0, 0)
        self.custom_hotkey = None
        self.is_setting_hotkey = False
        
        self.bridge = InputBridge()
        self.bridge.zoom_changed.connect(self.handle_global_zoom)
        self.bridge.toggle_follow.connect(self.toggle_follow)
        self.bridge.toggle_click_through.connect(self.toggle_click_through)
        self.bridge.hotkey_set.connect(self.on_hotkey_set)
        
        self.ctrl_pressed = False
        self.alt_pressed = False
        
        self.mouse_listener = mouse.Listener(on_click=self.on_global_click, on_scroll=self.on_global_scroll)
        self.key_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener.start()
        self.key_listener.start()
        
        self.setup_ui()
        
        self.sct = mss.mss()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_magnifier)
        self.timer.start(16)
        
        self.resize(420, 540)
        self.old_pos = None

    def setup_ui(self):
        self.container = ResizableContainer()
        self.setCentralWidget(self.container)
        
        # Stylize UI components using Apple design tokens
        self.setStyleSheet("""
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                color: #ffffff;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 14px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.16);
            }
            QPushButton:pressed {
                transform: scale(0.96);
            }
            QPushButton.PrimaryActive {
                background-color: #0066cc;
                border: 1px solid #0071e3;
            }
            QPushButton.PrimaryActive:hover {
                background-color: #0071e3;
            }
            QPushButton#CloseBtn {
                background-color: rgba(255, 69, 58, 0.2);
                color: #ff453a;
                border: 1px solid rgba(255, 69, 58, 0.3);
                border-radius: 12px;
                font-size: 11px;
            }
            QPushButton#CloseBtn:hover {
                background-color: rgba(255, 69, 58, 0.35);
            }
            QPushButton#HelpBtn {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                font-size: 12px;
            }
            QPushButton#HelpBtn:hover {
                background-color: rgba(255, 255, 255, 0.16);
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #0066cc;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 14px;
                height: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QLabel {
                font-size: 13px;
                background: transparent;
            }
        """)
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)
        
        # Title/Controls Bar
        self.title_layout = QHBoxLayout()
        self.title_layout.setSpacing(8)
        
        self.select_btn = QPushButton('영역 지정')
        self.select_btn.clicked.connect(self.start_selection)
        self.title_layout.addWidget(self.select_btn)
        
        self.follow_btn = QPushButton('따라오기: 켬')
        self.follow_btn.setProperty("class", "PrimaryActive")
        self.follow_btn.clicked.connect(self.toggle_follow)
        self.title_layout.addWidget(self.follow_btn)
        
        self.title_layout.addStretch()
        
        self.help_btn = QPushButton('?')
        self.help_btn.setObjectName('HelpBtn')
        self.help_btn.setFixedSize(24, 24)
        self.help_btn.clicked.connect(self.show_help)
        self.title_layout.addWidget(self.help_btn)
        
        self.close_btn = QPushButton('✕')
        self.close_btn.setObjectName('CloseBtn')
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.close)
        self.title_layout.addWidget(self.close_btn)
        
        self.main_layout.addLayout(self.title_layout)
        
        # Row for Click-Through Toggle and Hotkey Setting
        self.config_layout = QHBoxLayout()
        self.config_layout.setSpacing(8)
        
        self.click_through_btn = QPushButton('마우스 투과: 끔')
        self.click_through_btn.clicked.connect(self.toggle_click_through)
        self.config_layout.addWidget(self.click_through_btn)
        
        self.hotkey_btn = QPushButton('따라오기 단축키 변경 (Ctrl+휠클릭)')
        self.hotkey_btn.clicked.connect(self.start_setting_hotkey)
        self.config_layout.addWidget(self.hotkey_btn)
        
        self.main_layout.addLayout(self.config_layout)
        
        # Live Magnifier Display Screen
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet('border-radius: 12px; background-color: #000000; border: 1px solid rgba(255, 255, 255, 0.1);')
        self.label.setMinimumSize(100, 100)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(self.label)
        
        # Controls Group Layout (Zoom & Opacity Sliders)
        self.sliders_layout = QVBoxLayout()
        self.sliders_layout.setSpacing(10)
        
        # Zoom Factor Slider Control
        self.zoom_layout = QHBoxLayout()
        zoom_title = QLabel('배율:')
        zoom_title.setFixedWidth(50)
        self.zoom_layout.addWidget(zoom_title)
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 200)  # Support 1.0x to 20.0x
        self.zoom_slider.setValue(20)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
        self.zoom_layout.addWidget(self.zoom_slider)
        
        self.zoom_val_label = QLabel('2.0x')
        self.zoom_val_label.setFixedWidth(40)
        self.zoom_val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.zoom_layout.addWidget(self.zoom_val_label)
        self.sliders_layout.addLayout(self.zoom_layout)
        
        # Opacity Slider Control
        self.opacity_layout = QHBoxLayout()
        opacity_title = QLabel('투명도:')
        opacity_title.setFixedWidth(50)
        self.opacity_layout.addWidget(opacity_title)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(15, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.on_opacity_slider_changed)
        self.opacity_layout.addWidget(self.opacity_slider)
        
        self.opacity_val_label = QLabel('100%')
        self.opacity_val_label.setFixedWidth(40)
        self.opacity_val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.opacity_layout.addWidget(self.opacity_val_label)
        self.sliders_layout.addLayout(self.opacity_layout)
        
        self.main_layout.addLayout(self.sliders_layout)

    def start_setting_hotkey(self):
        self.is_setting_hotkey = True
        self.hotkey_btn.setText('키 입력 대기 중 (Ctrl+F1 등)...')
        self.hotkey_btn.setStyleSheet('background-color: rgba(255, 214, 10, 0.2); color: #ffd60a; border: 1px solid rgba(255, 214, 10, 0.4);')

    def on_hotkey_set(self, key_name):
        self.custom_hotkey = key_name
        self.hotkey_btn.setText(f'단축키: {key_name}')
        self.hotkey_btn.setStyleSheet('')
        self.is_setting_hotkey = False

    def on_key_press(self, key):
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            self.ctrl_pressed = True
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = True
            
        try:
            if hasattr(key, 'char') and key.char:
                current_key_name = key.char.lower()
            else:
                current_key_name = str(key).replace('Key.', '')
        except Exception:
            current_key_name = str(key)
            
        # Toggle click through globally on Ctrl+Alt+T
        if current_key_name == 't' and self.ctrl_pressed and self.alt_pressed:
            self.bridge.toggle_click_through.emit()
            return

        if self.is_setting_hotkey:
            if current_key_name in ['ctrl_l', 'ctrl_r', 'alt_l', 'alt_r', 'shift', 'shift_r', 'cmd']:
                return
            combo = []
            if self.ctrl_pressed:
                combo.append('Ctrl')
            if self.alt_pressed:
                combo.append('Alt')
            combo.append(current_key_name.upper())
            final_hotkey = '+'.join(combo)
            self.bridge.hotkey_set.emit(final_hotkey)
            return
            
        if self.custom_hotkey:
            parts = self.custom_hotkey.split('+')
            target_key = parts[-1].lower()
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
        modal = HelpModal(self)
        modal.exec()

    def start_selection(self):
        self.overlay = SelectionOverlay()
        self.overlay.areaSelected.connect(self.on_area_selected)
        self.overlay.show()

    def on_area_selected(self, rect):
        self.follow_mouse = False
        self.follow_btn.setText('따라오기: 끔')
        self.follow_btn.setProperty("class", "")
        self.follow_btn.style().unpolish(self.follow_btn)
        self.follow_btn.style().polish(self.follow_btn)
        self.last_capture_pos = rect.center()
        
        zw = self.label.width() / rect.width()
        zh = self.label.height() / rect.height()
        new_zoom = min(zw, zh)
        
        self.zoom_factor = max(1.0, min(20.0, new_zoom))
        self.zoom_slider.setValue(int(self.zoom_factor * 10))

    def toggle_follow(self):
        self.follow_mouse = not self.follow_mouse
        if self.follow_mouse:
            self.follow_btn.setText('따라오기: 켬')
            self.follow_btn.setProperty("class", "PrimaryActive")
            self.last_capture_pos = QCursor.pos()
        else:
            self.follow_btn.setText('따라오기: 끔')
            self.follow_btn.setProperty("class", "")
            
        self.follow_btn.style().unpolish(self.follow_btn)
        self.follow_btn.style().polish(self.follow_btn)

    def toggle_click_through(self):
        self.click_through = not self.click_through
        if self.click_through:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            self.click_through_btn.setText('마우스 투과: 켬')
            self.click_through_btn.setProperty("class", "PrimaryActive")
        else:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
            self.click_through_btn.setText('마우스 투과: 끔')
            self.click_through_btn.setProperty("class", "")
            
        self.click_through_btn.style().unpolish(self.click_through_btn)
        self.click_through_btn.style().polish(self.click_through_btn)
        self.show()

    def on_zoom_slider_changed(self, value):
        self.zoom_factor = value / 10.0
        self.zoom_val_label.setText(f'{self.zoom_factor:.1f}x')

    def on_opacity_slider_changed(self, value):
        opacity = value / 100.0
        self.setWindowOpacity(opacity)
        self.opacity_val_label.setText(f'{value}%')

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
            
            if self.follow_mouse:
                painter = QPainter(pixmap)
                painter.setPen(QPen(QColor(255, 69, 58, 200), 1))  # SF Red color crosshair
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
            # Prevent dragging if input transparent is on or if clicking size grip
            if self.click_through:
                return
            if self.container.grip.geometry().contains(event.pos()):
                return
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None and not self.click_through:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.mouse_listener.stop()
        self.key_listener.stop()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MagnifierWindow()
    window.show()
    sys.exit(app.exec())
