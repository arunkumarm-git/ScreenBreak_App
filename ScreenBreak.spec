# ScreenBreak.spec
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('.env', '.'),
        ('client_secret.json', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'google_auth_oauthlib',
        'google_auth_oauthlib.flow',
        'google.auth.transport.requests',
        'google.oauth2.credentials',
        'supabase',
        'dotenv',
        'PIL',
        'PIL.Image',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == 'win32':
    # ── Windows: single-file EXE ─────────────────────────────────────
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='ScreenBreak',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        console=False,
        icon='assets/icon.ico',
        onefile=True,
    )
else:
    # ── macOS: .app bundle ───────────────────────────────────────────
    # onefile=False is required — COLLECT+BUNDLE need folder mode
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,   # <-- required for COLLECT to work
        name='ScreenBreak',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon='assets/icon.icns',
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='ScreenBreak',
    )

    app = BUNDLE(
        coll,
        name='ScreenBreak.app',
        icon='assets/icon.icns',
        bundle_identifier='com.arun.screenbreak',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion':            '1',
            'NSHighResolutionCapable':    True,
            'LSMinimumSystemVersion':     '10.14',
            'NSPrincipalClass':           'NSApplication',
            'NSAppleScriptEnabled':       False,
        },
    )