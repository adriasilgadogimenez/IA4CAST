"""
Persistencia de pronosticos para comparativa entre ejecuciones (extra "e").

Cada pronostico se guarda en pronosticos_guardados/ con timestamp y un manifiesto
JSON que recoge metadatos para poder restaurarlo y compararlo despues.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import pandas as pd

from .config import CARPETA_PRONOSTICOS, LOG


def _ahora_iso() -> str:
    return datetime.now().strftime('%Y%m%dT%H%M%S')


def guardar_pronostico(pred: pd.DataFrame,
                       horizon: int,
                       ic: float,
                       filtros: dict | None = None,
                       nombre: str | None = None) -> Path:
    """
    Persiste un pronostico (parquet + manifiesto JSON).
    Devuelve la ruta del directorio creado.
    """
    if pred is None or pred.empty:
        raise ValueError('No se puede guardar un pronostico vacio.')

    ts = _ahora_iso()
    nombre_dir = f'pred_{ts}' + (f'_{nombre}' if nombre else '')
    destino = CARPETA_PRONOSTICOS / nombre_dir
    destino.mkdir(parents=True, exist_ok=True)

    pred.to_parquet(destino / 'forecast.parquet', index=False)

    manifest = {
        'timestamp': ts,
        'nombre': nombre or '',
        'horizon': int(horizon),
        'ic': float(ic),
        'n_filas': int(len(pred)),
        'n_productos': int(pred['unique_id'].nunique()) if 'unique_id' in pred.columns else 0,
        'filtros': filtros or {},
        'rango_fechas': {
            'inicio': str(pred['ds'].min()),
            'fin': str(pred['ds'].max()),
        },
    }
    with open(destino / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    LOG.info('Pronostico guardado en %s (%d filas)', destino, len(pred))
    return destino


def listar_pronosticos() -> List[Dict]:
    """Devuelve la lista de pronosticos guardados (mas reciente primero)."""
    items = []
    for d in sorted(CARPETA_PRONOSTICOS.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        mf = d / 'manifest.json'
        if not mf.exists():
            continue
        with open(mf, 'r', encoding='utf-8') as f:
            m = json.load(f)
        m['ruta'] = str(d)
        items.append(m)
    return items


def cargar_pronostico(ruta: str) -> pd.DataFrame:
    """Lee un pronostico previamente guardado."""
    p = Path(ruta) / 'forecast.parquet'
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_parquet(p)


def comparar_pronosticos(pred_a: pd.DataFrame, pred_b: pd.DataFrame) -> pd.DataFrame:
    """
    Compara dos pronosticos por (unique_id, ds), devolviendo yhat_a, yhat_b
    y delta = yhat_b - yhat_a.
    """
    a = pred_a[['unique_id', 'ds', 'yhat']].rename(columns={'yhat': 'yhat_a'})
    b = pred_b[['unique_id', 'ds', 'yhat']].rename(columns={'yhat': 'yhat_b'})
    m = a.merge(b, on=['unique_id', 'ds'], how='outer')
    m['delta'] = m['yhat_b'] - m['yhat_a']
    return m
