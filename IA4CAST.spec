# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para IA4CAST.

Genera un unico .exe en dist/IA4CAST.exe con todas las dependencias
embebidas (incluyendo el interprete de Python).

Uso:
    pyinstaller IA4CAST.spec --clean --noconfirm

Tiempo aproximado: 3-8 minutos.
Tamanio resultante: ~350-500 MB (LightGBM y statsforecast pesan).
"""
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
)


# ---------------------------------------------------------------
# Hidden imports: dependencias que PyInstaller no detecta de forma
# automatica porque se cargan dinamicamente.
# (Misma logica que la del manual seccion 3.1.1)
# ---------------------------------------------------------------
hiddenimports = []

# Numpy/scipy y sklearn extensiones cython
hiddenimports += [
    'sklearn.utils._cython_blas',
    'sklearn.neighbors.typedefs',
    'sklearn.neighbors.quad_tree',
    'sklearn.tree',
    'sklearn.tree._utils',
]

# LightGBM
hiddenimports += collect_submodules('lightgbm')

# StatsForecast / MLForecast / utilsforecast
hiddenimports += collect_submodules('statsforecast')
hiddenimports += collect_submodules('mlforecast')
hiddenimports += collect_submodules('utilsforecast')

# Pandas / Numpy / Numba (statsforecast usa numba)
hiddenimports += collect_submodules('numba')
hiddenimports += ['numpy.core._multiarray_tests']

# Pyarrow (parquet)
hiddenimports += collect_submodules('pyarrow')

# Cryptography
hiddenimports += collect_submodules('cryptography')

# Lectura de ODS
hiddenimports += ['odf', 'odf.opendocument', 'odf.table', 'odf.text']

# psycopg2 (stub, pero por si se activa)
hiddenimports += ['psycopg2', 'psycopg2.extensions']

hiddenimports += ['pyodbc']


# ---------------------------------------------------------------
# Datos a incluir
# ---------------------------------------------------------------
datas = []
datas += collect_data_files('lightgbm')
datas += collect_data_files('statsforecast')
datas += collect_data_files('mlforecast')
datas += collect_data_files('utilsforecast')
# Plantilla del config por si se quiere versionar con la app
datas += [('config/default.yaml', 'config')]

# DLLs/SOs nativas (LightGBM trae la suya)
binaries = []
binaries += collect_dynamic_libs('lightgbm')


# ---------------------------------------------------------------
# Bloque de analisis
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
        # Cosas que no usamos y abultan
        'tkinter', 'PyQt5', 'PyQt6', 'wx',
        'gradio', 'gradio_client',
        'IPython', 'jupyter', 'notebook',
        'pytest', 'sphinx',
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
    name='IA4CAST',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX puede romper LightGBM/numba
    runtime_tmpdir=None,
    console=False,             # ventana sin consola
    disable_windowed_traceback=False,
    icon='ia4cast/resources/icono.ico'   # opcional
                              if __import__('os').path.exists('ia4cast/resources/icono.ico')
                              else None,
)
