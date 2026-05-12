"""
Clasificacion ABC-XYZ + SBC y deteccion de anomalias en historicos.

ABC: Pareto por volumen (A=80%, B=15%, C=5%)
XYZ: variabilidad (X=baja, Y=media, Z=alta)
SBC: patron de demanda (Smooth/Erratic/Intermittent/Lumpy)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LOG


# ----------------------------------------------------------------------
# Features e indicadores por serie
# ----------------------------------------------------------------------
def calcular_features_serie(serie_y: pd.Series) -> dict:
    y = serie_y.values
    n_total = len(y)
    n_activos = int((y > 0).sum())
    if n_activos < 2:
        return {'n_activos': n_activos, 'adi': np.inf,
                'cv': np.inf, 'cv2': np.inf, 'total': float(y.sum())}
    adi = n_total / n_activos
    y_pos = y[y > 0]
    cv = y_pos.std() / y_pos.mean() if y_pos.mean() > 0 else np.inf
    return {'n_activos': n_activos, 'adi': adi,
            'cv': cv, 'cv2': cv ** 2, 'total': float(y.sum())}


def clasificar_sbc(adi: float, cv2: float) -> str:
    """Umbrales clasicos: ADI=1.32, CV2=0.49."""
    if adi < 1.32 and cv2 < 0.49:
        return 'Smooth'
    if adi < 1.32 and cv2 >= 0.49:
        return 'Erratic'
    if adi >= 1.32 and cv2 < 0.49:
        return 'Intermittent'
    return 'Lumpy'


# ----------------------------------------------------------------------
# Clasificacion completa
# ----------------------------------------------------------------------
def clasificar_productos(df_full: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for pid, grupo in df_full.groupby('unique_id'):
        f = calcular_features_serie(grupo['y'])
        f['unique_id'] = pid
        f['Product Name'] = grupo['Product Name'].iloc[0]
        f['Category'] = grupo['Category'].iloc[0]
        f['Sub-Category'] = grupo['Sub-Category'].iloc[0]
        f['sbc_class'] = clasificar_sbc(f['adi'], f['cv2'])
        filas.append(f)

    df_class = pd.DataFrame(filas).sort_values('total', ascending=False)

    total_global = df_class['total'].sum()
    if total_global > 0:
        df_class['total_cumpct'] = df_class['total'].cumsum() / total_global
    else:
        df_class['total_cumpct'] = 0.0

    df_class['abc'] = df_class['total_cumpct'].apply(
        lambda p: 'A' if p <= 0.80 else ('B' if p <= 0.95 else 'C')
    )
    df_class['xyz'] = df_class['cv'].apply(
        lambda c: 'X' if c < 0.5 else ('Y' if c < 1.0 else 'Z')
    )
    df_class['abc_xyz'] = df_class['abc'] + df_class['xyz']
    # Un producto se considera forecasteable individualmente si:
    #   - Tiene al menos 12 meses con venta (un ano completo)
    #   - Su ADI es <= 4 (no demasiado intermitente)
    #   - Su CV no es absurdamente alto (excluye lumpy extremos)
    # Si no cumple, se redirige a la ruta top-down a nivel Sub-Category.
    df_class['forecasteable'] = (
        (df_class['n_activos'] >= 12)
        & (df_class['adi'] <= 4)
        & (df_class['cv'] <= 3)
    )

    LOG.info('Clasificacion completa: %d productos', len(df_class))
    return df_class


# ----------------------------------------------------------------------
# Deteccion de anomalias en el historico
# ----------------------------------------------------------------------
def detectar_anomalias(df_full: pd.DataFrame, umbral_z: float = 3.0) -> pd.DataFrame:
    """
    Detecta meses con desviacion z > umbral_z respecto a la media
    historica del propio producto.

    Devuelve un DataFrame con (unique_id, Product Name, ds, y, z_score).
    """
    anomalias = []
    for pid, grupo in df_full.groupby('unique_id'):
        y = grupo['y'].values
        if len(y) < 6:
            continue
        media, sd = y.mean(), y.std()
        if sd == 0:
            continue
        z = (y - media) / sd
        for i, zi in enumerate(z):
            if abs(zi) > umbral_z:
                anomalias.append({
                    'unique_id': pid,
                    'Product Name': grupo['Product Name'].iloc[0],
                    'ds': grupo['ds'].iloc[i],
                    'y': float(y[i]),
                    'z_score': float(zi),
                    'tipo': 'pico' if zi > 0 else 'caida',
                })
    df_a = pd.DataFrame(anomalias)
    LOG.info('Anomalias detectadas: %d', len(df_a))
    return df_a
