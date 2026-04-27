# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\gabriel.costa\\Documents\\GitHub\\radio\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\gabriel.costa\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe', 'bin')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['anthropic', 'whisper', 'openai', 'tiktoken', 'IPython', 'jupyter', 'jupyter_client', 'jupyter_core', 'pytest', 'torch', 'torchaudio', 'torchcodec', 'sympy', 'networkx', 'librosa', 'numba', 'llvmlite', 'scipy', 'sklearn', 'pooch', 'tzdata'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    exclude_binaries=True,
    name='RadioAdDetector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='_internal',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='RadioAdDetector',
)
