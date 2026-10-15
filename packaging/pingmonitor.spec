# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: a windowed single-file executable (an .app bundle on macOS).

Build from the repository root:

    pyinstaller packaging/pingmonitor.spec --noconfirm
"""

import os
import sys

# SPECPATH is defined by PyInstaller: the directory containing this file.
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
RESOURCES = os.path.join(ROOT, "src", "pingmonitor", "resources")

# Platform-specific executable icon; Linux has none, the Qt window icon is
# loaded from the bundled PNG at runtime.
ICONS = {"win32": "icon.ico", "darwin": "icon.icns"}
ICON = os.path.join(RESOURCES, ICONS[sys.platform]) if sys.platform in ICONS else None

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=[(RESOURCES, "pingmonitor/resources")],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PingMonitor",
    console=False,
    icon=ICON,
    upx=False,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="PingMonitor.app",
        icon=ICON,
        bundle_identifier="io.github.gvcoder09.pingmonitor",
    )
