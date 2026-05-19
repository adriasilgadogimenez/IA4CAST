# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para IA4CAST.

Para que el icono aparezca en el .exe final:
  1) Colocar el fichero icono.ico en ia4cast/resources/icono.ico
  2) Ejecutar:  pyinstaller IA4CAST.spec --clean --noconfirm
  3) El .exe resultante en dist/ tendra el icono correcto

Importante: si Windows muestra el icono antiguo en el explorador, es por
el cache de iconos. Reinicia explorer.exe o borra %localappdata%\\IconCache.db
"""
import os
from PyInstaller.utils.hooks import (
    collect_submodules, collect_data_files, collect_dynamic_libs,
)


# ---------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------
hiddenimports = []

hiddenimports += [
    'sklearn.utils._cython_blas',
    'sklearn.neighbors.typedefs',
    'sklearn.neighbors.quad_tree',
    'sklearn.tree',
    'sklearn.tree._utils',
]

hiddenimports += collect_submodules('lightgbm')
hiddenimports += collect_submodules('statsforecast')
hiddenimports += collect_submodules('mlforecast')
hiddenimports += collect_submodules('utilsforecast')
hiddenimports += collect_submodules('numba')
hiddenimports += ['numpy.core._multiarray_tests']
hiddenimports += collect_submodules('pyarrow')
hiddenimports += collect_submodules('cryptography')
hiddenimports += ['odf', 'odf.opendocument', 'odf.table', 'odf.text']
hiddenimports += ['pyodbc', 'sqlalchemy', 'urllib.parse']

# ---------------------------------------------------------------
# Datos a incluir
# ---------------------------------------------------------------
datas = []
datas += collect_data_files('lightgbm')
datas += collect_data_files('statsforecast')
datas += collect_data_files('mlforecast')
datas += collect_data_files('utilsforecast')
datas += [('config/default.yaml', 'config')]

# Incluir el icono dentro del paquete si existe
ICONO_PATH = 'ia4cast/resources/icono.ico'
if os.path.exists(ICONO_PATH):
    datas += [(ICONO_PATH, 'ia4cast/resources')]
    print(f'[IA4CAST.spec] Icono encontrado: {ICONO_PATH}')
else:
    print(f'[IA4CAST.spec] ATENCION: no se encuentra {ICONO_PATH}')

binaries = []
binaries += collect_dynamic_libs('lightgbm')


# ---------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter', 'PyQt5', 'PyQt6', 'wx',
        'gradio', 'gradio_client',
        'IPython', 'jupyter', 'notebook',
        'pytest', 'sphinx',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------
# EXE - Aqui se asigna el icono al .exe final
# ---------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='IA4CAST',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=ICONO_PATH if os.path.exists(ICONO_PATH) else None,
    version=None,
)
