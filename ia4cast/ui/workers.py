"""
Workers en hilos para no bloquear la UI durante operaciones lentas.

VERSION 2: usa QThread heredando directamente, con run() en lugar de
moveToThread + Signal(object, ...). Mas robusto en Windows.
"""
from __future__ import annotations

import traceback
from typing import Optional

import pandas as pd
from PySide6.QtCore import QThread, Signal

from ..core.config import LOG
from ..core.data_loader import cargar_datos
from ..core.classification import clasificar_productos
from ..core.forecasting import ejecutar_forecast, backtest_por_producto


# ----------------------------------------------------------------------
# Carga + clasificacion
# ----------------------------------------------------------------------
class CargaWorker(QThread):
    progreso = Signal(int, str)
    finalizado = Signal(object, object, object, object)
    error = Signal(str)

    def __init__(self, ruta_archivo: Optional[str] = None,
                 desde_postgresql: bool = False, parent=None):
        super().__init__(parent)
        self.ruta_archivo = ruta_archivo
        self.desde_postgresql = desde_postgresql

    def run(self):
        try:
            LOG.info('CargaWorker.run() iniciado')
            self.progreso.emit(10, 'Leyendo fichero...')
            df_full, fmin, fmax = cargar_datos(
                ruta_archivo=self.ruta_archivo,
                desde_postgresql=self.desde_postgresql,
            )
            self.progreso.emit(60, 'Clasificando productos (ABC-XYZ + SBC)...')
            df_class = clasificar_productos(df_full)
            self.progreso.emit(100, 'Listo.')
            self.finalizado.emit(df_full, df_class, fmin, fmax)
        except Exception as e:
            tb = traceback.format_exc()
            LOG.error('Error en CargaWorker.run():\n%s', tb)
            self.error.emit(f'{e}\n\n{tb[-600:]}')


# ----------------------------------------------------------------------
# Forecasting
# ----------------------------------------------------------------------
class ForecastWorker(QThread):
    progreso = Signal(int, str)
    finalizado = Signal(object)
    error = Signal(str)

    def __init__(self, df_full: pd.DataFrame, df_class: pd.DataFrame,
                 horizon: int, ic: float, parent=None):
        super().__init__(parent)
        self.df_full = df_full
        self.df_class = df_class
        self.horizon = horizon
        self.ic = ic

    def run(self):
        try:
            LOG.info('ForecastWorker.run() iniciado')
            self.progreso.emit(20, 'Entrenando modelos quantile (q10/q50/q90)...')
            pred = ejecutar_forecast(self.df_full, self.df_class,
                                     self.horizon, ic=self.ic)
            self.progreso.emit(100, 'Pronostico generado.')
            self.finalizado.emit(pred)
        except Exception as e:
            tb = traceback.format_exc()
            LOG.error('Error en ForecastWorker.run():\n%s', tb)
            self.error.emit(f'{e}\n\n{tb[-600:]}')


# ----------------------------------------------------------------------
# Backtest por producto
# ----------------------------------------------------------------------
class BacktestWorker(QThread):
    progreso = Signal(int, str)
    finalizado = Signal(object)
    error = Signal(str)

    def __init__(self, df_full, df_class, meses_holdout: int = 3, parent=None):
        super().__init__(parent)
        self.df_full = df_full
        self.df_class = df_class
        self.meses_holdout = meses_holdout

    def run(self):
        try:
            LOG.info('BacktestWorker.run() iniciado')
            self.progreso.emit(30, 'Ejecutando backtest interno...')
            metricas = backtest_por_producto(self.df_full, self.df_class,
                                             meses_holdout=self.meses_holdout)
            self.progreso.emit(100, 'Backtest completado.')
            self.finalizado.emit(metricas)
        except Exception as e:
            tb = traceback.format_exc()
            LOG.error('Error en BacktestWorker.run():\n%s', tb)
            self.error.emit(f'{e}\n\n{tb[-600:]}')


# ----------------------------------------------------------------------
# Helper: lanzar worker (ahora el worker ES un QThread, solo hay que start)
# ----------------------------------------------------------------------
def lanzar_en_hilo(worker: QThread, on_finalizado, on_error,
                    on_progreso=None) -> QThread:
    """
    Conecta las senales del worker (que ya es un QThread) y lo arranca.
    Devuelve el propio worker (hay que mantener referencia para que no muera).
    """
    worker.finalizado.connect(on_finalizado)
    worker.error.connect(on_error)
    if on_progreso is not None:
        worker.progreso.connect(on_progreso)
    worker.start()
    return worker
