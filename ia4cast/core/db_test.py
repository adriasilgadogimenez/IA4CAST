"""
Procesado de los datos de instalacion (sql_install_data.txt).

Si Inno Setup ha dejado un fichero con los datos de SQL en
{app}\\config\\sql_install_data.txt, esta logica:
  1. Lee los datos.
  2. Prueba la conexion a SQL Server.
  3. Si la conexion funciona: actualiza config.yaml con los datos
     (la contrasenya se cifra con Fernet).
  4. Borra el fichero temporal (independientemente del resultado).
  5. Devuelve un dict con el resultado para que la app lo muestre.

Se ejecuta una sola vez al arrancar la app si detecta el fichero.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from .config import CONFIG, RUTA_CONFIG, guardar_config, LOG
from .security import cifrar_texto


def _ruta_app() -> Path:
    """
    Devuelve la carpeta del .exe (donde Inno Setup ha dejado el fichero).

    Cuando se ejecuta desde PyInstaller, sys.executable apunta al .exe;
    en desarrollo, apunta al interprete de Python.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _leer_fichero_install(ruta: Path) -> dict:
    """Lee el fichero clave=valor generado por Inno Setup."""
    datos = {}
    with open(ruta, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            if '=' in linea:
                clave, valor = linea.split('=', 1)
                datos[clave.strip()] = valor.strip()
    return datos


def _probar_conexion_sql(host: str, port: int, database: str,
                          user: str, password: str,
                          timeout: int = 5) -> tuple[bool, str]:
    """
    Intenta conectar a SQL Server. Devuelve (ok, mensaje).

    Prueba primero pyodbc (Driver SQL Server nativo) y si no esta
    disponible cae a pymssql. Si ninguno esta disponible, devuelve
    error sin abortar.
    """
    # Intento 1: pyodbc
    try:
        import pyodbc
        conn_str = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={host},{port};'
            f'DATABASE={database};'
            f'UID={user};PWD={password};'
            f'Connection Timeout={timeout};'
        )
        conn = pyodbc.connect(conn_str, timeout=timeout)
        conn.close()
        return True, 'Conexion correcta (pyodbc)'
    except ImportError:
        pass
    except Exception as e:
        # pyodbc esta pero la conexion falla
        return False, f'Error pyodbc: {e}'

    # Intento 2: pymssql
    try:
        import pymssql
        conn = pymssql.connect(
            server=host, port=port, database=database,
            user=user, password=password,
            login_timeout=timeout,
        )
        conn.close()
        return True, 'Conexion correcta (pymssql)'
    except ImportError:
        return False, ('No hay driver SQL instalado. '
                       'Instala "pyodbc" o "pymssql" para usar SQL Server.')
    except Exception as e:
        return False, f'Error pymssql: {e}'


def procesar_datos_instalacion() -> Optional[dict]:
    """
    Funcion principal. Se llama al arrancar la app.

    Devuelve:
      - None si no hay fichero de instalacion (caso normal).
      - dict {ok: bool, mensaje: str} si se ha procesado.
    """
    ruta_fichero = _ruta_app() / 'config' / 'sql_install_data.txt'
    if not ruta_fichero.exists():
        return None  # no hay nada que procesar

    LOG.info('Detectado fichero de instalacion: %s', ruta_fichero)

    try:
        datos = _leer_fichero_install(ruta_fichero)
    except Exception as e:
        LOG.error('Error leyendo el fichero de instalacion: %s', e)
        _borrar_fichero(ruta_fichero)
        return {'ok': False, 'mensaje': f'No se pudo leer el fichero: {e}'}

    host = datos.get('host', '')
    port_str = datos.get('port', '1433')
    database = datos.get('database', '')
    user = datos.get('user', '')
    password = datos.get('password', '')

    try:
        port = int(port_str)
    except ValueError:
        port = 1433

    LOG.info('Probando conexion a %s:%d/%s con usuario %s',
             host, port, database, user)

    ok, mensaje = _probar_conexion_sql(host, port, database, user, password)

    if ok:
        # Conexion correcta -> guardar en config.yaml
        CONFIG['base_dades']['habilitat'] = True
        CONFIG['base_dades']['motor'] = 'sqlserver'
        CONFIG['base_dades']['amfitrio'] = host
        CONFIG['base_dades']['port'] = port
        CONFIG['base_dades']['bd'] = database
        CONFIG['base_dades']['usuari'] = user
        CONFIG['base_dades']['contrasenya_xifrada'] = cifrar_texto(password)
        guardar_config(CONFIG)
        LOG.info('Conexion SQL guardada en config.yaml')
    else:
        # Conexion fallida -> dejamos config sin tocar
        LOG.warning('Conexion SQL fallida: %s', mensaje)
        CONFIG['base_dades']['habilitat'] = False
        guardar_config(CONFIG)

    # Borrar el fichero temporal SIEMPRE (haya funcionado o no)
    _borrar_fichero(ruta_fichero)

    return {'ok': ok, 'mensaje': mensaje, 'host': host, 'database': database}


def _borrar_fichero(ruta: Path) -> None:
    """Borra el fichero, suprimiendo errores."""
    try:
        ruta.unlink()
        LOG.info('Fichero de instalacion borrado: %s', ruta)
    except Exception as e:
        LOG.warning('No se pudo borrar el fichero de instalacion: %s', e)
