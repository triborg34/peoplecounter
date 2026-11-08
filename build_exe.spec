# PyInstaller build script for the People Counter desktop app.
# Build with:  pyinstaller build_exe.spec
# The result is a folder in dist/PeopleCounter (or a onefile exe with --onefile).
import os

block_cipher = None

datas = [
    ("app/gui/resources", "app/gui/resources"),
]

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "ultralytics",
    "ultralytics.models.yolo.model",
    "ultralytics.trackers.byte_tracker",
    "ultralytics.utils.ops",
    "cv2",
    "sqlalchemy.dialects.postgresql",
    "openpyxl",
    "reportlab",
    "pyqtgraph",
]

a = Analysis(
    ["app/main.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PySide2", "notebook"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PeopleCounter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PeopleCounter",
)
