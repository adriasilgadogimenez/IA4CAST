"""
Comparativa pronostico vs ventas historicas en el mismo rango temporal de
anos anteriores.

Ejemplo: si pronosticamos mayo-julio 2026, este modulo devuelve las ventas
reales de mayo-julio 2025, 2024, ... para poder hacer un grafico de barras
comparativo.
"""
from __future__ import annotations

from typing import List

import pandas as pd

from .security import descifrar_texto


def _filtrar_seleccion(df, nivel: str, valor: str | None):
    """Filtra el DataFrame segun el nivel: producto/sub-categoria/categoria/todos."""
    if nivel == 'todos' or valor is None or valor == 'Todos':
        return df
    if nivel == 'producto':
        # El nombre puede venir descifrado, hay que comparar descifrando.
        if 'Product Name' in df.columns:
            df = df.copy()
            df['_pn_des'] = df['Product Name'].apply(descifrar_texto)
            return df[df['_pn_des'] == valor].drop(columns='_pn_des')
        return df
    if nivel == 'sub-categoria':
        return df[df['Sub-Category'] == valor]
    if nivel == 'categoria':
        return df[df['Category'] == valor]
    return df


def comparativa_historica(df_full: pd.DataFrame,
                          pred: pd.DataFrame,
                          nivel: str = 'todos',
                          valor: str | None = None,
                          n_anios_historicos: int = 4) -> pd.DataFrame:
    """
    Devuelve un DataFrame con una fila por anio:
        - una fila por cada uno de los ultimos `n_anios_historicos` anos
          con las ventas reales del mismo rango mes-mes que el pronostico
        - una fila final con el total del pronostico

    Columnas devueltas:
        anio, etiqueta, unidades, es_pronostico
    """
    if pred is None or pred.empty:
        return pd.DataFrame(columns=['anio', 'etiqueta', 'unidades', 'es_pronostico'])

    # Filtrar segun seleccion
    df_h = _filtrar_seleccion(df_full, nivel, valor)
    df_p = _filtrar_seleccion(pred, nivel, valor)

    if df_p.empty:
        return pd.DataFrame(columns=['anio', 'etiqueta', 'unidades', 'es_pronostico'])

    pred_inicio = pd.to_datetime(df_p['ds'].min())
    pred_fin = pd.to_datetime(df_p['ds'].max())
    anio_pred = pred_inicio.year

    filas = []
    for offset in range(n_anios_historicos, 0, -1):
        anio_h = anio_pred - offset
        try:
            ini_h = pred_inicio.replace(year=anio_h)
            fin_h = pred_fin.replace(year=anio_h)
        except ValueError:
            # Caso de 29 de febrero; ajustamos al ultimo dia del mes
            ini_h = pred_inicio.replace(year=anio_h, day=1)
            fin_h = pred_fin.replace(year=anio_h, day=1) + pd.offsets.MonthEnd(0)
        ventas = df_h[(df_h['ds'] >= ini_h) & (df_h['ds'] <= fin_h)]['y'].sum()
        if ventas > 0 or offset <= 2:  # mostrar al menos los 2 ultimos anios aunque sean 0
            filas.append({
                'anio': anio_h,
                'etiqueta': f'Real {anio_h}',
                'unidades': float(ventas),
                'es_pronostico': False,
            })

    total_pred = float(df_p['yhat'].sum())
    filas.append({
        'anio': anio_pred,
        'etiqueta': f'Pronostico {anio_pred}',
        'unidades': total_pred,
        'es_pronostico': True,
    })
    return pd.DataFrame(filas)
