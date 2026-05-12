"""Estado de sesion compartido entre paginas (singleton sencillo)."""
from __future__ import annotations

from typing import Optional

import pandas as pd


class Sesion:
    """Contenedor de los datos cargados / pronosticados durante una sesion."""

    def __init__(self):
        self.df_full: Optional[pd.DataFrame] = None
        self.df_class: Optional[pd.DataFrame] = None
        self.fecha_min = None
        self.fecha_max = None

        self.pred: Optional[pd.DataFrame] = None
        self.pred_horizon: int = 0
        self.pred_ic: float = 0.80
        self.pred_filtros: dict = {}

        self.metricas_producto: Optional[pd.DataFrame] = None  # backtest

    @property
    def datos_listos(self) -> bool:
        return self.df_full is not None and self.df_class is not None

    @property
    def pronostico_listo(self) -> bool:
        return self.pred is not None and not self.pred.empty


SESION = Sesion()
