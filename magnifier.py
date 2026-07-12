import sys
import os
import json
import mss
import numpy as np
import winsound  # Win32 system sound for cooldown alerts
import threading  # Asynchronous threading to prevent mouse lagging
import traceback  # Traceback debugging helper to capture exact popup crashes
import base64
import atexit
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFrame, QPushButton, QSlider, 
                             QDialog, QSizeGrip, QSizePolicy, QGridLayout, QTabWidget,
                             QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
                             QCheckBox, QSpinBox)
from PyQt6.QtCore import QTimer, Qt, QPoint, QRect, pyqtSignal, QObject, QSize, QPropertyAnimation, QEasingCurve, QEvent
from PyQt6.QtGui import QImage, QPixmap, QCursor, QPainter, QPen, QColor, QIcon, QKeySequence, QWheelEvent
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
from PIL import Image
from pynput import keyboard, mouse
import cv2

# Import our custom modules
import cooldown_detector
import network_manager
from capture_overlay import CaptureOverlay

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

# New high-quality original penguin character SVG provided by the user
LUCIDE_PENGUIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 150">
<!-- SVG created with Arrow, by QuiverAI (https://quiver.ai) -->
  <style type="text/css">.cls-0 {fill:#283A60;}
.cls-1 {fill:url(#SVGID_1_);}
.cls-2 {fill:#4B739F;}
.cls-3 {fill:#FFFFFF;}
.cls-4 {fill:url(#SVGID_2_);}
.cls-5 {fill:url(#SVGID_3_);}
.cls-6 {fill:none;stroke:#283A60;stroke-width:2;stroke-linecap:round;stroke-miterlimit:10;}
.cls-7 {fill:url(#SVGID_4_);}
.cls-8 {fill:#F9D352;}
.cls-9 {opacity:0.3;fill:url(#SVGID_5_);enable-background:new    ;}
.cls-10 {fill:url(#SVGID_6_);}
.cls-11 {fill:url(#SVGID_7_);}
.cls-12 {fill:url(#SVGID_8_);}
.cls-13 {fill:url(#SVGID_9_);}</style>
  <path class="cls-0" d="m121.6 68.9c-2.7-3.6-2.6-16.9-5.2-26.5-4-15.1-18.4-31.9-41.3-31.9s-37 14.9-41.6 33.2c-1.6 6.2-2.2 19.8-4.1 24.6-1 2.4-7.4 8.6-11.2 20.4-3.3 10.6-2.4 17.3 2.3 17.2 2.8-0.1 5.7-2.3 7.6-3.8 0.9 10 5.5 17.4 13.6 24-2 1.3-5.6 3.9-5.6 6.7-0.1 4.1 4 4.3 8.1 3.9 2.3 2.1 3.7 2.5 7.1 2.5 4.7 0 11.1-1.8 14.4-4.9 4.3 0.4 12.2 0.5 18.5-0.1 2.4 2 8.1 4.9 15.3 5 2.7 0 4.4-0.4 6.1-2.4l0.1-0.1c3.7 0.2 8.4 1 8.3-3.8 0-2.9-3.7-5.5-5.8-6.7 2.8-1.7 7.7-6.5 9.8-10.5 1.8-3.5 3.5-9.1 3.6-13.9 2.4 1.7 4.7 4 8.1 4.1 6.8 0 5.3-14.6-2.5-29.1-0.7-1.1-3.6-5.9-5.6-7.9z"/>
  <linearGradient id="SVGID_1_" x1="75" x2="75" y1="-94.8" y2="-27.6" gradientTransform="translate(0 104)" gradientUnits="userSpaceOnUse">
    <stop stop-color="#4B739E" offset="0"/>
    <stop stop-color="#4C75A1" offset=".5909"/>
    <stop stop-color="#4B6088" offset=".9949"/>
  </linearGradient>
  <path class="cls-1" d="m120.3 72c-3.2-4.7-3.7-8.3-4.9-20.7-1.9-18.3-16.4-38.2-40.4-38.2-19.5 0-34.7 14.3-39.2 31.9-1.2 4.9-2.2 20-4 23.6-1.7 3.4-8.3 10.7-11.5 22.5-0.4 1.8-2.1 12 0.4 12 2.9-0.1 5.8-3 7.5-5h0.1c-0.1-6.3 2.2-13 4.2-14.3-1.6 7-3 21.6 1.9 30.1 3.9 6.6 9.1 10.7 15.1 13l3-1.4 22.4 6.6 25.3-3.4 6.1-3.8c4.2-2.7 7.8-5.8 10.9-12.9 3.9-9 2.4-20.6 0.1-28.3 2.4 1.7 4.3 7.2 4.6 14.2h-0.1c2.5 2.4 4.7 4.6 7.8 5.2 1.8 0.4 2.8-11.2-5.3-25.7-0.4-1-2.6-4-4-5.4z"/>
  <path class="cls-2" d="m31.5 86.6c-2.4 2.5-6.5 10.3-12.2 12.2v4.2h6.2l3.5-4 2.5-12.4z"/>
  <path class="cls-2" d="m119.6 87c1.9 4 6.1 9.9 11.1 11.8l0.2 4.9-5.5-0.7-4.5-3.6-1.3-12.4z"/>
  <path class="cls-3" d="m102.2 75.1c2.5-2.4 7.5-7.6 7.5-16.1 0-10-5.1-23.9-16.2-23.9-8.5 0-14.3 7.5-14.3 21.8l-8.6 0.1c0-9.7-3.5-21.9-13.8-21.9-8.9 0-16.6 9.9-16.6 22.6 0 8.8 4.3 14.4 7.6 17.6-2.7 3.3-10.7 13.7-10.7 28.7 0 8 3.2 16 9.1 20.6 4.8 3.6 14.2 7.5 28.7 7.5 15.3 0 23.7-2.7 28.2-5.6 5.1-3.4 10-11.8 10-21.9 0-13.1-6.1-22.7-10.9-29.5z"/>
  <linearGradient id="SVGID_2_" x1="50.5" x2="113.8" y1="-89.1" y2="-89.1" gradientTransform="translate(0 104)" gradientUnits="userSpaceOnUse">
    <stop stop-color="#fff" stop-opacity=".4" offset="0"/>
    <stop stop-color="#BCD0E2" stop-opacity=".9" offset="1"/>
  </linearGradient>
  <path class="cls-4" d="m75 15.1c18.5 0 34.6 12.4 38.8 28.5l-0.2-0.5c-3.5-14.9-16.6-29.8-38.6-30-13.7 0-25.3 6.9-31.9 17.8 5.8-7.4 16.6-15.8 31.9-15.8z"/>
  <linearGradient id="SVGID_3_" x1="75" x2="75" y1="-17.8" y2="-4.144" gradientTransform="translate(0 104)" gradientUnits="userSpaceOnUse">
    <stop stop-color="#CFDCE5" offset="0"/>
    <stop stop-color="#CCDCE7" offset="1"/>
  </linearGradient>
  <path class="cls-5" d="m75 72.2c-15 0-23.5 6-30.1 14.6l-7.8 12.2c-0.1 7 2.5 21.6 10.4 26.5 6.6 4.1 16 6.4 27.4 6.4 11.8 0.2 22.1-2.2 27-5.3 6.8-3.6 10.7-12.6 11.2-19.7l-3.2-6.7c-5.3-12.2-12.2-28-34.9-28z"/>
  <path class="cls-6" d="m65.2 63"/>
  <linearGradient id="SVGID_4_" x1="75.05" x2="75.05" y1=".8404" y2="27.47" gradientUnits="userSpaceOnUse">
    <stop stop-color="#FAD250" offset=".3939"/>
    <stop stop-color="#DCAC52" offset="1"/>
  </linearGradient>
  <path class="cls-7" d="m75 85.8c-14.6 0-27.7 11.9-27.7 27.3s6.8 19 28.2 19c21.1 0 27.2-5.1 27.2-18.1s-10-28.2-27.7-28.2z"/>
  <path class="cls-8" d="m44.7 127.6c-2.1 1-6.8 3.8-6 6.1 0.4 1.2 5.5 0.4 6.5 0.4 1.3 0 1.2 2.8 5.2 2.8 4.8 0.1 9.8-1.6 11.6-3-7-0.9-15.4-4.4-17.3-6.3z"/>
  <linearGradient id="SVGID_5_" x1="41.4" x2="57.9" y1="131.7" y2="131.7" gradientUnits="userSpaceOnUse">
    <stop stop-color="#DD8D38" offset="0"/>
    <stop stop-color="#DB9239" offset="1"/>
  </linearGradient>
  <path class="cls-9" d="m41.4 129.4c2.1 0.2 12.1 6.3 15.5 6.3 0.8 0 1-0.3 1-0.3l2.3-1.7c-2.2-0.6-11.3-2.8-15.6-6l-3.2 1.7z"/>
  <linearGradient id="SVGID_6_" x1="88.2" x2="111.2" y1="131.9" y2="131.9" gradientUnits="userSpaceOnUse">
    <stop stop-color="#F5CA37" offset="0"/>
    <stop stop-color="#F4BB2E" offset="1"/>
  </linearGradient>
  <path class="cls-10" d="m105.4 127.9c-2.5 1.6-9.3 4.6-17.2 5.8 2.2 1.4 8 3.2 12.2 3 3.3-0.1 3.5-2.6 4.2-2.8l0.4-0.1c0.7-0.1 5.6 1.2 6.2-0.2 1.2-2.2-3.5-5-5.8-5.7z"/>
  <linearGradient id="SVGID_7_" x1="93.5" x2="107.2" y1="131.6" y2="131.6" gradientUnits="userSpaceOnUse">
    <stop stop-color="#DE9539" offset="0"/>
    <stop stop-color="#DF9739" offset="1"/>
  </linearGradient>
  <path class="cls-11" d="m105.5 127.9c-3 1.7-8.9 4.1-12 4.5l-0.6 2.9c3.1 1.1 11.5-4.2 14.3-5.8v-1.6l-1-0.2h-0.7z"/>
  <linearGradient id="SVGID_8_" x1="74.84" x2="74.84" y1="57.6" y2="70.72" gradientUnits="userSpaceOnUse">
    <stop stop-color="#F5CB2E" offset="0"/>
    <stop stop-color="#F7BD28" offset=".5955"/>
  </linearGradient>
  <path class="cls-12" d="m74.9 56.7c-3.2 0-9.5 3.8-9.5 6.3 0 1.6 6.1 7.7 9.6 7.7 2.6 0 9.5-5.1 9.5-7.7 0-2.1-6.1-6.3-9.6-6.3z"/>
  <linearGradient id="SVGID_9_" x1="75.01" x2="75.01" y1="65.18" y2="70.41" gradientUnits="userSpaceOnUse">
    <stop stop-color="#E39F40" offset="0"/>
    <stop stop-color="#DA8D38" offset="1"/>
  </linearGradient>
  <path class="cls-13" d="m65.6 63.9c1.1 2 6.9 6.5 9.3 6.6 2 0.2 6.2-2.6 9.5-6.5-6.2 2.7-8.7 2.4-9.2 2.4-1.7 0-7.1-1.8-9.6-2.5z"/>
  <path class="cls-0" d="m75.1 55.7c-3.7-0.1-10.8 3.9-10.8 7s7.3 9 10.6 9.1c3.1 0.2 10.6-5.7 10.6-8.7 0.1-2.7-6.1-7.2-10.4-7.4zm-0.2 14.2c-1.5 0-5.9-2.7-8-5.2 2.2 0.8 6.2 2.2 8.1 2.2s5.7-1.3 7.6-2c-2.1 2-5.9 5-7.7 5zm0-4.4c-2 0-8.5-2.4-8.5-2.8 0-1.1 5.2-5 8.5-5 3.1-0.1 8.6 3.4 8.7 5 0.1 0.3-6.9 2.8-8.7 2.8z"/>
  <path class="cls-0" d="m56.2 47.8"/>
  <ellipse class="cls-0" cx="56.2" cy="54.2" rx="4.6" ry="5.9"/>
  <circle class="cls-3" cx="57.4" cy="51.8" r="1.7"/>
  <ellipse class="cls-0" cx="93.9" cy="54.2" rx="4.7" ry="6"/>
  <circle class="cls-3" cx="95" cy="51.8" r="1.7"/>
  <linearGradient id="SVGID_10_" x1="74.87" x2="74.87" y1="26.87" y2="40.01" gradientTransform="matrix(1 0 0 -1 0 152)" gradientUnits="userSpaceOnUse">
    <stop stop-color="#AB8040" stop-opacity=".5" offset="0"/>
    <stop stop-color="#CD9F43" offset="1"/>
  </linearGradient>
  <path d="m47.4 118c0.5 4.4 2 7.4 4.2 10 2.5 1 9.4 3.9 23.1 4.1 10.3 0 19.4-1.5 23.7-3.6 2-2.5 3.6-5.5 4-10.3-4.4 2.9-12.9 7.4-27.2 7.5-11.8 0-21.2-3.1-27.8-7.7z" fill="url(#SVGID_10_)"/>
</svg>"""

# Server Hosting (Host) & Client Link (Join) SVG Icons (Removed explicit width/height to avoid half-cut clipping)
LUCIDE_HOST_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0a84ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="2"/>
  <path d="M16.2 7.8a6 6 0 0 1 0 8.4m3.6-12a11 11 0 0 1 0 15.6M7.8 16.2a6 6 0 0 1 0-8.4M4.2 19.8a11 11 0 0 1 0-15.6"/>
</svg>
"""

LUCIDE_JOIN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#30d158" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M9 17H7A5 5 0 0 1 7 7h2m6 10h2a5 5 0 0 0 0-10h-2m-7 5h8"/>
</svg>
"""

LUCIDE_USER_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0a84ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
  <circle cx="12" cy="7" r="4"/>
</svg>
"""

LUCIDE_CHECK_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#30d158" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="20 6 9 17 4 12"/>
</svg>
"""

LUCIDE_CLOCK_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ff453a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <polyline points="12 6 12 12 16 14"/>
</svg>
"""

LUCIDE_STATUS_ON_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#30d158" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <circle cx="12" cy="12" r="3" fill="#30d158"/>
</svg>
"""

LUCIDE_STATUS_OFF_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#8e8e93" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
</svg>
"""

LUCIDE_LINKED_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#30d158" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
</svg>
"""

LUCIDE_UNLINKED_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#8e8e93" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="m18.84 18.84-3-3m-1.54-1.54-1.72 1.72a5 5 0 0 1-7.07-7.07l1.71-1.71"/>
  <path d="M14 11a5 5 0 0 0-7.54-.54l-1.3 1.3M10 13a5 5 0 0 0 7.54.54l1.3-1.3"/>
  <line x1="2" y1="2" x2="22" y2="22"/>
</svg>
"""

LUCIDE_ERROR_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ff453a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <line x1="15" y1="9" x2="9" y2="15"/>
  <line x1="9" y1="9" x2="15" y2="15"/>
</svg>
"""

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

# Dynamic renderer helper that guarantees no border half-cuts by drawing directly inside a clean QPixmap with anti-aliasing
def get_svg_pixmap(svg_str, size=18):
    try:
        from PyQt6.QtCore import QRectF
        renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0.0, 0.0, float(size), float(size)))
        painter.end()
        return pixmap
    except Exception:
        return QPixmap()

# Win32 helper to force system taskbar icon updates via SendMessageW using in-memory SVG to HICON
def force_set_window_icon(hwnd):
    try:
        renderer = QSvgRenderer(QByteArray(LUCIDE_PENGUIN_SVG.encode('utf-8')))
        if renderer.isValid():
            pixmap = QPixmap(256, 256)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            hicon = pixmap.toWinHICON()
            if hicon:
                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ICON_BIG = 1
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, int(hicon))
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, int(hicon))
    except Exception:
        pass

# Utility to traverse hierarchy and get the main window to call pause/resume on listeners
def get_main_window_instance(parent):
    if parent:
        curr = parent
        while curr:
            if isinstance(curr, QMainWindow):
                return curr
            curr = curr.parent()
    return None

# Custom Styled Dialogs with Listener Pausing to 100% prevent 1fps mouse lagging during modal blocking
def show_dark_message_box(parent, title, text, icon_type=QMessageBox.Icon.Information):
    main_win = get_main_window_instance(parent)
    if main_win and hasattr(main_win, 'pause_listeners'):
        main_win.pause_listeners()
        
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon_type)
    msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
    msg.setStyleSheet("""
        QMessageBox {
            background-color: #1c1c1e;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
        }
        QLabel {
            color: #ffffff;
            font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 4px;
        }
        QPushButton {
            background-color: rgba(255, 255, 255, 0.08);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 5px 15px;
            min-width: 65px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: rgba(255, 255, 255, 0.16);
        }
    """)
    result = msg.exec()
    
    if main_win and hasattr(main_win, 'resume_listeners'):
        main_win.resume_listeners()
        
        # Bring parent window explicitly back on top after dialog close
        parent.raise_()
        parent.activateWindow()
        
    return result

def get_dark_input_text(parent, title, label_text):
    main_win = get_main_window_instance(parent)
    if main_win and hasattr(main_win, 'pause_listeners'):
        main_win.pause_listeners()
        
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label_text)
    dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
    dialog.setStyleSheet("""
        QInputDialog {
            background-color: #1c1c1e;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
        }
        QLabel {
            color: #ffffff;
            font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 4px;
        }
        QLineEdit {
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            color: #ffffff;
            padding: 5px 8px;
            font-size: 12px;
        }
        QPushButton {
            background-color: rgba(255, 255, 255, 0.08);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 5px 15px;
            min-width: 65px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: rgba(255, 255, 255, 0.16);
        }
    """)
    ok = dialog.exec()
    val = dialog.textValue()
    
    if main_win and hasattr(main_win, 'resume_listeners'):
        main_win.resume_listeners()
        
        # Bring parent window explicitly back on top after input dialog close
        parent.raise_()
        parent.activateWindow()
        
    return val, ok


class InputBridge(QObject):
    zoom_changed = pyqtSignal(int)
    toggle_follow = pyqtSignal()
    toggle_click_through = pyqtSignal()
    toggle_hide = pyqtSignal()

# Floating transparent window displaying party skill statuses
# Floating transparent window displaying party skill statuses
class PartyPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__()  # 부모 전달 안 함 → 독립 윈도우 (메인 최소화 시 같이 안 숨겨짐)
        self.parent_window = parent
        self.panel_click_through = False
        self.setWindowTitle("파티원 쿨타임 현황")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setStyleSheet("""
            #Container {
                background-color: rgba(20, 20, 22, 0.90);
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
            }
            QLabel {
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QLabel#Title {
                font-size: 14px;
                font-weight: 700;
                color: #0a84ff;
            }
            QFrame.PlayerCard {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
                margin-top: 2px;
                margin-bottom: 2px;
            }
            QFrame.SkillBadge {
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        
        container = QFrame()
        container.setObjectName("Container")
        container.setMouseTracking(True)
        container.installEventFilter(self)
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(14, 14, 14, 14)
        self.container_layout.setSpacing(10)
        
        header_lay = QHBoxLayout()
        header_lay.setSpacing(6)
        
        header_icon = QLabel()
        header_icon.setFixedSize(18, 18)
        header_icon.setStyleSheet("border: none; background: transparent;")
        header_icon.setPixmap(get_svg_pixmap(LUCIDE_HOST_SVG, 18))
        
        title = QLabel("파티 스킬 모니터")
        title.setObjectName("Title")
        
        header_lay.addWidget(header_icon)
        header_lay.addWidget(title)
        header_lay.addStretch()
        self.container_layout.addLayout(header_lay)
        
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        self.container_layout.addLayout(self.list_layout)
        
        layout.addWidget(container)
        self.resize(240, 320)
        self.old_pos = None
        self.widgets = {}
        
        # Sizing and transparency configuration
        self.panel_opacity = 90
        self.setWindowOpacity(self.panel_opacity / 100.0)
        self.setMouseTracking(True)
        self.resize_dir = None
        self.drag_position = None
        
        # Real-time tick timer for countdown displays
        from PyQt6.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick_timers)
        self.timer.start(100)  # 100ms precision


    def update_states(self, party_states):
        current_players = set(party_states.keys())
        for p in list(self.widgets.keys()):
            if p not in current_players:
                self.widgets[p]["widget"].deleteLater()
                del self.widgets[p]
                
        for player, skills in party_states.items():
            if player not in self.widgets:
                player_widget = QFrame()
                player_widget.setProperty("class", "PlayerCard")
                player_widget.setObjectName("PlayerCardWidget")
                
                p_lay = QVBoxLayout(player_widget)
                p_lay.setContentsMargins(10, 8, 10, 8)
                p_lay.setSpacing(6)
                
                name_row = QHBoxLayout()
                name_row.setSpacing(6)
                
                u_icon = QLabel()
                u_icon.setFixedSize(14, 14)
                u_icon.setStyleSheet("border: none; background: transparent;")
                u_icon.setPixmap(get_svg_pixmap(LUCIDE_USER_SVG, 14))
                
                name_lbl = QLabel(player)
                name_lbl.setStyleSheet("font-weight: 700; color: #ffffff; font-size: 13px;")
                
                name_row.addWidget(u_icon)
                name_row.addWidget(name_lbl)
                name_row.addStretch()
                p_lay.addLayout(name_row)
                
                skills_lay = QVBoxLayout()
                skills_lay.setSpacing(4)
                p_lay.addLayout(skills_lay)
                
                self.list_layout.addWidget(player_widget)
                self.widgets[player] = {
                    "widget": player_widget,
                    "skills_layout": skills_lay,
                    "skill_widgets": {}
                }
                
            p_data = self.widgets[player]
            
            for s in list(p_data["skill_widgets"].keys()):
                if s not in skills:
                    p_data["skill_widgets"][s]["badge"].deleteLater()
                    del p_data["skill_widgets"][s]
                    
            for skill, s_info in skills.items():
                is_ready = s_info.get("is_ready", True)
                cooldown_duration = s_info.get("cooldown_duration", 0)
                timestamp = s_info.get("timestamp", 0.0)
                
                if skill not in p_data["skill_widgets"]:
                    badge = QFrame()
                    badge.setProperty("class", "SkillBadge")
                    b_lay = QHBoxLayout(badge)
                    b_lay.setContentsMargins(6, 4, 6, 4)
                    b_lay.setSpacing(6)
                    
                    status_icon = QLabel()
                    status_icon.setFixedSize(12, 12)
                    status_icon.setStyleSheet("border: none; background: transparent;")
                    
                    skill_lbl = QLabel(skill)
                    skill_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #ffffff;")
                    
                    status_text_lbl = QLabel()
                    status_text_lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
                    
                    b_lay.addWidget(status_icon)
                    b_lay.addWidget(skill_lbl)
                    b_lay.addStretch()
                    b_lay.addWidget(status_text_lbl)
                    
                    p_data["skills_layout"].addWidget(badge)
                    p_data["skill_widgets"][skill] = {
                        "badge": badge,
                        "status_icon": status_icon,
                        "status_text_lbl": status_text_lbl,
                        "is_ready": is_ready,
                        "cooldown_duration": cooldown_duration,
                        "timestamp": timestamp,
                        "ui_ready_state": None
                    }
                
                s_widgets = p_data["skill_widgets"][skill]
                s_widgets["is_ready"] = is_ready
                s_widgets["cooldown_duration"] = cooldown_duration
                s_widgets["timestamp"] = timestamp

    def tick_timers(self):
        import time
        import math
        current_time = time.time()
        
        for player, p_data in list(self.widgets.items()):
            for skill, s_widgets in list(p_data["skill_widgets"].items()):
                is_ready = s_widgets["is_ready"]
                cooldown_duration = s_widgets["cooldown_duration"]
                timestamp = s_widgets["timestamp"]
                
                remaining = 0
                if not is_ready and cooldown_duration > 0:
                    elapsed = current_time - timestamp
                    remaining = max(0.0, cooldown_duration - elapsed)
                
                visually_ready = is_ready or (cooldown_duration > 0 and remaining <= 0)
                
                if visually_ready:
                    if s_widgets["ui_ready_state"] != True:
                        s_widgets["ui_ready_state"] = True
                        s_widgets["badge"].setStyleSheet("""
                            QFrame.SkillBadge {
                                background-color: rgba(48, 209, 88, 0.08);
                                border: 1px solid rgba(48, 209, 88, 0.25);
                            }
                        """)
                        s_widgets["status_icon"].setPixmap(get_svg_pixmap(LUCIDE_CHECK_SVG, 12))
                        s_widgets["status_text_lbl"].setText("Ready")
                        s_widgets["status_text_lbl"].setStyleSheet("color: #30d158;")
                else:
                    if s_widgets["ui_ready_state"] != False:
                        s_widgets["ui_ready_state"] = False
                        s_widgets["badge"].setStyleSheet("""
                            QFrame.SkillBadge {
                                background-color: rgba(255, 69, 58, 0.08);
                                border: 1px solid rgba(255, 69, 58, 0.25);
                            }
                        """)
                        s_widgets["status_icon"].setPixmap(get_svg_pixmap(LUCIDE_CLOCK_SVG, 12))
                        s_widgets["status_text_lbl"].setStyleSheet("color: #ff453a;")
                    
                    if cooldown_duration > 0:
                        s_widgets["status_text_lbl"].setText(f"{int(math.ceil(remaining))}s")
                    else:
                        s_widgets["status_text_lbl"].setText("Cooldown")

    def mousePressEvent(self, event):
        if self.panel_click_through:
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            rect = self.rect()
            border = 15
            
            # Check edge areas for resizing
            is_right = pos.x() >= rect.width() - border
            is_bottom = pos.y() >= rect.height() - border
            
            if is_right and is_bottom:
                self.resize_dir = "BottomRight"
            elif is_right:
                self.resize_dir = "Right"
            elif is_bottom:
                self.resize_dir = "Bottom"
            else:
                self.resize_dir = None
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
    def mouseMoveEvent(self, event):
        if self.panel_click_through:
            return
            
        pos = event.position().toPoint()
        rect = self.rect()
        border = 15
        
        # Cursor styling when hovering over borders (Only when not clicking)
        if event.buttons() == Qt.MouseButton.NoButton:
            is_right = pos.x() >= rect.width() - border
            is_bottom = pos.y() >= rect.height() - border
            
            if is_right and is_bottom:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif is_right:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif is_bottom:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                
        # Perform resize or move operations
        elif event.buttons() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            if self.resize_dir == "BottomRight":
                w = max(150, global_pos.x() - self.x())
                h = max(100, global_pos.y() - self.y())
                self.resize(w, h)
            elif self.resize_dir == "Right":
                w = max(150, global_pos.x() - self.x())
                self.resize(w, self.height())
            elif self.resize_dir == "Bottom":
                h = max(100, global_pos.y() - self.y())
                self.resize(self.width(), h)
            elif self.drag_position is not None:
                self.move(global_pos - self.drag_position)
            
    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.resize_dir = None
        self.drag_position = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.parent_window:
            self.parent_window.save_settings()

    def eventFilter(self, obj, event):
        if not self.panel_click_through and event.type() == QEvent.Type.MouseMove:
            # Map global position of mouse move inside children to parent's local geometry
            local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
            rect = self.rect()
            border = 15
            
            is_right = local_pos.x() >= rect.width() - border
            is_bottom = local_pos.y() >= rect.height() - border
            
            if is_right and is_bottom:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif is_right:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif is_bottom:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().eventFilter(obj, event)
            
    def closeEvent(self, event):
        if self.parent_window:
            self.parent_window.save_settings()
        super().closeEvent(event)

    def set_click_through(self, enabled):
        self.panel_click_through = enabled
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            new_style = style | WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            new_style = style & ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0037)


class SettingsModal(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setWindowTitle("설정")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.is_setting_target = None

        
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
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #ffffff;
                padding: 4px 8px;
                font-size: 12px;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                background: transparent;
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-bottom-color: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 16px;
                color: #cccccc;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                border-bottom-color: rgba(28, 28, 30, 0.96);
            }
            QListWidget {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setObjectName("ModalContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(14)
        
        # Header Row
        title_layout_row = QHBoxLayout()
        title_layout_row.setSpacing(8)
        title_layout_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_icon = QLabel()
        title_icon.setFixedSize(20, 20)
        title_icon.setPixmap(get_svg_icon(LUCIDE_SETTINGS_SVG).pixmap(20, 20))
        title_label = QLabel("설정 및 쿨타임 동기화")
        title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        title_layout_row.addWidget(title_icon)
        title_layout_row.addWidget(title_label)
        container_layout.addLayout(title_layout_row)
        
        # Tab Control
        self.tabs = QTabWidget()
        
        # Tab 1: General Hotkeys & Display settings
        tab_hotkeys = QWidget()
        self.setup_hotkeys_tab(tab_hotkeys)
        self.tabs.addTab(tab_hotkeys, "단축키/표시")
        
        # Tab 2: Skill Cooldown Settings
        tab_skills = QWidget()
        self.setup_skills_tab(tab_skills)
        self.tabs.addTab(tab_skills, "스킬 감지")
        
        # Tab 3: Network Party Settings
        tab_network = QWidget()
        self.setup_network_tab(tab_network)
        self.tabs.addTab(tab_network, "파티 연동")
        
        container_layout.addWidget(self.tabs)
        
        # Bottom Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("확인")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(self.save_btn)
        
        container_layout.addLayout(btn_layout)
        layout.addWidget(container)
        
        self.resize(460, 480)
        self.old_pos = None

    def setup_hotkeys_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        
        grid = QGridLayout()
        grid.setSpacing(10)
        
        self.temp_follow = self.parent_window.hotkey_follow
        self.temp_transparent = self.parent_window.hotkey_transparent
        self.temp_hide = self.parent_window.hotkey_hide
        
        # 1. Follow Hotkey
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
        
        lay.addLayout(grid)
        
        # Divider Line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: rgba(255,255,255,0.06);")
        lay.addWidget(line)
        
        # UI Hiding Toggle Option (Newly Requested Feature)
        self.chk_hide_ui_on_transparent = QCheckBox("마우스 투과(On) 시 모든 제어 UI 숨기기")
        self.chk_hide_ui_on_transparent.setChecked(self.parent_window.hide_ui_on_transparent)
        lay.addWidget(self.chk_hide_ui_on_transparent)
        
        info = QLabel("※ 단축키 지정 대기 상태에서 ESC를 누르면 마우스 기본 설정(휠 클릭 리셋 등)으로 해제됨 애옹! 투과 UI 숨기기 옵션을 켜면, 마우스 투과 상태에서 버튼이랑 슬라이더 영역이 자동 가려져 깔끔한 화면만 떠있게 됨 애옹!")
        info.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.4); line-height: 1.4;")
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addStretch()

    def get_display_text(self, val, fallback):
        return val if val else fallback

    def start_setting(self, target, button):
        self.is_setting_target = target
        button.setText("키 입력 대기 중...")
        button.setStyleSheet("background-color: rgba(0, 102, 204, 0.4); border-color: #0066cc;")

    def setup_skills_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        
        btn_row = QHBoxLayout()
        self.add_skill_btn = QPushButton("스킬 추가")
        self.add_skill_btn.clicked.connect(self.add_new_skill_slot)
        btn_row.addWidget(self.add_skill_btn)
        
        self.cap_area_btn = QPushButton("영역 지정")
        self.cap_area_btn.clicked.connect(self.capture_selected_skill_area)
        btn_row.addWidget(self.cap_area_btn)
        
        self.del_skill_btn = QPushButton("삭제")
        self.del_skill_btn.clicked.connect(self.delete_selected_skill)
        btn_row.addWidget(self.del_skill_btn)
        
        lay.addLayout(btn_row)
        
        # Horizontal layout to split list and preview panel
        list_preview_lay = QHBoxLayout()
        list_preview_lay.setSpacing(10)
        
        self.skill_list = QListWidget()
        self.skill_list.currentRowChanged.connect(self.on_skill_selection_changed)
        list_preview_lay.addWidget(self.skill_list, 3) # Ratio 3
        
        # Preview Frame for captured template image
        self.preview_box = QFrame()
        self.preview_box.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        preview_lay = QVBoxLayout(self.preview_box)
        preview_lay.setContentsMargins(8, 8, 8, 8)
        preview_lay.setSpacing(6)
        preview_lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        lbl_preview_title = QLabel("Ready 스냅샷")
        lbl_preview_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #aaaaaa;")
        lbl_preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_lay.addWidget(lbl_preview_title)
        
        self.lbl_skill_img = QLabel("스냅샷 없음\n(영역 지정 필요)")
        self.lbl_skill_img.setFixedSize(96, 96)
        self.lbl_skill_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_skill_img.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px dashed rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                color: rgba(255, 255, 255, 0.3);
                font-size: 10px;
            }
        """)
        self.lbl_skill_img.setWordWrap(True)
        preview_lay.addWidget(self.lbl_skill_img)
        
        # Cooldown duration spinbox UI
        cooldown_lbl = QLabel("쿨타임 설정(초)")
        cooldown_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #aaaaaa; margin-top: 10px;")
        cooldown_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_lay.addWidget(cooldown_lbl)
        
        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(0, 3600)
        self.spin_cooldown.setSuffix(" 초")
        self.spin_cooldown.setValue(0)
        self.spin_cooldown.setStyleSheet("""
            QSpinBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: #ffffff;
                padding: 4px;
                font-size: 12px;
                font-weight: 500;
            }
        """)
        self.spin_cooldown.valueChanged.connect(self.on_cooldown_value_changed)
        preview_lay.addWidget(self.spin_cooldown)
        
        list_preview_lay.addWidget(self.preview_box, 2) # Ratio 2
        lay.addLayout(list_preview_lay)
        
        # Populate existing slots
        self.refresh_skill_list()
        
        self.lbl_selected_status = QLabel("선택된 스킬 없음 (Ready 스냅샷을 지정해 주셔야 활성화 판별이 시작됩니다.)")
        self.lbl_selected_status.setStyleSheet("font-size: 11px; color: #ffd60a;")
        self.lbl_selected_status.setWordWrap(True)
        lay.addWidget(self.lbl_selected_status)

    def setup_network_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        
        # Character Name Row
        char_row = QHBoxLayout()
        char_row.setSpacing(6)
        
        lbl_char_icon = QLabel()
        lbl_char_icon.setFixedSize(14, 14)
        lbl_char_icon.setScaledContents(True)
        lbl_char_icon.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")
        lbl_char_icon.setPixmap(get_svg_pixmap(LUCIDE_USER_SVG, 14))
        char_row.addWidget(lbl_char_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        
        char_lbl = QLabel("캐릭터명:")
        char_lbl.setStyleSheet("font-weight: bold; font-size: 13px; border: none; background: transparent;")
        char_row.addWidget(char_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        
        self.txt_char_name = QLineEdit(self.parent_window.player_name)
        self.txt_char_name.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 13px;
            }
        """)
        char_row.addWidget(self.txt_char_name, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(char_row)
        
        # Host Server Group
        host_box = QFrame()
        host_box.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 132, 255, 0.04); 
                border: 1px solid rgba(10, 132, 255, 0.18); 
                border-radius: 12px; 
                padding: 12px;
            }
        """)
        host_lay = QVBoxLayout(host_box)
        host_lay.setContentsMargins(12, 12, 12, 12)
        host_lay.setSpacing(10)
        
        host_title_lay = QHBoxLayout()
        host_title_lay.setSpacing(6)
        
        host_icon = QLabel()
        host_icon.setFixedSize(18, 18)
        host_icon.setStyleSheet("border: none; background: transparent; border-radius: 0px; padding: 0px;")
        host_icon.setPixmap(get_svg_pixmap(LUCIDE_HOST_SVG, 18))
        
        host_lbl = QLabel("<b>중계 방 만들기 (Host)</b>")
        host_lbl.setStyleSheet("color: #0a84ff; font-size: 14px; font-weight: 600; border: none; background: transparent;")
        host_title_lay.addWidget(host_icon)
        host_title_lay.addWidget(host_lbl)
        host_title_lay.addStretch()
        host_lay.addLayout(host_title_lay)
        
        srv_ctrl_row = QHBoxLayout()
        srv_ctrl_row.setSpacing(10)
        self.btn_toggle_server = QPushButton("대기실 서버 가동")
        self.btn_toggle_server.setStyleSheet("""
            QPushButton {
                background-color: rgba(10, 132, 255, 0.15);
                border: 1px solid rgba(10, 132, 255, 0.3);
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: rgba(10, 132, 255, 0.25);
            }
        """)
        self.btn_toggle_server.clicked.connect(self.toggle_local_server)
        srv_ctrl_row.addWidget(self.btn_toggle_server, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lbl_server_icon = QLabel()
        self.lbl_server_icon.setFixedSize(16, 16)
        self.lbl_server_icon.setScaledContents(True)
        self.lbl_server_icon.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")
        self.lbl_server_icon.setPixmap(get_svg_pixmap(LUCIDE_STATUS_OFF_SVG, 16))
        srv_ctrl_row.addWidget(self.lbl_server_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        
        self.lbl_server_status = QLabel("서버 상태: 꺼짐")
        self.lbl_server_status.setStyleSheet("color: #aaaaaa; border: none; background: transparent; font-size: 13px;")
        srv_ctrl_row.addWidget(self.lbl_server_status, 0, Qt.AlignmentFlag.AlignVCenter)
        srv_ctrl_row.addStretch()
        host_lay.addLayout(srv_ctrl_row)
        
        lay.addWidget(host_box)
        
        # Guest Connection Group
        guest_box = QFrame()
        guest_box.setStyleSheet("""
            QFrame {
                background-color: rgba(48, 209, 88, 0.04); 
                border: 1px solid rgba(48, 209, 88, 0.18); 
                border-radius: 12px; 
                padding: 12px;
            }
        """)
        guest_lay = QVBoxLayout(guest_box)
        guest_lay.setContentsMargins(12, 12, 12, 12)
        guest_lay.setSpacing(10)
        
        guest_title_lay = QHBoxLayout()
        guest_title_lay.setSpacing(6)
        
        guest_icon = QLabel()
        guest_icon.setFixedSize(18, 18)
        guest_icon.setStyleSheet("border: none; background: transparent; border-radius: 0px; padding: 0px;")
        guest_icon.setPixmap(get_svg_pixmap(LUCIDE_JOIN_SVG, 18))
        
        guest_lbl = QLabel("<b>대기실 접속하기 (Join)</b>")
        guest_lbl.setStyleSheet("color: #30d158; font-size: 14px; font-weight: 600; border: none; background: transparent;")
        guest_title_lay.addWidget(guest_icon)
        guest_title_lay.addWidget(guest_lbl)
        guest_title_lay.addStretch()
        guest_lay.addLayout(guest_title_lay)
        
        ip_row = QHBoxLayout()
        ip_lbl = QLabel("방장 IP주소:")
        ip_lbl.setStyleSheet("border: none; background: transparent; font-size: 12px; color: #cccccc;")
        ip_row.addWidget(ip_lbl)
        self.txt_host_url = QLineEdit(self.parent_window.server_url)
        self.txt_host_url.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: #ffffff;
                padding: 4px 8px;
            }
        """)
        ip_row.addWidget(self.txt_host_url)
        guest_lay.addLayout(ip_row)
        
        conn_row = QHBoxLayout()
        conn_row.setSpacing(10)
        self.btn_toggle_client = QPushButton("방 접속하기")
        self.btn_toggle_client.setStyleSheet("""
            QPushButton {
                background-color: rgba(48, 209, 88, 0.15);
                border: 1px solid rgba(48, 209, 88, 0.3);
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: rgba(48, 209, 88, 0.25);
            }
        """)
        self.btn_toggle_client.clicked.connect(self.toggle_client_connection)
        conn_row.addWidget(self.btn_toggle_client, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lbl_client_icon = QLabel()
        self.lbl_client_icon.setFixedSize(16, 16)
        self.lbl_client_icon.setScaledContents(True)
        self.lbl_client_icon.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")
        self.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_UNLINKED_SVG, 16))
        conn_row.addWidget(self.lbl_client_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        
        self.lbl_client_status = QLabel("접속 상태: 대기")
        self.lbl_client_status.setStyleSheet("color: #aaaaaa; border: none; background: transparent; font-size: 13px;")
        conn_row.addWidget(self.lbl_client_status, 0, Qt.AlignmentFlag.AlignVCenter)
        conn_row.addStretch()
        guest_lay.addLayout(conn_row)
        
        lay.addWidget(guest_box)
        
        # Party Panel Show Toggle
        self.btn_show_panel = QPushButton("파티 현황 켜기")
        self.btn_show_panel.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                padding: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.16);
            }
        """)
        self.btn_show_panel.clicked.connect(self.toggle_party_panel_visible)
        lay.addWidget(self.btn_show_panel)
        
        # Party Panel Click-Through Toggle
        self.btn_panel_click_through = QPushButton("파티 현황 마우스 투과: 끔")
        self.btn_panel_click_through.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 149, 0, 0.08);
                border: 1px solid rgba(255, 149, 0, 0.20);
                border-radius: 10px;
                padding: 8px;
                font-weight: 600;
                color: #ff9500;
            }
            QPushButton:hover {
                background-color: rgba(255, 149, 0, 0.18);
            }
        """)
        self.btn_panel_click_through.clicked.connect(self.toggle_panel_click_through)
        lay.addWidget(self.btn_panel_click_through)
        
        # Party Panel Opacity Slider Group
        opacity_lay = QHBoxLayout()
        opacity_lay.setSpacing(10)
        opacity_lay.setContentsMargins(0, 5, 0, 5)
        
        lbl_opacity_title = QLabel("파티 현황 투명도:")
        lbl_opacity_title.setStyleSheet("font-size: 12px; font-weight: bold; border: none; background: transparent; color: #ff9500;")
        
        self.party_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.party_opacity_slider.setRange(10, 100)
        # Safely read value, fallback to 90
        initial_op = 90
        if self.parent_window and self.parent_window.party_panel:
            initial_op = getattr(self.parent_window.party_panel, 'panel_opacity', 90)
        self.party_opacity_slider.setValue(initial_op)
        self.party_opacity_slider.valueChanged.connect(self.on_party_opacity_changed)
        
        self.lbl_party_opacity_val = QLabel(f"{self.party_opacity_slider.value()}%")
        self.lbl_party_opacity_val.setStyleSheet("font-size: 12px; font-weight: bold; border: none; background: transparent;")
        self.lbl_party_opacity_val.setFixedWidth(35)
        self.lbl_party_opacity_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        opacity_lay.addWidget(lbl_opacity_title)
        opacity_lay.addWidget(self.party_opacity_slider)
        opacity_lay.addWidget(self.lbl_party_opacity_val)
        lay.addLayout(opacity_lay)
        
        self.update_network_tab_texts()
        lay.addStretch()

    # Skill Logic
    def refresh_skill_list(self):
        selected_name = None
        curr = self.skill_list.currentItem()
        if curr:
            selected_name = curr.text()
            
        self.skill_list.clear()
        
        target_item = None
        for name in self.parent_window.detector.slots.keys():
            item = QListWidgetItem(name)
            self.skill_list.addItem(item)
            if name == selected_name:
                target_item = item
                
        if target_item:
            self.skill_list.setCurrentItem(target_item)

    def add_new_skill_slot(self):
        name, ok = get_dark_input_text(self, "스킬 추가", "감지할 스킬 이름을 입력하세요:")
        if ok and name.strip():
            name = name.strip()
            if name in self.parent_window.detector.slots:
                show_dark_message_box(self, "오류", "이미 존재하는 스킬명입니다.", QMessageBox.Icon.Warning)
                return
            self.parent_window.detector.add_slot(name, None)
            self.parent_window.save_settings()  # Auto-save config when slot added
            self.refresh_skill_list()

    def delete_selected_skill(self):
        curr = self.skill_list.currentItem()
        if curr:
            name = curr.text()
            self.parent_window.detector.remove_slot(name)
            self.parent_window.save_settings()  # Auto-save config when slot deleted
            self.refresh_skill_list()
            self.lbl_selected_status.setText("선택된 스킬 없음")

    def capture_selected_skill_area(self):
        curr = self.skill_list.currentItem()
        if not curr:
            show_dark_message_box(self, "선택 필요", "영역을 지정할 스킬을 목록에서 먼저 선택하세요.", QMessageBox.Icon.Warning)
            return
            
        self.hide()  # Hide modal momentarily to allow screen capture below it
        self.parent_window.start_cooldown_area_capture(curr.text(), self)

    def on_skill_selection_changed(self, row):
        curr = self.skill_list.currentItem()
        if not curr:
            self.lbl_selected_status.setText("선택된 스킬 없음")
            self.lbl_skill_img.setText("스냅샷 없음\n(영역 지정 필요)")
            self.lbl_skill_img.setPixmap(QPixmap())
            self.spin_cooldown.setEnabled(False)
            self.spin_cooldown.blockSignals(True)
            self.spin_cooldown.setValue(0)
            self.spin_cooldown.blockSignals(False)
            return
            
        name = curr.text()
        slot = self.parent_window.detector.slots.get(name)
        if slot:
            self.spin_cooldown.setEnabled(True)
            self.spin_cooldown.blockSignals(True)
            self.spin_cooldown.setValue(slot.cooldown_duration)
            self.spin_cooldown.blockSignals(False)
            
        name = curr.text()
        slot = self.parent_window.detector.slots.get(name)
        if slot:
            status = "좌표: 지정 완료" if slot.rect else "좌표: 미지정"
            has_template = " Ready 스냅샷: 있음" if slot.template is not None else " Ready 스냅샷: 없음 (영역 지정 필요)"
            self.lbl_selected_status.setText(f"[{name}] {status} | {has_template}")
            
            # Show visual snapshot preview if available (Prefer color snapshot)
            if slot.template_color is not None:
                try:
                    # Convert 3D RGB numpy array (uint8) to QImage (w * 3 bytes per line)
                    h, w = slot.template_color.shape[:2]
                    qimg = QImage(slot.template_color.data.tobytes(), w, h, w * 3, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    
                    # Smoothly scale to fit inside our 96x96 QLabel keeping aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        self.lbl_skill_img.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.lbl_skill_img.setPixmap(scaled_pixmap)
                except Exception:
                    self.lbl_skill_img.setText("이미지 로드 실패")
                    self.lbl_skill_img.setPixmap(QPixmap())
            elif slot.template is not None:
                try:
                    # Fallback: Convert 2D grayscale numpy array (uint8) to QImage
                    h, w = slot.template.shape[:2]
                    qimg = QImage(slot.template.data.tobytes(), w, h, w, QImage.Format.Format_Grayscale8)
                    pixmap = QPixmap.fromImage(qimg)
                    
                    scaled_pixmap = pixmap.scaled(
                        self.lbl_skill_img.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.lbl_skill_img.setPixmap(scaled_pixmap)
                except Exception:
                    self.lbl_skill_img.setText("이미지 로드 실패")
                    self.lbl_skill_img.setPixmap(QPixmap())
            else:
                self.lbl_skill_img.setText("스냅샷 없음\n(영역 지정 필요)")
                self.lbl_skill_img.setPixmap(QPixmap())

    def on_cooldown_value_changed(self, val):
        curr = self.skill_list.currentItem()
        if curr:
            name = curr.text()
            slot = self.parent_window.detector.slots.get(name)
            if slot:
                slot.cooldown_duration = val
                self.parent_window.save_settings()

    def on_party_opacity_changed(self, value):
        self.lbl_party_opacity_val.setText(f"{value}%")
        if self.parent_window and self.parent_window.party_panel:
            self.parent_window.party_panel.setWindowOpacity(value / 100.0)
            self.parent_window.party_panel.panel_opacity = value
            self.parent_window.save_settings()


    def update_network_tab_texts(self):
        if self.parent_window.server_running:
            self.btn_toggle_server.setText("서버 중지")
            actual_port = self.parent_window.server.port if self.parent_window.server else "?"
            self.lbl_server_status.setText(f"서버 가동 중 (포트 {actual_port})")
            self.lbl_server_status.setStyleSheet("color: #30d158; font-weight: 600; border: none; background: transparent; font-size: 13px;")
            self.lbl_server_icon.setPixmap(get_svg_pixmap(LUCIDE_STATUS_ON_SVG, 16))
        else:
            self.btn_toggle_server.setText("대기실 서버 가동")
            self.lbl_server_status.setText("서버 상태: 꺼짐")
            self.lbl_server_status.setStyleSheet("color: #aaaaaa; border: none; background: transparent; font-size: 13px;")
            self.lbl_server_icon.setPixmap(get_svg_pixmap(LUCIDE_STATUS_OFF_SVG, 16))
            
        if self.parent_window.client_running:
            self.btn_toggle_client.setText("접속 끊기")
            if "정상 연결" not in self.lbl_client_status.text():
                self.lbl_client_status.setText("동기화 연결 중")
            self.lbl_client_status.setStyleSheet("color: #30d158; font-weight: 600; border: none; background: transparent; font-size: 13px;")
            self.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_LINKED_SVG, 16))
        else:
            self.btn_toggle_client.setText("방 접속하기")
            self.lbl_client_status.setText("접속 상태: 대기")
            self.lbl_client_status.setStyleSheet("color: #aaaaaa; border: none; background: transparent; font-size: 13px;")
            self.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_UNLINKED_SVG, 16))
            
        if self.parent_window.party_panel.isVisible():
            self.btn_show_panel.setText("파티 현황 끄기")
        else:
            self.btn_show_panel.setText("파티 현황 켜기")
        
        if self.parent_window.party_panel.panel_click_through:
            self.btn_panel_click_through.setText("파티 현황 마우스 투과: 켬")
            self.btn_panel_click_through.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 149, 0, 0.20);
                    border: 1px solid rgba(255, 149, 0, 0.40);
                    border-radius: 10px;
                    padding: 8px;
                    font-weight: 600;
                    color: #ff9500;
                }
                QPushButton:hover {
                    background-color: rgba(255, 149, 0, 0.30);
                }
            """)
        else:
            self.btn_panel_click_through.setText("파티 현황 마우스 투과: 끔")
            self.btn_panel_click_through.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 149, 0, 0.08);
                    border: 1px solid rgba(255, 149, 0, 0.20);
                    border-radius: 10px;
                    padding: 8px;
                    font-weight: 600;
                    color: #ff9500;
                }
                QPushButton:hover {
                    background-color: rgba(255, 149, 0, 0.18);
                }
            """)

    def toggle_local_server(self):
        if self.parent_window.server_running:
            self.parent_window.stop_party_server()
        else:
            # Read character name from text field BEFORE starting server
            # so auto-join uses the correct player name
            char_name = self.txt_char_name.text().strip()
            if char_name:
                self.parent_window.player_name = char_name
            self.parent_window.start_party_server()
        self.update_network_tab_texts()

    def toggle_client_connection(self):
        char_name = self.txt_char_name.text().strip()
        url = self.txt_host_url.text().strip()
        
        if not char_name:
            show_dark_message_box(self, "이름 필요", "캐릭터명을 정확하게 기입하세요.", QMessageBox.Icon.Warning)
            return
        
        if not url:
            show_dark_message_box(self, "주소 필요", "방장의 IP 주소를 입력하세요.", QMessageBox.Icon.Warning)
            return
            
        self.parent_window.player_name = char_name
        self.parent_window.server_url = url
        self.parent_window.save_settings()
        
        if self.parent_window.client_running:
            self.parent_window.stop_party_client()
        else:
            self.parent_window.start_party_client()
        self.update_network_tab_texts()

    def toggle_party_panel_visible(self):
        if self.parent_window.party_panel.isVisible():
            self.parent_window.party_panel.hide()
        else:
            self.parent_window.party_panel.show()
            self.parent_window.party_panel.activateWindow()
        self.update_network_tab_texts()

    def toggle_panel_click_through(self):
        panel = self.parent_window.party_panel
        panel.set_click_through(not panel.panel_click_through)
        self.parent_window.save_settings()
        self.update_network_tab_texts()

    def save_and_close(self):
        self.parent_window.hotkey_follow = self.temp_follow
        self.parent_window.hotkey_transparent = self.temp_transparent
        self.parent_window.hotkey_hide = self.temp_hide
        
        self.parent_window.player_name = self.txt_char_name.text().strip()
        self.parent_window.server_url = self.txt_host_url.text().strip()
        self.parent_window.hide_ui_on_transparent = self.chk_hide_ui_on_transparent.isChecked()
        
        # Apply updated ui hiding right away
        self.parent_window.update_ui_visibility()
        self.parent_window.save_settings()  # Auto-save changes immediately
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
        if self.is_setting_target is not None:
            if event.button() == Qt.MouseButton.MiddleButton:
                final_hotkey = "Ctrl+MiddleClick"
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
                
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
            
    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
            
    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def showEvent(self, event):
        super().showEvent(event)
        geom = self.geometry()
        target_y = geom.y()
        start_y = target_y + 30
        
        self.move(geom.x(), start_y)
        self.anim_pos = QPropertyAnimation(self, b"pos")
        self.anim_pos.setDuration(220)
        self.anim_pos.setStartValue(QPoint(geom.x(), start_y))
        self.anim_pos.setEndValue(QPoint(geom.x(), target_y))
        self.anim_pos.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim_pos.start()
        
        self.setWindowOpacity(0.0)
        self.anim_opacity = QPropertyAnimation(self, b"windowOpacity")
        self.anim_opacity.setDuration(220)
        self.anim_opacity.setStartValue(0.0)
        self.anim_opacity.setEndValue(1.0)
        self.anim_opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim_opacity.start()

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
        
        # Lucide-style original penguin SVG loader next to clean title label text
        title_layout_row = QHBoxLayout()
        title_layout_row.setSpacing(8)
        title_layout_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_icon = QLabel()
        title_icon.setFixedSize(24, 24)
        title_icon.setPixmap(get_svg_icon(LUCIDE_PENGUIN_SVG).pixmap(24, 24))
        
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
    closed = pyqtSignal()  # Explicitly signal when window closes to restore parent key listener without destroyed lag

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

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

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
        
        self.follow_mouse = True
        self.click_through = False
        self.last_capture_pos = QPoint(0, 0)
        self.is_setting_hotkey = False
        
        # Player states and settings
        self.player_name = "플레이어"
        self.server_url = "http://127.0.0.1:19090"
        self.hide_ui_on_transparent = False  # Feature Toggle
        
        # Initialize detector
        self.detector = cooldown_detector.CooldownDetector()
        self.detector.device_ratio = QApplication.primaryScreen().devicePixelRatio()
        self.detector.state_changed.connect(self.on_skill_state_changed)
        self.detector.start_detection(100)  # Scan every 100ms (runs inside background QThread)
        
        # Network objects
        self.server = None
        self.client = None
        self.server_running = False
        self.client_running = False
        
        # Floating party statuses panel
        self.party_panel = PartyPanel(self)
        
        self.load_settings()
        self.load_icon()
        
        # Register atexit process termination handler for double-safe auto-saving
        atexit.register(self.save_settings)
        
        self.bridge = InputBridge()
        self.bridge.zoom_changed.connect(self.handle_global_zoom)
        self.bridge.toggle_follow.connect(self.toggle_follow)
        self.bridge.toggle_click_through.connect(self.toggle_click_through)
        self.bridge.toggle_hide.connect(self.toggle_hide_mode)
        
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.last_mbutton_pressed = False
        self.is_settings_open = False
        
        self.start_listeners()
        
        # Build global desktop screen coordinates rect to prevent border clipping issues
        self.desktop_rect = QRect()
        for screen in QApplication.screens():
            self.desktop_rect = self.desktop_rect.united(screen.geometry())
            
        self.setup_ui()
        
        # Apply native win32 SendMessageW to guarantee the taskbar icon displays correctly
        force_set_window_icon(int(self.winId()))
        
        self.sct = mss.mss()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_magnifier)
        self.timer.start(16)
        
        # Periodic timer to broadcast current skill states to the party server every 2 seconds
        self.party_sync_timer = QTimer()
        self.party_sync_timer.timeout.connect(self.broadcast_skill_states)
        self.party_sync_timer.start(2000)
        
        self.resize(420, 540)
        self.old_pos = None
        
        self.zoom_slider.setValue(int(self.zoom_factor * 10))
        self.opacity_slider.setValue(self.opacity_value)
        self.setWindowOpacity(self.opacity_value / 100.0)

    def start_listeners(self):
        try:
            self.key_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
            self.key_listener.start()
        except Exception:
            pass

    def pause_listeners(self):
        # We don't recreate listeners anymore, preventing PySide/PyQt cross-thread crashes!
        pass

    def resume_listeners(self):
        # We don't recreate listeners anymore, preventing PySide/PyQt cross-thread crashes!
        pass

    # Capture wheel events on top of the magnifier screen when window is focused
    def wheelEvent(self, event: QWheelEvent):
        # Adjust zoom when Ctrl key is pressed
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            if angle > 0:
                self.handle_global_zoom(1)
            elif angle < 0:
                self.handle_global_zoom(-1)
            event.accept()
        else:
            super().wheelEvent(event)

    def showEvent(self, event):
        force_set_window_icon(int(self.winId()))
        super().showEvent(event)

    def load_icon(self):
        try:
            renderer = QSvgRenderer(QByteArray(LUCIDE_PENGUIN_SVG.encode('utf-8')))
            if renderer.isValid():
                pixmap = QPixmap(256, 256)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                self.setWindowIcon(QIcon(pixmap))
        except Exception:
            pass

    def get_config_path(self):
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'PengZoom')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'config.json')

    def load_settings(self):
        config_path = self.get_config_path()
        
        # Default fallbacks
        self.zoom_factor = 2.0
        self.opacity_value = 100
        self.hotkey_follow = None
        self.hotkey_transparent = "Ctrl+Alt+T"
        self.hotkey_hide = "Ctrl+Alt+H"
        self.player_name = "플레이어"
        self.server_url = "http://127.0.0.1:19090"
        self.hide_ui_on_transparent = False
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.zoom_factor = data.get('zoom_factor', 2.0)
                    self.opacity_value = data.get('opacity', 100)
                    self.hotkey_follow = data.get('hotkey_follow', None)
                    self.hotkey_transparent = data.get('hotkey_transparent', "Ctrl+Alt+T")
                    self.hotkey_hide = data.get('hotkey_hide', "Ctrl+Alt+H")
                    
                    self.player_name = data.get('player_name', "플레이어")
                    self.server_url = data.get('server_url', "http://127.0.0.1:19090")
                    if ":9090" in self.server_url:
                        self.server_url = self.server_url.replace(":9090", ":19090")
                    self.hide_ui_on_transparent = data.get('hide_ui_on_transparent', False)
                    
                    # Restore party panel position and size
                    party_pos = data.get('party_panel_pos', None)
                    if party_pos and len(party_pos) == 2 and self.party_panel:
                        self.party_panel.move(party_pos[0], party_pos[1])
                    
                    party_size = data.get('party_panel_size', None)
                    if party_size and len(party_size) == 2 and self.party_panel:
                        self.party_panel.resize(party_size[0], party_size[1])
                        
                    party_opacity = data.get('party_panel_opacity', 90)
                    if self.party_panel:
                        self.party_panel.panel_opacity = party_opacity
                        self.party_panel.setWindowOpacity(party_opacity / 100.0)
                    
                    # Restore party panel click-through state
                    panel_ct = data.get('party_panel_click_through', False)
                    if panel_ct and self.party_panel:
                        self.party_panel.set_click_through(True)
                    
                    # Restore skill slots and templates (grayscale CV2 matrices) from config
                    skills = data.get('skills', [])
                    templates_dir = os.path.join(os.path.dirname(config_path), 'templates')
                    
                    self.detector.slots.clear()
                    
                    for s_info in skills:
                        name = s_info.get("name")
                        rect_val = s_info.get("rect")
                        threshold = s_info.get("threshold", 0.85)
                        cooldown_duration = s_info.get("cooldown_duration", 0)
                        
                        rect = QRect(rect_val[0], rect_val[1], rect_val[2], rect_val[3]) if rect_val else None
                        
                        template_img = None
                        try:
                            # Use base64 encoding to map skill slot names to safe local file system path formats
                            safe_filename = base64.urlsafe_b64encode(name.encode('utf-8')).decode('utf-8') + ".png"
                            img_path = os.path.join(templates_dir, safe_filename)
                            if os.path.exists(img_path):
                                img_array = np.fromfile(img_path, dtype=np.uint8)
                                bgr_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                if bgr_img is not None:
                                    template_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
                        except Exception:
                            pass
                            
                        self.detector.add_slot(name, rect, threshold, template_img=template_img, cooldown_duration=cooldown_duration)
                    return
            except Exception:
                pass

    def save_settings(self):
        config_path = self.get_config_path()
        try:
            # 1. Serialize and save skill slot configurations & template grayscale arrays safely
            skills_data = []
            templates_dir = os.path.join(os.path.dirname(config_path), 'templates')
            os.makedirs(templates_dir, exist_ok=True)
            
            for name, slot in self.detector.slots.items():
                r = slot.rect
                rect_val = [r.x(), r.y(), r.width(), r.height()] if isinstance(r, QRect) else (list(r) if r else None)
                skills_data.append({
                    "name": name,
                    "rect": rect_val,
                    "threshold": slot.threshold,
                    "cooldown_duration": slot.cooldown_duration
                })
                
                # Write CV2 templates to file with non-ascii Windows compatibility using numpy tofile
                # Save as color RGB (imencoded back as BGR) if template_color is present
                if slot.template_color is not None:
                    try:
                        safe_filename = base64.urlsafe_b64encode(name.encode('utf-8')).decode('utf-8') + ".png"
                        img_path = os.path.join(templates_dir, safe_filename)
                        bgr_img = cv2.cvtColor(slot.template_color, cv2.COLOR_RGB2BGR)
                        is_success, im_buf_arr = cv2.imencode(".png", bgr_img)
                        if is_success:
                            im_buf_arr.tofile(img_path)
                    except Exception:
                        pass
                elif slot.template is not None:
                    try:
                        safe_filename = base64.urlsafe_b64encode(name.encode('utf-8')).decode('utf-8') + ".png"
                        img_path = os.path.join(templates_dir, safe_filename)
                        is_success, im_buf_arr = cv2.imencode(".png", slot.template)
                        if is_success:
                            im_buf_arr.tofile(img_path)
                    except Exception:
                        pass

            party_pos = None
            party_size = None
            party_opacity = 90
            if self.party_panel:
                pos = self.party_panel.pos()
                party_pos = [pos.x(), pos.y()]
                party_size = [self.party_panel.width(), self.party_panel.height()]
                party_opacity = getattr(self.party_panel, 'panel_opacity', 90)

            data = {
                'zoom_factor': self.zoom_factor,
                'opacity': self.opacity_slider.value(),
                'hotkey_follow': self.hotkey_follow,
                'hotkey_transparent': self.hotkey_transparent,
                'hotkey_hide': self.hotkey_hide,
                'player_name': self.player_name,
                'server_url': self.server_url,
                'hide_ui_on_transparent': self.hide_ui_on_transparent,
                'skills': skills_data,
                'party_panel_pos': party_pos,
                'party_panel_size': party_size,
                'party_panel_opacity': party_opacity,
                'party_panel_click_through': self.party_panel.panel_click_through if self.party_panel else False
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
        
        # 1. Top Control Bar (packaged inside a container QWidget for toggle control)
        self.top_control_widget = QWidget()
        top_bar_layout = QHBoxLayout(self.top_control_widget)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(8)
        
        self.select_btn = QPushButton('영역 지정')
        self.select_btn.clicked.connect(self.start_selection)
        top_bar_layout.addWidget(self.select_btn)
        
        self.follow_btn = QPushButton('따라오기: 켬')
        self.follow_btn.setProperty("class", "PrimaryActive")
        self.follow_btn.clicked.connect(self.toggle_follow)
        top_bar_layout.addWidget(self.follow_btn)
        
        top_bar_layout.addStretch()
        
        self.minimize_btn = QPushButton()
        self.minimize_btn.setObjectName('MinimizeBtn')
        self.minimize_btn.setFixedSize(24, 24)
        self.minimize_btn.setIcon(get_svg_icon(LUCIDE_MINIMIZE_SVG))
        self.minimize_btn.clicked.connect(self.showMinimized)
        top_bar_layout.addWidget(self.minimize_btn)
        
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName('SettingsBtn')
        self.settings_btn.setFixedSize(24, 24)
        self.settings_btn.setIcon(get_svg_icon(LUCIDE_SETTINGS_SVG))
        self.settings_btn.clicked.connect(self.show_settings)
        top_bar_layout.addWidget(self.settings_btn)
        
        self.help_btn = QPushButton()
        self.help_btn.setObjectName('HelpBtn')
        self.help_btn.setFixedSize(24, 24)
        self.help_btn.setIcon(get_svg_icon(LUCIDE_HELP_SVG))
        self.help_btn.clicked.connect(self.show_help)
        top_bar_layout.addWidget(self.help_btn)
        
        self.close_btn = QPushButton()
        self.close_btn.setObjectName('CloseBtn')
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setIcon(get_svg_icon(LUCIDE_CLOSE_SVG))
        self.close_btn.clicked.connect(self.close)
        top_bar_layout.addWidget(self.close_btn)
        
        self.main_layout.addWidget(self.top_control_widget)
        
        # 2. Live Magnifier Display Screen (Always visible)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet('border-radius: 12px; background-color: #000000; border: 1px solid rgba(255, 255, 255, 0.1);')
        self.label.setMinimumSize(100, 100)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(self.label)
        
        # 3. Bottom Control Bar (packaged inside a container QWidget for toggle control)
        self.bottom_control_widget = QWidget()
        bottom_bar_layout = QVBoxLayout(self.bottom_control_widget)
        bottom_bar_layout.setContentsMargins(0, 0, 0, 0)
        bottom_bar_layout.setSpacing(10)
        
        # Row for Click-Through Toggle
        config_layout = QHBoxLayout()
        config_layout.setSpacing(8)
        self.click_through_btn = QPushButton('마우스 투과: 끔')
        self.click_through_btn.clicked.connect(self.toggle_click_through)
        config_layout.addWidget(self.click_through_btn)
        bottom_bar_layout.addLayout(config_layout)
        
        # Zoom Factor Slider Control
        zoom_layout = QHBoxLayout()
        zoom_title = QLabel('배율:')
        zoom_title.setFixedWidth(50)
        zoom_layout.addWidget(zoom_title)
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(20)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
        zoom_layout.addWidget(self.zoom_slider)
        
        self.zoom_val_label = QLabel('2.0x')
        self.zoom_val_label.setFixedWidth(40)
        self.zoom_val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        zoom_layout.addWidget(self.zoom_val_label)
        bottom_bar_layout.addLayout(zoom_layout)
        
        # Opacity Slider Control
        opacity_layout = QHBoxLayout()
        opacity_title = QLabel('투명도:')
        opacity_title.setFixedWidth(50)
        opacity_layout.addWidget(opacity_title)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(15, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.on_opacity_slider_changed)
        opacity_layout.addWidget(self.opacity_slider)
        
        self.opacity_val_label = QLabel('100%')
        self.opacity_val_label.setFixedWidth(40)
        self.opacity_val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacity_layout.addWidget(self.opacity_val_label)
        bottom_bar_layout.addLayout(opacity_layout)
        
        self.main_layout.addWidget(self.bottom_control_widget)

    # Dynamic visibility controller for minimalist HUD screen on click-through (now hides container border as well!)
    def update_ui_visibility(self):
        should_hide = self.click_through and self.hide_ui_on_transparent
        
        if should_hide:
            # 1. Capture the exact dimensions and screen coordinates self.label has BEFORE hiding layout
            global_pos = self.label.mapToGlobal(QPoint(0, 0))
            self.last_normal_size = self.size()
            
            w = max(30, self.label.width())
            h = max(30, self.label.height())
            
            # 2. Toggle control bar widgets visibility
            self.top_control_widget.setVisible(False)
            self.bottom_control_widget.setVisible(False)
            
            # 3. Toggle outer ResizableContainer frame style and margins
            self.container.setStyleSheet("""
                #MainContainer {
                    background-color: transparent;
                    border: none;
                }
            """)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.container.grip.hide()
            self.label.setStyleSheet('border-radius: 0px; background-color: #000000; border: none;')
            
            # 4. Dynamically shrink window constraints down to target label size
            self.setMinimumSize(30, 30)
            self.label.setMinimumSize(30, 30)
            self.resize(w, h)
            
            # 5. Relocate window so that the borderless zoom label aligns precisely to its original position
            self.move(global_pos)
        else:
            # 1. Capture the current global screen coordinates of the label
            global_pos = self.label.mapToGlobal(QPoint(0, 0))
            
            # 2. Retrieve previously stored size to restore exactly what the user size adjusted
            target_size = getattr(self, 'last_normal_size', None)
            if target_size is None or target_size.width() < 100 or target_size.height() < 100:
                target_size = self.size()
            
            # 3. Restore larger minimum size constraints for settings mode to prevent overlaps
            self.setMinimumSize(250, 300)
            self.label.setMinimumSize(100, 100)
            
            # 4. Toggle control bar widgets visibility
            self.top_control_widget.setVisible(True)
            self.bottom_control_widget.setVisible(True)
            
            # 5. Restore round corners, outer border frame and resize grip
            self.container.setStyleSheet("""
                #MainContainer {
                    background-color: rgba(28, 28, 30, 0.90);
                    border: 1.5px solid rgba(255, 255, 255, 0.12);
                    border-radius: 18px;
                }
            """)
            self.main_layout.setContentsMargins(16, 16, 16, 16)
            self.container.grip.show()
            self.label.setStyleSheet('border-radius: 12px; background-color: #000000; border: 1px solid rgba(255, 255, 255, 0.1);')
            
            # 6. Restore original window size
            self.resize(target_size.width(), target_size.height())
            
            # 7. Auto position correct: calculate restored margins offset and move window to prevent graphic displacement
            new_label_global = self.label.mapToGlobal(QPoint(0, 0))
            offset_x = new_label_global.x() - self.x()
            offset_y = new_label_global.y() - self.y()
            self.move(global_pos.x() - offset_x, global_pos.y() - offset_y)

    def start_selection(self):
        self.is_settings_open = True
        self.selection_overlay = SelectionOverlay()
        self.selection_overlay.areaSelected.connect(self.on_area_selected)
        self.selection_overlay.closed.connect(self.restore_settings_open_state)
        self.selection_overlay.show()

    def start_cooldown_area_capture(self, skill_name, config_dialog):
        self.cooldown_capture_name = skill_name
        self.config_dialog_ref = config_dialog
        
        self.is_settings_open = True
        
        # Hide the main magnifier window to prevent it from blocking capture overlay Z-order or mouse events
        self.hide()
        
        # Create as independent top-level window so parent hide() doesn't propagate to hide the overlay
        self.overlay = CaptureOverlay()
        self.overlay.capture_completed.connect(self.on_cooldown_area_captured)
        self.overlay.exec()  # Modal exec blocks execution until closed, capturing focus reliably
        self.restore_settings_open_state()

    def restore_settings_open_state(self):
        # Restore the main magnifier window first
        self.show()
        
        self.is_settings_open = hasattr(self, 'config_dialog_ref') and self.config_dialog_ref and self.config_dialog_ref.isVisible()
        # Always restore and show config dialog when capture finishes (success or cancel)
        if hasattr(self, 'config_dialog_ref') and self.config_dialog_ref:
            self.config_dialog_ref.show()
            self.config_dialog_ref.refresh_skill_list()

    def on_cooldown_area_captured(self, x, y, w, h, captured_gray):
        try:
            rect = QRect(x, y, w, h)
            # Add to detector (already cv2 array from CaptureOverlay)
            self.detector.add_slot(self.cooldown_capture_name, rect, threshold=0.85, template_img=captured_gray)
            
            # Auto-save changes immediately to preserve skill slots template images
            self.save_settings()
        except Exception as e:
            import traceback
            with open("capture_error.log", "a", encoding="utf-8") as f:
                f.write(f"Capture Error: {str(e)}\n{traceback.format_exc()}\n")

    def on_skill_state_changed(self, name, is_ready, similarity):
        if is_ready:
            pass  # 비프음 제거됨
            
        # Send update to party server if active
        if self.client_running and self.client:
            slot = self.detector.slots.get(name)
            cooldown_duration = slot.cooldown_duration if slot else 0
            self.client.send_update(name, is_ready, cooldown_duration)

    def broadcast_skill_states(self):
        # Periodically send all registered skill states to keep party server alive and sync initial states
        if self.client_running and self.client:
            for name, slot in self.detector.slots.items():
                self.client.send_update(name, slot.is_ready, slot.cooldown_duration)

    # Server hosting control (uses show_dark_message_box for gorgeous contrast popup)
    def start_party_server(self):
        try:
            self.server = network_manager.CooldownServer()
            self.server.start()
            self.server_running = True
            
            # Update server url to use the dynamically allocated port
            self.server_url = f"http://127.0.0.1:{self.server.port}"
            self.save_settings()
            
            # Dynamically update host url text field in open settings modal
            if hasattr(self, 'config_dialog_ref') and self.config_dialog_ref and self.config_dialog_ref.isVisible():
                self.config_dialog_ref.txt_host_url.setText(self.server_url)
            
            # Auto-join: host also connects as client so their own skill states are broadcast
            if not self.client_running:
                self.start_party_client()
                
        except Exception as e:
            err_msg = str(e)
            user_guide = ""
            if "10013" in err_msg:
                user_guide = "\n\n💡 [대처 요령]: 이 에러는 보안 프로그램(V3, 알약, 디펜더 등) 또는 윈도우 가상화 기능(Hyper-V/WSL)이 네트워크 포트를 차단했을 때 발생합니다. 백신의 실시간 감시를 잠시 끄시거나 방화벽 규칙을 허용해 주세요."
            elif "10048" in err_msg:
                user_guide = "\n\n💡 [대처 요령]: 해당 포트 대역이 이미 사용 중입니다. 백그라운드에 완전히 닫히지 않은 펭구 줌인 프로세스가 떠 있는지 확인해 보세요."
                
            show_dark_message_box(
                self, 
                "서버 오류", 
                f"대기실 서버 가동 중 오류가 발생했습니다:\n{err_msg}{user_guide}", 
                QMessageBox.Icon.Critical
            )

    def stop_party_server(self):
        # Stop client first if it was auto-connected
        if self.client_running:
            self.stop_party_client()
        if self.server:
            try:
                self.server.stop()
            except Exception:
                pass
            self.server = None
        self.server_running = False

    # Client networking control (uses show_dark_message_box for gorgeous contrast popup)
    def start_party_client(self):
        try:
            self.client = network_manager.CooldownClient(
                server_url=self.server_url, 
                player_name=self.player_name
            )
            self.client.status_updated.connect(self.party_panel.update_states)
            self.client.connection_failed.connect(self.on_client_connection_failed)
            self.client.connection_ok.connect(self.on_client_connection_ok)
            self.client.start()
            self.client_running = True
        except Exception as e:
            show_dark_message_box(self, "접속 오류", f"대기실 접속 시도 중 오류가 발생했습니다:\n{str(e)}", QMessageBox.Icon.Critical)

    def on_client_connection_ok(self):
        if hasattr(self, 'config_dialog_ref') and self.config_dialog_ref and self.config_dialog_ref.isVisible():
            self.config_dialog_ref.lbl_client_status.setText("동기화 정상 연결됨")
            self.config_dialog_ref.lbl_client_status.setStyleSheet("color: #30d158; font-weight: 600; border: none; background: transparent;")

    def on_client_connection_failed(self, error_msg):
        # Update settings status label dynamically on connection issues
        if hasattr(self, 'config_dialog_ref') and self.config_dialog_ref and self.config_dialog_ref.isVisible():
            # 영어 에러 메시지를 한글로 변환
            msg_lower = error_msg.lower()
            if 'timed out' in msg_lower or 'timeout' in msg_lower:
                korean_msg = "연결 시간 초과"
            elif 'refused' in msg_lower:
                korean_msg = "서버가 연결을 거부함"
            elif 'no route' in msg_lower or 'unreachable' in msg_lower:
                korean_msg = "서버에 도달할 수 없음"
            elif 'name or service not known' in msg_lower or 'getaddrinfo' in msg_lower:
                korean_msg = "잘못된 서버 주소"
            elif 'connection reset' in msg_lower:
                korean_msg = "연결이 끊어짐"
            elif 'eof' in msg_lower or 'empty' in msg_lower:
                korean_msg = "서버 응답 없음"
            else:
                short_msg = error_msg.split(":")[-1].strip() if ":" in error_msg else error_msg
                korean_msg = short_msg[:25]
            
            self.config_dialog_ref.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_ERROR_SVG, 16))
            self.config_dialog_ref.lbl_client_status.setText(f"실패: {korean_msg}")
            self.config_dialog_ref.lbl_client_status.setStyleSheet("color: #ff453a; font-weight: 600; border: none; background: transparent; font-size: 13px;")

    def stop_party_client(self):
        if self.client:
            try:
                self.client.stop()
            except Exception:
                pass
            self.client = None
        self.client_running = False

    def on_area_selected(self, rect):
        self.is_settings_open = False
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
        self.save_settings()  # Auto-save layout zoom factor

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
        self.save_settings()  # Auto-save follow setting

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
        
        # Refresh UI visible state based on click-through and toggle options
        self.update_ui_visibility()
        self.save_settings()  # Auto-save click-through setting

    def toggle_hide_mode(self):
        # 파티 스킬 모니터가 보이면 최소화 전에 기억해두고 메인만 최소화
        party_was_visible = self.party_panel.isVisible() if self.party_panel else False
        if self.isMinimized():
            self.showNormal()
            self.activateWindow()
            # 메인 복원 시 파티 패널이 원래 보이던 상태였으면 다시 표시
            if party_was_visible and self.party_panel and not self.party_panel.isVisible():
                self.party_panel.show()
        else:
            self.showMinimized()
            # 메인 최소화 후에도 파티 패널은 계속 표시
            if party_was_visible and self.party_panel:
                self.party_panel.show()
                self.party_panel.raise_()

    def on_zoom_slider_changed(self, value):
        self.zoom_factor = value / 10.0
        self.zoom_val_label.setText(f'{self.zoom_factor:.1f}x')
        self.save_settings()  # Auto-save zoom slider changes

    def on_opacity_slider_changed(self, value):
        opacity = value / 100.0
        self.setWindowOpacity(opacity)
        self.opacity_val_label.setText(f'{value}%')
        self.save_settings()  # Auto-save opacity slider changes

    def show_settings(self):
        try:
            self.is_settings_open = True
            dialog = SettingsModal(self)
            self.config_dialog_ref = dialog
            dialog.finished.connect(self.on_settings_closed)
            dialog.show()
        except Exception as e:
            self.is_settings_open = False
            err_msg = f"설정 창 실행 중 예외가 발생했습니다:\n{str(e)}\n\n{traceback.format_exc()}"
            show_dark_message_box(self, "설정 오류", err_msg, QMessageBox.Icon.Critical)

    def on_settings_closed(self, result):
        self.is_settings_open = False
        self.config_dialog_ref = None

    def show_help(self):
        try:
            self.is_settings_open = True
            dialog = HelpModal(self)
            dialog.finished.connect(self.on_help_closed)
            dialog.show()
        except Exception as e:
            self.is_settings_open = False
            err_msg = f"도움말 창 실행 중 예외가 발생했습니다:\n{str(e)}\n\n{traceback.format_exc()}"
            show_dark_message_box(self, "도움말 오류", err_msg, QMessageBox.Icon.Critical)

    def on_help_closed(self, result):
        self.is_settings_open = False

    def update_magnifier(self):
        try:
            # 1. 렉 없는 마우스 휠 클릭 감지 (WH_MOUSE_LL 훅 미사용)
            # VK_MBUTTON = 0x04
            curr_mbutton = (ctypes.windll.user32.GetAsyncKeyState(0x04) & 0x8000) != 0
            
            # 마우스 미들 버튼이 이번 프레임에 막 눌린 경우 (Edge Trigger)
            if curr_mbutton and not self.last_mbutton_pressed:
                if not self.is_setting_hotkey:
                    if self.hotkey_follow:
                        lower_hotkey = self.hotkey_follow.lower()
                        if lower_hotkey == "ctrl+middleclick":
                            is_ctrl = (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) != 0
                            if is_ctrl:
                                self.bridge.toggle_follow.emit()
                        elif lower_hotkey == "shift+middleclick":
                            is_shift = (ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000) != 0
                            if is_shift:
                                self.bridge.toggle_follow.emit()
                        elif lower_hotkey == "alt+middleclick":
                            is_alt = (ctypes.windll.user32.GetAsyncKeyState(0x12) & 0x8000) != 0
                            if is_alt:
                                self.bridge.toggle_follow.emit()
                        elif lower_hotkey == "middleclick":
                            self.bridge.toggle_follow.emit()
            
            self.last_mbutton_pressed = curr_mbutton
        except Exception:
            pass

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
            
            # --- Border Clipping Logic: Prevents box from going outside monitor boundaries ---
            x1 = x - cap_w // 2
            y1 = y - cap_h // 2
            
            # Clamp the top-left coordinate of the capture frame inside the desktop screen resolution bounds
            min_left = self.desktop_rect.left()
            min_top = self.desktop_rect.top()
            max_left = self.desktop_rect.right() - cap_w
            max_top = self.desktop_rect.bottom() - cap_h
            
            cx1 = max(min_left, min(max_left, x1))
            cy1 = max(min_top, min(max_top, y1))
            
            monitor = {
                'top': cy1, 
                'left': cx1, 
                'width': cap_w, 
                'height': cap_h
            }
            
            # Safe screen grab of strictly inner monitor coordinates
            sct_img = self.sct.grab(monitor)
            img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
            
            img = img.resize((view_w, view_h), Image.Resampling.NEAREST)
            img = img.convert('RGBA')
            data = img.tobytes('raw', 'RGBA')
            
            qimg = QImage(data, view_w, view_h, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)
            
            # Draw targeting crosshair
            if self.follow_mouse:
                # Offset crosshair position based on clamped box shift so it stays visually synced
                box_center_x = cx1 + cap_w / 2.0
                box_center_y = cy1 + cap_h / 2.0
                
                diff_x = x - box_center_x
                diff_y = y - box_center_y
                
                render_x = int(view_w / 2.0 + diff_x * self.zoom_factor)
                render_y = int(view_h / 2.0 + diff_y * self.zoom_factor)
                
                painter = QPainter(pixmap)
                painter.setPen(QPen(QColor(255, 69, 58, 200), 1))
                painter.drawLine(render_x - 15, render_y, render_x + 15, render_y)
                painter.drawLine(render_x, render_y - 15, render_x, render_y + 15)
                painter.end()
                
            self.label.setPixmap(pixmap)
        except Exception:
            pass

    def get_display_text(self, val, fallback):
        return val if val else fallback

    def check_hotkey_match(self, parsed_parts, current_key_name):
        target_key = parsed_parts[-1].lower()
        req_ctrl = 'ctrl' in parsed_parts
        req_alt = 'alt' in parsed_parts
        req_shift = 'shift' in parsed_parts
        
        # Real-time state check using Win32 API GetAsyncKeyState to bypass focus/tracking loss
        actual_ctrl = (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) != 0
        actual_alt = (ctypes.windll.user32.GetAsyncKeyState(0x12) & 0x8000) != 0
        actual_shift = (ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000) != 0
        
        if actual_ctrl != req_ctrl or actual_alt != req_alt or actual_shift != req_shift:
            return False
            
        if current_key_name == target_key:
            return True
            
        return False

    def on_key_press(self, key):
        try:
            if self.is_setting_hotkey:
                return
                
            try:
                if hasattr(key, 'char') and key.char:
                    current_key_name = key.char.lower()
                else:
                    current_key_name = str(key).replace('Key.', '').lower()
            except Exception:
                current_key_name = str(key).lower()
                
            # Guarantee non-english layout compatibility by forced virtual key mapping (VK A-Z, 0-9)
            if hasattr(key, 'vk') and key.vk is not None:
                vk = key.vk
                if 65 <= vk <= 90:
                    current_key_name = chr(vk).lower()
                elif 96 <= vk <= 105:
                    current_key_name = str(vk - 96)
                elif 48 <= vk <= 57:
                    current_key_name = str(vk - 48)
                
            if self.is_setting_hotkey:
                return

            if self.hotkey_transparent:
                parts = [p.lower() for p in self.hotkey_transparent.split('+')]
                if self.check_hotkey_match(parts, current_key_name):
                    self.bridge.toggle_click_through.emit()
                    return

            if self.hotkey_hide:
                parts = [p.lower() for p in self.hotkey_hide.split('+')]
                if self.check_hotkey_match(parts, current_key_name):
                    self.bridge.toggle_hide.emit()
                    return

            if self.hotkey_follow:
                parts = [p.lower() for p in self.hotkey_follow.split('+')]
                if self.check_hotkey_match(parts, current_key_name):
                    self.bridge.toggle_follow.emit()
                    return
        except Exception as e:
            try:
                import traceback
                with open("hotkey_error.log", "a", encoding="utf-8") as f:
                    f.write(f"Error in on_key_press: {str(e)}\n{traceback.format_exc()}\n")
            except Exception:
                pass

    def on_key_release(self, key):
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            self.ctrl_pressed = False
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.alt_pressed = False

    def handle_global_zoom(self, direction):
        if direction > 0:
            self.zoom_factor = min(20.0, self.zoom_factor + 0.5)
        else:
            self.zoom_factor = max(1.0, self.zoom_factor - 0.5)
        self.zoom_slider.setValue(int(self.zoom_factor * 10))

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
        self.detector.stop_detection()
        self.stop_party_server()
        self.stop_party_client()
        self.party_panel.close()
        self.pause_listeners()
        super().closeEvent(event)

def kill_zombie_processes():
    try:
        import psutil
        import os
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = proc.info['pid']
                if pid == current_pid:
                    continue
                
                is_target = False
                name = proc.info['name']
                cmdline = proc.info['cmdline'] or []
                
                if name:
                    if "펭구 줌인 Pro" in name or "PengZoomPro" in name:
                        is_target = True
                    elif "python" in name.lower():
                        if any("magnifier.py" in arg for arg in cmdline):
                            is_target = True
                            
                if is_target:
                    p = psutil.Process(pid)
                    p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    kill_zombie_processes()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    # Set global app icon directly from built-in high quality original penguin SVG
    try:
        renderer = QSvgRenderer(QByteArray(LUCIDE_PENGUIN_SVG.encode('utf-8')))
        if renderer.isValid():
            pixmap = QPixmap(256, 256)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            app.setWindowIcon(QIcon(pixmap))
    except Exception:
        pass
        
        # Ensure icon is loaded properly
    window = MagnifierWindow()
    window.show()
    sys.exit(app.exec())
