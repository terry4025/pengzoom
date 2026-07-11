import sys
import os
import json
import mss
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFrame, QPushButton, QSlider, 
                             QDialog, QSizeGrip, QSizePolicy, QGridLayout)
from PyQt6.QtCore import QTimer, Qt, QPoint, QRect, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap, QCursor, QPainter, QPen, QColor, QIcon, QKeySequence
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
from PIL import Image
from pynput import mouse, keyboard

# Set explicit AppUserModelID on Windows to fix Taskbar Icon grouping and display issues
import ctypes
try:
    myappid = 'terry4025.pengzoom.magnifier.2.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# Windows API constants for win32 window modification
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

# Lucide Icons SVG Data with precise color mapping and strong stroke widths
LUCIDE_MINIMIZE_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffd60a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-minus">
  <path d="M5 12h14"/>
</svg>
"""

LUCIDE_SETTINGS_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#30d158" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-settings">
  <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
  <circle cx="12" cy="12" r="3"/>
</svg>
"""

LUCIDE_HELP_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0a84ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-help-circle">
  <circle cx="12" cy="12" r="10"/>
  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
  <line x1="12" y1="17" x2="12.01" y2="17"/>
</svg>
"""

LUCIDE_CLOSE_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ff453a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-x">
  <line x1="18" y1="6" x2="6" y2="18"/>
  <line x1="6" y1="6" x2="18" y2="18"/>
</svg>
"""

# Custom Lucide-styled Penguin SVG design (stroke-width: 2.3, color: #0a84ff)
LUCIDE_PENGUIN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0a84ff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-penguin">
  <path d="M12 2a4 4 0 0 0-4 4v3a6 6 0 0 0 12 0V6a4 4 0 0 0-4-4z"/>
  <path d="M12 8a2.5 2.5 0 0 0-2.5 2.5v3.5a2.5 2.5 0 0 0 5 0v-3.5A2.5 2.5 0 0 0 12 8z"/>
  <path d="M6 10c-1 1-1.5 2.5-1 4 .5 1.5 2 2 3 1.5"/>
  <path d="M18 10c1 1 1.5 2.5 1 4-.5 1.5-2 2-3 1.5"/>
  <path d="M11 6.5l1 1 1-1-1-.5z" fill="#0a84ff"/>
  <path d="M9 20l-1 2h3l-1-2"/>
  <path d="M15 20l1 2h-3l1-2"/>
</svg>
"""

def get_icon_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, "icon2.ico")
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    local_path = os.path.join(exe_dir, "icon2.ico")
    if os.path.exists(local_path):
        return local_path
    if os.path.exists("icon2.ico"):
        return "icon2.ico"
    return ""

def get_svg_icon(svg_str):
    try:
        renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon()

# Win32 helper to force system taskbar icon updates via SendMessageW using toWinHICON
def force_set_window_icon(hwnd, icon_path):
    if not os.path.exists(icon_path):
        return
    try:
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            hicon = pixmap.toWinHICON()
            if hicon:
                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ICON_BIG = 1
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, int(hicon))
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, int(hicon))
    except Exception:
        pass

class InputBridge(QObject):
    zoom_changed = pyqtSignal(int)
    toggle_follow = pyqtSignal()
    toggle_click_through = pyqtSignal()
    toggle_hide = pyqtSignal()

class SettingsModal(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setWindowTitle("설정")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.is_setting_target = None
        
        # Load temporary values from parent window
        self.temp_follow = parent_window.hotkey_follow
        self.temp_transparent = parent_window.hotkey_transparent
        self.temp_hide = parent_window.hotkey_hide
        
        self.setStyleSheet("""
            #ModalContainer {
                background-color: rgba(28, 28, 30, 0.96);
                border: 1.5px solid rgba(255, 255, 255, 0.15);
                border-radius: 16px;
            }
            QLabel {
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.16);
            }
            QPushButton#SaveBtn {
                background-color: #0066cc;
                border: none;
                font-weight: 600;
            }
            QPushButton#SaveBtn:hover {
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
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(14)
        
        # Lucide Settings Icon next to clean title label text (Replaces unicode emoji gear)
        title_layout_row = QHBoxLayout()
        title_layout_row.setSpacing(8)
        title_layout_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_icon = QLabel()
        title_icon.setFixedSize(20, 20)
        title_icon.setPixmap(get_svg_icon(LUCIDE_SETTINGS_SVG).pixmap(20, 20))
        
        title_label = QLabel("펭구 줌인 설정")
        title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        
        title_layout_row.addWidget(title_icon)
        title_layout_row.addWidget(title_label)
        container_layout.addLayout(title_layout_row)
        
        # Grid layout for hotkey configurations
        grid = QGridLayout()
        grid.setSpacing(10)
        
        # 1. Follow Mouse Hotkey
        lbl_follow = QLabel("마우스 따라오기:")
        lbl_follow.setStyleSheet("font-size: 13px; color: #cccccc;")
        self.btn_follow = QPushButton(self.get_display_text(self.temp_follow, "Ctrl+MiddleClick"))
        self.btn_follow.clicked.connect(lambda: self.start_setting("follow", self.btn_follow))
        grid.addWidget(lbl_follow, 0, 0)
        grid.addWidget(self.btn_follow, 0, 1)
        
        # 2. Transparent (Click-through) Hotkey
        lbl_trans = QLabel("마우스 투과 토글:")
        lbl_trans.setStyleSheet("font-size: 13px; color: #cccccc;")
        self.btn_transparent = QPushButton(self.get_display_text(self.temp_transparent, "Ctrl+Alt+T"))
        self.btn_transparent.clicked.connect(lambda: self.start_setting("transparent", self.btn_transparent))
        grid.addWidget(lbl_trans, 1, 0)
        grid.addWidget(self.btn_transparent, 1, 1)
        
        # 3. Minimize Window Hotkey
        lbl_hide = QLabel("최소화(가리기) 토글:")
        lbl_hide.setStyleSheet("font-size: 13px; color: #cccccc;")
        self.btn_hide = QPushButton(self.get_display_text(self.temp_hide, "Ctrl+Alt+H"))
        self.btn_hide.clicked.connect(lambda: self.start_setting("hide", self.btn_hide))
        grid.addWidget(lbl_hide, 2, 0)
        grid.addWidget(self.btn_hide, 2, 1)
        
        container_layout.addLayout(grid)
        
        # Info label
        info_label = QLabel("※ 변경할 버튼을 클릭한 뒤, 키보드 단축키 조합을 입력하십시오. ESC를 누르면 단축키를 해제하고 마우스 기본 휠 클릭으로 리셋합니다.")
        info_label.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.45); line-height: 1.4;")
        info_label.setWordWrap(True)
        container_layout.addWidget(info_label)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.reset_btn = QPushButton("기본값 초기화")
        self.reset_btn.clicked.connect(self.reset_all)
        btn_layout.addWidget(self.reset_btn)
        
        self.save_btn = QPushButton("확인")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(self.save_btn)
        
        container_layout.addLayout(btn_layout)
        layout.addWidget(container)
        
        self.resize(350, 260)
        self.old_pos = None

    def get_display_text(self, value, default_text):
        return value if value else default_text

    def start_setting(self, target, button):
        self.is_setting_target = target
        self.btn_follow.setStyleSheet("")
        self.btn_transparent.setStyleSheet("")
        self.btn_hide.setStyleSheet("")
        
        button.setText("키 입력 대기 중...")
        button.setStyleSheet("background-color: rgba(255, 214, 10, 0.2); color: #ffd60a; border: 1px solid rgba(255, 214, 10, 0.4);")

    def reset_all(self):
        self.temp_follow = None
        self.temp_transparent = "Ctrl+Alt+T"
        self.temp_hide = "Ctrl+Alt+H"
        
        self.btn_follow.setText("Ctrl+MiddleClick")
        self.btn_transparent.setText("Ctrl+Alt+T")
        self.btn_hide.setText("Ctrl+Alt+H")
        
        self.btn_follow.setStyleSheet("")
        self.btn_transparent.setStyleSheet("")
        self.btn_hide.setStyleSheet("")
        self.is_setting_target = None

    def save_and_close(self):
        self.parent_window.hotkey_follow = self.temp_follow
        self.parent_window.hotkey_transparent = self.temp_transparent
        self.parent_window.hotkey_hide = self.temp_hide
        self.accept()

    def keyPressEvent(self, event):
        if self.is_setting_target is not None:
            modifiers = []
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                modifiers.append("Ctrl")
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                modifiers.append("Alt")
            
            key = event.key()
            if key in [Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta]:
                event.accept()
                return
                
            if key == Qt.Key.Key_Escape:
                if self.is_setting_target == 'follow':
                    self.temp_follow = None
                    self.btn_follow.setText("Ctrl+MiddleClick")
                elif self.is_setting_target == 'transparent':
                    self.temp_transparent = None
                    self.btn_transparent.setText("사용 안 함")
                elif self.is_setting_target == 'hide':
                    self.temp_hide = None
                    self.btn_hide.setText("사용 안 함")
                
                self.btn_follow.setStyleSheet("")
                self.btn_transparent.setStyleSheet("")
                self.btn_hide.setStyleSheet("")
                self.is_setting_target = None
                event.accept()
                return
                
            key_name = QKeySequence(key).toString().upper()
            if not key_name:
                event.accept()
                return
                
            combo = modifiers + [key_name]
            final_hotkey = "+".join(combo)
            
            if self.is_setting_target == 'follow':
                self.temp_follow = final_hotkey
                self.btn_follow.setText(final_hotkey)
            elif self.is_setting_target == 'transparent':
                self.temp_transparent = final_hotkey
                self.btn_transparent.setText(final_hotkey)
            elif self.is_setting_target == 'hide':
                self.temp_hide = final_hotkey
                self.btn_hide.setText(final_hotkey)
                
            self.btn_follow.setStyleSheet("")
            self.btn_transparent.setStyleSheet("")
            self.btn_hide.setStyleSheet("")
            self.is_setting_target = None
            event.accept()
            return
            
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
            
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
        
        # Lucide Penguin Icon next to clean title label text (Replaces unicode emoji penguin)
        title_layout_row = QHBoxLayout()
        title_layout_row.setSpacing(8)
        title_layout_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_icon = QLabel()
        title_icon.setFixedSize(22, 22)
        title_icon.setPixmap(get_svg_icon(LUCIDE_PENGUIN_SVG).pixmap(22, 22))
        
        title_label = QLabel("펭구쫭을 위한 사용 가이드")
        title_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #ffffff;")
        
        title_layout_row.addWidget(title_icon)
        title_layout_row.addWidget(title_label)
        container_layout.addLayout(title_layout_row)
        
        content_label = QLabel(
            "<b>주요 단축키 및 조작법</b><br><br>"
            "1. <b>확대/축소</b>: <span style='color: #0088ff;'>Ctrl + 마우스 휠</span><br>"
            "2. <b>따라오기 토글</b>: <span style='color: #0088ff;'>Ctrl + 휠 클릭</span> (또는 설정 단축키)<br>"
            "3. <b>영역 지정</b>: [영역 지정] 클릭 후 화면 드래그<br>"
            "4. <b>투명도 설정</b>: 하단 투명도 슬라이더 사용 (15% ~ 100%)<br>"
            "5. <b>마우스 투과 토글</b>: <span style='color: #0088ff;'>Ctrl + Alt + T</span> (또는 설정 단축키)<br>"
            "   <i>※ 투과 모드가 켜지면 마우스 클릭이 창을 통과해 뒤쪽 게임을 조작할 수 있습니다. 다시 일반 모드로 돌아오려면 단축키를 누르세요.</i><br>"
            "6. <b>프로그램 최소화 토글</b>: <span style='color: #0088ff;'>Ctrl + Alt + H</span> (또는 설정 단축키) 또는 상단 최소화 [-] 버튼<br>"
            "7. <b>프로그램 설정</b>: 상단 설정 버튼 클릭<br>"
            "8. <b>프로그램 종료</b>: [X] 버튼 또는 ESC 키"
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
        self.resize(340, 400)
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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.load_icon()
        self.load_settings()
        
        self.follow_mouse = True
        self.click_through = False
        self.last_capture_pos = QPoint(0, 0)
        self.is_setting_hotkey = False
        
        self.bridge = InputBridge()
        self.bridge.zoom_changed.connect(self.handle_global_zoom)
        self.bridge.toggle_follow.connect(self.toggle_follow)
        self.bridge.toggle_click_through.connect(self.toggle_click_through)
        self.bridge.toggle_hide.connect(self.toggle_hide_mode)
        
        self.ctrl_pressed = False
        self.alt_pressed = False
        
        self.mouse_listener = mouse.Listener(on_click=self.on_global_click, on_scroll=self.on_global_scroll)
        self.key_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener.start()
        self.key_listener.start()
        
        self.setup_ui()
        
        # Apply native win32 SendMessageW to guarantee the taskbar icon displays 100% correctly
        force_set_window_icon(int(self.winId()), get_icon_path())
        
        self.sct = mss.mss()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_magnifier)
        self.timer.start(16)
        
        self.resize(420, 540)
        self.old_pos = None
        
        self.zoom_slider.setValue(int(self.zoom_factor * 10))
        self.opacity_slider.setValue(self.opacity_value)
        self.setWindowOpacity(self.opacity_value / 100.0)

    def showEvent(self, event):
        force_set_window_icon(int(self.winId()), get_icon_path())
        super().showEvent(event)

    def load_icon(self):
        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

    def get_config_path(self):
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'PengZoom')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'config.json')

    def load_settings(self):
        config_path = self.get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.zoom_factor = data.get('zoom_factor', 2.0)
                    self.opacity_value = data.get('opacity', 100)
                    
                    self.hotkey_follow = data.get('hotkey_follow', None)
                    self.hotkey_transparent = data.get('hotkey_transparent', "Ctrl+Alt+T")
                    self.hotkey_hide = data.get('hotkey_hide', "Ctrl+Alt+H")
                    return
            except Exception:
                pass
        
        self.zoom_factor = 2.0
        self.opacity_value = 100
        self.hotkey_follow = None
        self.hotkey_transparent = "Ctrl+Alt+T"
        self.hotkey_hide = "Ctrl+Alt+H"

    def save_settings(self):
        config_path = self.get_config_path()
        try:
            data = {
                'zoom_factor': self.zoom_factor,
                'opacity': self.opacity_slider.value(),
                'hotkey_follow': self.hotkey_follow,
                'hotkey_transparent': self.hotkey_transparent,
                'hotkey_hide': self.hotkey_hide
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def setup_ui(self):
        self.container = ResizableContainer()
        self.setCentralWidget(self.container)
        
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
            
            QPushButton#MinimizeBtn {
                background-color: rgba(255, 214, 10, 0.2);
                border: 1px solid rgba(255, 214, 10, 0.3);
                border-radius: 12px;
            }
            QPushButton#MinimizeBtn:hover {
                background-color: rgba(255, 214, 10, 0.35);
            }
            
            QPushButton#SettingsBtn {
                background-color: rgba(48, 209, 88, 0.2);
                border: 1px solid rgba(48, 209, 88, 0.3);
                border-radius: 12px;
            }
            QPushButton#SettingsBtn:hover {
                background-color: rgba(48, 209, 88, 0.35);
            }
            
            QPushButton#HelpBtn {
                background-color: rgba(10, 132, 255, 0.2);
                border: 1px solid rgba(10, 132, 255, 0.3);
                border-radius: 12px;
            }
            QPushButton#HelpBtn:hover {
                background-color: rgba(10, 132, 255, 0.35);
            }
            
            QPushButton#CloseBtn {
                background-color: rgba(255, 69, 58, 0.2);
                border: 1px solid rgba(255, 69, 58, 0.3);
                border-radius: 12px;
            }
            QPushButton#CloseBtn:hover {
                background-color: rgba(255, 69, 58, 0.35);
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
        
        # Top-right button cluster (Minimize, Settings, Help, Close) all as 24x24 circular buttons with Lucide SVGs
        self.minimize_btn = QPushButton()
        self.minimize_btn.setObjectName('MinimizeBtn')
        self.minimize_btn.setFixedSize(24, 24)
        self.minimize_btn.setIcon(get_svg_icon(LUCIDE_MINIMIZE_SVG))
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.title_layout.addWidget(self.minimize_btn)
        
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName('SettingsBtn')
        self.settings_btn.setFixedSize(24, 24)
        self.settings_btn.setIcon(get_svg_icon(LUCIDE_SETTINGS_SVG))
        self.settings_btn.clicked.connect(self.show_settings)
        self.title_layout.addWidget(self.settings_btn)
        
        self.help_btn = QPushButton()
        self.help_btn.setObjectName('HelpBtn')
        self.help_btn.setFixedSize(24, 24)
        self.help_btn.setIcon(get_svg_icon(LUCIDE_HELP_SVG))
        self.help_btn.clicked.connect(self.show_help)
        self.title_layout.addWidget(self.help_btn)
        
        self.close_btn = QPushButton()
        self.close_btn.setObjectName('CloseBtn')
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setIcon(get_svg_icon(LUCIDE_CLOSE_SVG))
        self.close_btn.clicked.connect(self.close)
        self.title_layout.addWidget(self.close_btn)
        
        self.main_layout.addLayout(self.title_layout)
        
        # Row for Click-Through Toggle
        self.config_layout = QHBoxLayout()
        self.config_layout.setSpacing(8)
        
        self.click_through_btn = QPushButton('마우스 투과: 끔')
        self.click_through_btn.clicked.connect(self.toggle_click_through)
        self.config_layout.addWidget(self.click_through_btn)
        
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
        self.zoom_slider.setRange(10, 200)
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

    def show_settings(self):
        modal = SettingsModal(self)
        modal.exec()

    def start_setting_hotkey(self):
        self.is_setting_hotkey = True

    def on_hotkey_set(self, key_name):
        pass

    def check_hotkey_match(self, parsed_parts, current_key_name, is_t_key, is_h_key):
        target_key = parsed_parts[-1].lower()
        req_ctrl = 'ctrl' in parsed_parts
        req_alt = 'alt' in parsed_parts
        
        if self.ctrl_pressed != req_ctrl or self.alt_pressed != req_alt:
            return False
            
        if target_key == 't' and is_t_key:
            return True
        if target_key == 'h' and is_h_key:
            return True
        if current_key_name == target_key:
            return True
            
        return False

    def on_key_press(self, key):
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            self.ctrl_pressed = True
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = True
            
        try:
            if hasattr(key, 'char') and key.char:
                current_key_name = key.char.lower()
            else:
                current_key_name = str(key).replace('Key.', '').lower()
        except Exception:
            current_key_name = str(key).lower()
            
        is_t_key = False
        is_h_key = False
        if hasattr(key, 'vk'):
            if key.vk == 84:
                is_t_key = True
            elif key.vk == 72:
                is_h_key = True
        
        if not is_t_key and current_key_name in ['t', 'ㅅ']:
            is_t_key = True
        if not is_h_key and current_key_name in ['h', 'ㅗ']:
            is_h_key = True

        if self.is_setting_hotkey:
            combo = []
            if self.ctrl_pressed:
                combo.append('Ctrl')
            if self.alt_pressed:
                combo.append('Alt')
            
            btn_key = current_key_name.upper()
            if btn_key in ['CTRL_L', 'CTRL_R', 'ALT_L', 'ALT_R', 'SHIFT', 'SHIFT_R', 'CMD']:
                return
            
            combo.append(btn_key)
            final_hotkey = '+'.join(combo)
            self.bridge.hotkey_set.emit(final_hotkey)
            return

        if self.hotkey_transparent:
            parts = [p.lower() for p in self.hotkey_transparent.split('+')]
            if self.check_hotkey_match(parts, current_key_name, is_t_key, is_h_key):
                self.bridge.toggle_click_through.emit()
                return

        if self.hotkey_hide:
            parts = [p.lower() for p in self.hotkey_hide.split('+')]
            if self.check_hotkey_match(parts, current_key_name, is_t_key, is_h_key):
                self.bridge.toggle_hide.emit()
                return

        if self.hotkey_follow:
            parts = [p.lower() for p in self.hotkey_follow.split('+')]
            if self.check_hotkey_match(parts, current_key_name, is_t_key, is_h_key):
                self.bridge.toggle_follow.emit()
                return

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
        if self.hotkey_follow is None:
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
        hwnd = int(self.winId())
        
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if self.click_through:
            new_style = style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            self.click_through_btn.setText('마우스 투과: 켬')
            self.click_through_btn.setProperty("class", "PrimaryActive")
        else:
            new_style = style & ~WS_EX_TRANSPARENT
            self.click_through_btn.setText('마우스 투과: 끔')
            self.click_through_btn.setProperty("class", "")
            
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0037)
        
        self.click_through_btn.style().unpolish(self.click_through_btn)
        self.click_through_btn.style().polish(self.click_through_btn)

    def toggle_hide_mode(self):
        if self.isMinimized():
            self.showNormal()
            self.activateWindow()
        else:
            self.showMinimized()

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
                painter.setPen(QPen(QColor(255, 69, 58, 200), 1))
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
        self.save_settings()
        self.mouse_listener.stop()
        self.key_listener.stop()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    icon_path = get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    window = MagnifierWindow()
    window.show()
    sys.exit(app.exec())
