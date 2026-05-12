"""
Carga de datos desde Excel/CSV/ODS o desde PostgreSQL (stub).

El esquema requerido es el de la seccion 6.2 del manual:
    Order Date, Category, Sub-Category, Product ID, Product Name, Quantity
"""
from __future__ import annotations

import os
from typing import Tuple

import numpy as np
import pandas as pd
import urllib
from sqlalchemy import create_engine

from .config import CONFIG, LOG
from .security import cifrar_columnas, descifrar_texto


COLUMNAS_REQUERIDAS = [
    'Order Date', 'Category', 'Sub-Category',
    'Product ID', 'Product Name', 'Quantity',
]


# ----------------------------------------------------------------------
# Lectura cruda
# ----------------------------------------------------------------------
def _leer_fichero(ruta: str) -> pd.DataFrame:
    """Lee un fichero segun su extension."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext == '.ods':
        return pd.read_excel(ruta, engine='odf')
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(ruta)
    if ext == '.csv':
        # encoding='utf-8-sig' tolera tanto UTF-8 con BOM como sin BOM.
        # Probamos primero con coma (formato estandar) y si solo aparece
        # una columna, intentamos detectar el separador.
        try:
            df = pd.read_csv(ruta, encoding='utf-8-sig', sep=',')
            if df.shape[1] >= 2:
                return df
        except Exception:
            pass
        # Fallback: detectar separador automaticamente
        try:
            return pd.read_csv(ruta, encoding='utf-8-sig', sep=None, engine='python')
        except Exception:
            return pd.read_csv(ruta, encoding='utf-8-sig')
    raise ValueError(f'Formato no soportado: {ext}. Usa .ods, .xlsx, .xls o .csv')


def _leer_postgresql() -> pd.DataFrame:
    """
    STUB de lectura desde PostgreSQL.

    La estructura esta lista pero por defecto la conexion no se usa.
    Para activarla:
      1) Editar config.yaml -> base_dades.habilitat: true
      2) Configurar amfitrio, port, bd, usuari y contrasenya_xifrada
      3) Descomentar la implementacion real en este metodo
    """

    cfg = CONFIG['base_dades']
    if not cfg.get('habilitat'):
        raise RuntimeError(
            'La conexion a PostgreSQL esta deshabilitada. '
            'Activa "base_dades.habilitat: true" en config.yaml.'
        )
    else:
        
        password = descifrar_texto(cfg['contrasenya_xifrada'])

        conn_str = urllib.parse.quote_plus(
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={cfg['amfitrio']};"
            f"DATABASE={cfg['bd']};"
            f"UID={cfg['usuari']};"
            f"PWD={password};"
	    f"TrustServerCertificate=yes;"
        )

        engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={conn_str}"
        )

        query = f"""
            SELECT
                DocDate AS [Order Date],
                'Electronica' AS [Category],
                T2.ItmsGrpNam AS [Sub-Category],
                T0.ItemCode AS [Product ID],
                Dscription AS [Product Name],
                Quantity AS [Quantity]
            FROM INV1 T0
	    INNER JOIN OITM T1 ON T0.ItemCode = T1.ItemCode
	    INNER JOIN OITB T2 ON T1.ItmsGrpCod = T2.ItmsGrpCod
        """

        return pd.read_sql(query, engine)


# ----------------------------------------------------------------------
# Carga + normalizacion + cifrado
# ----------------------------------------------------------------------
def cargar_datos(ruta_archivo: str | None = None,
                 desde_postgresql: bool = False) -> Tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    """
    Carga datos y devuelve (df_full, fecha_min, fecha_max).

    df_full es un panel mensual largo (1 fila por producto y mes), con
    los campos sensibles ya cifrados.
    """
    dfs = []

    if ruta_archivo:
        df_excel = _leer_fichero(ruta_archivo)
        df_excel['Origen'] = 'Fichero'
        dfs.append(df_excel)

    if desde_postgresql:
        df_pg = _leer_postgresql()
        df_pg['Origen'] = 'SQL'
        dfs.append(df_pg)

    if not dfs:
        raise ValueError(
            'Debes proporcionar un fichero o activar PostgreSQL.'
        )

    df_raw = pd.concat(dfs, ignore_index=True)

    # Validar columnas
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df_raw.columns]
    if faltantes:
        raise ValueError(f'Faltan columnas requeridas: {faltantes}')

    LOG.info('Datos leidos: %d filas', len(df_raw))

    # Cifrado de campos sensibles ANTES de cualquier procesamiento
    df_raw = cifrar_columnas(df_raw, CONFIG['seguretat']['xifrar_camps'])

    # Normalizacion a formato largo
    df = df_raw[COLUMNAS_REQUERIDAS].copy()
    df['Order Date'] = pd.to_datetime(df['Order Date'])
    df['ds'] = df['Order Date'].values.astype('datetime64[M]')

    # Agregamos a nivel mensual por producto
    df_panel = (
        df.groupby(['Product ID', 'Category', 'Sub-Category', 'Product Name', 'ds'],
                   as_index=False)['Quantity']
          .sum()
          .rename(columns={'Product ID': 'unique_id', 'Quantity': 'y'})
    )

    fecha_min = df_panel['ds'].min()
    fecha_max = df_panel['ds'].max()
    idx = pd.date_range(fecha_min, fecha_max, freq='MS')

    # Reindexamos cada producto para que tenga TODOS los meses (rellenando con 0)
    bloques = []
    meta = df_panel[['unique_id', 'Category', 'Sub-Category', 'Product Name']].drop_duplicates()
    for pid in df_panel['unique_id'].unique():
        m = meta[meta['unique_id'] == pid].iloc[0]
        sub = (df_panel[df_panel['unique_id'] == pid]
               .groupby('ds', as_index=False)['y'].sum()
               .set_index('ds').reindex(idx).reset_index()
               .rename(columns={'index': 'ds'}))
        sub['unique_id'] = pid
        sub['Category'] = m['Category']
        sub['Sub-Category'] = m['Sub-Category']
        sub['Product Name'] = m['Product Name']
        sub['y'] = sub['y'].fillna(0)
        bloques.append(sub[['unique_id', 'Product Name', 'ds', 'y',
                            'Category', 'Sub-Category']])

    df_full = pd.concat(bloques, ignore_index=True)
    LOG.info('Panel construido: %d productos, %d meses (%s -> %s)',
             df_full['unique_id'].nunique(), len(idx),
             fecha_min.strftime('%Y-%m'), fecha_max.strftime('%Y-%m'))
    return df_full, fecha_min, fecha_max
