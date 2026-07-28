import sys
import os
import json
import time
import math
import mss
import numpy as np
import winsound  # Win32 system sound for cooldown alerts
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
from PyQt6.QtCore import QTimer, Qt, QPoint, QRect, pyqtSignal, QObject, QSize, QPropertyAnimation, QEasingCurve, QEvent
from PyQt6.QtGui import QImage, QPixmap, QCursor, QPainter, QPen, QColor, QIcon, QKeySequence, QWheelEvent, QFont, QBrush
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
from PIL import Image
from pynput import keyboard, mouse
import cv2

# Import our custom modules
import cooldown_detector
import network_manager
import boss_debuff_detector
from boss_debuff_panel import BossDebuffBanner, party_state_key
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

# Use APPDATA-based cache dir for EXE compatibility
if getattr(sys, 'frozen', False):
    _appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    CACHE_DIR = os.path.join(_appdata, 'PengZoom', 'cache')
else:
    CACHE_DIR = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "scratch", "cache")
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
    }
}

class CircularProgress(QWidget):
    def __init__(self, color_hex="#ff453a", parent=None):
        super().__init__(parent)
        self.value = 100.0
        self.color = QColor(color_hex)
        self.bg_color = QColor(255, 255, 255, 10)
        self.text = ""
        self.flash_val = 0.0
        self.setFixedSize(28, 28)
        
    def setValue(self, val):
        self.value = float(val)
        self.update()
        
    def setColor(self, color_hex):
        self.color = QColor(color_hex)
        self.update()
        
    def setText(self, text):
        self.text = text
        self.update()
        
    def setFlash(self, val):
        self.flash_val = float(val)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(2, 2, -2, -2)
        
        painter.setPen(QPen(self.bg_color, 2))
        painter.drawEllipse(rect)
        
        pen = QPen(self.color, 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        angle = int((self.value / 100.0) * 360 * 16)
        painter.drawArc(rect, 90 * 16, -angle)
        
        if self.text:
            painter.setPen(QPen(QColor("#ffffff")))
            font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)
            
        if self.flash_val > 0.0:
            flash_color = QColor(255, 255, 255, int(200 * self.flash_val))
            painter.setBrush(QBrush(flash_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))

class GlowDot(QWidget):
    def __init__(self, color_hex="#30d158", parent=None):
        super().__init__(parent)
        self.color = QColor(color_hex)
        self.setFixedSize(14, 14)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)
        
        self.start_time = time.time()
        self.speed = 1.0
        self.intensity = 1.0
        
    def setColor(self, color_hex):
        self.color = QColor(color_hex)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center = self.rect().center()
        base_rad = 3.0
        
        elapsed = time.time() - self.start_time
        scale = 0.5 + 0.5 * math.sin(elapsed * 2 * math.pi * 0.70 * self.speed)
        
        max_glow_radius = 6.5
        current_glow_radius = base_rad + (max_glow_radius - base_rad) * scale
        
        for r in range(int(current_glow_radius) + 1):
            if r <= base_rad:
                continue
            alpha = int((1.0 - (r - base_rad) / (max_glow_radius - base_rad)) * 45 * scale * self.intensity)
            c = QColor(self.color.red(), self.color.green(), self.color.blue(), max(0, min(255, alpha)))
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, r, r)
            
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, int(base_rad), int(base_rad))

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
        self.layout_mode = "세로형"
        self.display_mode = "상세 정보"
        self.ui_scale = 1.0
        self.speed = 1.0
        self.intensity = 1.0
        self.player_classes = {}
        self.icon_downloaded.connect(self._deliver_downloaded_icon)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        
        self.container = QFrame()
        self.container.setObjectName("Container")
        self.container.setMouseTracking(True)
        self.container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(14, 14, 14, 14)
        self.container_layout.setSpacing(10)
        
        # Boss debuff readout (암흑 수류탄) sits above the player cards
        self._boss_local_enabled = False
        self.boss_banner = BossDebuffBanner(ui_scale=self.ui_scale)
        self.boss_banner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.boss_banner.setVisible(False)
        self.container_layout.addWidget(self.boss_banner)
        
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        self.container_layout.addLayout(self.list_layout)
        
        layout.addWidget(self.container)
        self.resize(240, 320)
        
        self.widgets = {}
        self.panel_opacity = 90
        self.setWindowOpacity(self.panel_opacity / 100.0)
        
        self.resize_dir = None
        self.drag_position = None
        self.resize_border = 15
        
        # 60fps updates (16ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick_timers)
        self.timer.start(16)
        
        self.update_theme_styles()
        self.apply_theme()

    def _deliver_downloaded_icon(self, path, callback):
        try:
            callback(path)
        except RuntimeError:
            # The player card can disappear before its background download ends.
            pass
        
    def update_theme_styles(self):
        theme = THEMES[self.theme_name]
        self.container_style_normal = f"""
            #Container {{
                background-color: {theme['bg']};
                border: 1.2px solid rgba(255, 255, 255, 0.02);
                border-radius: 16px;
            }}
            QLabel {{ color: {theme['font_color']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
            QFrame.PlayerCard {{ background-color: {theme['card_bg']}; border: {theme['card_border']}; border-radius: 12px; }}
            QFrame.SkillBadge {{ background-color: rgba(255, 255, 255, 0.01); border: 1px solid rgba(255, 255, 255, 0.02); border-radius: 8px; }}
        """
        self.container_style_hover = f"""
            #Container {{
                background-color: {theme['bg']};
                border: {theme['border']};
                border-radius: 16px;
            }}
            QLabel {{ color: {theme['font_color']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
            QFrame.PlayerCard {{ background-color: {theme['card_bg']}; border: {theme['card_border']}; border-radius: 12px; }}
            QFrame.SkillBadge {{ background-color: rgba(255, 255, 255, 0.01); border: 1px solid rgba(255, 255, 255, 0.02); border-radius: 8px; }}
        """
        
    def apply_theme(self):
        self.update_theme_styles()
        self.container.setStyleSheet(self.container_style_normal)
        theme = THEMES[self.theme_name]
        
        if hasattr(self, "boss_banner"):
            self.boss_banner.apply_scale(self.ui_scale)
            self.boss_banner.apply_theme(theme)
        
        for player, p_info in self.widgets.items():
            for skill, s_widgets in p_info["skill_widgets"].items():
                s_widgets["glow"].setColor(theme['ready'])
                s_widgets["glow"].speed = self.speed
                s_widgets["glow"].intensity = self.intensity
                s_widgets["progress"].setColor(theme['cooldown'])

    # -- boss debuff (암흑 수류탄) -------------------------------------------
    def set_boss_debuff_enabled(self, enabled):
        """Local detection toggle; party reports can still show the banner."""
        self._boss_local_enabled = bool(enabled)
        if not enabled and hasattr(self, "boss_banner"):
            self.boss_banner.clear_local()
        self.sync_boss_banner_visibility()

    def sync_boss_banner_visibility(self):
        if not hasattr(self, "boss_banner"):
            return
        visible = getattr(self, "_boss_local_enabled", False) or self.boss_banner.has_reports()
        if self.boss_banner.isVisible() != visible:
            self.boss_banner.setVisible(visible)
            self.adjustSize()

    def update_boss_debuff(self, state):
        if hasattr(self, "boss_banner"):
            self.boss_banner.set_local_state(state or {})
            self.sync_boss_banner_visibility()
                
    def rebuild_cards(self):
        for i in reversed(range(self.list_layout.count())):
            item = self.list_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        self.widgets.clear()
        
        if self.parent_window and self.parent_window.client:
            self.update_states(self.parent_window.client.party_states)
            
    def update_states(self, party_states):
        received_at = time.time()
        current_players = set(party_states.keys())
        
        # Boss debuff reports ride along the party channel under a '_' prefixed
        # key, so the skill-badge loop below skips them automatically.
        if hasattr(self, "boss_banner"):
            local_name = getattr(self.parent_window, "player_name", "") if self.parent_window else ""
            self.boss_banner.ingest_party_states(party_states, exclude_player=local_name)
            self.sync_boss_banner_visibility()
        
        # Remove old players
        for p in list(self.widgets.keys()):
            if p not in current_players:
                self.widgets[p]["widget"].deleteLater()
                del self.widgets[p]
                
        for player, skills in party_states.items():
            if player not in self.widgets:
                player_widget = QFrame()
                player_widget.setProperty("class", "PlayerCard")
                player_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                
                p_lay = QVBoxLayout(player_widget)
                p_lay.setContentsMargins(10, 8, 10, 8)
                p_lay.setSpacing(6)
                
                name_row = QHBoxLayout()
                name_row.setSpacing(6)
                
                icon_lbl = QLabel()
                icon_lbl.setFixedSize(CLASS_ICON_SIZE, CLASS_ICON_SIZE)
                icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                
                name_lbl = QLabel(player)
                name_lbl.setStyleSheet(f"font-size: {int(12*self.ui_scale)}px; font-weight: 700; opacity: 0.85;")
                name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                
                name_row.addWidget(icon_lbl)
                name_row.addWidget(name_lbl)
                name_row.addStretch()
                p_lay.addLayout(name_row)
                
                skills_widget = QWidget()
                skills_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                if self.layout_mode == "가로형":
                    skills_lay = QHBoxLayout(skills_widget)
                    skills_lay.setContentsMargins(0, 0, 0, 0)
                    skills_lay.setSpacing(int(8*self.ui_scale))
                else:
                    skills_lay = QVBoxLayout(skills_widget)
                    skills_lay.setContentsMargins(0, 0, 0, 0)
                    skills_lay.setSpacing(int(4*self.ui_scale))
                
                p_lay.addWidget(skills_widget)
                self.list_layout.addWidget(player_widget)
                
                self.widgets[player] = {
                    "widget": player_widget,
                    "skills_layout": skills_lay,
                    "skills_widget_container": skills_widget,
                    "icon_lbl": icon_lbl,
                    "name_lbl": name_lbl,
                    "skill_widgets": {}
                }
                
            p_data = self.widgets[player]
            
            # Fetch emblem from the server or local mapping
            class_name = skills.get("_class", self.player_classes.get(player, "홀리나이트")) if isinstance(skills, dict) else "홀리나이트"
            self.player_classes[player] = class_name
            
            def _apply_icon(path, lbl=p_data["icon_lbl"]):
                if path and is_valid_class_icon(path):
                    renderer = QSvgRenderer(path)
                    if renderer.isValid():
                        pixmap = QPixmap(CLASS_ICON_SIZE, CLASS_ICON_SIZE)
                        pixmap.fill(Qt.GlobalColor.transparent)
                        painter = QPainter(pixmap)
                        renderer.render(painter)
                        # Official class SVGs use mixed dark/light fills.  Keep the
                        # vector alpha mask but normalize every emblem to HUD white.
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("#f5f5f7"))
                        painter.end()
                        lbl.setPixmap(pixmap)
                        return
                lbl.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border-radius: 9px;")
            
            # Try cached first (instant), else async download
            base_key = LOST_ARK_CLASSES.get(class_name)
            cached_path = os.path.join(CACHE_DIR, f"class_{base_key}.svg") if base_key else None
            if cached_path and is_valid_class_icon(cached_path):
                _apply_icon(cached_path)
            else:
                p_data["icon_lbl"].setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border-radius: 9px;")
                if base_key:
                    get_class_icon_async(
                        class_name,
                        lambda path, apply_icon=_apply_icon: self.icon_downloaded.emit(path, apply_icon)
                    )
                
            for s in list(p_data["skill_widgets"].keys()):
                if s not in skills:
                    p_data["skill_widgets"][s]["badge"].deleteLater()
                    del p_data["skill_widgets"][s]
                    
            for skill, s_info in (skills.items() if isinstance(skills, dict) else {}):
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
                reported_deadline = (
                    timestamp + cooldown_duration
                    if not is_ready and cooldown_duration > 0.0
                    else 0.0
                )
                
                if skill not in p_data["skill_widgets"]:
                    badge = QFrame()
                    badge.setProperty("class", "SkillBadge")
                    badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    b_lay = QHBoxLayout(badge)
                    b_lay.setContentsMargins(int(8*self.ui_scale), int(5*self.ui_scale), int(8*self.ui_scale), int(5*self.ui_scale))
                    b_lay.setSpacing(int(8*self.ui_scale))
                    
                    indicator_container = QWidget()
                    indicator_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    ind_lay = QHBoxLayout(indicator_container)
                    ind_lay.setContentsMargins(0, 0, 0, 0)
                    ind_lay.setSpacing(0)
                    
                    theme = THEMES[self.theme_name]
                    glow = GlowDot(theme["ready"])
                    glow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    glow.speed = self.speed
                    glow.intensity = self.intensity
                    
                    progress = CircularProgress(theme["cooldown"])
                    progress.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    
                    ind_lay.addWidget(glow)
                    ind_lay.addWidget(progress)
                    b_lay.addWidget(indicator_container)
                    
                    text_container = QWidget()
                    text_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    t_lay = QVBoxLayout(text_container)
                    t_lay.setContentsMargins(0, 0, 0, 0)
                    t_lay.setSpacing(0)
                    
                    skill_name_lbl = QLabel(skill)
                    skill_name_lbl.setStyleSheet(f"font-size: {int(11*self.ui_scale)}px; font-weight: 600;")
                    skill_name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    
                    status_lbl = QLabel("Ready")
                    status_lbl.setStyleSheet(f"font-size: {int(9*self.ui_scale)}px; font-weight: bold; opacity: 0.6;")
                    status_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    
                    t_lay.addWidget(skill_name_lbl)
                    t_lay.addWidget(status_lbl)
                    b_lay.addWidget(text_container)
                    b_lay.addStretch()
                    
                    p_data["skills_layout"].addWidget(badge)
                    p_data["skill_widgets"][skill] = {
                        "badge": badge,
                        "glow": glow,
                        "progress": progress,
                        "skill_name_lbl": skill_name_lbl,
                        "status_text_lbl": status_lbl,
                        "text_container": text_container,
                        "is_ready": is_ready,
                        "cooldown_duration": cooldown_duration,
                        "timestamp": timestamp,
                        "cycle_total": cooldown_duration if not is_ready else 0.0,
                        "cooldown_deadline": reported_deadline,
                        "flash_val": 0.0,
                        "was_ready": is_ready
                    }
                else:
                    s_widgets = p_data["skill_widgets"][skill]
                    previous_ready = bool(s_widgets.get("is_ready", False))
                    previous_total = max(0.0, float(s_widgets.get("cycle_total", 0.0) or 0.0))
                    previous_deadline = max(0.0, float(s_widgets.get("cooldown_deadline", 0.0) or 0.0))
                    expected_remaining = max(0.0, previous_deadline - received_at)
                    restarted_while_cooldown = (
                        reported_deadline > 0.0
                        and (
                            previous_deadline <= received_at
                            or cooldown_duration > expected_remaining + 1.25
                        )
                    )

                    if is_ready:
                        cycle_total = 0.0
                        cooldown_deadline = 0.0
                    elif previous_ready:
                        # A Ready -> Cooldown transition starts a new visual cycle.
                        cycle_total = cooldown_duration
                        cooldown_deadline = reported_deadline
                    elif restarted_while_cooldown:
                        # Gauge skills or cooldown resets can start another cycle
                        # without a debounced Ready frame between the two uses.
                        # A meaningful increase beyond the expected remaining
                        # time re-latches the total and deadline.
                        cycle_total = cooldown_duration
                        cooldown_deadline = reported_deadline
                    else:
                        # Periodic sync reports the *remaining* seconds.  Keep the
                        # first total as the ring denominator and only allow the
                        # estimated deadline to move earlier (OCR cooldown cut).
                        cycle_total = max(previous_total, cooldown_duration)
                        if previous_deadline > 0.0 and reported_deadline > 0.0:
                            cooldown_deadline = min(previous_deadline, reported_deadline)
                        elif previous_deadline > 0.0:
                            cooldown_deadline = previous_deadline
                        else:
                            cooldown_deadline = reported_deadline

                    s_widgets["is_ready"] = is_ready
                    s_widgets["cooldown_duration"] = cooldown_duration
                    s_widgets["timestamp"] = timestamp
                    s_widgets["cycle_total"] = cycle_total
                    s_widgets["cooldown_deadline"] = cooldown_deadline
                    
                s_widgets = p_data["skill_widgets"][skill]
                if self.display_mode == "아이콘만":
                    s_widgets["text_container"].hide()
                    s_widgets["badge"].setStyleSheet("QFrame.SkillBadge { border: none; background: transparent; }")
                else:
                    s_widgets["text_container"].show()

    def tick_timers(self):
        current_time = time.time()
        theme = THEMES[self.theme_name]
        
        if hasattr(self, "boss_banner") and self.boss_banner.isVisible():
            self.boss_banner.tick()
        
        for player, p_data in list(self.widgets.items()):
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
                    flash_val = max(0.0, flash_val - 0.04)
                    s_widgets["flash_val"] = flash_val
                    
                s_widgets["progress"].setFlash(flash_val)
                
                if is_ready:
                    s_widgets["glow"].show()
                    s_widgets["progress"].hide()
                    s_widgets["status_text_lbl"].setText("Ready")
                    s_widgets["status_text_lbl"].setStyleSheet(f"color: {theme['ready']}; font-size: {int(9*self.ui_scale)}px; font-weight: bold;")
                    
                    flash_alpha = int(12 + 60 * flash_val)
                    border_alpha = int(36 + 180 * flash_val)
                    s_widgets["badge"].setStyleSheet(f"QFrame.SkillBadge {{ background-color: rgba(48, 209, 88, {flash_alpha/255.0:.2f}); border: 1.2px solid rgba(48, 209, 88, {border_alpha/255.0:.2f}); }}")
                else:
                    s_widgets["glow"].hide()
                    s_widgets["progress"].show()

                    if cycle_total > 0.0 and remaining > 0.0:
                        pct = max(0.0, min(100.0, (remaining / cycle_total) * 100.0))
                        s_widgets["progress"].setValue(pct)

                        if remaining >= 1.0:
                            s_widgets["progress"].setText(f"{int(math.ceil(remaining))}")
                            s_widgets["status_text_lbl"].setText(f"{int(math.ceil(remaining))}s")
                        else:
                            s_widgets["progress"].setText(f"{remaining:.1f}")
                            s_widgets["status_text_lbl"].setText(f"{remaining:.1f}s")
                    else:
                        # Countdown reaching zero is not Ready.  Gauge-dependent
                        # skills can stay unavailable until the Ready template is
                        # actually recognized.
                        s_widgets["progress"].setValue(0.0)
                        s_widgets["progress"].setText("…")
                        s_widgets["status_text_lbl"].setText("Cooldown")
                        
                    s_widgets["status_text_lbl"].setStyleSheet(f"color: {theme['cooldown']}; font-size: {int(9*self.ui_scale)}px; font-weight: bold;")
                    s_widgets["badge"].setStyleSheet(f"QFrame.SkillBadge {{ background-color: rgba(255, 69, 58, 0.03); border: 1.2px solid rgba(255, 69, 58, 0.12); }}")

    def enterEvent(self, event):
        if not self.panel_click_through:
            self.container.setStyleSheet(self.container_style_hover)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if not self.panel_click_through:
            self.container.setStyleSheet(self.container_style_normal)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.panel_click_through: return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            rect = self.rect()
            
            is_right = pos.x() >= rect.width() - self.resize_border
            is_bottom = pos.y() >= rect.height() - self.resize_border
            
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
        if self.panel_click_through: return
        pos = event.position().toPoint()
        rect = self.rect()
        
        if event.buttons() == Qt.MouseButton.NoButton:
            is_right = pos.x() >= rect.width() - self.resize_border
            is_bottom = pos.y() >= rect.height() - self.resize_border
            if is_right and is_bottom:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif is_right:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif is_bottom:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        elif event.buttons() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            if self.resize_dir == "BottomRight":
                self.resize(max(150, global_pos.x() - self.x()), max(100, global_pos.y() - self.y()))
            elif self.resize_dir == "Right":
                self.resize(max(150, global_pos.x() - self.x()), self.height())
            elif self.resize_dir == "Bottom":
                self.resize(self.width(), max(100, global_pos.y() - self.y()))
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


class PartyOverlaySettingsModal(QDialog):
    def __init__(self, parent_window, parent_dialog=None):
        super().__init__(parent_dialog or parent_window)
        self.parent_window = parent_window
        self.overlay = parent_window.party_panel
        self.setWindowTitle("파티 현황 설정")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setStyleSheet("""
            #PartySettingsContainer {
                background-color: rgba(22, 22, 26, 0.98);
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }
            QLabel {
                color: #f5f5f7;
                font-family: 'Pretendard', 'Malgun Gothic', -apple-system, sans-serif;
                font-size: 13px;
                font-weight: 600;
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px 12px;
                color: #ffffff;
                font-family: 'Pretendard', 'Malgun Gothic', -apple-system, sans-serif;
                font-size: 12px;
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.20);
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e24;
                border: 1px solid rgba(255, 255, 255, 0.15);
                selection-background-color: #0a84ff;
                selection-color: #ffffff;
                color: #ffffff;
                padding: 4px;
            }
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0a84ff;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: none;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #0a84ff;
            }
            QPushButton {
                background-color: rgba(10, 132, 255, 0.15);
                border: 1px solid rgba(10, 132, 255, 0.3);
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                color: #0a84ff;
                font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(10, 132, 255, 0.25);
            }
            QPushButton#CloseBtn {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #ffffff;
            }
            QPushButton#CloseBtn:hover {
                background-color: rgba(255, 255, 255, 0.16);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setObjectName("PartySettingsContainer")
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(20, 20, 20, 20)
        container_lay.setSpacing(12)
        
        # Title with Lucide settings icon
        title_lay = QHBoxLayout()
        title_lay.setSpacing(8)
        title_icon = QLabel()
        title_icon.setFixedSize(20, 20)
        title_icon.setPixmap(get_svg_pixmap(LUCIDE_SETTINGS_SVG, 20))
        
        title_lbl = QLabel("파티 현황 설정")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #0a84ff;")
        
        title_lay.addWidget(title_icon)
        title_lay.addWidget(title_lbl)
        title_lay.addStretch()
        container_lay.addLayout(title_lay)
        
        # 1. Class Selection Group (Dynamic from active party states)
        class_group = QFrame()
        class_group.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; }")
        cg_lay = QVBoxLayout(class_group)
        cg_lay.setContentsMargins(10, 10, 10, 10)
        cg_lay.setSpacing(6)
        
        cg_title_lay = QHBoxLayout()
        cg_title_lay.setSpacing(6)
        user_icon = QLabel()
        user_icon.setFixedSize(14, 14)
        user_icon.setPixmap(get_svg_pixmap(LUCIDE_USER_SVG, 14))
        cg_title = QLabel("로스트아크 직업 설정")
        cg_title.setStyleSheet("color: #0a84ff; font-weight: bold; font-size: 13px;")
        cg_title_lay.addWidget(user_icon)
        cg_title_lay.addWidget(cg_title)
        cg_title_lay.addStretch()
        cg_lay.addLayout(cg_title_lay)
        
        self.class_combos = {}
        player = self.parent_window.player_name
        
        p_lay = QHBoxLayout()
        lbl = QLabel(f"{player}:")
        lbl.setStyleSheet("font-size: 12px; color: #dddddd;")
        lbl.setMinimumWidth(80)
        
        combo = QComboBox()
        combo.addItems(list(LOST_ARK_CLASSES.keys()))
        default_val = getattr(self.parent_window, 'player_class', "홀리나이트")
        combo.setCurrentText(default_val)
        combo.currentTextChanged.connect(lambda text, p=player: self.change_player_class(p, text))
        
        p_lay.addWidget(lbl)
        p_lay.addWidget(combo)
        cg_lay.addLayout(p_lay)
        self.class_combos[player] = combo
            
        container_lay.addWidget(class_group)
        
        # Form grid for settings
        grid = QGridLayout()
        grid.setSpacing(10)
        
        # Theme Preset
        theme_lbl = QLabel("테마 프리셋:")
        theme_lbl.setStyleSheet("font-size: 12px; color: #cccccc;")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        if self.overlay:
            self.theme_combo.setCurrentText(self.overlay.theme_name)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        grid.addWidget(theme_lbl, 0, 0)
        grid.addWidget(self.theme_combo, 0, 1)
        
        # Layout Mode
        layout_lbl = QLabel("배치 형태 레이아웃:")
        layout_lbl.setStyleSheet("font-size: 12px; color: #cccccc;")
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["세로형", "가로형"])
        if self.overlay:
            self.layout_combo.setCurrentText(self.overlay.layout_mode)
        self.layout_combo.currentTextChanged.connect(self.change_layout)
        grid.addWidget(layout_lbl, 1, 0)
        grid.addWidget(self.layout_combo, 1, 1)
        
        # Display Mode
        display_lbl = QLabel("세부 표시 모드:")
        display_lbl.setStyleSheet("font-size: 12px; color: #cccccc;")
        self.display_combo = QComboBox()
        self.display_combo.addItems(["상세 정보", "아이콘만"])
        if self.overlay:
            self.display_combo.setCurrentText(self.overlay.display_mode)
        self.display_combo.currentTextChanged.connect(self.change_display)
        grid.addWidget(display_lbl, 2, 0)
        grid.addWidget(self.display_combo, 2, 1)
        
        container_lay.addLayout(grid)
        
        # Click-Through Toggle Row (Moved from main settings dialog)
        self.btn_panel_click_through = QPushButton()
        self.btn_panel_click_through.clicked.connect(self.toggle_panel_click_through)
        self.update_click_through_button_text()
        container_lay.addWidget(self.btn_panel_click_through)
        
        # Sliders for UI Scale, Opacity, Speed
        # UI Scale
        scale_lbl_lay = QHBoxLayout()
        scale_lbl = QLabel("크기 스케일:")
        scale_lbl.setStyleSheet("font-size: 12px; color: #cccccc;")
        self.lbl_scale_val = QLabel("1.0x")
        self.lbl_scale_val.setStyleSheet("font-size: 11px; opacity: 0.6;")
        scale_lbl_lay.addWidget(scale_lbl)
        scale_lbl_lay.addStretch()
        scale_lbl_lay.addWidget(self.lbl_scale_val)
        container_lay.addLayout(scale_lbl_lay)
        
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(8, 15)
        if self.overlay:
            self.scale_slider.setValue(int(self.overlay.ui_scale * 10))
            self.lbl_scale_val.setText(f"{self.overlay.ui_scale:.1f}x")
        self.scale_slider.valueChanged.connect(self.change_scale)
        container_lay.addWidget(self.scale_slider)
        
        # Opacity (Moved from main settings dialog)
        opacity_lbl_lay = QHBoxLayout()
        opacity_lbl = QLabel("투명도:")
        opacity_lbl.setStyleSheet("font-size: 12px; color: #cccccc;")
        self.lbl_opacity_val = QLabel("90%")
        self.lbl_opacity_val.setStyleSheet("font-size: 11px; opacity: 0.6;")
        opacity_lbl_lay.addWidget(opacity_lbl)
        opacity_lbl_lay.addStretch()
        opacity_lbl_lay.addWidget(self.lbl_opacity_val)
        container_lay.addLayout(opacity_lbl_lay)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        if self.overlay:
            self.opacity_slider.setValue(int(self.overlay.panel_opacity))
            self.lbl_opacity_val.setText(f"{self.overlay.panel_opacity}%")
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        container_lay.addWidget(self.opacity_slider)
        
        # Ready Dot Speed
        speed_lbl_lay = QHBoxLayout()
        speed_lbl = QLabel("Ready 도트 펄스 속도:")
        speed_lbl.setStyleSheet("font-size: 12px; color: #cccccc;")
        self.lbl_speed_val = QLabel("1.0x")
        self.lbl_speed_val.setStyleSheet("font-size: 11px; opacity: 0.6;")
        speed_lbl_lay.addWidget(speed_lbl)
        speed_lbl_lay.addStretch()
        speed_lbl_lay.addWidget(self.lbl_speed_val)
        container_lay.addLayout(speed_lbl_lay)
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 20)
        if self.overlay:
            self.speed_slider.setValue(int(self.overlay.speed * 10))
            self.lbl_speed_val.setText(f"{self.overlay.speed:.1f}x")
        self.speed_slider.valueChanged.connect(self.change_speed)
        container_lay.addWidget(self.speed_slider)
        
        # Close Button
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        close_btn = QPushButton("확인")
        close_btn.setObjectName("CloseBtn")
        close_btn.clicked.connect(self.close_and_save)
        btn_lay.addWidget(close_btn)
        container_lay.addLayout(btn_lay)
        
        layout.addWidget(container)
        self.resize(320, 520)
        
        self.drag_position = None
        
    def toggle_panel_click_through(self):
        if self.overlay:
            self.overlay.set_click_through(not self.overlay.panel_click_through)
            self.update_click_through_button_text()
            self.parent_window.save_settings()

    def update_click_through_button_text(self):
        if self.overlay and self.overlay.panel_click_through:
            self.btn_panel_click_through.setText("마우스 투과 상태: 켬")
            self.btn_panel_click_through.setStyleSheet("""
                QPushButton {
                    background-color: rgba(48, 209, 88, 0.15);
                    border: 1px solid rgba(48, 209, 88, 0.35);
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: 600;
                    color: #30d158;
                }
                QPushButton:hover {
                    background-color: rgba(48, 209, 88, 0.25);
                }
            """)
        else:
            self.btn_panel_click_through.setText("마우스 투과 상태: 끔")
            self.btn_panel_click_through.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: 600;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.10);
                }
            """)

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
        
        # Trigger key UI
        trigger_lbl = QLabel("트리거 단축키 (예: f)")
        trigger_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #aaaaaa; margin-top: 10px;")
        trigger_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_lay.addWidget(trigger_lbl)
        
        self.txt_trigger_key = QLineEdit()
        self.txt_trigger_key.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: #ffffff;
                padding: 4px;
                font-size: 12px;
                font-weight: 500;
            }
        """)
        self.txt_trigger_key.setMaxLength(10)
        self.txt_trigger_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_trigger_key.textChanged.connect(self.on_trigger_key_changed)
        preview_lay.addWidget(self.txt_trigger_key)
        
        list_preview_lay.addWidget(self.preview_box, 2) # Ratio 2
        lay.addLayout(list_preview_lay)
        
        # Populate existing slots
        self.refresh_skill_list()
        
        self.lbl_selected_status = QLabel("선택된 스킬 없음 (Ready 스냅샷을 지정해 주셔야 활성화 판별이 시작됩니다.)")
        self.lbl_selected_status.setStyleSheet("font-size: 11px; color: #ffd60a;")
        self.lbl_selected_status.setWordWrap(True)
        lay.addWidget(self.lbl_selected_status)

        manual_notice = QLabel(
            "남은 쿨타임은 입력한 초와 트리거 단축키로 계산합니다. "
            "Ready 판정은 저장된 스킬 스냅샷을 사용합니다."
        )
        manual_notice.setWordWrap(True)
        manual_notice.setStyleSheet(
            "font-size: 10px; color: rgba(255,255,255,0.55);"
        )
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

        guide = QLabel(
            "보스 체력바 아래 <b>디버프 칸 줄</b>만 감지 영역으로 잡아 주세요. "
            "칸은 디버프가 늘거나 줄 때 좌우로 움직이므로, 한 칸이 아니라 줄 전체를 넉넉히 지정합니다. "
            "우측 하단 배틀 아이템 칸의 같은 아이콘을 잡지 않으려면 이 영역 밖으로 두는 것이 중요합니다."
        )
        guide.setWordWrap(True)
        guide.setStyleSheet("color: #a9cfff; font-size: 11px;")
        lay.addWidget(guide)

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
        preview_title = QLabel("감지 영역 미리보기 (초록=감지됨, 파랑=후보, 노랑=남은시간 숫자 영역)")
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
        sample_guide = QLabel(
            "남은 초 숫자는 8px 정도로 매우 작아 표본 없이는 값을 표시하지 않습니다. "
            "샘플 수집을 켜고 암흑 수류탄을 한 번 쓰면, 2자리→1자리로 바뀌는 순간(=9초)을 기준으로 "
            "이전 프레임까지 소급 라벨링되어 0~9 숫자 표본이 한 번에 모입니다."
        )
        sample_guide.setWordWrap(True)
        sample_guide.setStyleSheet("color: #a9cfff; font-size: 11px;")
        sample_lay.addWidget(sample_guide)
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
        detector = self.parent_window.boss_debuff_detector
        digits = detector.profile.digit_coverage
        if detector.profile.trusted:
            self.boss_train_status.setText(f"숫자 인식 사용 가능 · 학습된 숫자 {digits}")
        else:
            missing = [d for d in range(10) if d not in digits]
            self.boss_train_status.setText(
                f"숫자 표본 부족 (학습됨 {digits} / 없음 {missing}) · 지금은 지속시간 기반 추정만 사용합니다."
            )

    def on_boss_controls_changed(self, *_args):
        config = self._boss_config()
        config['enabled'] = self.boss_enable_check.isChecked()
        config['threshold'] = self.boss_threshold_slider.value() / 100.0
        config['duration'] = float(self.boss_duration_spin.value())
        config['share_with_party'] = self.boss_share_check.isChecked()
        config['collect_samples'] = self.boss_collect_check.isChecked()
        self.boss_threshold_value.setText(f"{config['threshold']:.2f}")
        self.parent_window.apply_boss_debuff_settings()
        self.parent_window.save_settings()

    def select_boss_debuff_region(self):
        self.hide()
        self.parent_window.start_boss_debuff_region_capture(self)

    def auto_boss_debuff_region(self):
        region = self.parent_window.auto_estimate_boss_debuff_region()
        self.refresh_boss_debuff_ui()
        self.boss_status_label.setText(
            f"기본 위치로 추정했습니다: {region}. 인게임 화면과 맞지 않으면 '영역 지정'으로 직접 잡아 주세요."
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
        summary = (
            f"이미지 {result['used_images']}장 사용 · 글리프 {result['added_glyphs']}개 추가 · "
            f"학습된 숫자 {result['digits']}"
        )
        if not result["trusted"]:
            summary += f" · 아직 부족한 숫자 {result['missing_digits']}"
        self.boss_train_status.setText(summary)

    def on_boss_debuff_state(self, state):
        if not isinstance(state, dict) or not state:
            return
        if state.get("active"):
            remaining = state.get("remaining")
            source = {
                "ocr": "숫자 인식", "anchor": "자릿수 보정",
                "duration": "지속시간 추정", "unknown": "시간 미확인",
            }.get(state.get("source", ""), state.get("source", ""))
            value = "?" if remaining is None else f"{math.ceil(float(remaining))}초"
            self.boss_status_label.setText(
                f"감지됨 · 남은 시간 {value} ({source}) · 일치율 {state.get('score', 0):.2f} · "
                f"학습된 지속시간 {state.get('learned_duration', 0)}초"
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
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        
        # 1. Main Configuration Box
        config_box = QFrame()
        config_box.setStyleSheet("""
            QFrame {
                background-color: rgba(48, 209, 88, 0.04); 
                border: 1px solid rgba(48, 209, 88, 0.18); 
                border-radius: 12px; 
                padding: 14px;
            }
        """)
        config_lay = QVBoxLayout(config_box)
        config_lay.setContentsMargins(12, 12, 12, 12)
        config_lay.setSpacing(12)
        
        title_lay = QHBoxLayout()
        title_lay.setSpacing(6)
        join_icon = QLabel()
        join_icon.setFixedSize(18, 18)
        join_icon.setScaledContents(True)
        join_icon.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")
        join_icon.setPixmap(get_svg_pixmap(LUCIDE_JOIN_SVG, 18))
        title_lbl = QLabel("<b>파티 쿨타임 공유 연결</b>")
        title_lbl.setStyleSheet("color: #30d158; font-size: 14px; font-weight: 600; border: none; background: transparent;")
        title_lay.addWidget(join_icon)
        title_lay.addWidget(title_lbl)
        title_lay.addStretch()
        config_lay.addLayout(title_lay)
        
        # Character Name Row
        char_row = QHBoxLayout()
        char_lbl = QLabel("캐릭터명:")
        char_lbl.setStyleSheet("font-weight: bold; font-size: 13px; border: none; background: transparent; color: #cccccc;")
        char_row.addWidget(char_lbl)
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
        char_row.addWidget(self.txt_char_name)
        self.btn_lookup_character = QPushButton("직업 자동 감지")
        self.btn_lookup_character.setStyleSheet("""
            QPushButton {
                background-color: rgba(10, 132, 255, 0.12);
                border: 1px solid rgba(10, 132, 255, 0.28);
                border-radius: 8px;
                color: #64a8ff;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: rgba(10, 132, 255, 0.22); }
            QPushButton:disabled { color: #777777; background-color: rgba(255, 255, 255, 0.04); }
        """)
        self.btn_lookup_character.clicked.connect(self.lookup_character_class)
        char_row.addWidget(self.btn_lookup_character)
        config_lay.addLayout(char_row)

        self.lbl_character_lookup = QLabel(
            f"현재 직업: {getattr(self.parent_window, 'player_class', '홀리나이트')} · 캐릭터명 입력 후 자동 감지"
        )
        self.lbl_character_lookup.setStyleSheet(
            "color: #8e8e93; border: none; background: transparent; font-size: 12px; padding-left: 2px;"
        )
        config_lay.addWidget(self.lbl_character_lookup)
        self.txt_char_name.editingFinished.connect(self.lookup_character_class)

        # Room ID Row
        room_row = QHBoxLayout()
        room_lbl = QLabel("방 코드 (Room ID):")
        room_lbl.setStyleSheet("font-weight: bold; font-size: 13px; border: none; background: transparent; color: #cccccc;")
        room_row.addWidget(room_lbl)
        room_val = getattr(self.parent_window, "room_id", "default")
        self.txt_room_id = QLineEdit(room_val)
        self.txt_room_id.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 13px;
            }
        """)
        room_row.addWidget(self.txt_room_id)
        config_lay.addLayout(room_row)

        # Server URL Row (Bypassed but kept for flexibility)
        ip_row = QHBoxLayout()
        ip_lbl = QLabel("서버 주소 (URL):")
        ip_lbl.setStyleSheet("border: none; background: transparent; font-size: 12px; color: #888888;")
        ip_row.addWidget(ip_lbl)
        self.txt_host_url = QLineEdit(self.parent_window.server_url)
        self.txt_host_url.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                color: #aaaaaa;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)
        self.txt_host_url.setReadOnly(True)
        ip_row.addWidget(self.txt_host_url)
        config_lay.addLayout(ip_row)

        # Connection status row
        conn_row = QHBoxLayout()
        conn_row.setContentsMargins(0, 0, 0, 0)
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
        config_lay.addLayout(conn_row)
        
        lay.addWidget(config_box)
        
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
        
        # Party Panel Settings Button
        self.btn_party_settings = QPushButton("파티 현황 설정")
        self.btn_party_settings.setIcon(get_svg_icon(LUCIDE_SETTINGS_SVG))
        self.btn_party_settings.setStyleSheet("""
            QPushButton {
                background-color: rgba(10, 132, 255, 0.08);
                border: 1px solid rgba(10, 132, 255, 0.20);
                border-radius: 10px;
                padding: 8px;
                font-weight: 600;
                color: #0a84ff;
            }
            QPushButton:hover {
                background-color: rgba(10, 132, 255, 0.18);
            }
        """)
        self.btn_party_settings.clicked.connect(self.open_party_design_settings)
        lay.addWidget(self.btn_party_settings)
        
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
        curr = self.skill_list.currentItem()
        if not curr:
            self.lbl_selected_status.setText("선택된 스킬 없음")
            self.lbl_skill_img.setText("스냅샷 없음\n(영역 지정 필요)")
            self.lbl_skill_img.setPixmap(QPixmap())
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
        self.lbl_character_lookup.setStyleSheet(
            "color: #0a84ff; border: none; background: transparent; font-size: 12px; padding-left: 2px;"
        )
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
        self.lbl_character_lookup.setStyleSheet(
            "color: #30d158; border: none; background: transparent; font-size: 12px; font-weight: 600; padding-left: 2px;"
        )
        if should_connect:
            self._start_client_connection()

    def on_character_lookup_progress(self, message):
        if not self.character_lookup_in_progress:
            return
        self.lbl_character_lookup.setText(str(message))
        self.lbl_character_lookup.setStyleSheet(
            "color: #ffd60a; border: none; background: transparent; font-size: 12px; padding-left: 2px;"
        )

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
        self.lbl_character_lookup.setStyleSheet(
            "color: #ff9f0a; border: none; background: transparent; font-size: 12px; padding-left: 2px;"
        )
        if should_connect:
            self._start_client_connection()

    def update_network_tab_texts(self):
        if self.parent_window.client_running:
            self.btn_toggle_client.setText("접속 끊기")
        else:
            self.btn_toggle_client.setText("방 접속하기")
            self.lbl_client_status.setText("접속 상태: 대기")
            self.lbl_client_status.setStyleSheet("color: #aaaaaa; border: none; background: transparent; font-size: 13px;")
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
        self.lbl_client_status.setStyleSheet("color: #0a84ff; font-weight: 600; border: none; background: transparent; font-size: 13px;")
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
        self.setWindowTitle('펭구 줌인 Pro v2.46')
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
                        self.party_panel.resize(party_size[0], party_size[1])
                        
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
                        
                        layout_loaded = data.get('party_layout_mode', "세로형")
                        if layout_loaded == "List":
                            layout_loaded = "세로형"
                        elif layout_loaded == "Grid":
                            layout_loaded = "가로형"
                        if layout_loaded not in ["세로형", "가로형"]:
                            layout_loaded = "세로형"
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
            party_layout = "세로형"
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
                party_layout = getattr(self.party_panel, 'layout_mode', "세로형")
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
                duration = self.detector.get_remaining_seconds(name) if not is_ready else 0
                self.client.send_update(name, is_ready, duration)

    def broadcast_skill_states(self):
        # Periodically send all registered skill states to keep party server alive and sync initial states
        if self.client_running and self.client:
            for name, slot in self.detector.slots.items():
                duration = self.detector.get_remaining_seconds(name) if not slot.is_ready else 0
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
        
        # Persist a newly learned total duration so the next session starts with it.
        config = getattr(self, 'boss_debuff_config', None)
        learned = float(self.boss_debuff_state.get('learned_duration', 0) or 0)
        if isinstance(config, dict) and learned > float(config.get('learned_duration', 0) or 0) + 0.05:
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
            dlg.lbl_client_status.setStyleSheet("color: #30d158; font-weight: 600; border: none; background: transparent; font-size: 13px;")

    def on_client_connection_failed(self, error_msg):
        import time
        if hasattr(self, 'config_dialog_ref') and self.config_dialog_ref and self.config_dialog_ref.isVisible():
            dlg = self.config_dialog_ref
            elapsed = time.time() - dlg.client_connection_start_time
            if elapsed < 45.0:
                dlg.lbl_client_status.setText("서버 활성화 중... (최대 1분 소요)")
                dlg.lbl_client_status.setStyleSheet("color: #ff9500; font-weight: 600; border: none; background: transparent; font-size: 13px;")
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
            dlg.lbl_client_status.setStyleSheet("color: #ff453a; font-weight: 600; border: none; background: transparent; font-size: 13px;")

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
        self.detector.stop_detection()
        try:
            self.boss_debuff_detector.stop_detection()
        except Exception:
            pass
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
        
    window = MagnifierWindow()
    window.show()
    sys.exit(app.exec())
