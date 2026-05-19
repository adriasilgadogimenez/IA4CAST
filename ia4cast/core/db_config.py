"""
Gestion de la configuracion de SQL Server desde la UI.

Permite al usuario configurar los datos de conexion sin tener que editar
config.yaml manualmente. La contrasena se guarda cifrada con Fernet.
"""
from __future__ import annotations

from typing import Tuple

from .config import CONFIG, guardar_config, LOG
from .security import cifrar_texto, descifrar_texto


def probar_conexion(host: str, port: int, database: str,
                     user: str, password: str,
                     timeout: int = 5) -> Tuple[bool, str]:
    """
    Intenta conectar a SQL Server y devolver (ok, mensaje).

    Prueba primero con pyodbc (driver nativo Microsoft) y si no esta
    disponible cae a pymssql. Devuelve un mensaje legible explicando
    el resultado.
    """
    try:
        import pyodbc
    except ImportError:
        return False, ('Falta el driver pyodbc. Instalalo con: '
                       'pip install pyodbc')

    conn_str = (
        f'DRIVER={{ODBC Driver 18 for SQL Server}};'
        f'SERVER={host};'
        f'DATABASE={database};'
        f'UID={user};PWD={password};'
        f'TrustServerCertificate=yes;'
        f'Connection Timeout={timeout};'
    )

    try:
        conn = pyodbc.connect(conn_str, timeout=timeout)
        # Hacemos una query simple para verificar que la BD responde
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        conn.close()
        return True, f'Conexion correcta a {host}:{port}/{database}'
    except pyodbc.Error as e:
        # Mensaje legible (sin todo el stack)
        msg = str(e)
        if 'Login failed' in msg:
            return False, 'Credenciales incorrectas (usuario o contrasena)'
        if 'server was not found' in msg.lower() or 'network-related' in msg.lower():
            return False, f'No se puede contactar con el servidor {host}:{port}'
        if 'Cannot open database' in msg:
            return False, f'La base de datos "{database}" no existe o no tienes permisos'
        return False, f'Error de conexion: {msg[:200]}'
    except Exception as e:
        return False, f'Error inesperado: {e}'


def guardar_configuracion_sql(host: str, port: int, database: str,
                                user: str, password: str,
                                habilitada: bool = True) -> None:
    """
    Guarda la configuracion de SQL en config.yaml.
    La contrasena se cifra con Fernet antes de guardarla.
    """
    CONFIG['base_dades']['habilitat'] = habilitada
    CONFIG['base_dades']['motor'] = 'sqlserver'
    CONFIG['base_dades']['amfitrio'] = host
    CONFIG['base_dades']['port'] = port
    CONFIG['base_dades']['bd'] = database
    CONFIG['base_dades']['usuari'] = user
    if password:
        CONFIG['base_dades']['contrasenya_xifrada'] = cifrar_texto(password)
    guardar_config(CONFIG)
    LOG.info('Configuracion SQL guardada (habilitada=%s)', habilitada)


def leer_configuracion_sql() -> dict:
    """
    Devuelve la configuracion actual de SQL, con la contrasena DESCIFRADA
    (solo para mostrar en el formulario).
    """
    cfg = CONFIG['base_dades']
    password = ''
    cifrada = cfg.get('contrasenya_xifrada', '')
    if cifrada:
        try:
            password = descifrar_texto(cifrada)
        except Exception:
            password = ''  # si no se puede descifrar, dejamos vacio
    return {
        'habilitada': cfg.get('habilitat', False),
        'host': cfg.get('amfitrio', 'localhost'),
        'port': int(cfg.get('port', 1433)),
        'database': cfg.get('bd', ''),
        'user': cfg.get('usuari', ''),
        'password': password,
    }


def deshabilitar_sql() -> None:
    """Marca SQL como deshabilitado pero conserva las credenciales."""
    CONFIG['base_dades']['habilitat'] = False
    guardar_config(CONFIG)
    LOG.info('Conexion SQL deshabilitada')
