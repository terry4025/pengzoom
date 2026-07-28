import sys
import os
import json
import time
import math
import re
import mss
import numpy as np
import threading  # Asynchronous threading to prevent mouse lagging
import traceback  # Traceback debugging helper to capture exact popup crashes
import base64
import atexit
import urllib.request
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFrame, QPushButton, QSlider, 
                             QDialog, QSizeGrip, QSizePolicy, QGridLayout, QTabWidget,
                             QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
                             QCheckBox, QSpinBox, QComboBox, QDoubleSpinBox)
from PyQt6.QtCore import (QTimer, Qt, QPoint, QPointF, QRect, QRectF, pyqtSignal, QObject,
                          QSize, QPropertyAnimation, QEasingCurve)
from PyQt6.QtGui import (QImage, QPixmap, QCursor, QPainter, QPainterPath, QPen, QColor,
                         QIcon, QKeySequence, QWheelEvent, QFont, QFontMetrics, QBrush,
                         QPolygonF)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
from pynput import keyboard
import cv2

# Import our custom modules
import cooldown_detector
import network_manager
import boss_debuff_detector
from boss_debuff_panel import BossDebuffBanner, party_state_key
from capture_overlay import CaptureOverlay

# 앱 버전. 창 제목/브랜드 배지/AppUserModelID/빌드 산출물 이름이 모두 이 값을
# 따른다. 이전에는 문자열이 흩어져 있어 한쪽만 올라가는 일이 있었다.
APP_VERSION = "2.49"
APP_NAME = "펭구 줌인"

# Set explicit AppUserModelID on Windows to fix Taskbar Icon grouping and display issues
import ctypes
try:
    myappid = f'terry4025.pengzoom.magnifier.{APP_VERSION}'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# Windows API constants for win32 window modification
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

# Additional Lucide Icons
LUCIDE_LOCK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-lock"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>"""
LUCIDE_LOCK_OPEN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-lock-open"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>"""
LUCIDE_PALETTE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-palette"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.92 0 1.63-.77 1.63-1.7 0-.42-.16-.83-.44-1.14l-.3-.33a.43.43 0 0 1-.1-.28c0-.23.18-.42.41-.42H15c5 0 9-4 9-9c0-5.5-4.5-10-10-10Z"/></svg>"""
LUCIDE_LAYOUT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-layout"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>"""
LUCIDE_EYE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>"""
LUCIDE_SCALE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-maximize-2"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" x2="14" y1="3" y2="10"/><line x1="3" x2="10" y1="21" y2="14"/></svg>"""
LUCIDE_SLIDERS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-sliders-horizontal"><line x1="4" x2="14" y1="4" y2="4"/><line x1="20" x2="20" y1="4" y2="4"/><line x1="4" x2="6" y1="12" y2="12"/><line x1="12" x2="20" y1="12" y2="12"/><line x1="4" x2="14" y1="20" y2="20"/><line x1="20" x2="20" y1="20" y2="20"/><circle cx="17" cy="4" r="3"/><circle cx="9" cy="12" r="3"/><circle cx="17" cy="20" r="3"/></svg>"""
LUCIDE_SPARKLES_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-sparkles"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>"""

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

LUCIDE_LOADER_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0a84ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
</svg>
"""

LUCIDE_ERROR_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ff453a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <line x1="15" y1="9" x2="9" y2="15"/>
  <line x1="9" y1="9" x2="15" y2="15"/>
</svg>
"""

_SVG_STROKE_RE = re.compile(r'stroke="#[0-9a-fA-F]{3,8}"')


def recolor_svg_stroke(svg_str, color_hex):
    """SVG의 stroke 색을 지정 색으로 치환한다.

    Lucide 아이콘 상수들은 stroke 색이 하드코딩(노랑/초록/파랑/빨강)돼 있다.
    v2.46 리디자인은 크롬을 무채색으로 통일하므로 렌더 시점에 톤을 맞춘다.
    """
    return _SVG_STROKE_RE.sub(f'stroke="{color_hex}"', svg_str)


# 메인 창 컨테이너/뷰포트 스타일. 이전에는 동일한 QSS 문자열이 setup_ui와
# update_ui_visibility에 중복돼 있어 한쪽만 고치면 스타일이 어긋났다.
CONTAINER_STYLE_FRAMED = """
    #MainContainer {
        background-color: rgba(22, 22, 25, 0.93);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 18px;
    }
"""

CONTAINER_STYLE_BARE = """
    #MainContainer {
        background-color: transparent;
        border: none;
    }
"""

VIEWPORT_STYLE_FRAMED = (
    'border-radius: 12px; background-color: #000000; '
    'border: 1px solid rgba(255, 255, 255, 0.10);'
)

VIEWPORT_STYLE_BARE = 'border-radius: 0px; background-color: #000000; border: none;'


# ---------------------------------------------------------------------------
# 모달 공용 디자인 시스템
# ---------------------------------------------------------------------------
# 설정/파티설정/도움말 모달이 각자 인라인 QSS를 들고 있어서 탭 모양, 입력창
# 라운드, 버튼 색이 조금씩 달랐다. 팔레트와 컴포넌트 규칙을 한 곳에 모은다.
#
# 색 규칙: 크롬은 전부 무채색, 액센트(#0a84ff)는 '지금 활성/선택된 것' 하나에만.
# 의미색은 상태 표시에만 쓴다(성공 #30d158 / 경고 #ff9f0a / 위험 #ff453a).
UI = {
    "bg": "rgba(22, 22, 25, 0.97)",
    "border": "rgba(255, 255, 255, 0.10)",
    "surface": "rgba(255, 255, 255, 0.04)",
    "surface_hi": "rgba(255, 255, 255, 0.07)",
    "hairline": "rgba(255, 255, 255, 0.07)",
    "text": "#f5f5f7",
    "text_dim": "rgba(245, 245, 247, 0.62)",
    "text_faint": "rgba(245, 245, 247, 0.38)",
    "accent": "#0a84ff",
    "accent_hi": "#2b95ff",
    "ok": "#30d158",
    "warn": "#ff9f0a",
    "danger": "#ff453a",
    "font": "'Segoe UI Variable Display', 'Segoe UI', 'Malgun Gothic', sans-serif",
    "mono": "'Consolas', 'Segoe UI', monospace",
}

_CHECK_ASSET_PATH = None


def get_check_asset_path():
    """체크박스 인디케이터용 체크마크 PNG를 캐시에 생성하고 경로를 돌려준다.

    QSS의 image: 속성은 파일 경로만 받는다. 액센트 채움만으로는 hover와 checked를
    구분하기 어려워 실제 체크마크를 그려 둔다.
    """
    global _CHECK_ASSET_PATH
    if _CHECK_ASSET_PATH:
        return _CHECK_ASSET_PATH
    try:
        path = os.path.join(CACHE_DIR, "ui_check_white.png")
        if not os.path.exists(path):
            pixmap = QPixmap(17, 17)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#ffffff"), 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(QPolygonF([
                QPointF(4.0, 9.0), QPointF(7.2, 12.2), QPointF(13.0, 5.2),
            ]))
            painter.end()
            pixmap.save(path, "PNG")
        # QSS는 백슬래시를 이스케이프로 해석하므로 슬래시로 정규화한다.
        _CHECK_ASSET_PATH = path.replace("\\", "/")
    except Exception:
        _CHECK_ASSET_PATH = ""
    return _CHECK_ASSET_PATH


_CHEVRON_ASSET_PATH = None


def get_chevron_asset_path():
    """콤보박스 드롭다운 화살표용 셰브론 PNG를 캐시에 생성하고 경로를 돌려준다.

    QSS로 ::drop-down 을 커스터마이즈하면 Qt가 네이티브 화살표를 더 이상 그리지
    않는다. 직접 그려서 image: 로 넣어야 '펼칠 수 있는 입력'임이 보인다.
    """
    global _CHEVRON_ASSET_PATH
    if _CHEVRON_ASSET_PATH:
        return _CHEVRON_ASSET_PATH
    try:
        path = os.path.join(CACHE_DIR, "ui_chevron_down.png")
        if not os.path.exists(path):
            pixmap = QPixmap(12, 12)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#c7c7cc"), 1.7)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(QPolygonF([
                QPointF(2.8, 4.6), QPointF(6.0, 7.8), QPointF(9.2, 4.6),
            ]))
            painter.end()
            pixmap.save(path, "PNG")
        _CHEVRON_ASSET_PATH = path.replace("\\", "/")
    except Exception:
        _CHEVRON_ASSET_PATH = ""
    return _CHEVRON_ASSET_PATH


_MODAL_STYLE_CACHE = None


def get_modal_style():
    """모달 공용 QSS를 생성한다(생성 비용이 있어 한 번만 만든다).

    모듈 최상단에서 만들지 않는 이유는 CACHE_DIR 등 아래에서 정의되는 값을
    참조해야 하기 때문이다.
    """
    global _MODAL_STYLE_CACHE
    if _MODAL_STYLE_CACHE is not None:
        return _MODAL_STYLE_CACHE

    check_path = get_check_asset_path()
    check_rule = f"image: url({check_path});" if check_path else ""

    chevron_path = get_chevron_asset_path()
    chevron_rule = f"image: url({chevron_path});" if chevron_path else ""

    _MODAL_STYLE_CACHE = (MODAL_STYLE_TEMPLATE
                          .replace("__CHECK_IMAGE__", check_rule)
                          .replace("__CHEVRON_IMAGE__", chevron_rule))
    return _MODAL_STYLE_CACHE


MODAL_STYLE_TEMPLATE = f"""
    #ModalContainer {{
        background-color: {UI['bg']};
        border: 1px solid {UI['border']};
        border-radius: 18px;
    }}
    QWidget {{
        font-family: {UI['font']};
        color: {UI['text']};
    }}
    QLabel {{
        font-size: 12px;
        background: transparent;
    }}
    /* 모달 제목 / 섹션 제목 / 항목 라벨 / 보조 설명의 4단 위계 */
    QLabel#ModalTitle {{
        font-size: 15px;
        font-weight: 800;
        letter-spacing: 0.2px;
    }}
    QLabel#ModalSubtitle {{
        font-size: 10px;
        font-weight: 600;
        color: {UI['text_faint']};
    }}
    QLabel#SectionTitle {{
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 1.1px;
        color: {UI['text_dim']};
    }}
    QLabel#FieldLabel {{
        font-size: 12px;
        font-weight: 600;
        color: {UI['text_dim']};
    }}
    QLabel#Hint {{
        font-size: 11px;
        color: {UI['text_faint']};
    }}
    QLabel#ValueMono {{
        font-family: {UI['mono']};
        font-size: 12px;
        font-weight: 700;
    }}
    QLabel#StatusOk    {{ font-size: 11px; font-weight: 700; color: {UI['ok']}; }}
    QLabel#StatusWarn  {{ font-size: 11px; font-weight: 700; color: {UI['warn']}; }}
    QLabel#StatusError {{ font-size: 11px; font-weight: 700; color: {UI['danger']}; }}
    QLabel#StatusIdle  {{ font-size: 11px; font-weight: 700; color: {UI['text_faint']}; }}
    QLabel#StatusInfo  {{ font-size: 11px; font-weight: 700; color: {UI['accent']}; }}

    /* 섹션 카드: 관련 설정을 하나의 면으로 묶는다 */
    QFrame#Card {{
        background-color: {UI['surface']};
        border: 1px solid {UI['hairline']};
        border-radius: 12px;
    }}
    QFrame#Divider {{
        background-color: {UI['hairline']};
        border: none;
        max-height: 1px;
        min-height: 1px;
    }}

    /* 탭바를 세그먼티드 컨트롤로. 기존의 테두리 있는 브라우저 탭 모양을 버린다 */
    QTabWidget::pane {{
        border: none;
        background: transparent;
        top: -1px;
    }}
    QTabWidget::tab-bar {{
        alignment: left;
    }}
    QTabBar {{
        qproperty-drawBase: 0;
        background: transparent;
    }}
    QTabBar::tab {{
        background: transparent;
        border: none;
        border-radius: 9px;
        padding: 7px 16px;
        margin-right: 3px;
        color: {UI['text_dim']};
        font-size: 12px;
        font-weight: 600;
    }}
    QTabBar::tab:hover {{
        background: {UI['surface_hi']};
        color: {UI['text']};
    }}
    QTabBar::tab:selected {{
        background: {UI['accent']};
        color: #ffffff;
        font-weight: 700;
    }}

    /* 버튼: 기본은 무채색 고스트, 액센트는 명시적으로 지정할 때만 */
    QPushButton {{
        background-color: {UI['surface_hi']};
        color: {UI['text']};
        border: 1px solid {UI['border']};
        border-radius: 9px;
        padding: 7px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.13);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }}
    QPushButton:pressed {{
        background-color: rgba(255, 255, 255, 0.06);
    }}
    QPushButton:disabled {{
        color: {UI['text_faint']};
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
    }}
    QPushButton#PrimaryBtn, QPushButton#SaveBtn {{
        background-color: {UI['accent']};
        color: #ffffff;
        border: none;
        font-weight: 700;
        padding: 8px 20px;
    }}
    QPushButton#PrimaryBtn:hover, QPushButton#SaveBtn:hover {{
        background-color: {UI['accent_hi']};
    }}
    QPushButton#DangerBtn {{
        background-color: rgba(255, 69, 58, 0.14);
        border: 1px solid rgba(255, 69, 58, 0.32);
        color: {UI['danger']};
    }}
    QPushButton#DangerBtn:hover {{
        background-color: rgba(255, 69, 58, 0.26);
    }}
    QPushButton#SuccessBtn {{
        background-color: rgba(48, 209, 88, 0.14);
        border: 1px solid rgba(48, 209, 88, 0.32);
        color: {UI['ok']};
    }}
    QPushButton#SuccessBtn:hover {{
        background-color: rgba(48, 209, 88, 0.26);
    }}
    /* 단축키 지정처럼 값을 담는 버튼은 입력창처럼 보이게 한다 */
    QPushButton#KeyBtn {{
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid {UI['border']};
        border-radius: 9px;
        font-family: {UI['mono']};
        font-size: 12px;
        font-weight: 700;
        padding: 8px 14px;
    }}
    QPushButton#KeyBtn:hover {{
        border: 1px solid rgba(10, 132, 255, 0.55);
        background-color: rgba(10, 132, 255, 0.10);
    }}
    QPushButton#KeyBtnArmed {{
        background-color: rgba(10, 132, 255, 0.20);
        border: 1px solid {UI['accent']};
        border-radius: 9px;
        font-family: {UI['mono']};
        font-size: 12px;
        font-weight: 700;
        padding: 8px 14px;
        color: #ffffff;
    }}
    /* 아이콘 전용 정사각 버튼 */
    QPushButton#IconBtn {{
        background-color: {UI['surface_hi']};
        border: 1px solid {UI['border']};
        border-radius: 8px;
        padding: 0px;
    }}
    QPushButton#IconBtn:hover {{
        background-color: rgba(255, 255, 255, 0.16);
    }}
    QPushButton#CloseIconBtn {{
        background-color: {UI['surface_hi']};
        border: 1px solid {UI['border']};
        border-radius: 8px;
        padding: 0px;
    }}
    QPushButton#CloseIconBtn:hover {{
        background-color: rgba(255, 69, 58, 0.85);
        border: 1px solid rgba(255, 69, 58, 0.9);
    }}

    QLineEdit {{
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid {UI['border']};
        border-radius: 9px;
        color: {UI['text']};
        padding: 7px 11px;
        font-size: 12px;
        selection-background-color: {UI['accent']};
    }}
    QLineEdit:focus {{
        border: 1px solid {UI['accent']};
        background-color: rgba(10, 132, 255, 0.08);
    }}
    QLineEdit:disabled {{
        color: {UI['text_faint']};
    }}

    QComboBox {{
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid {UI['border']};
        border-radius: 9px;
        padding: 7px 11px;
        color: {UI['text']};
        font-size: 12px;
        font-weight: 600;
    }}
    QComboBox:hover {{
        background-color: {UI['surface_hi']};
        border: 1px solid rgba(255, 255, 255, 0.20);
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox::down-arrow {{
        __CHEVRON_IMAGE__
        width: 12px;
        height: 12px;
    }}
    QComboBox QAbstractItemView {{
        background-color: #1b1b20;
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 10px;
        selection-background-color: {UI['accent']};
        selection-color: #ffffff;
        color: {UI['text']};
        padding: 5px;
        outline: none;
    }}

    QSpinBox, QDoubleSpinBox {{
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid {UI['border']};
        border-radius: 9px;
        padding: 6px 9px;
        color: {UI['text']};
        font-family: {UI['mono']};
        font-size: 12px;
        font-weight: 700;
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {UI['accent']};
    }}

    /* 체크박스: 기본 네이티브 인디케이터 대신 액센트 채움 사각형 */
    QCheckBox {{
        font-size: 12px;
        font-weight: 600;
        color: {UI['text']};
        spacing: 9px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 5px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        background-color: rgba(255, 255, 255, 0.05);
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid rgba(10, 132, 255, 0.65);
    }}
    QCheckBox::indicator:checked {{
        background-color: {UI['accent']};
        border: 1px solid {UI['accent']};
        __CHECK_IMAGE__
    }}

    QSlider {{ background: transparent; }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: rgba(255, 255, 255, 0.14);
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {UI['accent']};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: #ffffff;
        width: 13px;
        height: 13px;
        margin-top: -5px;
        margin-bottom: -5px;
        border-radius: 6px;
    }}

    QListWidget {{
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid {UI['hairline']};
        border-radius: 10px;
        color: {UI['text']};
        font-size: 12px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        border-radius: 7px;
        padding: 7px 9px;
        margin: 1px 2px;
    }}
    QListWidget::item:hover {{
        background-color: {UI['surface_hi']};
    }}
    QListWidget::item:selected {{
        background-color: rgba(10, 132, 255, 0.28);
        color: #ffffff;
    }}

    /* 얇은 오버레이 스크롤바 */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255, 255, 255, 0.18);
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba(255, 255, 255, 0.30);
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
        border: none;
        height: 0px;
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
"""


def build_modal_header(title, subtitle=None, on_close=None, icon_svg=None):
    """모달 상단 헤더(브랜드 마크 + 제목 + 부제 + 닫기)를 만든다.

    기존 모달들은 제목을 가운데 정렬한 라벨 하나로만 두고 닫기 버튼이 없었다.
    메인 창과 같은 좌측 정렬 타이틀바 문법으로 통일한다.

    Returns:
        (QWidget, QPushButton|None) 헤더 위젯과 닫기 버튼
    """
    header = QWidget()
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(9)

    mark = QLabel()
    mark.setFixedSize(22, 22)
    mark.setPixmap(get_svg_pixmap(icon_svg or LUCIDE_PENGUIN_SVG, 22))
    row.addWidget(mark)

    text_box = QWidget()
    text_col = QVBoxLayout(text_box)
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(0)
    title_label = QLabel(title)
    title_label.setObjectName("ModalTitle")
    text_col.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("ModalSubtitle")
        text_col.addWidget(subtitle_label)
    row.addWidget(text_box)
    row.addStretch()

    close_btn = None
    if on_close is not None:
        close_btn = QPushButton()
        close_btn.setObjectName("CloseIconBtn")
        close_btn.setFixedSize(23, 23)
        close_btn.setIcon(get_svg_icon(recolor_svg_stroke(LUCIDE_CLOSE_SVG, "#c7c7cc")))
        close_btn.setIconSize(QSize(13, 13))
        close_btn.setToolTip("닫기")
        close_btn.clicked.connect(on_close)
        row.addWidget(close_btn)

    return header, close_btn


def build_section_card(title, icon_svg=None):
    """섹션 카드를 만든다.

    Returns:
        (QFrame, QVBoxLayout) 카드와 내용을 담을 레이아웃
    """
    card = QFrame()
    card.setObjectName("Card")
    outer = QVBoxLayout(card)
    outer.setContentsMargins(14, 12, 14, 14)
    outer.setSpacing(10)

    if title:
        head = QHBoxLayout()
        head.setSpacing(7)
        if icon_svg:
            icon = QLabel()
            icon.setFixedSize(13, 13)
            icon.setPixmap(get_svg_pixmap(recolor_svg_stroke(icon_svg, "#9a9aa0"), 13))
            head.addWidget(icon)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        head.addWidget(label)
        head.addStretch()
        outer.addLayout(head)

    body = QVBoxLayout()
    body.setSpacing(9)
    outer.addLayout(body)
    return card, body


def build_divider():
    line = QFrame()
    line.setObjectName("Divider")
    return line


def apply_widget_tone(widget, object_name):
    """objectName을 바꿔 공용 QSS 규칙을 다시 적용한다.

    인라인 setStyleSheet 대신 쓰는 경로다. Qt는 objectName만 바꿔도 스타일을
    다시 계산하지 않으므로 unpolish/polish로 강제 갱신해야 한다.
    """
    widget.setObjectName(object_name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# 스킬 Ready 스냅샷 자리표시자. 점선 테두리로 '아직 비어 있음'을 알린다.
SNAPSHOT_PLACEHOLDER_STYLE = f"""
    QLabel {{
        background-color: rgba(0, 0, 0, 0.35);
        border: 1px dashed rgba(255, 255, 255, 0.16);
        border-radius: 9px;
        color: {UI['text_faint']};
        font-size: 11px;
    }}
"""

# 스냅샷이 실제로 채워졌을 때(픽스맵 표시)의 스타일.
SNAPSHOT_FILLED_STYLE = """
    QLabel {
        background-color: rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(48, 209, 88, 0.45);
        border-radius: 9px;
    }
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

# Official Lost Ark class SVG identifiers from the live Class page.
# These SVGs cover the current Korean class roster and remain sharp at HUD size.
LOST_ARK_CLASSES = {
    "버서커": "berserker",
    "디스트로이어": "destroyer",
    "워로드": "warlord",
    "홀리나이트": "holyknight",
    "슬레이어": "slayer",
    "발키리": "valkyrie",
    "스트라이커": "striker",
    "브레이커": "breaker",
    "배틀마스터": "battlemaster",
    "인파이터": "infighter",
    "기공사": "soulmaster",
    "창술사": "lancemaster",
    "블래스터": "blaster",
    "스카우터": "scouter",
    "데빌헌터": "devilhunter",
    "호크아이": "hawkeye",
    "건슬링어": "gunslinger",
    "바드": "bard",
    "서머너": "summoner",
    "아르카나": "arcana",
    "소서리스": "magician",
    "블레이드": "blade",
    "데모닉": "demonic",
    "리퍼": "reaper",
    "소울이터": "souleater",
    "도화가": "artist",
    "기상술사": "aeromancer",
    "환수사": "wildsoul",
    "차원술사": "dimension_master",
    "가디언나이트": "dragon_knight",
}

CLASS_ICON_CDN = "https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/class"
CLASS_ICON_SIZE = 22

# 클래스 아이콘 캐시는 APPDATA에 둔다. 이전에는 소스 실행 시에만 무관한 도구의
# 경로(~/.gemini/antigravity/scratch/cache)를 쓰고 있어서, exe가 이미 받아둔
# 아이콘을 재사용하지 못하고 22개를 다시 내려받았다. config.json도 이미 APPDATA를
# 쓰므로 경로를 통일한다(frozen exe 기준 경로는 그대로다).
_appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
CACHE_DIR = os.path.join(_appdata, 'PengZoom', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Set of class keys that failed to download — skip retry within same session
_icon_download_failed = set()
_icon_download_in_progress = set()
_icon_download_callbacks = {}
_icon_download_lock = threading.Lock()

def is_valid_class_icon(path):
    try:
        if not os.path.exists(path) or os.path.getsize(path) < 500:
            return False
        with open(path, "rb") as icon_file:
            return b"<svg" in icon_file.read(512).lower()
    except OSError:
        return False

def get_class_icon(class_name):
    base_key = LOST_ARK_CLASSES.get(class_name)
    if not base_key:
        return None
    local_path = os.path.join(CACHE_DIR, f"class_{base_key}.svg")
    
    if is_valid_class_icon(local_path):
        return local_path
    
    # Skip if already failed this session
    if base_key in _icon_download_failed:
        return None
    
    url = f"{CLASS_ICON_CDN}/{base_key}.svg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5.0) as res:
            data = res.read()
            if len(data) > 500 and b"<svg" in data[:512].lower():
                with open(local_path, "wb") as f:
                    f.write(data)
                return local_path
            else:
                _icon_download_failed.add(base_key)
                return None
    except Exception:
        _icon_download_failed.add(base_key)
        return None

def get_class_icon_async(class_name, callback):
    """Download once per class and deliver every waiting callback when it completes."""
    base_key = LOST_ARK_CLASSES.get(class_name)
    if not base_key:
        callback(None)
        return
    with _icon_download_lock:
        if base_key in _icon_download_failed:
            callback(None)
            return
        _icon_download_callbacks.setdefault(base_key, []).append(callback)
        if base_key in _icon_download_in_progress:
            return
        _icon_download_in_progress.add(base_key)

    def _worker():
        try:
            path = get_class_icon(class_name)
        finally:
            with _icon_download_lock:
                callbacks = _icon_download_callbacks.pop(base_key, [])
                _icon_download_in_progress.discard(base_key)
        for waiting_callback in callbacks:
            waiting_callback(path)

    threading.Thread(target=_worker, daemon=True).start()

# Preset Styling Themes for Party Overlay
THEMES = {
    "옵시디언 글래스": {
        "bg": "rgba(18, 18, 23, 0.88)",
        "border": "1.2px solid rgba(255, 255, 255, 0.08)",
        "accent": "#0a84ff",        # Premium iOS Royal Blue
        "accent_secondary": "#8e8e93",
        "ready": "#30d158",         # Apple Green
        "cooldown": "#ff9f0a",      # Amber Orange
        "card_bg": "rgba(255, 255, 255, 0.02)",
        "card_border": "1px solid rgba(255, 255, 255, 0.03)",
        "shadow": "rgba(0, 0, 0, 0.45)",
        "font_color": "#f5f5f7"
    },
    "노르딕 라이트": {
        "bg": "rgba(240, 242, 245, 0.92)",
        "border": "1.2px solid rgba(0, 0, 0, 0.06)",
        "accent": "#007aff",        # macOS Blue
        "accent_secondary": "#8e8e93",
        "ready": "#34c759",
        "cooldown": "#ff9500",
        "card_bg": "rgba(0, 0, 0, 0.01)",
        "card_border": "1px solid rgba(0, 0, 0, 0.02)",
        "shadow": "rgba(0, 0, 0, 0.08)",
        "font_color": "#1d1d1f"
    },
    "크림슨 벨벳": {
        "bg": "rgba(26, 18, 20, 0.94)",
        "border": "1.2px solid rgba(255, 59, 48, 0.16)",
        "accent": "#ff3b30",        # Deep Red Accent
        "accent_secondary": "#aeaeb2",
        "ready": "#30d158",
        "cooldown": "#ff453a",
        "card_bg": "rgba(255, 255, 255, 0.02)",
        "card_border": "1px solid rgba(255, 255, 255, 0.03)",
        "shadow": "rgba(255, 59, 48, 0.06)",
        "font_color": "#f5f5f7"
    },
    "미드나이트 오션": {
        "bg": "rgba(11, 21, 36, 0.92)",
        "border": "1.2px solid rgba(100, 210, 255, 0.14)",
        "accent": "#64d2ff",        # Cyan
        "accent_secondary": "#8ea3b8",
        "ready": "#30d158",
        "cooldown": "#ffd60a",
        "card_bg": "rgba(255, 255, 255, 0.02)",
        "card_border": "1px solid rgba(255, 255, 255, 0.03)",
        "shadow": "rgba(0, 0, 0, 0.5)",
        "font_color": "#eaf3ff"
    },
    "포레스트 나이트": {
        "bg": "rgba(13, 26, 20, 0.93)",
        "border": "1.2px solid rgba(50, 215, 75, 0.14)",
        "accent": "#5ac8fa",
        "accent_secondary": "#9bb3a4",
        "ready": "#32d74b",
        "cooldown": "#ff9f0a",
        "card_bg": "rgba(255, 255, 255, 0.02)",
        "card_border": "1px solid rgba(255, 255, 255, 0.03)",
        "shadow": "rgba(0, 0, 0, 0.5)",
        "font_color": "#e9f6ec"
    },
    "로열 바이올렛": {
        "bg": "rgba(24, 18, 38, 0.93)",
        "border": "1.2px solid rgba(191, 90, 242, 0.18)",
        "accent": "#bf5af2",
        "accent_secondary": "#a99cb8",
        "ready": "#30d158",
        "cooldown": "#ff9f0a",
        "card_bg": "rgba(255, 255, 255, 0.02)",
        "card_border": "1px solid rgba(255, 255, 255, 0.03)",
        "shadow": "rgba(0, 0, 0, 0.5)",
        "font_color": "#f2ecff"
    },
    "그래파이트": {
        "bg": "rgba(24, 24, 26, 0.94)",
        "border": "1.2px solid rgba(255, 255, 255, 0.10)",
        "accent": "#a1a1a6",
        "accent_secondary": "#8e8e93",
        "ready": "#30d158",
        "cooldown": "#ff9f0a",
        "card_bg": "rgba(255, 255, 255, 0.02)",
        "card_border": "1px solid rgba(255, 255, 255, 0.04)",
        "shadow": "rgba(0, 0, 0, 0.55)",
        "font_color": "#f5f5f7"
    },
    "아이스 라이트": {
        "bg": "rgba(231, 239, 250, 0.93)",
        "border": "1.2px solid rgba(0, 0, 0, 0.07)",
        "accent": "#0a6cff",
        "accent_secondary": "#6b7a90",
        "ready": "#248a3d",
        "cooldown": "#c25e00",
        "card_bg": "rgba(0, 0, 0, 0.01)",
        "card_border": "1px solid rgba(0, 0, 0, 0.02)",
        "shadow": "rgba(0, 0, 0, 0.10)",
        "font_color": "#16233a"
    },
    "샌드 페이퍼": {
        "bg": "rgba(247, 242, 233, 0.94)",
        "border": "1.2px solid rgba(0, 0, 0, 0.07)",
        "accent": "#a86400",
        "accent_secondary": "#8a7c68",
        "ready": "#248a3d",
        "cooldown": "#c93400",
        "card_bg": "rgba(0, 0, 0, 0.01)",
        "card_border": "1px solid rgba(0, 0, 0, 0.02)",
        "shadow": "rgba(0, 0, 0, 0.09)",
        "font_color": "#2b2320"
    }
}

# ---------------------------------------------------------------------------
# 커스텀 페인팅 기반 파티 HUD 지원 유틸
# ---------------------------------------------------------------------------
# v2.46 이전 구현은 파티원·스킬마다 QFrame/QLabel/GlowDot/CircularProgress
# 위젯을 만들고, 16ms 타이머에서 위젯별로 setStyleSheet()을 다시 호출했다.
# 4인 파티 x 4스킬 기준 초당 약 500회 QSS 재파싱이 일어나고, GlowDot마다
# 독립 QTimer가 붙어 숨겨진 상태에서도 계속 repaint를 트리거했다.
#
# 지금은 PartyPanel 하나가 paintEvent에서 전부 직접 그린다.
#   - 핫 패스의 setStyleSheet 호출: 0회
#   - QTimer: 패널당 1개
#   - 위젯 트리 크기: 파티원 수와 무관하게 고정
# 아래 상태 홀더들이 기존 위젯의 호출 계약(setValue/setText/text/show/hide)을
# 그대로 유지하므로 update_states/tick_timers 로직과 테스트는 변하지 않는다.

_CSS_RGBA_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")
_CSS_PX_RE = re.compile(r"([\d.]+)px")

# 파티 동기화는 '남은 초'를 실어 보낸다. 반올림/네트워크 지연 때문에 같은
# 쿨타임이라도 보고마다 종료 시각이 조금씩 달라지므로, 이 폭 안의 차이는
# 흔들림으로 보고 무시한다. 이보다 크게 늘어난 값만 재사용으로 취급한다.
HUD_DEADLINE_JITTER_SEC = 1.5
HUD_RESTART_MARGIN_SEC = 2.5


def sync_remaining_seconds(detector, name):
    """파티에 보낼 남은 시간. 정밀 값이 있으면 그것을 쓴다."""
    getter = getattr(detector, "get_remaining_seconds_precise", None)
    if callable(getter):
        try:
            return round(max(0.0, float(getter(name))), 2)
        except (TypeError, ValueError):
            pass
    return detector.get_remaining_seconds(name)


def parse_css_color(value, fallback=None):
    """THEMES 프리셋의 '#hex' / 'rgba(r,g,b,a)' 문자열을 QColor로 변환한다."""
    fallback = QColor(255, 255, 255) if fallback is None else QColor(fallback)
    if isinstance(value, QColor):
        return QColor(value)
    if not isinstance(value, str):
        return fallback
    match = _CSS_RGBA_RE.search(value)
    if match:
        red, green, blue, alpha = match.groups()
        alpha_255 = 255 if alpha is None else int(round(float(alpha) * 255))
        return QColor(int(red), int(green), int(blue),
                      max(0, min(255, alpha_255)))
    stripped = value.strip()
    if stripped.startswith("#"):
        color = QColor(stripped)
        if color.isValid():
            return color
    return fallback


def parse_css_border(value, fallback_color=None, fallback_width=1.0):
    """'1.2px solid rgba(...)' 형태를 (QColor, width) 튜플로 변환한다."""
    color = parse_css_color(value, fallback_color or QColor(255, 255, 255, 20))
    width = fallback_width
    if isinstance(value, str):
        match = _CSS_PX_RE.search(value)
        if match:
            try:
                width = float(match.group(1))
            except ValueError:
                width = fallback_width
    return color, max(0.5, width)


# (클래스명, 크기, 색) -> QPixmap. 파티원이 들어올 때마다 SVG를 다시 렌더링해
# UI 스레드를 블로킹하던 문제를 없앤다.
_emblem_cache = {}


def get_class_emblem(class_name, size, color_hex):
    """클래스 엠블럼을 HUD 단색 마스크 QPixmap으로 캐싱해 반환한다.

    캐시에 없고 로컬 SVG도 없으면 None을 돌려준다(호출측이 비동기 다운로드).
    """
    size = max(8, int(size))
    key = (class_name, size, color_hex)
    cached = _emblem_cache.get(key)
    if cached is not None:
        return cached

    base_key = LOST_ARK_CLASSES.get(class_name)
    if not base_key:
        return None
    path = os.path.join(CACHE_DIR, f"class_{base_key}.svg")
    if not is_valid_class_icon(path):
        return None
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return None

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    # 공식 클래스 SVG는 밝은 fill과 어두운 fill이 섞여 있다. 벡터 알파 마스크만
    # 남기고 모든 엠블럼을 HUD 단색으로 정규화한다.
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color_hex))
    painter.end()
    _emblem_cache[key] = pixmap
    return pixmap


class SkillGauge:
    """쿨타임 게이지 상태 홀더. 구 CircularProgress 위젯을 대체한다."""

    __slots__ = ("value", "text", "flash_val", "color", "_visible")

    def __init__(self, color_hex="#ff9f0a"):
        self.value = 100.0
        self.text = ""
        self.flash_val = 0.0
        self.color = QColor(color_hex)
        self._visible = True

    def setValue(self, val):
        try:
            self.value = float(val)
        except (TypeError, ValueError):
            self.value = 0.0

    def setText(self, text):
        self.text = "" if text is None else str(text)

    def setFlash(self, val):
        try:
            self.flash_val = float(val)
        except (TypeError, ValueError):
            self.flash_val = 0.0

    def setColor(self, color_hex):
        self.color = QColor(color_hex)

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def isVisible(self):
        return self._visible


class ReadyPulse:
    """Ready 펄스 상태 홀더. 구 GlowDot과 달리 자체 QTimer를 갖지 않는다."""

    __slots__ = ("color", "speed", "intensity", "_visible")

    def __init__(self, color_hex="#30d158"):
        self.color = QColor(color_hex)
        self.speed = 1.0
        self.intensity = 1.0
        self._visible = True

    def setColor(self, color_hex):
        self.color = QColor(color_hex)

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def isVisible(self):
        return self._visible


class LabelState:
    """텍스트 상태 홀더. 구 QLabel의 text()/setText() 계약만 유지한다."""

    __slots__ = ("_text",)

    def __init__(self, text=""):
        self._text = "" if text is None else str(text)

    def text(self):
        return self._text

    def setText(self, value):
        self._text = "" if value is None else str(value)

    def setStyleSheet(self, _value):
        # 레거시 호출 호환용 no-op. 실제 색상은 PartyPanel.paintEvent가 정한다.
        pass

    def show(self):
        pass

    def hide(self):
        pass

# 파티 HUD 레이아웃 기준값 (ui_scale 배율 적용 전)
HUD_EDGE = 6                  # 리사이즈 히트박스를 확보하는 창 여백
HUD_PAD = 14                  # 컨테이너 내부 여백
HUD_HEADER_H = 30
HUD_NAME_ROW_H = 24
HUD_SKILL_ROW_H = 27          # 스킬명 + 게이지 트랙 한 줄
HUD_SKILL_ROW_H_MIN = 20      # '아이콘만' 모드
HUD_CARD_GAP = 8
HUD_COMPACT_ROW_H = 50
HUD_COMPACT_GAP = 4
HUD_STALE_AFTER_SEC = 6.0     # 이 시간 동안 갱신이 없으면 오프라인으로 표시
# 보고에서 잠깐 빠진 스킬을 곧바로 지우면 위젯이 새로 만들어지면서 진행 바
# 사이클이 리셋된다. 이 시간 동안은 유예한다.
HUD_SKILL_DROP_GRACE_SEC = 5.0

# 약 30fps. 쿨타임 HUD에는 충분하고 기존 16ms 대비 이벤트 루프 부하가 절반이다.
HUD_FRAME_INTERVAL_MS = 33
# Ready 전환 플래시가 약 0.4초간 감쇠하도록 프레임 간격에서 역산한다.
HUD_FLASH_DECAY = HUD_FRAME_INTERVAL_MS / 400.0


class PartyPanel(QWidget):
    icon_downloaded = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent_window = parent
        self.panel_click_through = False
        self.setWindowTitle("파티원 쿨타임 현황")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.theme_name = "옵시디언 글래스"
        self.layout_mode = "표준"
        self.display_mode = "상세 정보"
        self.ui_scale = 1.0
        self.speed = 1.0
        self.intensity = 1.0
        self.player_classes = {}
        self.icon_downloaded.connect(self._deliver_downloaded_icon)

        # 보스 디버프(암흑 수류탄) 배너. 패널 본체는 커스텀 페인팅이지만 배너는
        # 자체 QSS로 완결된 위젯이라 그대로 자식으로 얹고 _relayout에서 배치한다.
        self._boss_local_enabled = False
        self.boss_banner = BossDebuffBanner(self, ui_scale=self.ui_scale)
        self.boss_banner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.boss_banner.setVisible(False)

        self.widgets = {}
        self.panel_opacity = 90
        self.setWindowOpacity(self.panel_opacity / 100.0)

        self.resize_dir = None
        self.drag_position = None
        self.resize_border = 15

        self._hover = False
        self._layout_cache = []
        self._content_height = 0
        self._min_content_width = 0
        self._autofitting = False
        # 사용자가 직접 크기를 조절했는지. True면 자동 맞춤이 축소하지 않는다.
        self._user_sized = False
        self._pulse_origin = time.monotonic()

        self.resize(272, 210)
        self._refresh_palette()
        self._relayout()

        # 패널 전체를 구동하는 단일 타이머. 파티원 수와 무관하게 1개다.
        # 실제 시작은 showEvent에서 한다. 한 번도 표시되지 않은 패널이 프레임을
        # 돌릴 이유가 없고, hideEvent가 다시 멈춘다.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick_timers)

    # ---------------------------------------------------------------- 테마
    def _refresh_palette(self):
        """THEMES 프리셋 문자열을 페인팅용 QColor 팔레트로 변환한다."""
        theme = THEMES.get(self.theme_name) or THEMES["옵시디언 글래스"]

        self._c_bg = parse_css_color(theme.get("bg"), QColor(18, 18, 23, 224))
        self._c_border, self._border_w = parse_css_border(
            theme.get("border"), QColor(255, 255, 255, 20), 1.2)
        self._c_text = parse_css_color(theme.get("font_color"), QColor(245, 245, 247))
        self._c_ready = parse_css_color(theme.get("ready"), QColor(48, 209, 88))
        self._c_cool = parse_css_color(theme.get("cooldown"), QColor(255, 159, 10))
        self._c_accent = parse_css_color(theme.get("accent"), QColor(10, 132, 255))

        # 스킬 이름 상태색: 사용 가능=초록, 쿨타임=빨강. 게이지/숫자에 쓰는
        # cooldown 색(테마에 따라 주황)과 달리 두 상태가 확실히 갈려야 한다.
        self._c_busy = QColor(255, 69, 58)

        self._c_text_dim = QColor(self._c_text)
        self._c_text_dim.setAlpha(130)
        self._c_text_faint = QColor(self._c_text)
        self._c_text_faint.setAlpha(85)

        # 유휴 상태 테두리는 거의 보이지 않게 두고, 호버 시에만 테마 테두리를 쓴다.
        self._c_border_idle = QColor(self._c_border)
        self._c_border_idle.setAlpha(max(6, self._c_border.alpha() // 4))

        # 프리셋의 card_bg는 알파가 0.01~0.02라 어떤 배경에서도 사실상 보이지 않는다.
        # 카드/트랙 대비는 배경 명도에서 직접 유도해 3개 테마 모두 가독성을 보장한다.
        if self._c_bg.lightnessF() > 0.5:
            self._c_card = QColor(0, 0, 0, 13)
            self._c_card_border = QColor(0, 0, 0, 20)
            self._c_track = QColor(0, 0, 0, 32)
            self._c_idle_bar = QColor(0, 0, 0, 34)
            self._c_chrome = QColor(0, 0, 0, 16)
        else:
            self._c_card = QColor(255, 255, 255, 12)
            self._c_card_border = QColor(255, 255, 255, 18)
            self._c_track = QColor(255, 255, 255, 28)
            self._c_idle_bar = QColor(255, 255, 255, 30)
            self._c_chrome = QColor(255, 255, 255, 18)

    def update_theme_styles(self):
        """레거시 호환: QSS 문자열 대신 페인팅 팔레트를 재계산한다."""
        self._refresh_palette()

    def apply_theme(self):
        self._refresh_palette()
        ready_hex = self._c_ready.name()
        cool_hex = self._c_cool.name()
        text_hex = self._c_text.name()
        emblem_size = self._emblem_size()

        for p_data in self.widgets.values():
            class_name = p_data.get("class_name")
            if class_name:
                p_data["emblem"] = get_class_emblem(class_name, emblem_size, text_hex)
            for s_widgets in p_data["skill_widgets"].values():
                s_widgets["glow"].setColor(ready_hex)
                s_widgets["glow"].speed = self.speed
                s_widgets["glow"].intensity = self.intensity
                s_widgets["progress"].setColor(cool_hex)

        # 배너는 자체 QSS를 쓰므로 팔레트와 배율만 넘겨 준다.
        self.boss_banner.apply_scale(self.ui_scale)
        self.boss_banner.apply_theme(THEMES.get(self.theme_name) or THEMES["옵시디언 글래스"])

        self._relayout()
        self._autofit_size()
        self.update()

    # -- boss debuff (암흑 수류탄) -------------------------------------------
    def set_boss_debuff_enabled(self, enabled):
        """로컬 감지 on/off. 꺼도 파티원이 보내온 보고는 계속 표시한다."""
        self._boss_local_enabled = bool(enabled)
        if not enabled:
            self.boss_banner.clear_local()
        self.sync_boss_banner_visibility()

    def sync_boss_banner_visibility(self):
        """로컬 감지 중이거나 최신 파티 보고가 있을 때만 배너를 띄운다."""
        visible = self._boss_local_enabled or self.boss_banner.has_reports()
        if self.boss_banner.isVisible() != visible:
            self.boss_banner.setVisible(visible)
            # 배너가 차지하는 높이가 바뀌므로 카드 배치를 다시 계산한다.
            self._relayout()
            self._autofit_size()
            self.update()

    def update_boss_debuff(self, state):
        self.boss_banner.set_local_state(state or {})
        self.sync_boss_banner_visibility()

    def rebuild_cards(self):
        self.widgets.clear()
        client = getattr(self.parent_window, "client", None) if self.parent_window else None
        if client is not None:
            self.update_states(client.party_states)
        else:
            self._relayout()
            self._autofit_size()
            self.update()

    # ------------------------------------------------------------ 엠블럼
    def _emblem_size(self):
        return max(12, int(round(CLASS_ICON_SIZE * max(0.6, self.ui_scale))))

    def _resolve_emblem(self, class_name, player):
        """캐시/로컬 SVG에서 즉시 가져오고, 없으면 비동기 다운로드를 예약한다."""
        pixmap = get_class_emblem(class_name, self._emblem_size(), self._c_text.name())
        if pixmap is not None:
            return pixmap
        if LOST_ARK_CLASSES.get(class_name):
            get_class_icon_async(
                class_name,
                lambda path, cls=class_name, who=player: self.icon_downloaded.emit(path, (cls, who)))
        return None

    def _deliver_downloaded_icon(self, path, payload):
        """백그라운드 다운로드가 끝나면 해당 파티원의 엠블럼만 갱신한다."""
        if not path or not isinstance(payload, tuple) or len(payload) != 2:
            return
        class_name, player = payload
        p_data = self.widgets.get(player)
        if not p_data:
            # 다운로드가 끝나기 전에 파티원이 사라질 수 있다.
            return
        p_data["emblem"] = get_class_emblem(
            class_name, self._emblem_size(), self._c_text.name())
        if self.isVisible():
            self.update()

    # ----------------------------------------------------------- 레이아웃
    def _is_compact(self):
        return self.layout_mode == "컴팩트"

    def _shows_names(self):
        return self.display_mode != "아이콘만"

    def _skill_status(self, skill, s_widgets, stale):
        """상태 슬롯에 무엇을 그릴지 결정한다.

        남은 초를 아는 동안에는 숫자를, 모르는 동안에는 RDY/CD 같은 약어 대신
        사용자가 설정해 둔 스킬 이름을 상태색(사용 가능=초록, 쿨타임=빨강)으로
        보여준다. '아이콘만' 표시 모드에서는 이름을 숨기는 것이 설정 의도이므로
        기존 약어를 유지한다.

        Returns:
            (문자열, 색, 종류) - 종류는 "number" | "name" | "label"
        """
        is_ready = bool(s_widgets.get("is_ready"))
        raw = s_widgets["status_text_lbl"].text()
        numeric = raw.endswith("s") and not is_ready
        if numeric:
            return raw[:-1], (self._c_text_faint if stale else self._c_cool), "number"
        if not self._shows_names():
            return ("RDY" if is_ready else "CD"), \
                (self._c_text_faint if stale else (self._c_ready if is_ready else self._c_cool)), "label"
        if stale:
            colour = self._c_text_faint
        else:
            colour = self._c_ready if is_ready else self._c_busy
        return str(skill), colour, "name"

    def _relayout(self):
        """카드/행 사각형을 미리 계산해 paintEvent가 산술만 하도록 만든다."""
        scale = max(0.6, float(self.ui_scale or 1.0))
        pad = HUD_PAD * scale
        inner_x = HUD_EDGE + pad
        inner_w = max(90.0, self.width() - (HUD_EDGE + pad) * 2)
        compact = self._is_compact()
        gap = (HUD_COMPACT_GAP if compact else HUD_CARD_GAP) * scale
        row_h = (HUD_SKILL_ROW_H if self._shows_names() else HUD_SKILL_ROW_H_MIN) * scale

        y = HUD_EDGE + pad + HUD_HEADER_H * scale
        cache = []
        max_skills = 1

        # 보스 디버프 배너는 카드 위에 놓인다. 커스텀 페인팅 패널이라 레이아웃이
        # 없으므로 직접 배치하고, 차지한 높이만큼 카드 시작점을 내린다.
        banner_h = 0.0
        if self.boss_banner.isVisible():
            banner_h = max(34.0, self.boss_banner.sizeHint().height() * 1.0)
            self.boss_banner.setGeometry(
                int(inner_x), int(y), int(inner_w), int(banner_h))
            y += banner_h + gap

        for player, p_data in self.widgets.items():
            skills = list(p_data["skill_widgets"].keys())
            max_skills = max(max_skills, len(skills))
            if compact:
                card_h = HUD_COMPACT_ROW_H * scale
            else:
                card_h = 16 * scale + HUD_NAME_ROW_H * scale + max(1, len(skills)) * row_h
            cache.append({
                "player": player,
                "rect": QRectF(inner_x, y, inner_w, card_h),
                "skills": skills,
                "row_h": row_h,
            })
            y += card_h + gap

        if cache:
            y -= gap
        self._layout_cache = cache
        self._content_height = int(math.ceil(
            max(120.0, y + pad + HUD_EDGE)))
        # 컴팩트 모드는 스킬 셀이 가로로 늘어서므로 최소 폭을 확보해야 읽힌다.
        if compact:
            self._min_content_width = int(math.ceil(
                (150 + 58 * max_skills) * scale + (HUD_EDGE + pad) * 2))
        else:
            self._min_content_width = int(math.ceil(210 * scale))

        # 배너는 아이콘 + 이름/상세 + 남은 초를 한 줄에 담아야 읽힌다.
        if self.boss_banner.isVisible():
            self._min_content_width = max(
                self._min_content_width,
                int(math.ceil(232 * scale + (HUD_EDGE + pad) * 2)))

    def _autofit_size(self):
        """내용이 잘리지 않을 최소 크기를 보장한다.

        사용자가 직접 크기를 조절한 뒤에는(_user_sized) 절대 축소하지 않고,
        내용이 현재 크기보다 커질 때만 늘린다. 초기 상태에서는 카드 수에 맞춰
        높이를 정확히 맞춰 준다.
        """
        if self._autofitting:
            return
        target_w = max(self.width(), self._min_content_width)
        if self._user_sized:
            target_h = max(self.height(), self._content_height)
        else:
            target_h = self._content_height
        if target_w == self.width() and abs(self.height() - target_h) <= 1:
            return
        self._autofitting = True
        try:
            self.resize(target_w, target_h)
        finally:
            self._autofitting = False
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def showEvent(self, event):
        self._relayout()
        self._autofit_size()
        if not self.timer.isActive():
            self.timer.start(HUD_FRAME_INTERVAL_MS)
        super().showEvent(event)

    def hideEvent(self, event):
        # 숨겨진 패널이 계속 프레임을 돌리지 않게 한다.
        self.timer.stop()
        super().hideEvent(event)
    def _local_manual_cooldown(self, player, skill):
        """내 캐릭터 스킬이면 로컬 수동 타이머를 그대로 쓴다.

        내 쿨타임은 이미 이 PC에 정확한 값(시작 시각 + 총 쿨타임)으로 있는데,
        예전에는 그걸 서버로 보냈다가 되돌아온 '남은 초' 보고로 다시 복원했다.
        왕복 지연·서버 시각 보정·반올림이 섞이면 종료 시각이 보고마다 미세하게
        달라지고, 그 차이가 진행 바를 조금씩 되돌린다. 왕복을 아예 빼면 그
        원인이 전부 사라진다.

        Returns:
            (종료 시각, 총 쿨타임) 또는 None
        """
        window = self.parent_window
        if not window or not player:
            return None
        if player != getattr(window, "player_name", ""):
            return None
        detector = getattr(window, "detector", None)
        slot = getattr(detector, "slots", {}).get(skill) if detector else None
        if slot is None:
            return None
        started = float(getattr(slot, "cooldown_start_time", 0.0) or 0.0)
        total = float(getattr(slot, "cooldown_duration", 0.0) or 0.0)
        if started <= 0.0 or total <= 0.0:
            return None
        return started + total, total

    def update_states(self, party_states):
        received_at = time.time()
        if not isinstance(party_states, dict):
            party_states = {}
        current_players = set(party_states.keys())

        # 보스 디버프 보고는 파티 채널에 '_' 접두 키로 실려 오므로 아래 스킬
        # 배지 루프가 자동으로 건너뛴다.
        local_name = getattr(self.parent_window, "player_name", "") if self.parent_window else ""
        self.boss_banner.ingest_party_states(party_states, exclude_player=local_name)
        self.sync_boss_banner_visibility()

        # 사라진 파티원 제거. 위젯 트리가 없으므로 deleteLater가 필요 없다.
        for player in list(self.widgets.keys()):
            if player not in current_players:
                del self.widgets[player]

        for player, skills in party_states.items():
            if player not in self.widgets:
                self.widgets[player] = {
                    "skill_widgets": {},
                    "emblem": None,
                    "class_name": "",
                    "latest_timestamp": 0.0,
                    "is_stale": False,
                }
            p_data = self.widgets[player]

            # 서버가 보낸 클래스 또는 로컬 매핑으로 엠블럼을 결정한다.
            if isinstance(skills, dict):
                class_name = skills.get("_class") or self.player_classes.get(player, "홀리나이트")
            else:
                class_name = "홀리나이트"
            self.player_classes[player] = class_name
            if p_data.get("class_name") != class_name or p_data.get("emblem") is None:
                p_data["class_name"] = class_name
                p_data["emblem"] = self._resolve_emblem(class_name, player)

            skill_map = skills if isinstance(skills, dict) else {}
            # 한 프레임 빠진 스킬을 곧바로 지우면 위젯이 새로 만들어지면서
            # 진행 바 사이클이 리셋된다. 잠깐 사라진 건 유예한다.
            missing_since = p_data.setdefault("missing_since", {})
            for known in list(p_data["skill_widgets"].keys()):
                if known in skill_map:
                    missing_since.pop(known, None)
                    continue
                first_missing = missing_since.setdefault(known, received_at)
                if received_at - first_missing >= HUD_SKILL_DROP_GRACE_SEC:
                    del p_data["skill_widgets"][known]
                    missing_since.pop(known, None)

            latest_timestamp = 0.0
            for skill, s_info in skill_map.items():
                if not isinstance(skill, str) or skill.startswith('_') or not isinstance(s_info, dict):
                    continue
                is_ready = bool(s_info.get("is_ready", False))
                try:
                    cooldown_duration = max(0.0, float(s_info.get("cooldown_duration", 0) or 0))
                except (TypeError, ValueError):
                    cooldown_duration = 0.0
                try:
                    timestamp = float(s_info.get("timestamp", 0.0) or 0.0)
                except (TypeError, ValueError):
                    timestamp = 0.0
                latest_timestamp = max(latest_timestamp, timestamp)
                reported_deadline = (
                    timestamp + cooldown_duration
                    if not is_ready and cooldown_duration > 0.0
                    else 0.0
                )
                # 내 스킬은 왕복 보고 대신 로컬 수동 타이머를 그대로 쓴다.
                local_manual = None if is_ready else self._local_manual_cooldown(player, skill)
                if local_manual is not None:
                    reported_deadline, cooldown_duration = local_manual[0], local_manual[1]

                if skill not in p_data["skill_widgets"]:
                    glow = ReadyPulse(self._c_ready.name())
                    glow.speed = self.speed
                    glow.intensity = self.intensity
                    p_data["skill_widgets"][skill] = {
                        "glow": glow,
                        "progress": SkillGauge(self._c_cool.name()),
                        "skill_name_lbl": LabelState(skill),
                        "status_text_lbl": LabelState("Ready"),
                        "is_ready": is_ready,
                        "cooldown_duration": cooldown_duration,
                        "timestamp": timestamp,
                        "cycle_total": cooldown_duration if not is_ready else 0.0,
                        "cooldown_deadline": reported_deadline,
                        "cycle_seq": 1,
                        "gauge_pct": None,
                        "gauge_seq": 0,
                        "flash_val": 0.0,
                        "was_ready": is_ready
                    }
                else:
                    s_widgets = p_data["skill_widgets"][skill]
                    previous_ready = bool(s_widgets.get("is_ready", False))
                    previous_total = max(0.0, float(s_widgets.get("cycle_total", 0.0) or 0.0))
                    previous_deadline = max(0.0, float(s_widgets.get("cooldown_deadline", 0.0) or 0.0))
                    started_new_cycle = False
                    # 늘어난 폭으로 재사용을 판정한다. 남은 시간을 반올림해서
                    # 보내던 시절에는 이 판정이 흔들림에도 걸려, 진행 바가
                    # 쿨타임 도중에 계속 앞쪽으로 되돌아갔다.
                    deadline_delta = (reported_deadline - previous_deadline
                                      if reported_deadline > 0.0 and previous_deadline > 0.0
                                      else 0.0)
                    restarted_while_cooldown = (
                        reported_deadline > 0.0
                        and (previous_deadline <= received_at
                             or deadline_delta > HUD_RESTART_MARGIN_SEC)
                    )

                    if is_ready:
                        cycle_total = 0.0
                        cooldown_deadline = 0.0
                    elif previous_ready:
                        # A Ready -> Cooldown transition starts a new visual cycle.
                        cycle_total = cooldown_duration
                        cooldown_deadline = reported_deadline
                        started_new_cycle = True
                    elif restarted_while_cooldown:
                        # Gauge skills or cooldown resets can start another cycle
                        # without a debounced Ready frame between the two uses.
                        cycle_total = cooldown_duration
                        cooldown_deadline = reported_deadline
                        started_new_cycle = True
                    else:
                        # Periodic sync reports the *remaining* seconds.  Keep the
                        # first total as the ring denominator, ignore differences
                        # inside the jitter band, and only ever move the deadline
                        # earlier (OCR / manual cooldown cut short).
                        cycle_total = max(previous_total, cooldown_duration)
                        if previous_deadline <= 0.0:
                            cooldown_deadline = reported_deadline
                        elif reported_deadline <= 0.0:
                            cooldown_deadline = previous_deadline
                        elif reported_deadline < previous_deadline - HUD_DEADLINE_JITTER_SEC:
                            cooldown_deadline = reported_deadline
                        else:
                            cooldown_deadline = previous_deadline

                    s_widgets["is_ready"] = is_ready
                    s_widgets["cooldown_duration"] = cooldown_duration
                    s_widgets["timestamp"] = timestamp
                    s_widgets["cycle_total"] = cycle_total
                    s_widgets["cooldown_deadline"] = cooldown_deadline
                    if started_new_cycle or is_ready:
                        # 새 사이클에서는 진행 바를 다시 채워도 된다.
                        s_widgets["cycle_seq"] = int(s_widgets.get("cycle_seq", 0)) + 1
                        s_widgets["gauge_pct"] = None

            p_data["latest_timestamp"] = latest_timestamp

        self._relayout()
        self._autofit_size()
        if self.isVisible():
            self.update()

    def tick_timers(self):
        current_time = time.time()

        if self.boss_banner.isVisible():
            self.boss_banner.tick()

        for player, p_data in list(self.widgets.items()):
            latest = float(p_data.get("latest_timestamp", 0.0) or 0.0)
            # 갱신이 끊긴 파티원은 오프라인으로 흐리게 표시한다.
            p_data["is_stale"] = bool(
                latest > 0.0 and (current_time - latest) > HUD_STALE_AFTER_SEC)

            for skill, s_widgets in list(p_data["skill_widgets"].items()):
                is_ready = bool(s_widgets.get("is_ready", False))
                try:
                    cycle_total = max(0.0, float(s_widgets.get("cycle_total", 0) or 0))
                except (TypeError, ValueError):
                    cycle_total = 0.0
                try:
                    cooldown_deadline = max(0.0, float(s_widgets.get("cooldown_deadline", 0) or 0))
                except (TypeError, ValueError):
                    cooldown_deadline = 0.0

                remaining = 0.0
                if not is_ready and cooldown_deadline > 0.0:
                    remaining = max(0.0, cooldown_deadline - current_time)

                if is_ready:
                    if not s_widgets.get("was_ready", True):
                        s_widgets["flash_val"] = 1.0
                    s_widgets["was_ready"] = True
                else:
                    s_widgets["was_ready"] = False

                flash_val = s_widgets.get("flash_val", 0.0)
                if flash_val > 0.0:
                    flash_val = max(0.0, flash_val - HUD_FLASH_DECAY)
                    s_widgets["flash_val"] = flash_val

                gauge = s_widgets["progress"]
                gauge.setFlash(flash_val)

                if is_ready:
                    s_widgets["glow"].show()
                    gauge.hide()
                    gauge.setValue(0.0)
                    s_widgets["gauge_pct"] = None
                    s_widgets["status_text_lbl"].setText("Ready")
                else:
                    s_widgets["glow"].hide()
                    gauge.show()

                    if cycle_total > 0.0 and remaining > 0.0:
                        pct = max(0.0, min(100.0, (remaining / cycle_total) * 100.0))
                        # 한 사이클 안에서 진행 바는 절대 되돌아가지 않는다.
                        # 동기화 보고가 조금 흔들려도 0까지 매끄럽게 줄어든다.
                        cycle_seq = int(s_widgets.get("cycle_seq", 0))
                        previous_pct = s_widgets.get("gauge_pct")
                        if previous_pct is not None and s_widgets.get("gauge_seq") == cycle_seq:
                            pct = min(pct, float(previous_pct))
                        s_widgets["gauge_pct"] = pct
                        s_widgets["gauge_seq"] = cycle_seq
                        gauge.setValue(pct)

                        if remaining >= 1.0:
                            whole = f"{int(math.ceil(remaining))}"
                            gauge.setText(whole)
                            s_widgets["status_text_lbl"].setText(f"{whole}s")
                        else:
                            gauge.setText(f"{remaining:.1f}")
                            s_widgets["status_text_lbl"].setText(f"{remaining:.1f}s")
                    else:
                        # 카운트다운이 0에 닿아도 Ready는 아니다. 게이지 의존 스킬은
                        # Ready 템플릿이 실제로 인식될 때까지 사용 불가로 남는다.
                        gauge.setValue(0.0)
                        gauge.setText("…")
                        s_widgets["gauge_pct"] = 0.0
                        s_widgets["gauge_seq"] = int(s_widgets.get("cycle_seq", 0))
                        s_widgets["status_text_lbl"].setText("Cooldown")

        if self.isVisible():
            self.update()

    # ------------------------------------------------------------- 페인팅
    @staticmethod
    def _fill_round(painter, rect, radius, color):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QBrush(color))

    @staticmethod
    def _stroke_round(painter, rect, radius, color, width=1.0):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.strokePath(path, QPen(color, width))

    @staticmethod
    def _font(size, weight=400, mono=False, spacing=0.0):
        font = QFont("Consolas" if mono else "Segoe UI", max(6, int(round(size))))
        font.setWeight(QFont.Weight(weight))
        if spacing:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        return font

    @staticmethod
    def _elide(painter, text, width):
        return QFontMetrics(painter.font()).elidedText(
            str(text), Qt.TextElideMode.ElideRight, max(10, int(width)))

    @staticmethod
    def _tint(color, alpha):
        tinted = QColor(color)
        tinted.setAlpha(max(0, min(255, int(alpha))))
        return tinted

    def _pulse_scale(self):
        """Ready 표시용 호흡 애니메이션 값(0.0~1.0)."""
        elapsed = time.monotonic() - self._pulse_origin
        speed = max(0.1, float(self.speed or 1.0))
        return 0.5 + 0.5 * math.sin(elapsed * 2 * math.pi * 0.70 * speed)

    def _brand_mark(self, size):
        key = ("__brand__", int(size), "penguin")
        pixmap = _emblem_cache.get(key)
        if pixmap is None:
            pixmap = get_svg_pixmap(LUCIDE_PENGUIN_SVG, int(size))
            _emblem_cache[key] = pixmap
        return pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        scale = max(0.6, float(self.ui_scale or 1.0))
        frame = QRectF(HUD_EDGE, HUD_EDGE,
                       max(1, self.width() - HUD_EDGE * 2),
                       max(1, self.height() - HUD_EDGE * 2))
        radius = 16 * scale

        self._fill_round(painter, frame, radius, self._c_bg)
        border = (self._c_border if (self._hover and not self.panel_click_through)
                  else self._c_border_idle)
        self._stroke_round(painter, frame, radius, border, self._border_w)

        self._paint_header(painter, frame, scale)

        compact = self._is_compact()
        for entry in self._layout_cache:
            p_data = self.widgets.get(entry["player"])
            if not p_data:
                continue
            if compact:
                self._paint_player_compact(painter, entry, p_data, scale)
            else:
                self._paint_player_card(painter, entry, p_data, scale)

        if not self.widgets:
            painter.setPen(QPen(self._c_text_faint))
            painter.setFont(self._font(9 * scale, 500))
            painter.drawText(frame.adjusted(0, HUD_HEADER_H * scale, 0, 0),
                             Qt.AlignmentFlag.AlignCenter, "파티원 접속 대기 중")

    def _paint_header(self, painter, frame, scale):
        pad = HUD_PAD * scale
        x = frame.x() + pad
        width = frame.width() - pad * 2
        height = HUD_HEADER_H * scale
        y = frame.y() + pad * 0.55

        chip = QRectF(x, y + (height - 20 * scale) / 2.0, 20 * scale, 20 * scale)
        self._fill_round(painter, chip, 6 * scale, self._c_chrome)
        mark_size = int(round(14 * scale))
        mark = self._brand_mark(mark_size)
        if mark is not None and not mark.isNull():
            painter.drawPixmap(int(chip.center().x() - mark_size / 2.0),
                               int(chip.center().y() - mark_size / 2.0), mark)

        painter.setPen(QPen(self._c_text_dim))
        painter.setFont(self._font(8 * scale, 700, spacing=1.5 * scale))
        painter.drawText(QRectF(x + 27 * scale, y, max(40.0, width - 120 * scale), height),
                         Qt.AlignmentFlag.AlignVCenter, "PARTY STATUS")

        connected = bool(getattr(self.parent_window, "client_running", False)) if self.parent_window else False
        count = len(self.widgets)
        if connected or count:
            label, accent = f"LIVE {count}", self._c_ready
        else:
            label, accent = "OFFLINE", self._c_text_faint

        badge_w = 54 * scale
        badge = QRectF(frame.right() - pad - badge_w,
                       y + (height - 17 * scale) / 2.0, badge_w, 17 * scale)
        self._fill_round(painter, badge, badge.height() / 2.0, self._tint(accent, 34))
        self._stroke_round(painter, badge, badge.height() / 2.0, self._tint(accent, 80), 1.0)
        painter.setPen(QPen(accent))
        painter.setFont(self._font(7.5 * scale, 700))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_player_card(self, painter, entry, p_data, scale):
        card = entry["rect"]
        skills = entry["skills"]
        row_h = entry["row_h"]
        skill_widgets = p_data["skill_widgets"]
        stale = bool(p_data.get("is_stale"))
        ready_count = sum(1 for s in skills
                          if (skill_widgets.get(s) or {}).get("is_ready"))
        total = len(skills)

        self._fill_round(painter, card, 12 * scale, self._c_card)
        self._stroke_round(painter, card, 12 * scale, self._c_card_border, 1.0)

        # 카드 좌측 상태 바. 준비된 스킬 유무를 주변시로 즉시 알 수 있다.
        bar_color = self._c_ready if (ready_count and not stale) else self._c_idle_bar
        bar = QRectF(card.x() + 1.5 * scale, card.y() + 9 * scale,
                     3 * scale, max(4.0, card.height() - 18 * scale))
        self._fill_round(painter, bar, 1.5 * scale, bar_color)

        content_x = card.x() + 13 * scale
        name_x = content_x
        emblem = p_data.get("emblem")
        if emblem is not None and not emblem.isNull():
            painter.setOpacity(0.4 if stale else 1.0)
            painter.drawPixmap(int(content_x), int(card.y() + 10 * scale), emblem)
            painter.setOpacity(1.0)
            name_x = content_x + emblem.width() + 8 * scale

        summary_w = 78 * scale
        name_rect = QRectF(name_x, card.y() + 8 * scale,
                           max(30.0, card.right() - 13 * scale - summary_w - name_x),
                           HUD_NAME_ROW_H * scale)
        painter.setPen(QPen(self._c_text_faint if stale else self._c_text))
        painter.setFont(self._font(10.5 * scale, 700))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter,
                         self._elide(painter, entry["player"], name_rect.width()))

        painter.setFont(self._font(7.5 * scale, 700))
        if stale:
            painter.setPen(QPen(self._c_text_faint))
            summary = "오프라인"
        else:
            painter.setPen(QPen(self._c_ready if ready_count else self._c_text_faint))
            summary = f"{ready_count}/{total} READY" if total else "대기"
        painter.drawText(QRectF(card.x(), card.y() + 8 * scale,
                                card.width() - 13 * scale, HUD_NAME_ROW_H * scale),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         summary)

        row_y = card.y() + (8 + HUD_NAME_ROW_H) * scale
        row_w = max(40.0, card.right() - 13 * scale - content_x)
        for skill in skills:
            s_widgets = skill_widgets.get(skill)
            if s_widgets is None:
                continue
            self._paint_skill_row(painter, skill, s_widgets,
                                  QRectF(content_x, row_y, row_w, row_h), scale, stale)
            row_y += row_h

    def _paint_skill_row(self, painter, skill, s_widgets, rect, scale, stale):
        show_names = self._shows_names()
        is_ready = bool(s_widgets.get("is_ready"))
        flash = max(0.0, min(1.0, float(s_widgets.get("flash_val", 0.0) or 0.0)))
        gauge = s_widgets["progress"]
        accent = self._c_text_faint if stale else (self._c_ready if is_ready else self._c_cool)
        value_text, value_colour, value_kind = self._skill_status(skill, s_widgets, stale)

        # Ready 행은 배경 틴트로 한 번 더 구분한다.
        if is_ready and not stale:
            self._fill_round(painter,
                             rect.adjusted(-5 * scale, 0, 5 * scale, -2 * scale),
                             7 * scale, self._tint(self._c_ready, 16 + 46 * flash))

        track_h = max(2.0, 3 * scale)
        if show_names:
            text_h = 15 * scale
            track_y = rect.y() + 18 * scale
        else:
            text_h = 12 * scale
            track_y = rect.y() + 13 * scale
        text_rect = QRectF(rect.x(), rect.y(), rect.width(), text_h)
        track = QRectF(rect.x(), track_y, rect.width(), track_h)

        if value_kind == "number":
            value_font = self._font(9 * scale, 700, mono=True)
            value_text = f"{value_text}s"
        elif value_kind == "name":
            value_font = self._font(9.5 * scale, 700)
        else:
            value_font = self._font(7.5 * scale, 700)
            value_text = "READY" if is_ready else "COOLDOWN"

        if value_kind == "name":
            # 남은 초를 모르는 동안에는 스킬 이름 자체가 상태 표시다.
            # 행 전체를 이름에 쓰고 별도 이름표는 그리지 않는다.
            painter.setFont(value_font)
            painter.setPen(QPen(value_colour))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter,
                             self._elide(painter, value_text, text_rect.width()))
        else:
            value_w = 54 * scale
            if show_names:
                painter.setPen(QPen(self._c_text_faint if stale
                                    else (self._c_text if is_ready else self._c_text_dim)))
                painter.setFont(self._font(9 * scale, 600))
                name_w = max(20.0, text_rect.width() - value_w)
                painter.drawText(QRectF(text_rect.x(), text_rect.y(), name_w, text_rect.height()),
                                 Qt.AlignmentFlag.AlignVCenter,
                                 self._elide(painter, skill, name_w))

            painter.setFont(value_font)
            painter.setPen(QPen(value_colour))
            painter.drawText(text_rect,
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             value_text)

        self._fill_round(painter, track, track_h / 2.0, self._c_track)

        has_cycle = float(s_widgets.get("cycle_total", 0.0) or 0.0) > 0.0
        ratio = 1.0 if is_ready else (
            max(0.0, min(1.0, gauge.value / 100.0)) if has_cycle else 0.0)

        if is_ready and not stale:
            # 호흡 헤일로. 준비 완료를 화면을 보지 않고도 감지할 수 있게 한다.
            pulse = self._pulse_scale() * max(0.0, min(2.0, float(self.intensity or 1.0)))
            grow = 1.6 * scale * pulse
            self._fill_round(painter, track.adjusted(0, -grow, 0, grow),
                             (track_h + 2 * grow) / 2.0,
                             self._tint(self._c_ready, 46 + 70 * pulse + 90 * flash))
        if ratio > 0.0:
            self._fill_round(painter,
                             QRectF(track.x(), track.y(),
                                    max(track_h, track.width() * ratio), track_h),
                             track_h / 2.0, accent)

    def _paint_player_compact(self, painter, entry, p_data, scale):
        card = entry["rect"]
        skills = entry["skills"]
        skill_widgets = p_data["skill_widgets"]
        stale = bool(p_data.get("is_stale"))
        ready_count = sum(1 for s in skills
                          if (skill_widgets.get(s) or {}).get("is_ready"))

        self._fill_round(painter, card, 8 * scale, self._c_card)
        self._stroke_round(painter, card, 8 * scale, self._c_card_border, 1.0)

        if ready_count and not stale:
            marker = QPainterPath()
            mid = card.center().y()
            marker.moveTo(card.x() + 5 * scale, mid - 5 * scale)
            marker.lineTo(card.x() + 11 * scale, mid)
            marker.lineTo(card.x() + 5 * scale, mid + 5 * scale)
            marker.closeSubpath()
            painter.fillPath(marker, QBrush(self._c_ready))

        info_x = card.x() + 16 * scale
        emblem = p_data.get("emblem")
        if emblem is not None and not emblem.isNull():
            painter.setOpacity(0.4 if stale else 1.0)
            painter.drawPixmap(int(info_x),
                               int(card.center().y() - emblem.height() / 2.0), emblem)
            painter.setOpacity(1.0)
            info_x += emblem.width() + 8 * scale

        name_w = 84 * scale
        painter.setPen(QPen(self._c_text_faint if stale else self._c_text))
        painter.setFont(self._font(9.5 * scale, 700))
        painter.drawText(QRectF(info_x, card.y() + 7 * scale, name_w, 15 * scale),
                         Qt.AlignmentFlag.AlignVCenter,
                         self._elide(painter, entry["player"], name_w))
        painter.setPen(QPen(self._c_text_faint))
        painter.setFont(self._font(7 * scale, 500))
        painter.drawText(QRectF(info_x, card.bottom() - 21 * scale, name_w, 14 * scale),
                         Qt.AlignmentFlag.AlignVCenter,
                         self._elide(painter,
                                     "오프라인" if stale else p_data.get("class_name", ""),
                                     name_w))

        cell_x = info_x + name_w + 6 * scale
        available = max(30.0, card.right() - 10 * scale - cell_x)
        cell_w = available / max(1, len(skills))
        for skill in skills:
            s_widgets = skill_widgets.get(skill)
            if s_widgets is None:
                continue
            cell = QRectF(cell_x, card.y() + 5 * scale,
                          max(26.0, cell_w - 5 * scale), card.height() - 10 * scale)
            self._paint_skill_cell(painter, skill, s_widgets, cell, scale, stale)
            cell_x += cell_w

    def _paint_skill_cell(self, painter, skill, s_widgets, cell, scale, stale):
        is_ready = bool(s_widgets.get("is_ready"))
        flash = max(0.0, min(1.0, float(s_widgets.get("flash_val", 0.0) or 0.0)))
        gauge = s_widgets["progress"]
        accent = self._c_text_faint if stale else (self._c_ready if is_ready else self._c_cool)
        value_text, value_colour, value_kind = self._skill_status(skill, s_widgets, stale)

        if is_ready and not stale:
            self._fill_round(painter, cell, 4 * scale,
                             self._tint(self._c_ready, 26 + 50 * flash))
            self._stroke_round(painter, cell, 4 * scale,
                               self._tint(self._c_ready, 96), 1.0)
        else:
            self._fill_round(painter, cell, 4 * scale, self._c_chrome)
            self._stroke_round(painter, cell, 4 * scale, self._c_card_border, 1.0)

        # 상태 슬롯이 이미 스킬 이름을 보여줄 때 위쪽 이름표는 중복이다.
        show_header = self._shows_names() and value_kind != "name"
        if show_header:
            painter.setPen(QPen(self._c_text_faint))
            painter.setFont(self._font(7 * scale, 600))
            painter.drawText(QRectF(cell.x() + 5 * scale, cell.y() + 3 * scale,
                                    cell.width() - 10 * scale, 12 * scale),
                             Qt.AlignmentFlag.AlignVCenter,
                             self._elide(painter, skill, cell.width() - 10 * scale))
            value_y = cell.y() + 14 * scale
        else:
            value_y = cell.y() + 8 * scale

        painter.setPen(QPen(value_colour))
        if value_kind == "number":
            painter.setFont(self._font(13 * scale, 800, mono=True))
        elif value_kind == "name":
            painter.setFont(self._font(8.5 * scale, 800))
            value_y = cell.y() + (cell.height() - 26 * scale) / 2.0
        else:
            painter.setFont(self._font(11 * scale if is_ready else 8 * scale, 800))
        value_rect = QRectF(cell.x() + 2 * scale, value_y,
                            max(10.0, cell.width() - 4 * scale), 20 * scale)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter,
                         self._elide(painter, value_text, value_rect.width()))

        track_h = max(2.0, 2 * scale)
        track = QRectF(cell.x() + 4 * scale, cell.bottom() - 6 * scale,
                       max(8.0, cell.width() - 8 * scale), track_h)
        self._fill_round(painter, track, track_h / 2.0, self._c_track)

        has_cycle = float(s_widgets.get("cycle_total", 0.0) or 0.0) > 0.0
        ratio = 1.0 if is_ready else (
            max(0.0, min(1.0, gauge.value / 100.0)) if has_cycle else 0.0)
        if ratio > 0.0:
            self._fill_round(painter,
                             QRectF(track.x(), track.y(),
                                    max(track_h, track.width() * ratio), track_h),
                             track_h / 2.0, accent)

    # -------------------------------------------------------- 마우스/호버
    def enterEvent(self, event):
        if not self.panel_click_through:
            self._hover = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._hover:
            self._hover = False
            self.update()
        super().leaveEvent(event)

    # 리사이즈 방향 -> 커서 매핑. 모서리는 대각 커서를 준다.
    _RESIZE_CURSORS = {
        "Left": Qt.CursorShape.SizeHorCursor,
        "Right": Qt.CursorShape.SizeHorCursor,
        "Top": Qt.CursorShape.SizeVerCursor,
        "Bottom": Qt.CursorShape.SizeVerCursor,
        "TopLeft": Qt.CursorShape.SizeFDiagCursor,
        "BottomRight": Qt.CursorShape.SizeFDiagCursor,
        "TopRight": Qt.CursorShape.SizeBDiagCursor,
        "BottomLeft": Qt.CursorShape.SizeBDiagCursor,
    }

    def _resize_zone(self, pos):
        """커서 위치가 어느 리사이즈 영역인지 판정한다.

        네 변과 네 모서리를 모두 지원한다. 모서리 히트박스를 변보다 넓게 잡아야
        실제로 집기 쉬우므로 corner를 우선 판정한다.
        """
        border = self.resize_border
        corner = border + 6
        width, height = self.width(), self.height()
        x, y = pos.x(), pos.y()

        near_left = x <= border
        near_right = x >= width - border
        near_top = y <= border
        near_bottom = y >= height - border

        corner_left = x <= corner
        corner_right = x >= width - corner
        corner_top = y <= corner
        corner_bottom = y >= height - corner

        if corner_top and corner_left:
            return "TopLeft"
        if corner_top and corner_right:
            return "TopRight"
        if corner_bottom and corner_left:
            return "BottomLeft"
        if corner_bottom and corner_right:
            return "BottomRight"
        if near_left:
            return "Left"
        if near_right:
            return "Right"
        if near_top:
            return "Top"
        if near_bottom:
            return "Bottom"
        return None

    def _apply_resize(self, zone, global_pos):
        """드래그 중인 방향에 맞춰 지오메트리를 갱신한다.

        좌/상단을 잡으면 창 위치까지 움직여야 반대편 변이 고정된 것처럼 보인다.
        높이를 사용자가 직접 조절할 수 있어야 하므로, 내용 기반 자동 맞춤은
        '최소 높이'로만 작동한다(_user_sized 플래그).
        """
        geometry = self.geometry()
        min_w = max(160, self._min_content_width)
        min_h = max(90, self._content_height)

        left, top = geometry.left(), geometry.top()
        right, bottom = geometry.right(), geometry.bottom()

        if "Left" in zone:
            left = min(global_pos.x(), right - min_w + 1)
        if "Right" in zone:
            right = max(global_pos.x(), left + min_w - 1)
        if "Top" in zone:
            top = min(global_pos.y(), bottom - min_h + 1)
        if "Bottom" in zone:
            bottom = max(global_pos.y(), top + min_h - 1)

        self._user_sized = True
        self.setGeometry(QRect(QPoint(left, top), QPoint(right, bottom)))

    def mousePressEvent(self, event):
        if self.panel_click_through:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            zone = self._resize_zone(event.position().toPoint())
            if zone:
                self.resize_dir = zone
                self.drag_position = None
            else:
                self.resize_dir = None
                self.drag_position = (event.globalPosition().toPoint()
                                      - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if self.panel_click_through:
            return
        if event.buttons() == Qt.MouseButton.NoButton:
            # 호버만으로 어느 방향으로 늘릴 수 있는지 커서로 알려준다.
            zone = self._resize_zone(event.position().toPoint())
            self.setCursor(self._RESIZE_CURSORS.get(zone, Qt.CursorShape.SizeAllCursor)
                           if zone else Qt.CursorShape.SizeAllCursor)
        elif event.buttons() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            if self.resize_dir:
                self._apply_resize(self.resize_dir, global_pos)
            elif self.drag_position is not None:
                self.move(global_pos - self.drag_position)

    def mouseReleaseEvent(self, event):
        self.resize_dir = None
        self.drag_position = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.parent_window:
            self.parent_window.save_settings()

    def set_click_through(self, enabled):
        self.panel_click_through = enabled
        hwnd = int(self.winId())
        try:
            import ctypes
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enabled:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        except Exception:
            # Fallback
            if enabled:
                self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowTransparentForInput)
            else:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowTransparentForInput)
            self.show()

    def closeEvent(self, event):
        if self.parent_window:
            self.parent_window.save_settings()
        super().closeEvent(event)


def scale_bgra_frame_to_qimage(bgra_bytes, src_w, src_h, view_w, view_h):
    """mss의 BGRA 버퍼를 nearest-neighbor로 확대해 QImage로 변환한다.

    v2.46 이전에는 PIL로 frombytes -> resize -> convert('RGBA') -> tobytes를
    거쳐 프레임마다 대형 버퍼를 4번 할당했다. 60fps에서 임시 메모리 처리량이
    수백 MB/s에 달해 GC 부담이 컸다. 여기서는 numpy 인덱싱 한 번으로 끝낸다.

    QImage는 전달된 버퍼를 복사하지 않으므로, 호출측이 QPixmap으로 변환하기
    전까지 살아 있어야 하는 numpy 배열을 함께 돌려준다.

    Returns:
        (QImage, numpy.ndarray) 또는 유효하지 않은 입력이면 (None, None)
    """
    if src_w <= 0 or src_h <= 0 or view_w <= 0 or view_h <= 0:
        return None, None

    frame = np.frombuffer(bgra_bytes, dtype=np.uint8).reshape(src_h, src_w, 4)

    # 정수 인덱스 매핑. PIL의 Resampling.NEAREST와 동일하게 출력 픽셀의
    # '중심'을 원본으로 되돌려 샘플링한다((i + 0.5) * src / view).
    # 좌상단 편향을 막기 위해 floor(i * src / view)를 쓰지 않는다.
    rows = ((np.arange(view_h, dtype=np.int64) * 2 + 1) * src_h) // (view_h * 2)
    cols = ((np.arange(view_w, dtype=np.int64) * 2 + 1) * src_w) // (view_w * 2)

    # mss의 알파 채널은 신뢰할 수 없다. BGR 3채널만 넘기면 채널 스왑도 생략된다.
    buffer = np.ascontiguousarray(frame[rows[:, None], cols[None, :], :3])
    image = QImage(buffer.data, view_w, view_h, buffer.strides[0],
                   QImage.Format.Format_BGR888)
    return image, buffer


class PartyOverlaySettingsModal(QDialog):
    def __init__(self, parent_window, parent_dialog=None):
        super().__init__(parent_dialog or parent_window)
        self.parent_window = parent_window
        self.overlay = parent_window.party_panel
        self.setWindowTitle("파티 현황 설정")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setStyleSheet(get_modal_style())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setObjectName("ModalContainer")
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(20, 16, 20, 18)
        container_lay.setSpacing(12)

        header, _ = build_modal_header(
            "파티 현황 설정",
            "PARTY HUD",
            on_close=self.close_and_save,
            icon_svg=LUCIDE_PALETTE_SVG,
        )
        container_lay.addWidget(header)
        container_lay.addWidget(build_divider())

        # 1. Class Selection Group (Dynamic from active party states)
        class_group, cg_lay = build_section_card("직업 설정", LUCIDE_USER_SVG)

        self.class_combos = {}
        player = self.parent_window.player_name

        p_lay = QHBoxLayout()
        p_lay.setSpacing(8)
        lbl = QLabel(player)
        lbl.setObjectName("FieldLabel")
        lbl.setMinimumWidth(92)

        combo = QComboBox()
        combo.addItems(list(LOST_ARK_CLASSES.keys()))
        default_val = getattr(self.parent_window, 'player_class', "홀리나이트")
        combo.setCurrentText(default_val)
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.currentTextChanged.connect(lambda text, p=player: self.change_player_class(p, text))

        p_lay.addWidget(lbl)
        p_lay.addWidget(combo, 1)
        cg_lay.addLayout(p_lay)
        self.class_combos[player] = combo

        container_lay.addWidget(class_group)

        # 2. 외형 카드: 테마 / 밀도 / 표시 모드
        look_card, look_body = build_section_card("외형", LUCIDE_PALETTE_SVG)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        # Theme Preset
        theme_lbl = QLabel("테마 프리셋")
        theme_lbl.setObjectName("FieldLabel")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        if self.overlay:
            self.theme_combo.setCurrentText(self.overlay.theme_name)
        self.theme_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        grid.addWidget(theme_lbl, 0, 0)
        grid.addWidget(self.theme_combo, 0, 1)

        # Density Mode (표준 = 카드형, 컴팩트 = 행 단위 테이블형)
        layout_lbl = QLabel("밀도 모드")
        layout_lbl.setObjectName("FieldLabel")
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["표준", "컴팩트"])
        if self.overlay:
            self.layout_combo.setCurrentText(self.overlay.layout_mode)
        self.layout_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.layout_combo.currentTextChanged.connect(self.change_layout)
        grid.addWidget(layout_lbl, 1, 0)
        grid.addWidget(self.layout_combo, 1, 1)

        # Display Mode
        display_lbl = QLabel("세부 표시 모드")
        display_lbl.setObjectName("FieldLabel")
        self.display_combo = QComboBox()
        self.display_combo.addItems(["상세 정보", "아이콘만"])
        if self.overlay:
            self.display_combo.setCurrentText(self.overlay.display_mode)
        self.display_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.display_combo.currentTextChanged.connect(self.change_display)
        grid.addWidget(display_lbl, 2, 0)
        grid.addWidget(self.display_combo, 2, 1)

        look_body.addLayout(grid)

        # Click-Through Toggle Row (Moved from main settings dialog)
        self.btn_panel_click_through = QPushButton()
        self.btn_panel_click_through.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_panel_click_through.clicked.connect(self.toggle_panel_click_through)
        self.update_click_through_button_text()
        look_body.addWidget(self.btn_panel_click_through)
        container_lay.addWidget(look_card)

        # 3. 미세 조정 카드: 크기 / 투명도 / 펄스 속도
        tune_card, tune_body = build_section_card("미세 조정", LUCIDE_SLIDERS_SVG)

        def add_slider_row(caption, value_text):
            """'라벨 ...... 현재값' 한 행과 그 아래 슬라이더를 만든다."""
            row = QHBoxLayout()
            row.setSpacing(8)
            caption_label = QLabel(caption)
            caption_label.setObjectName("FieldLabel")
            value_label = QLabel(value_text)
            value_label.setObjectName("ValueMono")
            row.addWidget(caption_label)
            row.addStretch()
            row.addWidget(value_label)
            tune_body.addLayout(row)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setCursor(Qt.CursorShape.PointingHandCursor)
            tune_body.addWidget(slider)
            return slider, value_label

        # UI Scale
        self.scale_slider, self.lbl_scale_val = add_slider_row("크기 스케일", "1.0x")
        self.scale_slider.setRange(8, 15)
        if self.overlay:
            self.scale_slider.setValue(int(self.overlay.ui_scale * 10))
            self.lbl_scale_val.setText(f"{self.overlay.ui_scale:.1f}x")
        self.scale_slider.valueChanged.connect(self.change_scale)

        # Opacity (Moved from main settings dialog)
        self.opacity_slider, self.lbl_opacity_val = add_slider_row("투명도", "90%")
        self.opacity_slider.setRange(20, 100)
        if self.overlay:
            self.opacity_slider.setValue(int(self.overlay.panel_opacity))
            self.lbl_opacity_val.setText(f"{self.overlay.panel_opacity}%")
        self.opacity_slider.valueChanged.connect(self.change_opacity)

        # Ready Dot Speed
        self.speed_slider, self.lbl_speed_val = add_slider_row("Ready 도트 펄스 속도", "1.0x")
        self.speed_slider.setRange(5, 20)
        if self.overlay:
            self.speed_slider.setValue(int(self.overlay.speed * 10))
            self.lbl_speed_val.setText(f"{self.overlay.speed:.1f}x")
        self.speed_slider.valueChanged.connect(self.change_speed)

        container_lay.addWidget(tune_card)
        container_lay.addStretch()

        # Close Button
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        close_btn = QPushButton("확인")
        close_btn.setObjectName("PrimaryBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_and_save)
        btn_lay.addWidget(close_btn)
        container_lay.addLayout(btn_lay)

        layout.addWidget(container)
        self.resize(360, 600)
        
        self.drag_position = None
        
    def toggle_panel_click_through(self):
        if self.overlay:
            self.overlay.set_click_through(not self.overlay.panel_click_through)
            self.update_click_through_button_text()
            self.parent_window.save_settings()

    def update_click_through_button_text(self):
        if self.overlay and self.overlay.panel_click_through:
            self.btn_panel_click_through.setText("마우스 투과 상태: 켬")
            apply_widget_tone(self.btn_panel_click_through, "SuccessBtn")
        else:
            self.btn_panel_click_through.setText("마우스 투과 상태: 끔")
            apply_widget_tone(self.btn_panel_click_through, "")

    def change_player_class(self, player, text):
        if self.overlay:
            self.overlay.player_classes[player] = text
        if player == self.parent_window.player_name:
            self.parent_window.player_class = text
            if self.parent_window.client:
                self.parent_window.client.set_class_name(text)
            self.parent_window.save_settings()
        if self.overlay:
            self.overlay.rebuild_cards()
            self.overlay.apply_theme()
            
    def change_theme(self, text):
        if self.overlay:
            self.overlay.theme_name = text
            self.overlay.apply_theme()
            
    def change_layout(self, text):
        if self.overlay:
            self.overlay.layout_mode = text
            self.overlay.rebuild_cards()
            self.overlay.apply_theme()
            
    def change_display(self, text):
        if self.overlay:
            self.overlay.display_mode = text
            self.overlay.rebuild_cards()
            self.overlay.apply_theme()
            
    def change_scale(self, value):
        if self.overlay:
            self.overlay.ui_scale = value / 10.0
            self.lbl_scale_val.setText(f"{self.overlay.ui_scale:.1f}x")
            self.overlay.rebuild_cards()
            self.overlay.apply_theme()
            
    def change_opacity(self, value):
        if self.overlay:
            self.overlay.panel_opacity = value
            self.overlay.setWindowOpacity(value / 100.0)
            self.lbl_opacity_val.setText(f"{value}%")
            
    def change_speed(self, value):
        if self.overlay:
            self.overlay.speed = value / 10.0
            self.lbl_speed_val.setText(f"{self.overlay.speed:.1f}x")
            self.overlay.apply_theme()
            
    def close_and_save(self):
        self.parent_window.save_settings()
        self.accept()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            
    def mouseReleaseEvent(self, event):
        self.drag_position = None


class SettingsModal(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setWindowTitle("설정")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.is_setting_target = None
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self.rotate_spinner_icon)
        self.spinner_angle = 0
        self.client_connection_start_time = 0.0
        self.character_lookup_in_progress = False
        self.pending_connect_after_lookup = False
        self.pending_lookup_name = ""

        
        self.setStyleSheet(get_modal_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setObjectName("ModalContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 16, 20, 18)
        container_layout.setSpacing(14)
        
        # 헤더: 좌측 정렬 타이틀 + 닫기. 메인 창 타이틀바와 같은 문법.
        header, _ = build_modal_header(
            "설정 및 쿨타임 동기화",
            f"PENGU ZOOM PRO {APP_VERSION}",
            on_close=self.save_and_close,
        )
        container_layout.addWidget(header)
        container_layout.addWidget(build_divider())
        
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
        
        # Tab 4: Boss debuff (암흑 수류탄) detection
        tab_boss = QWidget()
        self.setup_boss_debuff_tab(tab_boss)
        self.tabs.addTab(tab_boss, "보스 디버프")
        
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
        
        self.resize(620, 700)
        self.old_pos = None

    def setup_hotkeys_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(2, 14, 2, 2)
        lay.setSpacing(12)

        self.temp_follow = self.parent_window.hotkey_follow
        self.temp_transparent = self.parent_window.hotkey_transparent
        self.temp_hide = self.parent_window.hotkey_hide

        # 단축키 카드: 라벨 + 값 버튼을 한 행으로 정렬한다. 값 버튼은 입력창처럼
        # 보이게 해서 '누르면 바뀌는 값'임을 드러낸다.
        hotkey_card, hotkey_body = build_section_card("단축키", LUCIDE_SLIDERS_SVG)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        self.btn_follow = QPushButton(self.get_display_text(self.temp_follow, "Ctrl+MiddleClick"))
        self.btn_transparent = QPushButton(self.get_display_text(self.temp_transparent, "Ctrl+Alt+T"))
        self.btn_hide = QPushButton(self.get_display_text(self.temp_hide, "Ctrl+Alt+H"))

        rows = (
            ("마우스 따라오기", self.btn_follow, "follow"),
            ("마우스 투과 토글", self.btn_transparent, "transparent"),
            ("최소화(가리기) 토글", self.btn_hide, "hide"),
        )
        for row_index, (caption, button, target) in enumerate(rows):
            label = QLabel(caption)
            label.setObjectName("FieldLabel")
            button.setObjectName("KeyBtn")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip("클릭 후 원하는 키 조합을 누르세요 (ESC = 기본값)")
            button.clicked.connect(
                lambda _checked=False, t=target, b=button: self.start_setting(t, b))
            grid.addWidget(label, row_index, 0)
            grid.addWidget(button, row_index, 1)

        hotkey_body.addLayout(grid)
        lay.addWidget(hotkey_card)

        # 표시 옵션 카드
        display_card, display_body = build_section_card("표시 옵션", LUCIDE_EYE_SVG)
        self.chk_hide_ui_on_transparent = QCheckBox("마우스 투과 시 모든 제어 UI 숨기기")
        self.chk_hide_ui_on_transparent.setChecked(self.parent_window.hide_ui_on_transparent)
        self.chk_hide_ui_on_transparent.setCursor(Qt.CursorShape.PointingHandCursor)
        display_body.addWidget(self.chk_hide_ui_on_transparent)

        hint = QLabel(
            "켜면 마우스 투과 상태에서 버튼과 슬라이더가 자동으로 숨겨져 "
            "확대 화면만 남습니다.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        display_body.addWidget(hint)
        lay.addWidget(display_card)

        tip = QLabel("단축키 지정 대기 중 ESC를 누르면 기본값으로 되돌립니다.")
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        lay.addStretch()

    def get_display_text(self, val, fallback):
        return val if val else fallback

    def start_setting(self, target, button):
        self.is_setting_target = target
        button.setText("키 입력 대기 중…")
        # 인라인 QSS 대신 objectName을 바꿔 공용 스타일의 armed 규칙을 적용한다.
        apply_widget_tone(button, "KeyBtnArmed")

    def _reset_hotkey_button_styles(self):
        """키 지정이 끝난 버튼들을 기본 KeyBtn 외형으로 되돌린다."""
        for button in (self.btn_follow, self.btn_transparent, self.btn_hide):
            apply_widget_tone(button, "KeyBtn")

    def setup_skills_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(2, 14, 2, 2)
        lay.setSpacing(12)

        # 액션 행: 주 동작(스킬 추가)만 액센트, 파괴적 동작(삭제)만 위험색.
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.add_skill_btn = QPushButton("스킬 추가")
        self.add_skill_btn.setObjectName("PrimaryBtn")
        self.add_skill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_skill_btn.clicked.connect(self.add_new_skill_slot)
        btn_row.addWidget(self.add_skill_btn)

        self.cap_area_btn = QPushButton("Ready 영역 지정")
        self.cap_area_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cap_area_btn.clicked.connect(self.capture_selected_skill_area)
        btn_row.addWidget(self.cap_area_btn)

        self.del_skill_btn = QPushButton("삭제")
        self.del_skill_btn.setObjectName("DangerBtn")
        self.del_skill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_skill_btn.clicked.connect(self.delete_selected_skill)
        btn_row.addWidget(self.del_skill_btn)

        btn_row.addStretch()
        lay.addLayout(btn_row)

        # 좌: 등록된 스킬 목록 / 우: 선택한 스킬의 상세 설정
        split = QHBoxLayout()
        split.setSpacing(10)

        list_card, list_body = build_section_card("감지 스킬", LUCIDE_LAYOUT_SVG)
        self.skill_list = QListWidget()
        self.skill_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skill_list.currentRowChanged.connect(self.on_skill_selection_changed)
        list_body.addWidget(self.skill_list)
        split.addWidget(list_card, 3)

        detail_card, detail_body = build_section_card("선택한 스킬", LUCIDE_SLIDERS_SVG)
        self.preview_box = detail_card

        # Ready 스냅샷 미리보기
        snap_label = QLabel("Ready 스냅샷")
        snap_label.setObjectName("FieldLabel")
        detail_body.addWidget(snap_label)

        self.lbl_skill_img = QLabel("스냅샷 없음\n영역 지정이 필요합니다")
        self.lbl_skill_img.setFixedHeight(104)
        self.lbl_skill_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_skill_img.setWordWrap(True)
        self.lbl_skill_img.setStyleSheet(SNAPSHOT_PLACEHOLDER_STYLE)
        detail_body.addWidget(self.lbl_skill_img)

        # 쿨타임(초)
        cooldown_label = QLabel("쿨타임 (초)")
        cooldown_label.setObjectName("FieldLabel")
        detail_body.addWidget(cooldown_label)

        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(0, 3600)
        self.spin_cooldown.setSuffix(" 초")
        self.spin_cooldown.setValue(0)
        self.spin_cooldown.valueChanged.connect(self.on_cooldown_value_changed)
        detail_body.addWidget(self.spin_cooldown)

        # 트리거 키
        trigger_label = QLabel("트리거 단축키")
        trigger_label.setObjectName("FieldLabel")
        detail_body.addWidget(trigger_label)

        self.txt_trigger_key = QLineEdit()
        self.txt_trigger_key.setMaxLength(10)
        self.txt_trigger_key.setPlaceholderText("예: f")
        self.txt_trigger_key.textChanged.connect(self.on_trigger_key_changed)
        detail_body.addWidget(self.txt_trigger_key)

        detail_body.addStretch()
        split.addWidget(detail_card, 2)
        lay.addLayout(split)

        # Populate existing slots
        self.refresh_skill_list()

        self.lbl_selected_status = QLabel(
            "선택된 스킬 없음 · Ready 스냅샷을 지정하면 활성화 판별이 시작됩니다")
        self.lbl_selected_status.setObjectName("StatusWarn")
        self.lbl_selected_status.setWordWrap(True)
        lay.addWidget(self.lbl_selected_status)

        manual_notice = QLabel(
            "남은 쿨타임은 입력한 초와 트리거 단축키로 계산하고, "
            "Ready 판정은 저장된 스냅샷을 사용합니다.")
        manual_notice.setObjectName("Hint")
        manual_notice.setWordWrap(True)
        lay.addWidget(manual_notice)

    def setup_ocr_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(9)

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("OCR 슬롯:"))
        self.ocr_skill_combo = QComboBox()
        self.ocr_skill_combo.currentTextChanged.connect(self.on_ocr_skill_changed)
        select_row.addWidget(self.ocr_skill_combo, 2)
        select_row.addWidget(QLabel("판정 모드:"))
        self.ocr_mode_combo = QComboBox()
        self.ocr_mode_combo.addItem("꺼짐", "off")
        self.ocr_mode_combo.addItem("Shadow (비교 로그)", "shadow")
        self.ocr_mode_combo.addItem("숫자 OCR 자동", "primary")
        self.ocr_mode_combo.currentIndexChanged.connect(self.on_ocr_controls_changed)
        select_row.addWidget(self.ocr_mode_combo, 2)
        lay.addLayout(select_row)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("배율 프로필:"))
        self.ocr_profile_combo = QComboBox()
        self.ocr_profile_combo.setEditable(True)
        profile_names = self.parent_window.detector.ocr_engine.available_profiles()
        for profile_name in profile_names or [cooldown_detector.DEFAULT_PROFILE_ID]:
            self.ocr_profile_combo.addItem(profile_name)
        self.ocr_profile_combo.currentTextChanged.connect(self.on_ocr_controls_changed)
        profile_row.addWidget(self.ocr_profile_combo, 1)
        self.ocr_diagnostics_check = QCheckBox("저신뢰 슬롯 이미지 저장 (최대 100MB)")
        self.ocr_diagnostics_check.toggled.connect(self.on_ocr_controls_changed)
        profile_row.addWidget(self.ocr_diagnostics_check)
        self.ocr_train_captures_btn = QPushButton("캡처 폴더 학습")
        self.ocr_train_captures_btn.clicked.connect(self.train_developer_capture_profile)
        profile_row.addWidget(self.ocr_train_captures_btn)
        lay.addLayout(profile_row)

        preview_row = QHBoxLayout()
        self.ocr_original_frame, self.ocr_original_preview = self._make_ocr_preview("원본 슬롯")
        self.ocr_roi_frame, self.ocr_roi_preview = self._make_ocr_preview("숫자 ROI")
        self.ocr_binary_frame, self.ocr_binary_preview = self._make_ocr_preview("이진화·경계")
        preview_row.addWidget(self.ocr_original_frame)
        preview_row.addWidget(self.ocr_roi_frame)
        preview_row.addWidget(self.ocr_binary_frame)
        lay.addLayout(preview_row)

        roi_title = QLabel("숫자 ROI 미세 조정 (슬롯 크기 대비 비율)")
        roi_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #cccccc;")
        lay.addWidget(roi_title)
        roi_row = QHBoxLayout()
        self.ocr_roi_spins = []
        for label_text, value in zip(("X", "Y", "너비", "높이"), cooldown_detector.DEFAULT_DIGIT_ROI):
            roi_row.addWidget(QLabel(label_text))
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.01)
            spin.setValue(value)
            spin.valueChanged.connect(self.on_ocr_controls_changed)
            self.ocr_roi_spins.append(spin)
            roi_row.addWidget(spin)
        self.ocr_auto_roi_btn = QPushButton("1080p 자동 맞춤")
        self.ocr_auto_roi_btn.clicked.connect(self.auto_fit_ocr_roi)
        roi_row.addWidget(self.ocr_auto_roi_btn)
        lay.addLayout(roi_row)

        calibration_box = QFrame()
        calibration_box.setStyleSheet(
            "QFrame { background: rgba(10,132,255,0.06); border: 1px solid rgba(10,132,255,0.20); "
            "border-radius: 9px; } QLabel { border: none; background: transparent; }"
        )
        cal_lay = QVBoxLayout(calibration_box)
        cal_lay.setContentsMargins(10, 8, 10, 8)
        cal_lay.setSpacing(6)
        instruction = QLabel(
            "프로필 보정은 선택 사항입니다. 화면에 시작 숫자가 나타나는 순간 아래 녹화를 누르세요. "
            "슬롯 이미지만 15FPS로 로컬 저장하며 전체 화면이나 서버 업로드는 하지 않습니다."
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet("color: #a9cfff; font-size: 11px;")
        cal_lay.addWidget(instruction)
        cal_row = QHBoxLayout()
        cal_row.addWidget(QLabel("시작 숫자:"))
        self.ocr_calibration_seconds = QSpinBox()
        self.ocr_calibration_seconds.setRange(10, 9999)
        self.ocr_calibration_seconds.setValue(30)
        self.ocr_calibration_seconds.setSuffix(" 초")
        cal_row.addWidget(self.ocr_calibration_seconds)
        self.ocr_start_collection_btn = QPushButton("15FPS 프로필 녹화 시작")
        self.ocr_start_collection_btn.clicked.connect(self.start_ocr_collection)
        cal_row.addWidget(self.ocr_start_collection_btn)
        self.ocr_stop_collection_btn = QPushButton("중지·프로필 학습")
        self.ocr_stop_collection_btn.clicked.connect(self.stop_ocr_collection)
        self.ocr_stop_collection_btn.setEnabled(False)
        cal_row.addWidget(self.ocr_stop_collection_btn)
        cal_lay.addLayout(cal_row)
        lay.addWidget(calibration_box)

        self.ocr_quality_status = QLabel("슬롯을 선택하면 OCR 인식 품질이 여기에 표시됩니다.")
        self.ocr_quality_status.setWordWrap(True)
        self.ocr_quality_status.setStyleSheet("font-size: 11px; color: #ffd60a;")
        lay.addWidget(self.ocr_quality_status)

        self.refresh_ocr_skill_combo()
        self.ocr_preview_timer = QTimer(self)
        self.ocr_preview_timer.timeout.connect(self.refresh_ocr_preview)
        self.ocr_preview_timer.start(250)

    def _make_ocr_preview(self, title):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.10); "
            "border-radius: 8px; } QLabel { border: none; background: transparent; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        heading = QLabel(title)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 10px; color: #aaaaaa;")
        layout.addWidget(heading)
        preview = QLabel("대기 중")
        preview.setMinimumSize(150, 88)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet("background: #050505; color: #555555; border-radius: 5px;")
        layout.addWidget(preview)
        return frame, preview

    def refresh_ocr_skill_combo(self):
        if not hasattr(self, "ocr_skill_combo"):
            return
        selected = self.ocr_skill_combo.currentText()
        self.ocr_skill_combo.blockSignals(True)
        self.ocr_skill_combo.clear()
        self.ocr_skill_combo.addItems(list(self.parent_window.detector.slots.keys()))
        index = self.ocr_skill_combo.findText(selected)
        self.ocr_skill_combo.setCurrentIndex(index if index >= 0 else (0 if self.ocr_skill_combo.count() else -1))
        self.ocr_skill_combo.blockSignals(False)
        self.on_ocr_skill_changed(self.ocr_skill_combo.currentText())

    def on_ocr_skill_changed(self, name):
        slot = self.parent_window.detector.slots.get(name)
        controls = [self.ocr_mode_combo, self.ocr_profile_combo, self.ocr_diagnostics_check,
                    self.ocr_auto_roi_btn, self.ocr_start_collection_btn, *self.ocr_roi_spins]
        for control in controls:
            control.setEnabled(slot is not None)
        if slot is None:
            return
        self.ocr_mode_combo.blockSignals(True)
        mode_index = self.ocr_mode_combo.findData(slot.ocr_mode)
        self.ocr_mode_combo.setCurrentIndex(max(0, mode_index))
        self.ocr_mode_combo.blockSignals(False)
        self.ocr_profile_combo.blockSignals(True)
        self.ocr_profile_combo.setCurrentText(slot.ocr_profile_id)
        self.ocr_profile_combo.blockSignals(False)
        self.ocr_diagnostics_check.blockSignals(True)
        self.ocr_diagnostics_check.setChecked(slot.ocr_save_diagnostics)
        self.ocr_diagnostics_check.blockSignals(False)
        for spin, value in zip(self.ocr_roi_spins, slot.digit_roi):
            spin.blockSignals(True)
            spin.setValue(float(value))
            spin.blockSignals(False)
        self.refresh_ocr_preview()

    def on_ocr_controls_changed(self, *args):
        if not hasattr(self, "ocr_skill_combo"):
            return
        name = self.ocr_skill_combo.currentText()
        slot = self.parent_window.detector.slots.get(name)
        if slot is None:
            return
        roi = [spin.value() for spin in self.ocr_roi_spins]
        if roi[0] + roi[2] > 1.0 or roi[1] + roi[3] > 1.0 or roi[2] < 0.05 or roi[3] < 0.05:
            self.ocr_quality_status.setText("ROI가 슬롯 밖으로 나가거나 너무 작습니다.")
            return
        selected_profile = self.ocr_profile_combo.currentText().strip() or cooldown_detector.DEFAULT_PROFILE_ID
        if (
            self.ocr_mode_combo.currentData() == "primary"
            and (
                selected_profile in (
                    cooldown_detector.DEFAULT_PROFILE_ID,
                    cooldown_detector.CAPTURE_PROFILE_ID,
                )
            )
        ):
            selected_profile = self.parent_window.detector.best_profile_for_slot(slot)
            self.ocr_profile_combo.blockSignals(True)
            self.ocr_profile_combo.setCurrentText(selected_profile)
            self.ocr_profile_combo.blockSignals(False)
        self.parent_window.detector.configure_ocr(
            name,
            mode=self.ocr_mode_combo.currentData(),
            profile_id=selected_profile,
            digit_roi=roi,
            save_diagnostics=self.ocr_diagnostics_check.isChecked(),
        )
        self.parent_window.save_settings()

    def auto_fit_ocr_roi(self):
        for spin, value in zip(self.ocr_roi_spins, cooldown_detector.DEFAULT_DIGIT_ROI):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        self.on_ocr_controls_changed()
        self.ocr_quality_status.setText("1920×1080 / 100% 기본 숫자 영역으로 자동 맞춤했습니다.")

    def train_developer_capture_profile(self):
        self.ocr_train_captures_btn.setEnabled(False)
        self.ocr_quality_status.setText("캡처 폴더를 검증하고 숫자 프로필을 학습하는 중...")
        QApplication.processEvents()
        result = self.parent_window.detector.import_developer_captures(force=True)
        self.ocr_train_captures_btn.setEnabled(True)
        if not result.get("ok"):
            self.ocr_quality_status.setText(
                f"캡처 학습 실패: {result.get('error', '알 수 없는 오류')} · "
                f"제외 세션 {result.get('rejected_sessions', 0)}개"
            )
            return

        profile_ids = result.get("profile_ids", [])
        for profile_id in profile_ids:
            if self.ocr_profile_combo.findText(profile_id) < 0:
                self.ocr_profile_combo.addItem(profile_id)
        for slot in self.parent_window.detector.slots.values():
            if slot.ocr_mode == "primary":
                slot.ocr_profile_id = self.parent_window.detector.best_profile_for_slot(slot)
        selected = self.parent_window.detector.slots.get(self.ocr_skill_combo.currentText())
        if selected is not None:
            self.ocr_profile_combo.setCurrentText(selected.ocr_profile_id)
        self.parent_window.save_settings()
        benchmark = result.get("benchmark", {})
        accuracy = float(benchmark.get("confirmed_accuracy", 0.0)) * 100.0
        self.ocr_quality_status.setText(
            f"캡처 학습 완료 · 크기별 프로필 {len(profile_ids)}개 · "
            f"사용 {result.get('accepted_sessions', 0)}세션/"
            f"{result.get('images', 0)}장 · 제외 {result.get('rejected_sessions', 0)}세션 · "
            f"학습 표본 정확도 {accuracy:.1f}%"
        )

    def start_ocr_collection(self):
        name = self.ocr_skill_combo.currentText()
        try:
            path = self.parent_window.detector.start_calibration_collection(
                name, self.ocr_calibration_seconds.value()
            )
            self.ocr_start_collection_btn.setEnabled(False)
            self.ocr_stop_collection_btn.setEnabled(True)
            self.ocr_quality_status.setText(f"녹화 중: {path} · 화면 숫자가 1초가 될 때까지 유지해 주세요.")
        except Exception as exc:
            show_dark_message_box(self, "OCR 녹화", str(exc), QMessageBox.Icon.Warning)

    def stop_ocr_collection(self):
        self.ocr_stop_collection_btn.setEnabled(False)
        self.ocr_quality_status.setText("수집 이미지를 분석해 사용자 프로필을 만드는 중...")
        QApplication.processEvents()
        result = self.parent_window.detector.stop_calibration_collection(train=True)
        self.ocr_start_collection_btn.setEnabled(True)
        if result.get("ok"):
            self.ocr_quality_status.setText(
                f"프로필 학습 완료 · {result.get('segmented_images', 0)}개 숫자 프레임 · "
                f"새 글리프 {result.get('added_glyphs', 0)}개 (전체 {result.get('glyphs', 0)}개)"
            )
        else:
            self.ocr_quality_status.setText(f"프로필 학습 실패: {result.get('error', '알 수 없는 오류')}")

    def refresh_ocr_preview(self):
        if not hasattr(self, "ocr_skill_combo"):
            return
        slot = self.parent_window.detector.slots.get(self.ocr_skill_combo.currentText())
        if slot is None:
            return
        payload = getattr(slot, "last_ocr_quality", {}) or {}
        frame = payload.get("frame")
        roi = payload.get("digit_roi_image")
        binary = payload.get("binary_image")
        self._set_ocr_preview_image(self.ocr_original_preview, frame)
        self._set_ocr_preview_image(self.ocr_roi_preview, roi)
        if binary is not None:
            marked = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            for box in payload.get("digit_boxes", []):
                x, y, w, h = [int(v) for v in box]
                cv2.rectangle(marked, (x, y), (x + w, y + h), (48, 209, 88), 1)
            suffix = payload.get("suffix_box")
            if suffix:
                x, y, w, h = [int(v) for v in suffix]
                cv2.rectangle(marked, (x, y), (x + w, y + h), (255, 214, 10), 1)
            self._set_ocr_preview_image(self.ocr_binary_preview, marked)
        else:
            self._set_ocr_preview_image(self.ocr_binary_preview, None)

        if payload:
            confidence = float(payload.get("confidence", 0.0)) * 100.0
            value = payload.get("seconds") if payload.get("accepted") else "unknown"
            reason = payload.get("reject_reason") or "정상 확정"
            collecting = f" · 수집 {payload.get('frame_count', 0)}프레임" if payload.get("collecting") else ""
            self.ocr_quality_status.setText(
                f"현재 값: {value}초 · 신뢰도 {confidence:.1f}% · {reason} · "
                f"보간 {payload.get('remaining', 0)}초 · 프로필 {payload.get('profile_id', '-')}{collecting}"
            )

    @staticmethod
    def _set_ocr_preview_image(label, image):
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            label.setPixmap(QPixmap())
            label.setText("대기 중")
            return
        try:
            if image.ndim == 2:
                h, w = image.shape
                qimage = QImage(image.data.tobytes(), w, h, w, QImage.Format.Format_Grayscale8)
            else:
                rgb = image[:, :, :3]
                h, w = rgb.shape[:2]
                qimage = QImage(rgb.data.tobytes(), w, h, w * 3, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage).scaled(
                label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            label.setText("")
            label.setPixmap(pixmap)
        except Exception:
            label.setPixmap(QPixmap())
            label.setText("미리보기 실패")

    # ------------------------------------------------------------------
    # Boss debuff (암흑 수류탄) tab
    # ------------------------------------------------------------------
    def setup_boss_debuff_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self.boss_enable_check = QCheckBox("암흑 수류탄 디버프 감지 사용")
        self.boss_enable_check.toggled.connect(self.on_boss_controls_changed)
        lay.addWidget(self.boss_enable_check)

        region_row = QHBoxLayout()
        self.boss_region_label = QLabel("영역 미지정")
        self.boss_region_label.setStyleSheet("font-size: 11px; color: #cccccc;")
        region_row.addWidget(self.boss_region_label, 1)
        self.boss_select_region_btn = QPushButton("영역 지정")
        self.boss_select_region_btn.clicked.connect(self.select_boss_debuff_region)
        region_row.addWidget(self.boss_select_region_btn)
        self.boss_auto_region_btn = QPushButton("자동 추정")
        self.boss_auto_region_btn.clicked.connect(self.auto_boss_debuff_region)
        region_row.addWidget(self.boss_auto_region_btn)
        lay.addLayout(region_row)

        tune_row = QHBoxLayout()
        tune_row.addWidget(QLabel("아이콘 일치율:"))
        self.boss_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.boss_threshold_slider.setRange(60, 95)
        self.boss_threshold_slider.setValue(int(boss_debuff_detector.DEFAULT_MATCH_THRESHOLD * 100))
        self.boss_threshold_slider.valueChanged.connect(self.on_boss_controls_changed)
        tune_row.addWidget(self.boss_threshold_slider, 2)
        self.boss_threshold_value = QLabel("0.80")
        self.boss_threshold_value.setStyleSheet("font-size: 11px; color: #ffd60a;")
        tune_row.addWidget(self.boss_threshold_value)
        tune_row.addWidget(QLabel("지속시간:"))
        self.boss_duration_spin = QDoubleSpinBox()
        self.boss_duration_spin.setRange(0.0, 120.0)
        self.boss_duration_spin.setDecimals(1)
        self.boss_duration_spin.setSingleStep(0.5)
        self.boss_duration_spin.setSuffix(" 초 (0=자동)")
        self.boss_duration_spin.valueChanged.connect(self.on_boss_controls_changed)
        tune_row.addWidget(self.boss_duration_spin)
        self.boss_learned_label = QLabel("학습값 없음")
        self.boss_learned_label.setStyleSheet("font-size: 10px; color: #aaaaaa;")
        tune_row.addWidget(self.boss_learned_label)
        self.boss_reset_learned_btn = QPushButton("학습값 초기화")
        self.boss_reset_learned_btn.setToolTip(
            "자동 학습된 총 지속시간을 지웁니다. 값이 실제보다 길게 굳어 "
            "디버프가 걸릴 때마다 엉뚱한 숫자가 스칠 때 사용하세요."
        )
        self.boss_reset_learned_btn.clicked.connect(self.reset_boss_learned_duration)
        tune_row.addWidget(self.boss_reset_learned_btn)
        lay.addLayout(tune_row)

        self.boss_share_check = QCheckBox("파티원에게 보스 디버프 상태 공유")
        self.boss_share_check.toggled.connect(self.on_boss_controls_changed)
        lay.addWidget(self.boss_share_check)

        preview_frame = QFrame()
        preview_frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.10); "
            "border-radius: 8px; } QLabel { border: none; background: transparent; }"
        )
        preview_lay = QVBoxLayout(preview_frame)
        preview_lay.setContentsMargins(6, 6, 6, 6)
        preview_lay.setSpacing(4)
        preview_title = QLabel("미리보기 · 초록=감지, 파랑=후보, 노랑=숫자 영역")
        preview_title.setStyleSheet("font-size: 10px; color: #aaaaaa;")
        preview_lay.addWidget(preview_title)
        self.boss_preview_label = QLabel("대기 중")
        self.boss_preview_label.setMinimumSize(540, 96)
        self.boss_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.boss_preview_label.setStyleSheet("background: #050505; color: #555555; border-radius: 5px;")
        preview_lay.addWidget(self.boss_preview_label)
        lay.addWidget(preview_frame)

        self.boss_status_label = QLabel("영역을 지정하면 상태가 표시됩니다.")
        self.boss_status_label.setWordWrap(True)
        self.boss_status_label.setStyleSheet("font-size: 11px; color: #ffd60a;")
        lay.addWidget(self.boss_status_label)

        sample_box = QFrame()
        sample_box.setStyleSheet(
            "QFrame { background: rgba(10,132,255,0.06); border: 1px solid rgba(10,132,255,0.20); "
            "border-radius: 9px; } QLabel { border: none; background: transparent; }"
        )
        sample_lay = QVBoxLayout(sample_box)
        sample_lay.setContentsMargins(10, 8, 10, 8)
        sample_lay.setSpacing(6)
        sample_row = QHBoxLayout()
        self.boss_collect_check = QCheckBox("숫자 샘플 수집")
        self.boss_collect_check.toggled.connect(self.on_boss_controls_changed)
        sample_row.addWidget(self.boss_collect_check)
        self.boss_open_samples_btn = QPushButton("샘플 폴더 열기")
        self.boss_open_samples_btn.clicked.connect(self.open_boss_sample_folder)
        sample_row.addWidget(self.boss_open_samples_btn)
        self.boss_train_btn = QPushButton("샘플로 숫자 학습")
        self.boss_train_btn.clicked.connect(self.train_boss_debuff_profile)
        sample_row.addWidget(self.boss_train_btn)
        sample_lay.addLayout(sample_row)
        self.boss_train_status = QLabel("")
        self.boss_train_status.setWordWrap(True)
        self.boss_train_status.setStyleSheet("font-size: 11px; color: #cccccc;")
        sample_lay.addWidget(self.boss_train_status)
        lay.addWidget(sample_box)
        lay.addStretch()

        self._boss_sct = None
        self.refresh_boss_debuff_ui()
        self.boss_preview_timer = QTimer(self)
        self.boss_preview_timer.timeout.connect(self.refresh_boss_debuff_preview)
        self.boss_preview_timer.start(300)
        self.finished.connect(self._stop_boss_preview)

    def _boss_config(self):
        window = self.parent_window
        config = getattr(window, 'boss_debuff_config', None)
        if not isinstance(config, dict):
            config = window.default_boss_debuff_config()
            window.boss_debuff_config = config
        return config

    def refresh_boss_debuff_ui(self):
        config = self._boss_config()
        for widget in (self.boss_enable_check, self.boss_threshold_slider,
                       self.boss_duration_spin, self.boss_share_check, self.boss_collect_check):
            widget.blockSignals(True)
        self.boss_enable_check.setChecked(bool(config.get('enabled')))
        self.boss_threshold_slider.setValue(int(round(float(config.get('threshold', 0.8)) * 100)))
        self.boss_duration_spin.setValue(float(config.get('duration', 0.0) or 0.0))
        self.boss_share_check.setChecked(bool(config.get('share_with_party', True)))
        self.boss_collect_check.setChecked(bool(config.get('collect_samples')))
        for widget in (self.boss_enable_check, self.boss_threshold_slider,
                       self.boss_duration_spin, self.boss_share_check, self.boss_collect_check):
            widget.blockSignals(False)
        self.boss_threshold_value.setText(f"{self.boss_threshold_slider.value() / 100.0:.2f}")
        region = config.get('region')
        if region:
            self.boss_region_label.setText(
                f"영역: X {region[0]} · Y {region[1]} · {region[2]}×{region[3]}"
            )
        else:
            self.boss_region_label.setText("영역 미지정")
        self.refresh_boss_learned_label()
        detector = self.parent_window.boss_debuff_detector
        digits = detector.profile.digit_coverage
        if detector.profile.trusted:
            accuracy = float(detector.profile.accuracy or 0.0)
            suffix = f" · 정확도 {accuracy:.2f}" if accuracy > 0.0 else ""
            self.boss_train_status.setText(f"숫자 인식 사용 중{suffix}")
        else:
            missing = [d for d in range(10) if d not in digits]
            self.boss_train_status.setText(
                f"숫자 표본 부족 (없음 {missing}) · 지속시간 기반 추정만 사용")

    def refresh_boss_learned_label(self):
        """자동 학습된 총 지속시간을 그대로 보여준다.

        예전에는 이 값이 보이지 않아서, 20초 디버프가 28.8초로 굳어 있어도
        사용자가 원인을 알 수 없었다.
        """
        config = self._boss_config()
        learned = float(config.get('learned_duration', 0) or 0)
        manual = float(config.get('duration', 0) or 0)
        if manual > 0.0:
            text = f"학습값 {learned:.1f}초 (수동 {manual:.1f}초 사용)" if learned > 0 \
                else f"수동 {manual:.1f}초 사용"
        elif learned > 0.0:
            text = f"학습값 {learned:.1f}초"
        else:
            text = "학습값 없음"
        self.boss_learned_label.setText(text)

    def reset_boss_learned_duration(self):
        config = self._boss_config()
        config['learned_duration'] = 0.0
        detector = self.parent_window.boss_debuff_detector
        detector.reset_learned_duration()
        self.parent_window.save_settings()
        self.refresh_boss_learned_label()
        self.boss_status_label.setText(
            "학습된 지속시간을 지웠습니다. 다음 캐스트에서 읽은 숫자로 다시 학습합니다."
        )

    def on_boss_controls_changed(self, *_args):
        config = self._boss_config()
        config['enabled'] = self.boss_enable_check.isChecked()
        config['threshold'] = self.boss_threshold_slider.value() / 100.0
        config['duration'] = float(self.boss_duration_spin.value())
        config['share_with_party'] = self.boss_share_check.isChecked()
        config['collect_samples'] = self.boss_collect_check.isChecked()
        self.boss_threshold_value.setText(f"{config['threshold']:.2f}")
        self.refresh_boss_learned_label()
        self.parent_window.apply_boss_debuff_settings()
        self.parent_window.save_settings()

    def select_boss_debuff_region(self):
        self.hide()
        self.parent_window.start_boss_debuff_region_capture(self)

    def auto_boss_debuff_region(self):
        region = self.parent_window.auto_estimate_boss_debuff_region()
        self.refresh_boss_debuff_ui()
        self.boss_status_label.setText(
            f"기본 위치로 추정: {region} · 맞지 않으면 '영역 지정'으로 직접 잡아 주세요."
        )

    def open_boss_sample_folder(self):
        path = self.parent_window.boss_debuff_detector.sample_root
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except Exception as exc:
            self.boss_train_status.setText(f"폴더를 열 수 없습니다: {exc}")

    def train_boss_debuff_profile(self):
        detector = self.parent_window.boss_debuff_detector
        paths = sorted(detector.sample_root.glob("*.png")) if detector.sample_root.exists() else []
        if not paths:
            self.boss_train_status.setText("학습할 샘플이 없습니다. 샘플 수집을 켠 상태로 암흑 수류탄을 사용해 주세요.")
            return
        try:
            result = boss_debuff_detector.train_timer_profile(paths, detector.debuff_id)
        except Exception as exc:
            self.boss_train_status.setText(f"학습 실패: {exc}")
            return
        detector.reload_assets()
        self.refresh_boss_debuff_ui()
        summary = (f"학습 완료 · 이미지 {result['used_images']}장 · "
                   f"정확도 {result.get('accuracy', 0):.2f}")
        if not result["trusted"]:
            summary = (f"학습 실패 (정확도 {result.get('accuracy', 0):.2f}) · "
                       f"부족한 숫자 {result['missing_digits']} · "
                       "샘플 폴더를 비우고 다시 수집해 주세요.")
        self.boss_train_status.setText(summary)

    def on_boss_debuff_state(self, state):
        if not isinstance(state, dict) or not state:
            return
        self.refresh_boss_learned_label()
        if state.get("active"):
            remaining = state.get("remaining")
            source = {
                "ocr": "숫자 인식", "anchor": "자릿수 보정",
                "duration": "지속시간 추정", "unknown": "시간 미확인",
            }.get(state.get("source", ""), state.get("source", ""))
            value = "?" if remaining is None else f"{math.ceil(float(remaining))}초"
            self.boss_status_label.setText(
                f"감지됨 · 남은 {value} ({source}) · 일치율 {state.get('score', 0):.2f}"
            )
        else:
            self.boss_status_label.setText(
                f"디버프 없음 · 최근 일치율 {state.get('score', 0):.2f}"
            )

    def refresh_boss_debuff_preview(self):
        if not self.isVisible():
            return
        detector = self.parent_window.boss_debuff_detector
        region = self._boss_config().get('region')
        if not region:
            self._set_ocr_preview_image(self.boss_preview_label, None)
            return
        try:
            if self._boss_sct is None:
                self._boss_sct = mss.mss()
            band = detector.grab_band(self._boss_sct)
        except Exception as exc:
            self.boss_status_label.setText(f"화면 캡처 실패: {exc}")
            return
        if band is None:
            return

        if detector.enabled and detector.isRunning():
            state = detector.status()
            self.on_boss_debuff_state(state)
        else:
            # Stateless probe so the region can be aimed before enabling.
            gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
            match = boss_debuff_detector.match_icon(
                gray, detector.templates, detector.min_icon_px, detector.max_icon_px
            )
            state = {}
            if match is not None:
                state = {
                    "cell": [match.x, match.y, match.size, match.size],
                    "active": match.score >= detector.match_threshold,
                    "score": match.score,
                }
                self.boss_status_label.setText(
                    f"미리보기(감지 꺼짐) · 최고 일치율 {match.score:.2f} · 아이콘 크기 {match.size}px"
                )
        self._set_ocr_preview_image(self.boss_preview_label, detector.render_preview(band, state))

    def _stop_boss_preview(self, *_args):
        if hasattr(self, "boss_preview_timer"):
            self.boss_preview_timer.stop()
        if getattr(self, "_boss_sct", None) is not None:
            try:
                self._boss_sct.close()
            except Exception:
                pass
            self._boss_sct = None

    def setup_network_tab(self, tab):
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(2, 14, 2, 2)
        lay.setSpacing(12)

        # 1. 내 캐릭터 카드
        me_card, me_body = build_section_card("내 캐릭터", LUCIDE_USER_SVG)

        char_row = QHBoxLayout()
        char_row.setSpacing(8)
        char_lbl = QLabel("캐릭터명")
        char_lbl.setObjectName("FieldLabel")
        char_lbl.setFixedWidth(104)
        char_row.addWidget(char_lbl)

        self.txt_char_name = QLineEdit(self.parent_window.player_name)
        self.txt_char_name.setPlaceholderText("로스트아크 캐릭터명")
        self.txt_char_name.editingFinished.connect(self.lookup_character_class)
        char_row.addWidget(self.txt_char_name, 1)

        self.btn_lookup_character = QPushButton("직업 자동 감지")
        self.btn_lookup_character.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lookup_character.clicked.connect(self.lookup_character_class)
        char_row.addWidget(self.btn_lookup_character)
        me_body.addLayout(char_row)

        self.lbl_character_lookup = QLabel(
            f"현재 직업: {getattr(self.parent_window, 'player_class', '홀리나이트')}"
            " · 캐릭터명 입력 후 자동 감지")
        self.lbl_character_lookup.setObjectName("Hint")
        self.lbl_character_lookup.setWordWrap(True)
        me_body.addWidget(self.lbl_character_lookup)
        lay.addWidget(me_card)

        # 2. 방 연결 카드
        room_card, room_body = build_section_card("파티 방 연결", LUCIDE_JOIN_SVG)

        room_row = QHBoxLayout()
        room_row.setSpacing(8)
        room_lbl = QLabel("방 코드")
        room_lbl.setObjectName("FieldLabel")
        room_lbl.setFixedWidth(104)
        room_row.addWidget(room_lbl)
        self.txt_room_id = QLineEdit(getattr(self.parent_window, "room_id", "default"))
        self.txt_room_id.setPlaceholderText("파티원과 동일하게 입력")
        room_row.addWidget(self.txt_room_id, 1)
        room_body.addLayout(room_row)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        url_lbl = QLabel("릴레이 서버")
        url_lbl.setObjectName("FieldLabel")
        url_lbl.setFixedWidth(104)
        url_row.addWidget(url_lbl)
        self.txt_host_url = QLineEdit(self.parent_window.server_url)
        self.txt_host_url.setReadOnly(True)
        self.txt_host_url.setToolTip("고정 릴레이 서버입니다")
        url_row.addWidget(self.txt_host_url, 1)
        room_body.addLayout(url_row)

        room_body.addWidget(build_divider())

        # 접속 상태 행: 버튼 + 연결 아이콘 + 상태 문구
        conn_row = QHBoxLayout()
        conn_row.setSpacing(9)
        self.btn_toggle_client = QPushButton("방 접속하기")
        self.btn_toggle_client.setObjectName("PrimaryBtn")
        self.btn_toggle_client.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_client.clicked.connect(self.toggle_client_connection)
        conn_row.addWidget(self.btn_toggle_client, 0, Qt.AlignmentFlag.AlignVCenter)

        self.lbl_client_icon = QLabel()
        self.lbl_client_icon.setFixedSize(16, 16)
        self.lbl_client_icon.setScaledContents(True)
        self.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_UNLINKED_SVG, 16))
        conn_row.addWidget(self.lbl_client_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.lbl_client_status = QLabel("대기 중")
        self.lbl_client_status.setObjectName("StatusIdle")
        conn_row.addWidget(self.lbl_client_status, 0, Qt.AlignmentFlag.AlignVCenter)
        conn_row.addStretch()
        room_body.addLayout(conn_row)
        lay.addWidget(room_card)

        # 3. 파티 현황판 카드
        hud_card, hud_body = build_section_card("파티 현황판", LUCIDE_LAYOUT_SVG)

        hud_row = QHBoxLayout()
        hud_row.setSpacing(8)
        self.btn_show_panel = QPushButton("파티 현황 켜기")
        self.btn_show_panel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_show_panel.clicked.connect(self.toggle_party_panel_visible)
        hud_row.addWidget(self.btn_show_panel, 1)

        self.btn_party_settings = QPushButton("디자인 설정")
        self.btn_party_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_party_settings.setIcon(
            get_svg_icon(recolor_svg_stroke(LUCIDE_PALETTE_SVG, "#c7c7cc")))
        self.btn_party_settings.setIconSize(QSize(13, 13))
        self.btn_party_settings.clicked.connect(self.open_party_design_settings)
        hud_row.addWidget(self.btn_party_settings, 1)
        hud_body.addLayout(hud_row)

        hud_hint = QLabel(
            "현황판은 마우스로 옮기고 네 변·네 모서리에서 크기를 조절할 수 있습니다. "
            "마우스 투과를 켜면 클릭이 게임으로 전달됩니다.")
        hud_hint.setObjectName("Hint")
        hud_hint.setWordWrap(True)
        hud_body.addWidget(hud_hint)
        lay.addWidget(hud_card)

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
        if hasattr(self, "ocr_skill_combo"):
            self.refresh_ocr_skill_combo()

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
        return self._refresh_selected_skill_detail()

    def _set_snapshot_placeholder(self, text):
        """스냅샷이 없을 때: 점선 테두리 + 안내 문구."""
        self.lbl_skill_img.setPixmap(QPixmap())
        self.lbl_skill_img.setText(text)
        self.lbl_skill_img.setStyleSheet(SNAPSHOT_PLACEHOLDER_STYLE)

    def _set_snapshot_pixmap(self, pixmap):
        """스냅샷이 있을 때: 실선(성공색) 테두리 + 이미지."""
        self.lbl_skill_img.setText("")
        self.lbl_skill_img.setStyleSheet(SNAPSHOT_FILLED_STYLE)
        self.lbl_skill_img.setPixmap(pixmap.scaled(
            self.lbl_skill_img.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def _set_selected_status(self, text, tone="StatusIdle"):
        """상태 문구와 색조(정상/주의/대기)를 함께 바꾼다."""
        self.lbl_selected_status.setText(text)
        apply_widget_tone(self.lbl_selected_status, tone)

    @staticmethod
    def _template_to_pixmap(template):
        """탐지기 템플릿(numpy)을 QPixmap으로 변환한다. 실패 시 None."""
        try:
            height, width = template.shape[:2]
            if template.ndim == 3:
                image = QImage(template.data.tobytes(), width, height,
                               width * 3, QImage.Format.Format_RGB888)
            else:
                image = QImage(template.data.tobytes(), width, height,
                               width, QImage.Format.Format_Grayscale8)
            return QPixmap.fromImage(image)
        except Exception:
            return None

    def _refresh_selected_skill_detail(self):
        curr = self.skill_list.currentItem()
        if not curr:
            self._set_selected_status(
                "선택된 스킬 없음 · 목록에서 스킬을 고르세요", "StatusIdle")
            self._set_snapshot_placeholder("스냅샷 없음\n영역 지정이 필요합니다")
            self.spin_cooldown.setEnabled(False)
            self.spin_cooldown.blockSignals(True)
            self.spin_cooldown.setValue(0)
            self.spin_cooldown.blockSignals(False)
            
            self.txt_trigger_key.setEnabled(False)
            self.txt_trigger_key.blockSignals(True)
            self.txt_trigger_key.setText("")
            self.txt_trigger_key.blockSignals(False)
            return
            
        name = curr.text()
        if hasattr(self, "ocr_skill_combo"):
            index = self.ocr_skill_combo.findText(name)
            if index >= 0:
                self.ocr_skill_combo.setCurrentIndex(index)
        slot = self.parent_window.detector.slots.get(name)
        if slot:
            self.spin_cooldown.setEnabled(True)
            self.spin_cooldown.blockSignals(True)
            self.spin_cooldown.setValue(slot.cooldown_duration)
            self.spin_cooldown.blockSignals(False)
            
            self.txt_trigger_key.setEnabled(True)
            self.txt_trigger_key.blockSignals(True)
            self.txt_trigger_key.setText(slot.trigger_key if slot.trigger_key else "")
            self.txt_trigger_key.blockSignals(False)

            template = (slot.template_color
                        if slot.template_color is not None else slot.template)
            if template is None:
                self._set_selected_status(
                    f"{name} · Ready 스냅샷이 없어 감지가 시작되지 않습니다", "StatusWarn")
                self._set_snapshot_placeholder("스냅샷 없음\n영역 지정이 필요합니다")
                return

            pixmap = self._template_to_pixmap(template)
            if pixmap is None:
                self._set_selected_status(f"{name} · 스냅샷 로드 실패", "StatusError")
                self._set_snapshot_placeholder("이미지 로드 실패")
                return

            self._set_snapshot_pixmap(pixmap)
            coords = "좌표 지정 완료" if slot.rect else "좌표 미지정"
            tone = "StatusOk" if slot.rect else "StatusWarn"
            self._set_selected_status(f"{name} · {coords} · 스냅샷 있음", tone)

    def on_cooldown_value_changed(self, val):
        curr = self.skill_list.currentItem()
        if curr:
            name = curr.text()
            slot = self.parent_window.detector.slots.get(name)
            if slot:
                slot.cooldown_duration = val
                self.parent_window.save_settings()

    def on_trigger_key_changed(self, text):
        curr = self.skill_list.currentItem()
        if curr:
            name = curr.text()
            slot = self.parent_window.detector.slots.get(name)
            if slot:
                slot.trigger_key = text.strip().lower() if text.strip() else None
                self.parent_window.save_settings()

    def on_developer_capture_toggled(self, enabled):
        enabled = bool(enabled)
        self.parent_window.developer_capture_mode = enabled
        self.parent_window.detector.developer_capture_enabled = enabled
        if enabled:
            self.lbl_developer_capture_status.setText(
                "캡처 대기 중 — 설정한 트리거 키를 누르면 0.25초 뒤부터 1초마다 저장합니다."
            )
        else:
            self.lbl_developer_capture_status.setText("개발자 캡처 모드가 꺼져 있습니다.")
        self.parent_window.save_settings()

    def open_developer_capture_folder(self):
        try:
            folder = self.parent_window.detector.developer_capture_root
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except Exception as exc:
            show_dark_message_box(
                self,
                "폴더 열기 실패",
                f"캡처 폴더를 열지 못했습니다:\n{exc}",
                QMessageBox.Icon.Warning,
            )

    def on_developer_capture_status(self, skill_name, status):
        if not isinstance(status, dict) or not hasattr(self, "lbl_developer_capture_status"):
            return
        event = status.get("event")
        if event == "started":
            text = f"[{skill_name}] 캡처 시작 — {status.get('expected', 0)}장 예정"
        elif event == "saved":
            text = (
                f"[{skill_name}] {status.get('seconds', '?')}s 저장 "
                f"({status.get('saved', 0)}장)"
            )
        elif event == "finished":
            text = f"[{skill_name}] 캡처 완료 — {status.get('saved', 0)}장 저장"
        else:
            text = f"[{skill_name}] {status.get('reason', '캡처 오류')}"
        self.lbl_developer_capture_status.setText(text)

    def lookup_character_class(self, connect_after=False):
        char_name = self.txt_char_name.text().strip()
        url = self.txt_host_url.text().strip()
        if not char_name or not url:
            return

        if self.character_lookup_in_progress and self.pending_lookup_name.casefold() == char_name.casefold():
            self.pending_connect_after_lookup = self.pending_connect_after_lookup or bool(connect_after)
            return

        self.character_lookup_in_progress = True
        self.pending_connect_after_lookup = bool(connect_after)
        self.pending_lookup_name = char_name
        self.btn_lookup_character.setEnabled(False)
        self.btn_lookup_character.setText("확인 중...")
        self.lbl_character_lookup.setText("로스트아크에서 캐릭터 직업을 확인하는 중...")
        self._set_lookup_tone("StatusInfo")
        self.parent_window.request_character_profile(char_name, url)

    def on_character_lookup_succeeded(self, profile):
        requested_name = str(profile.get("requested_name", "")).strip()
        if requested_name.casefold() != self.txt_char_name.text().strip().casefold():
            return

        should_connect = self.pending_connect_after_lookup
        self.character_lookup_in_progress = False
        self.pending_connect_after_lookup = False
        self.pending_lookup_name = ""
        self.btn_lookup_character.setEnabled(True)
        self.btn_lookup_character.setText("다시 감지")

        class_name = profile.get("character_class", "")
        server_name = profile.get("server_name", "")
        suffix = f" · {server_name}" if server_name else ""
        self.lbl_character_lookup.setText(f"직업 자동 설정 완료: {class_name}{suffix}")
        self._set_lookup_tone("StatusOk")
        if should_connect:
            self._start_client_connection()

    def on_character_lookup_progress(self, message):
        if not self.character_lookup_in_progress:
            return
        self.lbl_character_lookup.setText(str(message))
        self._set_lookup_tone("Hint")

    def on_character_lookup_failed(self, requested_name, message):
        if requested_name.casefold() != self.pending_lookup_name.casefold():
            return

        should_connect = self.pending_connect_after_lookup
        self.character_lookup_in_progress = False
        self.pending_connect_after_lookup = False
        self.pending_lookup_name = ""
        self.btn_lookup_character.setEnabled(True)
        self.btn_lookup_character.setText("다시 시도")
        self.lbl_character_lookup.setText(f"자동 감지 실패: {message} 수동 설정 직업을 사용합니다.")
        self._set_lookup_tone("StatusWarn")
        if should_connect:
            self._start_client_connection()

    def _set_client_status(self, text, tone="StatusIdle"):
        """접속 상태 문구와 색조를 공용 스타일 규칙으로 바꾼다."""
        self.lbl_client_status.setText(text)
        apply_widget_tone(self.lbl_client_status, tone)

    def _apply_client_status_tone(self, tone):
        """접속 상태 라벨의 색조만 바꾼다(문구는 호출부에서 이미 설정한 상태)."""
        apply_widget_tone(self.lbl_client_status, tone)

    def _set_lookup_tone(self, tone):
        """직업 자동 감지 안내 라벨의 색조만 바꾼다.

        진행 중(StatusInfo) / 성공(StatusOk) / 경고(StatusWarn) / 보조설명(Hint)
        네 가지를 쓴다.
        """
        apply_widget_tone(self.lbl_character_lookup, tone)

    def update_network_tab_texts(self):
        if self.parent_window.client_running:
            self.btn_toggle_client.setText("접속 끊기")
            apply_widget_tone(self.btn_toggle_client, "DangerBtn")
        else:
            self.btn_toggle_client.setText("방 접속하기")
            apply_widget_tone(self.btn_toggle_client, "PrimaryBtn")
            self._set_client_status("대기 중", "StatusIdle")
            self.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_UNLINKED_SVG, 16))

        if self.parent_window.party_panel.isVisible():
            self.btn_show_panel.setText("파티 현황 끄기")
        else:
            self.btn_show_panel.setText("파티 현황 켜기")

    def rotate_spinner_icon(self):
        self.spinner_angle = (self.spinner_angle + 8) % 360
        canvas = QPixmap(24, 24)
        canvas.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        painter.translate(12, 12)
        painter.rotate(self.spinner_angle)
        
        pixmap = get_svg_pixmap(LUCIDE_LOADER_SVG, 16)
        painter.drawPixmap(-8, -8, pixmap)
        painter.end()
        
        self.lbl_client_icon.setPixmap(canvas)

    def toggle_client_connection(self):
        char_name = self.txt_char_name.text().strip()
        url = self.txt_host_url.text().strip()
        room_id = self.txt_room_id.text().strip()
        
        if not char_name:
            show_dark_message_box(self, "이름 필요", "캐릭터명을 정확하게 기입하세요.", QMessageBox.Icon.Warning)
            return
        
        if not url:
            show_dark_message_box(self, "주소 필요", "서버 주소를 입력하세요.", QMessageBox.Icon.Warning)
            return
            
        if not room_id:
            show_dark_message_box(self, "방 코드 필요", "방 코드 (Room ID)를 입력하세요.", QMessageBox.Icon.Warning)
            return
            
        if self.parent_window.client_running:
            self.spinner_timer.stop()
            self.parent_window.stop_party_client()
            self.update_network_tab_texts()
            return

        self.parent_window.player_name = char_name
        self.parent_window.server_url = url
        self.parent_window.room_id = room_id
        resolved_name = getattr(self.parent_window, "resolved_character_name", "")
        if resolved_name.casefold() != char_name.casefold():
            self.lookup_character_class(connect_after=True)
        else:
            self._start_client_connection()

    def _start_client_connection(self):
        import time
        char_name = self.txt_char_name.text().strip()
        if not char_name or self.parent_window.client_running:
            return
        self.parent_window.player_name = char_name
        self.parent_window.server_url = self.txt_host_url.text().strip()
        self.parent_window.room_id = self.txt_room_id.text().strip()
        self.parent_window.save_settings()
        self.client_connection_start_time = time.time()
        self.spinner_angle = 0
        self.lbl_client_icon.setVisible(True)
        self.spinner_timer.start(30)
        self.lbl_client_status.setText("동기화 연결 중...")
        self._apply_client_status_tone("StatusInfo")
        self.parent_window.start_party_client()
        self.update_network_tab_texts()

    def toggle_party_panel_visible(self):
        if self.parent_window.party_panel.isVisible():
            self.parent_window.party_panel.hide()
        else:
            self.parent_window.party_panel.show()
            self.parent_window.party_panel.activateWindow()
        self.update_network_tab_texts()

    def open_party_design_settings(self):
        if hasattr(self, 'party_settings_dlg') and self.party_settings_dlg and self.party_settings_dlg.isVisible():
            self.party_settings_dlg.raise_()
            self.party_settings_dlg.activateWindow()
            return
            
        self.party_settings_dlg = PartyOverlaySettingsModal(self.parent_window, self)
        self.party_settings_dlg.show()

    def save_and_close(self):
        self.parent_window.hotkey_follow = self.temp_follow
        self.parent_window.hotkey_transparent = self.temp_transparent
        self.parent_window.hotkey_hide = self.temp_hide
        
        self.parent_window.player_name = self.txt_char_name.text().strip()
        self.parent_window.server_url = self.txt_host_url.text().strip()
        self.parent_window.room_id = self.txt_room_id.text().strip()
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
                
                self._reset_hotkey_button_styles()
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
                
            self._reset_hotkey_button_styles()
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
                    
                self._reset_hotkey_button_styles()
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
        
        self.setStyleSheet(get_modal_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("ModalContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 16, 20, 18)
        container_layout.setSpacing(12)

        header, _ = build_modal_header(
            "사용 가이드",
            f"PENGU ZOOM PRO {APP_VERSION}",
            on_close=self.accept,
            icon_svg=LUCIDE_PENGUIN_SVG,
        )
        container_layout.addWidget(header)
        container_layout.addWidget(build_divider())

        guide_card, guide_body = build_section_card("주요 단축키 및 조작법", LUCIDE_SLIDERS_SVG)

        # 단축키 조합은 액센트색 + 고정폭으로 본문과 구분한다.
        def key(text):
            return (f"<span style=\"color: {UI['accent']}; font-family: {UI['mono']};"
                    f" font-weight: 700;\">{text}</span>")

        content_label = QLabel(
            "<table cellspacing='0' cellpadding='3'>"
            f"<tr><td><b>확대/축소</b></td><td>{key('Ctrl + 마우스 휠')}</td></tr>"
            f"<tr><td><b>따라오기 토글</b></td><td>{key('Ctrl + 휠 클릭')}</td></tr>"
            f"<tr><td><b>마우스 투과 토글</b></td><td>{key('Ctrl + Alt + T')}</td></tr>"
            f"<tr><td><b>최소화 토글</b></td><td>{key('Ctrl + Alt + H')}</td></tr>"
            f"<tr><td><b>종료</b></td><td>{key('ESC')} 또는 [X] 버튼</td></tr>"
            "</table>"
        )
        content_label.setWordWrap(True)
        guide_body.addWidget(content_label)
        guide_body.addWidget(build_divider())

        detail_label = QLabel(
            "· <b>영역 지정</b>: [영역 지정] 클릭 후 화면을 드래그합니다.<br>"
            "· <b>투명도</b>: 하단 슬라이더로 15% ~ 100% 사이를 조절합니다.<br>"
            "· <b>투과 모드</b>: 켜면 마우스 클릭이 창을 통과해 뒤쪽 게임을 조작할 수 "
            "있습니다. 같은 단축키로 되돌립니다.<br>"
            "· 따라오기·투과·최소화 단축키는 설정에서 바꿀 수 있습니다."
        )
        detail_label.setObjectName("Hint")
        detail_label.setWordWrap(True)
        guide_body.addWidget(detail_label)

        container_layout.addWidget(guide_card)
        container_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("확인")
        close_btn.setObjectName("PrimaryBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        container_layout.addLayout(btn_layout)

        layout.addWidget(container)
        self.resize(440, 420)
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
        self.setStyleSheet(CONTAINER_STYLE_FRAMED)
        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background-color: transparent; width: 20px; height: 20px;")

    def resizeEvent(self, event):
        rect = self.rect()
        self.grip.move(rect.right() - 20, rect.bottom() - 20)
        super().resizeEvent(event)

class MagnifierWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'{APP_NAME} Pro v{APP_VERSION}')
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
        self.server_url = "https://pengzoom-pro-relay.onrender.com"
        self.room_id = "default"
        self.hide_ui_on_transparent = False  # Feature Toggle
        
        # Initialize detector
        self.detector = cooldown_detector.CooldownDetector()
        self.detector.device_ratio = QApplication.primaryScreen().devicePixelRatio()
        self.detector.state_changed.connect(self.on_skill_state_changed)
        self.detector.start_detection(50)  # Scan every 50ms (runs inside background QThread)
        
        # Boss debuff (암흑 수류탄) detector — scans the strip under the boss HP bar
        self.boss_debuff_detector = boss_debuff_detector.BossDebuffDetector(debuff_id=boss_debuff_detector.DEFAULT_DEBUFF_ID)
        self.boss_debuff_detector.device_ratio = QApplication.primaryScreen().devicePixelRatio()
        self.boss_debuff_detector.debuff_updated.connect(
            self.on_boss_debuff_updated, Qt.ConnectionType.QueuedConnection
        )
        self.boss_debuff_state = {}
        self.boss_debuff_last_sent = (None, None, 0.0)
        
        # Network objects
        self.server = None
        self.client = None
        self.server_running = False
        self.client_running = False
        self.resolved_character_name = ""
        self.active_character_lookup_request = 0
        
        # Floating party statuses panel
        self.party_panel = PartyPanel(self)
        
        self.load_settings()
        self.apply_boss_debuff_settings()
        self.character_profile_lookup = network_manager.CharacterProfileLookup(self)
        self.character_profile_lookup.profile_loaded.connect(
            self.on_character_profile_loaded, Qt.ConnectionType.QueuedConnection
        )
        self.character_profile_lookup.lookup_progress.connect(
            self.on_character_profile_progress, Qt.ConnectionType.QueuedConnection
        )
        self.character_profile_lookup.lookup_failed.connect(
            self.on_character_profile_failed, Qt.ConnectionType.QueuedConnection
        )
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
        # update_magnifier는 핫 패스라 예외를 잡아 넘기지만, 첫 실패는 보관해
        # 원인 추적이 가능하게 한다.
        self.last_frame_error = None
        self.frame_error_count = 0
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
            self.key_listener = None

    def stop_listeners(self):
        """pynput 리스너를 정리한다. 호출하지 않으면 종료 후에도 윈도우
        키보드 훅과 데몬 스레드가 남는다."""
        listener = getattr(self, 'key_listener', None)
        if listener is None:
            return
        try:
            listener.stop()
        except Exception:
            pass
        self.key_listener = None

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
        self.server_url = "https://pengzoom-pro-relay.onrender.com"
        self.room_id = "default"
        self.hide_ui_on_transparent = False
        self.client_id = None
        self.player_class = "홀리나이트"
        self.developer_capture_mode = False
        self.detector.developer_capture_enabled = False
        self.boss_debuff_config = self.default_boss_debuff_config()
        
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
                    self.server_url = data.get('server_url', "https://pengzoom-pro-relay.onrender.com")
                    if "://" not in self.server_url:
                        self.server_url = "https://" + self.server_url.lstrip("/")
                    if "127.0.0.1" in self.server_url or "localhost" in self.server_url or self.server_url.startswith("http://"):
                        self.server_url = "https://pengzoom-pro-relay.onrender.com"
                    if ":9090" in self.server_url:
                        self.server_url = self.server_url.replace(":9090", ":19090")
                    self.room_id = data.get('room_id', "default")
                    self.hide_ui_on_transparent = data.get('hide_ui_on_transparent', False)
                    self.client_id = data.get('client_id', None)
                    self.player_class = data.get('player_class', "홀리나이트")
                    # Cooldown OCR/developer capture was retired in v2.46.
                    # Ignore legacy flags so old configs migrate to manual mode.
                    self.developer_capture_mode = False
                    self.detector.developer_capture_enabled = False
                    
                    # Boss debuff (암흑 수류탄) detection settings
                    stored_boss = data.get('boss_debuff', {})
                    config = self.default_boss_debuff_config()
                    if isinstance(stored_boss, dict):
                        for key, value in stored_boss.items():
                            if key in config:
                                config[key] = value
                    region = config.get('region')
                    if not (isinstance(region, (list, tuple)) and len(region) == 4):
                        config['region'] = None
                    else:
                        config['region'] = [int(v) for v in region]
                    self.boss_debuff_config = config
                    
                    # Restore party panel position and size
                    party_pos = data.get('party_panel_pos', None)
                    if party_pos and len(party_pos) == 2 and self.party_panel:
                        self.party_panel.move(party_pos[0], party_pos[1])
                    
                    party_size = data.get('party_panel_size', None)
                    if party_size and len(party_size) == 2 and self.party_panel:
                        # 사용자가 조절한 크기를 그대로 복원한다. _user_sized를
                        # 세워 두면 내용 기반 자동 맞춤이 이 크기를 줄이지 않는다.
                        self.party_panel.resize(party_size[0], party_size[1])
                        self.party_panel._user_sized = True
                        
                    party_opacity = data.get('party_panel_opacity', 90)
                    if self.party_panel:
                        self.party_panel.panel_opacity = party_opacity
                        self.party_panel.setWindowOpacity(party_opacity / 100.0)
                    
                    # Restore party panel click-through state
                    panel_ct = data.get('party_panel_click_through', False)
                    if panel_ct and self.party_panel:
                        self.party_panel.set_click_through(True)
                        
                    # Restore additional party panel custom options
                    if self.party_panel:
                        theme_loaded = data.get('party_theme_name', "옵시디언 글래스")
                        if theme_loaded == "Obsidian Glass (Default)":
                            theme_loaded = "옵시디언 글래스"
                        elif theme_loaded == "Nordic Light (Minimal)":
                            theme_loaded = "노르딕 라이트"
                        elif theme_loaded == "Crimson Velvet (Luxury)":
                            theme_loaded = "크림슨 벨벳"
                        if theme_loaded not in THEMES:
                            theme_loaded = "옵시디언 글래스"
                        self.party_panel.theme_name = theme_loaded
                        
                        # v2.46: '세로형/가로형' 배치 옵션이 '표준/컴팩트' 밀도
                        # 모드로 바뀌었다. 구버전 설정값을 그대로 매핑한다.
                        layout_loaded = data.get('party_layout_mode', "표준")
                        if layout_loaded in ("List", "세로형"):
                            layout_loaded = "표준"
                        elif layout_loaded in ("Grid", "가로형"):
                            layout_loaded = "컴팩트"
                        if layout_loaded not in ("표준", "컴팩트"):
                            layout_loaded = "표준"
                        self.party_panel.layout_mode = layout_loaded
                        
                        display_loaded = data.get('party_display_mode', "상세 정보")
                        if display_loaded == "Detailed":
                            display_loaded = "상세 정보"
                        elif display_loaded == "Minimal":
                            display_loaded = "아이콘만"
                        if display_loaded not in ["상세 정보", "아이콘만"]:
                            display_loaded = "상세 정보"
                        self.party_panel.display_mode = display_loaded
                        
                        self.party_panel.ui_scale = data.get('party_ui_scale', 1.0)
                        self.party_panel.speed = data.get('party_speed', 1.0)
                        self.party_panel.intensity = data.get('party_intensity', 1.0)
                        
                        classes_loaded = data.get('party_player_classes', {})
                        normalized_classes = {}
                        for player, cls_name in classes_loaded.items():
                            if cls_name in LOST_ARK_CLASSES:
                                normalized_classes[player] = cls_name
                            else:
                                clean_name = cls_name.split(" ")[0]
                                if clean_name in LOST_ARK_CLASSES:
                                    normalized_classes[player] = clean_name
                                else:
                                    normalized_classes[player] = "홀리나이트"
                        self.party_panel.player_classes = normalized_classes
                        
                        self.party_panel.apply_theme()
                        self.party_panel.rebuild_cards()
                    
                    # Restore skill slots and templates (grayscale CV2 matrices) from config
                    skills = data.get('skills', [])
                    templates_dir = os.path.join(os.path.dirname(config_path), 'templates')
                    
                    self.detector.slots.clear()
                    
                    for s_info in skills:
                        name = s_info.get("name")
                        rect_val = s_info.get("rect")
                        threshold = s_info.get("threshold", 0.85)
                        cooldown_duration = s_info.get("cooldown_duration", 0)
                        trigger_key = s_info.get("trigger_key", None)
                        slot_device_ratio = s_info.get("device_ratio", self.detector.device_ratio)
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
                        slot = self.detector.slots.get(name)
                        if slot:
                            slot.trigger_key = trigger_key
                            slot.device_ratio = slot_device_ratio
                            slot.ocr_mode = "off"
                            slot.ocr_enabled = False
                    if not self.client_id:
                        import uuid
                        self.client_id = str(uuid.uuid4())
                    return
            except Exception:
                pass
        if not self.client_id:
            import uuid
            self.client_id = str(uuid.uuid4())

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
                    "cooldown_duration": slot.cooldown_duration,
                    "trigger_key": getattr(slot, 'trigger_key', None),
                    "device_ratio": getattr(slot, 'device_ratio', None) or self.detector.device_ratio
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
            party_theme = "옵시디언 글래스"
            party_layout = "표준"
            party_display = "상세 정보"
            party_scale = 1.0
            party_speed = 1.0
            party_intensity = 1.0
            party_classes = {}
            
            if self.party_panel:
                pos = self.party_panel.pos()
                party_pos = [pos.x(), pos.y()]
                party_size = [self.party_panel.width(), self.party_panel.height()]
                party_opacity = getattr(self.party_panel, 'panel_opacity', 90)
                party_theme = getattr(self.party_panel, 'theme_name', "옵시디언 글래스")
                party_layout = getattr(self.party_panel, 'layout_mode', "표준")
                party_display = getattr(self.party_panel, 'display_mode', "상세 정보")
                party_scale = getattr(self.party_panel, 'ui_scale', 1.0)
                party_speed = getattr(self.party_panel, 'speed', 1.0)
                party_intensity = getattr(self.party_panel, 'intensity', 1.0)
                party_classes = getattr(self.party_panel, 'player_classes', {})

            data = {
                'zoom_factor': self.zoom_factor,
                'opacity': self.opacity_slider.value(),
                'hotkey_follow': self.hotkey_follow,
                'hotkey_transparent': self.hotkey_transparent,
                'hotkey_hide': self.hotkey_hide,
                'player_name': self.player_name,
                'server_url': self.server_url,
                'room_id': self.room_id,
                'hide_ui_on_transparent': self.hide_ui_on_transparent,
                'client_id': self.client_id,
                'player_class': getattr(self, 'player_class', "홀리나이트"),
                'skills': skills_data,
                'party_panel_pos': party_pos,
                'party_panel_size': party_size,
                'party_panel_opacity': party_opacity,
                'party_panel_click_through': self.party_panel.panel_click_through if self.party_panel else False,
                'party_theme_name': party_theme,
                'party_layout_mode': party_layout,
                'party_display_mode': party_display,
                'party_ui_scale': party_scale,
                'party_speed': party_speed,
                'party_intensity': party_intensity,
                'party_player_classes': party_classes,
                'boss_debuff': getattr(self, 'boss_debuff_config', None) or self.default_boss_debuff_config()
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def setup_ui(self):
        self.container = ResizableContainer()
        self.setCentralWidget(self.container)

        # v2.46 리디자인: 노랑/초록/파랑/빨강 원색 버튼 4개가 나란히 있던 구성을
        # 무채색 기반 + 단일 액센트(iOS 블루)로 바꿨다. 색은 상태를 표현할 때만
        # 쓰고, 평상시 크롬은 전부 회색조로 물러나 게임 화면을 방해하지 않는다.
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Malgun Gothic', sans-serif;
                color: #f5f5f7;
            }
            QLabel {
                font-size: 12px;
                background: transparent;
            }
            QLabel#BrandName {
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1.2px;
                color: #f5f5f7;
            }
            QLabel#BrandVersion {
                font-size: 9px;
                font-weight: 700;
                color: rgba(245, 245, 247, 0.45);
                background-color: rgba(255, 255, 255, 0.07);
                border-radius: 6px;
                padding: 2px 6px;
            }
            QLabel#FieldLabel {
                font-size: 10px;
                font-weight: 700;
                color: rgba(245, 245, 247, 0.42);
            }
            QLabel#FieldValue {
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 11px;
                font-weight: 700;
                color: #f5f5f7;
            }

            /* 세그먼티드 컨트롤: 트랙 하나 안에 버튼 세 개 */
            QFrame#SegmentTrack {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 10px;
            }
            QPushButton {
                background-color: transparent;
                color: rgba(245, 245, 247, 0.62);
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
                color: #f5f5f7;
            }
            QPushButton.PrimaryActive {
                background-color: #0a84ff;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton.PrimaryActive:hover {
                background-color: #2b95ff;
            }

            /* 타이틀바 아이콘 버튼: 평상시 무채색, 호버에서만 의미색 노출 */
            QPushButton#MinimizeBtn, QPushButton#SettingsBtn,
            QPushButton#HelpBtn, QPushButton#CloseBtn {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 7px;
                padding: 0px;
            }
            QPushButton#MinimizeBtn:hover, QPushButton#SettingsBtn:hover,
            QPushButton#HelpBtn:hover {
                background-color: rgba(255, 255, 255, 0.16);
                border: 1px solid rgba(255, 255, 255, 0.22);
            }
            QPushButton#CloseBtn:hover {
                background-color: rgba(255, 69, 58, 0.85);
                border: 1px solid rgba(255, 69, 58, 0.9);
            }

            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.14);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0a84ff;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 13px;
                height: 13px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #ffffff;
                width: 15px;
                margin-left: -1px;
                margin-right: -1px;
                border-radius: 7px;
            }
        """)

        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(16, 14, 16, 14)
        self.main_layout.setSpacing(12)

        # 1. 브랜드 타이틀바 + 창 제어 (toggle 대상이라 컨테이너로 묶는다)
        self.top_control_widget = QWidget()
        top_bar_layout = QHBoxLayout(self.top_control_widget)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(7)

        self.brand_mark = QLabel()
        self.brand_mark.setFixedSize(22, 22)
        self.brand_mark.setPixmap(get_svg_pixmap(LUCIDE_PENGUIN_SVG, 22))
        top_bar_layout.addWidget(self.brand_mark)

        brand_name = QLabel("PENGU ZOOM")
        brand_name.setObjectName("BrandName")
        top_bar_layout.addWidget(brand_name)

        brand_version = QLabel(f"PRO {APP_VERSION}")
        brand_version.setObjectName("BrandVersion")
        top_bar_layout.addWidget(brand_version)

        top_bar_layout.addStretch()

        # 아이콘은 전부 동일한 중성 회색으로 톤을 맞춘다.
        icon_tint = "#c7c7cc"
        for attr, object_name, svg, handler in (
            ("minimize_btn", "MinimizeBtn", LUCIDE_MINIMIZE_SVG, self.showMinimized),
            ("settings_btn", "SettingsBtn", LUCIDE_SETTINGS_SVG, self.show_settings),
            ("help_btn", "HelpBtn", LUCIDE_HELP_SVG, self.show_help),
            ("close_btn", "CloseBtn", LUCIDE_CLOSE_SVG, self.close),
        ):
            button = QPushButton()
            button.setObjectName(object_name)
            button.setFixedSize(23, 23)
            button.setIcon(get_svg_icon(recolor_svg_stroke(svg, icon_tint)))
            button.setIconSize(QSize(13, 13))
            button.clicked.connect(handler)
            top_bar_layout.addWidget(button)
            setattr(self, attr, button)

        self.main_layout.addWidget(self.top_control_widget)

        # 2. 세그먼티드 컨트롤: 흩어져 있던 토글 3개를 한 트랙으로 묶는다
        self.segment_track = QFrame()
        self.segment_track.setObjectName("SegmentTrack")
        segment_layout = QHBoxLayout(self.segment_track)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(3)

        self.select_btn = QPushButton('영역 지정')
        self.select_btn.clicked.connect(self.start_selection)
        segment_layout.addWidget(self.select_btn)

        self.follow_btn = QPushButton('따라오기 켬')
        self.follow_btn.setProperty("class", "PrimaryActive")
        self.follow_btn.clicked.connect(self.toggle_follow)
        segment_layout.addWidget(self.follow_btn)

        self.click_through_btn = QPushButton('마우스 투과 끔')
        self.click_through_btn.clicked.connect(self.toggle_click_through)
        segment_layout.addWidget(self.click_through_btn)

        self.main_layout.addWidget(self.segment_track)

        # 3. 확대 화면 (항상 표시)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(VIEWPORT_STYLE_FRAMED)
        self.label.setMinimumSize(100, 100)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(self.label)

        # 4. 하단 슬라이더 (toggle 대상)
        self.bottom_control_widget = QWidget()
        bottom_bar_layout = QVBoxLayout(self.bottom_control_widget)
        bottom_bar_layout.setContentsMargins(0, 0, 0, 0)
        bottom_bar_layout.setSpacing(10)

        self.zoom_val_label = QLabel('2.0x')
        self.opacity_val_label = QLabel('100%')
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(20)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(15, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.on_opacity_slider_changed)

        # 라벨과 값을 슬라이더 위 한 줄에 올려 좌우 정렬을 맞춘다.
        for caption, value_label, slider in (
            ('배율', self.zoom_val_label, self.zoom_slider),
            ('투명도', self.opacity_val_label, self.opacity_slider),
        ):
            row = QVBoxLayout()
            row.setSpacing(3)

            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            caption_label = QLabel(caption)
            caption_label.setObjectName("FieldLabel")
            value_label.setObjectName("FieldValue")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            head.addWidget(caption_label)
            head.addStretch()
            head.addWidget(value_label)

            row.addLayout(head)
            row.addWidget(slider)
            bottom_bar_layout.addLayout(row)

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
            self.segment_track.setVisible(False)
            self.bottom_control_widget.setVisible(False)
            
            # 3. Toggle outer ResizableContainer frame style and margins
            self.container.setStyleSheet(CONTAINER_STYLE_BARE)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.container.grip.hide()
            self.label.setStyleSheet(VIEWPORT_STYLE_BARE)
            
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
            self.segment_track.setVisible(True)
            self.bottom_control_widget.setVisible(True)
            
            # 5. Restore round corners, outer border frame and resize grip
            self.container.setStyleSheet(CONTAINER_STYLE_FRAMED)
            self.main_layout.setContentsMargins(16, 14, 16, 14)
            self.container.grip.show()
            self.label.setStyleSheet(VIEWPORT_STYLE_FRAMED)
            
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
            screen = QApplication.screenAt(QPoint(x + w // 2, y + h // 2)) or QApplication.primaryScreen()
            ratio = screen.devicePixelRatio()
            self.detector.slots[self.cooldown_capture_name].device_ratio = ratio
            
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
            if slot:
                duration = 0 if is_ready else sync_remaining_seconds(self.detector, name)
                self.client.send_update(name, is_ready, duration)

    def broadcast_skill_states(self):
        # Periodically send all registered skill states to keep party server alive and sync initial states
        if self.client_running and self.client:
            for name, slot in self.detector.slots.items():
                duration = 0 if slot.is_ready else sync_remaining_seconds(self.detector, name)
                self.client.send_update(name, slot.is_ready, duration)
        self.broadcast_boss_debuff(force=True)

    # ------------------------------------------------------------------
    # Boss debuff (암흑 수류탄) detection
    # ------------------------------------------------------------------
    @staticmethod
    def default_boss_debuff_config():
        return {
            'enabled': False,
            'region': None,
            'threshold': boss_debuff_detector.DEFAULT_MATCH_THRESHOLD,
            'duration': 0.0,          # 0 = learn the total duration automatically
            'learned_duration': 0.0,  # auto-learned total, kept across restarts
            'min_icon_px': boss_debuff_detector.DEFAULT_MIN_ICON_PX,
            'max_icon_px': boss_debuff_detector.DEFAULT_MAX_ICON_PX,
            'collect_samples': False,
            'share_with_party': True,
        }

    def apply_boss_debuff_settings(self):
        """Push the stored config into the detector and start/stop its thread."""
        config = getattr(self, 'boss_debuff_config', None) or self.default_boss_debuff_config()
        self.boss_debuff_config = config
        region = config.get('region')
        ratio = QApplication.primaryScreen().devicePixelRatio()
        if region:
            screen = QApplication.screenAt(QPoint(int(region[0] + region[2] // 2),
                                                  int(region[1] + region[3] // 2)))
            if screen:
                ratio = screen.devicePixelRatio()
        self.boss_debuff_detector.configure(
            enabled=bool(config.get('enabled')) and bool(region),
            region=region,
            device_ratio=ratio,
            match_threshold=config.get('threshold'),
            duration=config.get('duration'),
            learned_duration=config.get('learned_duration'),
            min_icon_px=config.get('min_icon_px'),
            max_icon_px=config.get('max_icon_px'),
            collect_samples=config.get('collect_samples'),
        )
        if self.party_panel:
            self.party_panel.set_boss_debuff_enabled(self.boss_debuff_detector.enabled)
        if self.boss_debuff_detector.enabled:
            self.boss_debuff_detector.start_detection(100)
        else:
            self.boss_debuff_state = {}
            if self.boss_debuff_detector.isRunning():
                self.boss_debuff_detector.stop_detection()

    def start_boss_debuff_region_capture(self, config_dialog):
        """Drag-select the debuff strip band under the boss HP bar."""
        self.config_dialog_ref = config_dialog
        self.is_settings_open = True
        self.hide()
        self.boss_region_overlay = CaptureOverlay()
        self.boss_region_overlay.capture_completed.connect(self.on_boss_debuff_region_captured)
        self.boss_region_overlay.exec()
        self.restore_settings_open_state()
        dialog = getattr(self, 'config_dialog_ref', None)
        if dialog and hasattr(dialog, 'refresh_boss_debuff_ui'):
            dialog.refresh_boss_debuff_ui()

    def on_boss_debuff_region_captured(self, x, y, w, h, captured_rgb):
        # Only the rectangle is kept; the icon template ships with the app.
        if w < 40 or h < 20:
            return
        config = getattr(self, 'boss_debuff_config', None) or self.default_boss_debuff_config()
        config['region'] = [int(x), int(y), int(w), int(h)]
        self.boss_debuff_config = config
        self.apply_boss_debuff_settings()
        self.save_settings()

    def auto_estimate_boss_debuff_region(self):
        screen = QApplication.primaryScreen()
        geometry = screen.geometry()
        region = self.boss_debuff_detector.auto_region_for_screen(geometry.width(), geometry.height())
        region[0] += geometry.x()
        region[1] += geometry.y()
        config = getattr(self, 'boss_debuff_config', None) or self.default_boss_debuff_config()
        config['region'] = region
        self.boss_debuff_config = config
        self.apply_boss_debuff_settings()
        self.save_settings()
        return region

    def on_boss_debuff_updated(self, debuff_id, state):
        self.boss_debuff_state = state or {}
        if self.party_panel:
            self.party_panel.update_boss_debuff(self.boss_debuff_state)
        self.broadcast_boss_debuff()
        
        # Persist the learned total duration, in both directions.  It used to be
        # written only when it grew, so a value inflated by an old build (a 20s
        # debuff stored as 28.8s) survived every restart and each new cast
        # started by flashing 28초 until OCR corrected it.
        config = getattr(self, 'boss_debuff_config', None)
        learned = float(self.boss_debuff_state.get('learned_duration', 0) or 0)
        if isinstance(config, dict) and self.boss_debuff_state.get('active'):
            stored = float(config.get('learned_duration', 0) or 0)
            if learned > 0.0 and abs(learned - stored) > 0.05:
                config['learned_duration'] = round(learned, 1)
                self.save_settings()
        
        dialog = getattr(self, 'config_dialog_ref', None)
        if dialog and dialog.isVisible() and hasattr(dialog, 'on_boss_debuff_state'):
            dialog.on_boss_debuff_state(self.boss_debuff_state)

    def broadcast_boss_debuff(self, force=False):
        """Share the boss debuff with the party over the existing skill channel."""
        config = getattr(self, 'boss_debuff_config', None) or {}
        if not config.get('share_with_party', True):
            return
        if not (self.client_running and self.client):
            return
        state = getattr(self, 'boss_debuff_state', None) or {}
        if not state:
            return
        active = bool(state.get('active'))
        remaining = state.get('remaining')
        seconds = 0 if remaining is None else max(0, int(math.ceil(float(remaining))))
        previous_active, previous_seconds, previous_at = getattr(
            self, 'boss_debuff_last_sent', (None, None, 0.0)
        )
        now = time.time()
        if not force and previous_active == active and previous_seconds == seconds and now - previous_at < 1.0:
            return
        self.boss_debuff_last_sent = (active, seconds, now)
        self.client.send_update(party_state_key(self.boss_debuff_detector.debuff_id), active, seconds)

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

    def request_character_profile(self, character_name, server_url=None):
        lookup_url = (server_url or self.server_url).strip()
        self.active_character_lookup_request = self.character_profile_lookup.lookup(
            lookup_url,
            character_name,
        )

    def on_character_profile_loaded(self, request_id, profile):
        if request_id != self.active_character_lookup_request:
            return

        requested_name = str(profile.get("requested_name", "")).strip()
        dialog = getattr(self, "config_dialog_ref", None)
        if dialog and dialog.isVisible():
            current_name = dialog.txt_char_name.text().strip()
            if current_name.casefold() != requested_name.casefold():
                return

        class_name = str(profile.get("character_class", "")).strip()
        if class_name not in LOST_ARK_CLASSES:
            self.on_character_profile_failed(
                request_id,
                f"지원 목록에 없는 직업입니다: {class_name or '알 수 없음'}",
            )
            return

        old_name = self.player_name
        self.player_name = requested_name
        self.player_class = class_name
        self.resolved_character_name = requested_name

        if old_name and old_name != requested_name:
            self.party_panel.player_classes.pop(old_name, None)
        self.party_panel.player_classes[requested_name] = class_name

        if self.client and self.client.player_name.casefold() == requested_name.casefold():
            self.client.set_class_name(class_name)
            self.client.party_states.setdefault(self.client.player_name, {})["_class"] = class_name
            self.party_panel.update_states(self.client.party_states)

        self.save_settings()
        if dialog and dialog.isVisible():
            dialog.on_character_lookup_succeeded(profile)

    def on_character_profile_progress(self, request_id, message):
        if request_id != self.active_character_lookup_request:
            return
        dialog = getattr(self, "config_dialog_ref", None)
        if dialog and dialog.isVisible():
            dialog.on_character_lookup_progress(message)

    def on_character_profile_failed(self, request_id, message):
        if request_id != self.active_character_lookup_request:
            return
        dialog = getattr(self, "config_dialog_ref", None)
        if dialog and dialog.isVisible():
            dialog.on_character_lookup_failed(dialog.pending_lookup_name, message)

    # Client networking control (uses show_dark_message_box for gorgeous contrast popup)
    def start_party_client(self):
        try:
            self.client = network_manager.CooldownClient(
                server_url=self.server_url, 
                player_name=self.player_name,
                room_id=self.room_id,
                client_id=self.client_id,
                class_name=getattr(self, 'player_class', "홀리나이트")
            )
            self.client.status_updated.connect(self.party_panel.update_states, Qt.ConnectionType.QueuedConnection)
            self.client.connection_failed.connect(self.on_client_connection_failed, Qt.ConnectionType.QueuedConnection)
            self.client.connection_ok.connect(self.on_client_connection_ok, Qt.ConnectionType.QueuedConnection)
            self.client.start()
            self.client_running = True
        except Exception as e:
            self.client_running = False
            try:
                show_dark_message_box(self, "접속 오류", f"대기실 접속 시도 중 오류가 발생했습니다:\n{str(e)}", QMessageBox.Icon.Critical)
            except Exception:
                pass

    def on_client_connection_ok(self):
        if hasattr(self, 'config_dialog_ref') and self.config_dialog_ref and self.config_dialog_ref.isVisible():
            dlg = self.config_dialog_ref
            dlg.spinner_timer.stop()
            dlg.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_CHECK_SVG, 16))
            dlg.lbl_client_icon.setVisible(True)
            dlg.lbl_client_status.setText("동기화 정상 연결됨")
            dlg._apply_client_status_tone("StatusOk")

    def on_client_connection_failed(self, error_msg):
        import time
        if hasattr(self, 'config_dialog_ref') and self.config_dialog_ref and self.config_dialog_ref.isVisible():
            dlg = self.config_dialog_ref
            elapsed = time.time() - dlg.client_connection_start_time
            if elapsed < 45.0:
                dlg.lbl_client_status.setText("서버 활성화 중... (최대 1분 소요)")
                dlg._apply_client_status_tone("StatusWarn")
                return
            
            dlg.spinner_timer.stop()
            
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
            
            dlg.lbl_client_icon.setPixmap(get_svg_pixmap(LUCIDE_ERROR_SVG, 16))
            dlg.lbl_client_icon.setVisible(True)
            dlg.lbl_client_status.setText(f"실패: {korean_msg}")
            dlg._apply_client_status_tone("StatusError")

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
        self.follow_btn.setText('따라오기 끔')
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
            self.follow_btn.setText('따라오기 켬')
            self.follow_btn.setProperty("class", "PrimaryActive")
            self.last_capture_pos = QCursor.pos()
        else:
            self.follow_btn.setText('따라오기 끔')
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
            self.click_through_btn.setText('마우스 투과 켬')
            self.click_through_btn.setProperty("class", "PrimaryActive")
        else:
            new_style = style & ~WS_EX_TRANSPARENT
            self.click_through_btn.setText('마우스 투과 끔')
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

            src_w, src_h = sct_img.size
            qimg, frame_buffer = scale_bgra_frame_to_qimage(
                sct_img.bgra, src_w, src_h, view_w, view_h)
            if qimg is None:
                return
            pixmap = QPixmap.fromImage(qimg)
            # QPixmap이 픽셀을 복사한 뒤에야 numpy 버퍼를 놓아준다.
            del frame_buffer
            
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
            # 핫 패스라 매 프레임 로그를 남길 수는 없다. 다만 통째로 삼키면
            # 프레임 드롭 원인을 추적할 수 없으므로 첫 실패만 보관해 둔다.
            self.frame_error_count += 1
            if self.last_frame_error is None:
                self.last_frame_error = traceback.format_exc()

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

            # Trigger manual cooldown for matching skill slots
            for name, slot in list(self.detector.slots.items()):
                if getattr(slot, 'trigger_key', None) == current_key_name:
                    self.detector.request_trigger(name)
                    
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
        # 렌더 타이머를 먼저 멈춰야 아래에서 mss를 닫은 뒤 update_magnifier가
        # 이미 닫힌 핸들로 grab을 시도하지 않는다.
        try:
            self.timer.stop()
            self.party_sync_timer.stop()
        except Exception:
            pass
        self.detector.stop_detection()
        try:
            self.boss_debuff_detector.stop_detection()
        except Exception:
            pass
        self.stop_party_server()
        self.stop_party_client()
        self.party_panel.close()
        self.stop_listeners()
        # mss는 GDI 리소스를 잡고 있어 명시적으로 닫지 않으면 장시간 구동 시
        # 핸들이 누적된다.
        try:
            self.sct.close()
        except Exception:
            pass
        super().closeEvent(event)

def get_own_process_names():
    """현재 실행 형태에 해당하는 프로세스 이름 후보를 돌려준다.

    기존 구현은 "펭구 줌인 Pro" 문자열을 하드코딩했는데, 실제 산출물 이름은
    "펭구 줌인 2.47 Pro.exe"라 부분 문자열이 일치하지 않았다. 그래서 중복 인스턴스
    정리가 한 번도 동작하지 않았고, 두 번 실행하면 전역 훅이 두 벌 걸렸다.
    이제 sys.executable 이름에서 직접 유도해 이름을 바꿔도 따라간다.
    """
    names = set()
    try:
        exe_name = os.path.basename(sys.executable or "")
        if exe_name:
            names.add(exe_name.lower())
    except Exception:
        pass
    # 하위호환: 과거 배포본 이름들
    names.update({"pengzoompro.exe", "펭구 줌인 pro.exe"})
    return names


def kill_zombie_processes():
    """이전 인스턴스를 정리한다(크래시 후 남은 프로세스 포함).

    PyInstaller onefile은 부트로더 부모와 실제 앱 자식이 같은 이름을 갖는다.
    부모를 죽이면 자신이 함께 내려가므로 조상 PID는 건드리지 않는다.
    """
    try:
        import psutil
    except ImportError:
        return

    try:
        current_pid = os.getpid()
        current = psutil.Process(current_pid)
        # 자기 자신과 조상(onefile 부트로더 부모 포함)은 대상에서 제외한다.
        protected = {current_pid}
        try:
            for parent in current.parents():
                protected.add(parent.pid)
        except Exception:
            pass

        frozen = getattr(sys, 'frozen', False)
        own_names = get_own_process_names()

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = proc.info['pid']
                if pid in protected:
                    continue

                name = (proc.info['name'] or "").lower()
                cmdline = proc.info['cmdline'] or []

                if frozen:
                    is_target = name in own_names
                else:
                    is_target = ("python" in name
                                 and any("magnifier.py" in arg for arg in cmdline))

                if is_target:
                    psutil.Process(pid).terminate()
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
        
    window = MagnifierWindow()
    window.show()
    sys.exit(app.exec())
