# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller definition for the Linux x86_64 AutoTyper executable."""

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files


PROJECT_DIR = Path(SPECPATH).parent
PYTHON_LIB_DIR = Path(sys.base_prefix) / "lib"

# ttkbootstrap reads its themes and widget assets at runtime. PyInstaller's
# tkinter hook collects Tcl/Tk's data files.
datas = collect_data_files("ttkbootstrap.assets")

# The build interpreter ships Tcl/Tk 9 outside the host loader path. Bundle the
# shared libraries explicitly so the one-file executable is self-contained.
binaries = [
    (str(PYTHON_LIB_DIR / "libtcl9.0.so"), "."),
    (str(PYTHON_LIB_DIR / "libtcl9tk9.0.so"), "."),
]

# pynput selects its platform implementation dynamically.  The application
# also chooses evdev at runtime for eligible Wayland sessions.
hiddenimports = [
    "PIL._imagingtk",
    "PIL._tkinter_finder",
    "evdev",
    "evdev.ecodes",
    "evdev.device",
    "evdev.events",
    "evdev.uinput",
    "pynput._util.uinput",
    "pynput._util.xorg",
    "pynput._util.xorg_keysyms",
    "pynput.keyboard._uinput",
    "pynput.keyboard._xorg",
    "pynput.mouse._xorg",
]

a = Analysis(
    [str(PROJECT_DIR / "typer.py")],
    pathex=[str(PROJECT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AutoTyper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
