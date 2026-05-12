"""
Sistema de alertas conforme a la seccion 5.3 del manual de administracion.

Genera alertas cuando:
  - WAPE medio global supera el umbral critico (40% por defecto)
  - Sesgo absoluto global supera el umbral (15% por defecto)
  - Hay degradacion respecto a la ejecucion anterior
"""
from __future__ import annotations

from typing import List, Dict

import numpy as np

from .config import CONFIG, LOG


def evaluar_alertas(wape_global: float,
                    bias_global: float,
                    wape_anterior: float | None = None) -> List[Dict]:
    """
    Devuelve una lista de dicts {nivel, codigo, mensaje} con las alertas
    activas segun los llindars configurados.
    """
    alertas = []
    cfg = CONFIG.get('alertes', {})
    umbral_wape = cfg.get('wape_critic_pct', 40.0)
    umbral_bias = cfg.get('biaix_critic_pct', 15.0)
    umbral_deg = cfg.get('degradacio_pp', 10.0)

    if not np.isnan(wape_global) and wape_global > umbral_wape:
        alertas.append({
            'nivel': 'CRITICA',
            'codigo': 'WAPE_ALTO',
            'mensaje': (f'WAPE global = {wape_global:.1f}% por encima del umbral '
                        f'critico ({umbral_wape:.0f}%). Revisa la calidad de los datos.'),
        })

    if not np.isnan(bias_global) and abs(bias_global) > umbral_bias:
        signo = 'sobreestimacion' if bias_global > 0 else 'infraestimacion'
        alertas.append({
            'nivel': 'AVISO',
            'codigo': 'BIAS_ALTO',
            'mensaje': (f'Sesgo global = {bias_global:+.1f}% indica '
                        f'{signo} sistematica (umbral +-{umbral_bias:.0f}%).'),
        })

    if wape_anterior is not None and not np.isnan(wape_anterior):
        delta = wape_global - wape_anterior
        if delta > umbral_deg:
            alertas.append({
                'nivel': 'AVISO',
                'codigo': 'DEGRADACION',
                'mensaje': (f'Degradacion respecto a ejecucion anterior: '
                            f'+{delta:.1f} puntos (umbral {umbral_deg:.0f}pp).'),
            })

    for a in alertas:
        LOG.warning('[ALERTA %s] %s', a['nivel'], a['mensaje'])

    return alertas
