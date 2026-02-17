# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# Получаем путь к текущему файлу
project_root = os.path.dirname(os.path.abspath(sys.argv[0]))

print(f"Building WebDAV Manager (one-file) from: {project_root}")

# Путь к иконкам
icons_dir = os.path.join(project_root, 'icons')

# Собираем иконки для включения в EXE
datas = []
if os.path.exists(icons_dir):
    for file in os.listdir(icons_dir):
        if file.endswith(('.ico', '.png')):
            file_path = os.path.join(icons_dir, file)
            datas.append((file_path, 'icons'))
            print(f"Adding icon: {file}")

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt5.sip',
        'cryptography',
        'cryptography.hazmat.backends.openssl',
        'requests',
        'webdav3',
        'core',
        'services',
        'ui',
        'utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
        'pydoc',
        'doctest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WebDAVManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Без консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(icons_dir, 'app.ico') if os.path.exists(os.path.join(icons_dir, 'app.ico')) else None
)