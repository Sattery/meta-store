# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['meta_store\\tray.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static')],
    hiddenimports=['meta_store.scanner', 'meta_store.store', 'meta_store.server', 'meta_store.gui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='meta-store',
    onefile=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
