"""Metricas de error: WAPE, MASE, sMAPE, bias."""
from __future__ import annotations

import numpy as np


def wape(y_true, y_pred) -> float:
    """Weighted Absolute Percentage Error (en %)."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    s = np.sum(np.abs(y_true))
    return float(np.sum(np.abs(y_true - y_pred)) / s * 100) if s > 0 else float('nan')


def mase(y_true, y_pred, y_train, season: int = 12) -> float:
    """Mean Absolute Scaled Error (relativo al naive estacional)."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    y_train = np.asarray(y_train)
    if len(y_train) <= season:
        scale = np.mean(np.abs(np.diff(y_train))) if len(y_train) > 1 else 1.0
    else:
        scale = np.mean(np.abs(y_train[season:] - y_train[:-season]))
    if scale == 0 or np.isnan(scale):
        return float('nan')
    return float(np.mean(np.abs(y_true - y_pred)) / scale)


def smape(y_true, y_pred) -> float:
    """Symmetric MAPE robusto (tolera ceros)."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    mask = (y_true + y_pred) > 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(2 * np.abs(y_pred[mask] - y_true[mask]) /
                         (np.abs(y_true[mask]) + np.abs(y_pred[mask]))) * 100)


def bias(y_true, y_pred) -> float:
    """Sesgo en %: positivo=sobreestimacion, negativo=infraestimacion."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    s = np.sum(np.abs(y_true))
    return float(np.sum(y_pred - y_true) / s * 100) if s > 0 else float('nan')
