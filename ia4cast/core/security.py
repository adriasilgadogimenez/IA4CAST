"""
Cifrado de campos sensibles con Fernet (AES-128 CBC + HMAC-SHA256).

La clave se genera en el primer arranque con os.urandom y se guarda en
keys/fernet.key con permisos restrictivos (solo el propietario).
Conforme a la seccion 7.2 del manual.
"""
from __future__ import annotations

import os
import stat
from typing import Iterable

from cryptography.fernet import Fernet

from .config import RUTA_CLAVE, LOG


def obtener_clave_fernet() -> bytes:
    """Devuelve la clave Fernet, generandola la primera vez."""
    if RUTA_CLAVE.exists():
        with open(RUTA_CLAVE, 'rb') as f:
            return f.read()

    clave = Fernet.generate_key()
    with open(RUTA_CLAVE, 'wb') as f:
        f.write(clave)

    # Permisos 0o600: solo el propietario puede leer/escribir
    try:
        os.chmod(RUTA_CLAVE, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        LOG.warning('No se han podido aplicar permisos restrictivos a la clave: %s', e)

    LOG.info('Nueva clave Fernet generada en %s', RUTA_CLAVE)
    return clave


_CLAVE = obtener_clave_fernet()
FERNET = Fernet(_CLAVE)


def cifrar_texto(texto) -> str:
    """Cifra un string. Devuelve cadena vacia para None/NaN/vacio."""
    if texto is None:
        return ''
    s = str(texto)
    if s == '' or s.lower() == 'nan':
        return ''
    return FERNET.encrypt(s.encode('utf-8')).decode('utf-8')


def descifrar_texto(token) -> str:
    """Descifra un token Fernet. Si falla, devuelve el original."""
    if not token:
        return ''
    try:
        return FERNET.decrypt(str(token).encode('utf-8')).decode('utf-8')
    except Exception:
        return str(token)


def cifrar_columnas(df, columnas: Iterable[str]):
    """Cifra in-place las columnas indicadas que existan en el DataFrame."""
    df_out = df.copy()
    for col in columnas:
        if col in df_out.columns:
            df_out[col] = df_out[col].apply(cifrar_texto)
            LOG.info('Columna cifrada: %s', col)
    return df_out


def descifrar_columnas(df, columnas: Iterable[str]):
    """Descifra las columnas indicadas (para mostrarlas al usuario)."""
    df_out = df.copy()
    for col in columnas:
        if col in df_out.columns:
            df_out[col] = df_out[col].apply(descifrar_texto)
    return df_out
