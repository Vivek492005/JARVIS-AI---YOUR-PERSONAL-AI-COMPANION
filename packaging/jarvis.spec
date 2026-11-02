# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for JARVIS — one-dir build (NOT one-file: faster launch,
smaller updates).

Build on Windows from the repo root:
    pip install pyinstaller
    pyinstaller packaging/jarvis.spec
Result: dist/JARVIS/JARVIS.exe

Notes:
* Gesture support (mediapipe/cv2) is EXCLUDED from v1 — heavy and fragile
  under PyInstaller. run_gestures.py stays source-only until v2.
  (The lazy access_os/__init__ means nothing at startup needs it.)
* datas[] paths are relative to this spec file (packaging/).
* Console is disabled: the app is GUI-first (pythonw equivalent).
"""

block_cipher = None

a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../puppy.jpg', '.'),
        ('../voice_config.json', '.'),
        ('../env.example', '.'),
        ('../VOICE_COMMANDS.md', '.'),
        ('../GESTURE_COMMANDS.md', '.'),
    ],
    hiddenimports=[
        # STT / TTS chain
        'speech_recognition',
        'pyttsx3.drivers.sapi5',
        'edge_tts',
        # tools
        'yt_dlp',
        'PIL',
        'numpy',
        'fuzzywuzzy',
        'pyperclip',
        'psutil',
        # package modules PyInstaller's static analysis can miss
        'access_os.actions',
        'access_os.command_policy',
        'access_os.first_run',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'mediapipe', 'cv2', 'matplotlib', 'torch', 'torchvision',
        'tkinter.test', 'unittest', 'pytest',
    ],
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
    name='JARVIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app: no console window
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
    name='JARVIS',
)
