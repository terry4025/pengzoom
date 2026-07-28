# -*- mode: python ; coding: utf-8 -*-
"""펭구 줌인 Pro 단일 실행파일 빌드 스펙.

빌드:
    pyinstaller --noconfirm pengzoom.spec

산출물:
    dist/펭구 줌인 <버전> Pro.exe

명령줄 인자를 길게 나열하는 대신 스펙 파일로 관리한다. 번들 대상 데이터와
제외 모듈이 코드로 기록되므로 빌드가 재현 가능하다.
"""

import os
import re
from pathlib import Path

ROOT = Path(SPECPATH)

# PENGZOOM_DEBUG_CONSOLE=1 로 빌드하면 콘솔이 붙은 진단용 바이너리를 만든다.
# windowed 빌드는 stdout/stderr가 사라져 기동 실패 원인을 볼 수 없다.
DEBUG_CONSOLE = os.environ.get("PENGZOOM_DEBUG_CONSOLE") == "1"

# magnifier.py의 APP_VERSION을 단일 진실 공급원으로 사용한다.
# magnifier를 import하면 Qt/ctypes 초기화가 따라오므로 소스에서 직접 읽는다.
_source = (ROOT / "magnifier.py").read_text(encoding="utf-8")
APP_VERSION = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', _source, re.M).group(1)
EXE_NAME = f"펭구 줌인 {APP_VERSION} Pro"
if DEBUG_CONSOLE:
    EXE_NAME += " (debug-console)"

# cooldown_ocr._resource_path()가 sys._MEIPASS 아래에서 찾는 경로.
datas = [
    (str(ROOT / "ocr_profiles"), "ocr_profiles"),
]

hiddenimports = [
    "PyQt6.QtWebSockets",
    "PyQt6.QtNetwork",
    "PyQt6.QtSvg",
]

# 런타임에 쓰지 않는 대형 의존성을 제외해 배포 크기를 줄인다.
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "IPython",
    "pytest",
    "unittest",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtQuick",
    "PyQt6.QtQml",
    "PyQt6.Qt3DCore",
    "PyQt6.QtMultimedia",
    "PyQt6.QtBluetooth",
    "PyQt6.QtDesigner",
    "PyQt6.QtTest",
]

a = Analysis(
    ["magnifier.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=DEBUG_CONSOLE,  # windowed 빌드는 콘솔 없음
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "icon2.ico"),
)
