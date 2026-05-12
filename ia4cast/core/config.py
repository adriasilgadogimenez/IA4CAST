"""
Configuracion y logging.

Crea las carpetas de usuario tal como exige el manual:
    Windows: %APPDATA%\\IA4CAST
    Linux/Mac: ~/.ia4cast

Lee/escribe config.yaml con los valores por defecto si no existe.
Configura el logger 'ia4cast' con rotacion diaria.
"""
from __future__ import annotations

import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import yaml


# ----------------------------------------------------------------------
# Carpetas del usuario
# ----------------------------------------------------------------------
def obtener_carpeta_usuario() -> Path:
    """Devuelve la carpeta donde se guardan los datos del usuario."""
    if sys.platform.startswith('win'):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return Path(base) / 'IA4CAST'
    return Path.home() / '.ia4cast'


CARPETA_USUARIO = obtener_carpeta_usuario()
CARPETA_LOGS = CARPETA_USUARIO / 'logs'
CARPETA_CACHE = CARPETA_USUARIO / 'cache'
CARPETA_KEYS = CARPETA_USUARIO / 'keys'
CARPETA_PRONOSTICOS = CARPETA_USUARIO / 'pronosticos_guardados'
RUTA_CONFIG = CARPETA_USUARIO / 'config.yaml'
RUTA_CLAVE = CARPETA_KEYS / 'fernet.key'

for _carpeta in (CARPETA_USUARIO, CARPETA_LOGS, CARPETA_CACHE, CARPETA_KEYS,
                 CARPETA_PRONOSTICOS):
    _carpeta.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# Configuracion por defecto (estructura del manual, seccion 3.4)
# ----------------------------------------------------------------------
CONFIG_POR_DEFECTO = {
    'app': {
        'idioma': 'ca',
        'retencio_logs_dies': 30,
        'tema_ui': 'light_blue',  # tema qt-material
    },
    'forecast': {
        'horitzo_mesos': 12,
        'metrica_seleccio': 'wape',
        'cache_models': True,
        'intervalo_confianza': 0.80,  # IC 80%: q10..q90
    },
    'base_dades': {
        'habilitat': True,
        'motor': 'sqlserver',
        'amfitrio': 'localhost',
        'port': 1433,
        'bd': 'IA4CAST',
        'esquema': 'dbo',
        'taula': 'RDR1',
        'usuari': 'ia4cast',
        'contrasenya_xifrada': '1234',
    },
    'seguretat': {
        'xifrar_camps': ['Customer Name', 'Product Name'],
        'nivell_registre': 'INFO',
    },
    'alertes': {
        # Llindars de la seccio 5.3 del manual
        'wape_critic_pct': 40.0,
        'biaix_critic_pct': 15.0,
        'degradacio_pp': 10.0,
    },
}


def cargar_config() -> dict:
    """Lee config.yaml o crea uno con valores por defecto si no existe."""
    if not RUTA_CONFIG.exists():
        with open(RUTA_CONFIG, 'w', encoding='utf-8') as f:
            yaml.safe_dump(CONFIG_POR_DEFECTO, f, allow_unicode=True, sort_keys=False)
        return _copy_dict(CONFIG_POR_DEFECTO)

    with open(RUTA_CONFIG, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}

    # Fusion con defaults para no romper si falta una clave nueva
    for seccion, valores in CONFIG_POR_DEFECTO.items():
        cfg.setdefault(seccion, {})
        for k, v in valores.items():
            cfg[seccion].setdefault(k, v)
    return cfg


def guardar_config(cfg: dict) -> None:
    """Persiste el diccionario de configuracion."""
    with open(RUTA_CONFIG, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def _copy_dict(d):
    return {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in d.items()}


# Singleton: se carga una vez al importar el modulo
CONFIG = cargar_config()


# ----------------------------------------------------------------------
# Logging con rotacion diaria
# ----------------------------------------------------------------------
def configurar_logging(nivel: str = 'INFO') -> logging.Logger:
    """Crea un logger 'ia4cast' que escribe en logs/ con rotacion diaria."""
    logger = logging.getLogger('ia4cast')
    logger.setLevel(getattr(logging, nivel, logging.INFO))

    # Evitar handlers duplicados al re-importar
    if logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)

    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    fichero = CARPETA_LOGS / 'ia4cast.log'
    fh = TimedRotatingFileHandler(
        fichero,
        when='midnight',
        backupCount=CONFIG['app']['retencio_logs_dies'],
        encoding='utf-8',
    )
    fh.suffix = '%Y-%m-%d'
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


LOG = configurar_logging(CONFIG['seguretat']['nivell_registre'])
LOG.info('IA4CAST iniciado. Carpeta de usuario: %s', CARPETA_USUARIO)
