# -*- mode: python ; coding: utf-8 -*-

import os
import sys

project_root = os.path.dirname(os.path.abspath(sys.argv[0]))
icons_dir = os.path.join(project_root, 'icons')

# Собираем иконки
datas = []
if os.path.exists(icons_dir):
    for file in os.listdir(icons_dir):
        if file.endswith(('.ico', '.png')):
            datas.append((os.path.join(icons_dir, file), 'icons'))

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt5.sip',
        'cryptography',
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
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# НЕ создаем корневой EXE, только COLLECT
coll = COLLECT(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WebDAVManager'
)