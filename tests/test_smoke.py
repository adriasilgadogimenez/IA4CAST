"""
Test rapido (sin UI) para validar que todos los modulos del core funcionan.
Util antes de empaquetar a .exe.

Uso:
    python tests/test_smoke.py
"""
import sys
from pathlib import Path

# Permitir ejecutar desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

print('-> Test smoke IA4CAST')

# 1) Cifrado
print('  [1] Cifrado Fernet...', end=' ')
from ia4cast.core.security import cifrar_texto, descifrar_texto
assert descifrar_texto(cifrar_texto('hola')) == 'hola'
print('OK')

# 2) Carga de datos
print('  [2] Carga de datos...', end=' ')
np.random.seed(42)
fechas = pd.date_range('2023-01-01', '2024-12-01', freq='MS')
filas = []
for pid in range(1, 11):
    for f in fechas:
        filas.append({
            'Order Date': f, 'Category': 'CatA', 'Sub-Category': 'SubA',
            'Product ID': f'P{pid}', 'Product Name': f'Producto {pid}',
            'Quantity': float(np.random.randint(50, 200))
        })
df_raw = pd.DataFrame(filas)
import tempfile
ruta = str(Path(tempfile.gettempdir()) / 'smoke_test.csv')
df_raw.to_csv(ruta, index=False)

from ia4cast.core.data_loader import cargar_datos
df_full, fmin, fmax = cargar_datos(ruta_archivo=ruta)
assert df_full['unique_id'].nunique() == 10
print('OK')

# 3) Clasificacion
print('  [3] Clasificacion ABC-XYZ + SBC...', end=' ')
from ia4cast.core.classification import clasificar_productos
df_class = clasificar_productos(df_full)
assert len(df_class) == 10
assert 'abc_xyz' in df_class.columns
assert 'sbc_class' in df_class.columns
print('OK')

# 4) Forecast
print('  [4] Motor de forecasting con IC...', end=' ')
from ia4cast.core.forecasting import ejecutar_forecast
pred = ejecutar_forecast(df_full, df_class, horizon_meses=3, ic=0.80)
assert not pred.empty
assert 'yhat' in pred.columns
assert 'yhat_min' in pred.columns
assert 'yhat_max' in pred.columns
assert (pred['yhat_min'] <= pred['yhat']).all()
assert (pred['yhat'] <= pred['yhat_max']).all()
print('OK')

# 5) Comparativa historica
print('  [5] Comparativa historica...', end=' ')
from ia4cast.core.comparison import comparativa_historica
cmp = comparativa_historica(df_full, pred)
assert not cmp.empty
print('OK')

# 6) Backtest
print('  [6] Backtest por producto...', end=' ')
from ia4cast.core.forecasting import backtest_por_producto
m = backtest_por_producto(df_full, df_class, meses_holdout=3)
assert 'wape_pct' in m.columns
print('OK')

# 7) Alertas
print('  [7] Sistema de alertas...', end=' ')
from ia4cast.core.alerts import evaluar_alertas
a = evaluar_alertas(50.0, 20.0)  # caso critico
assert len(a) == 2
print('OK')

# 8) Persistencia
print('  [8] Guardar/cargar pronosticos...', end=' ')
from ia4cast.core.forecast_store import guardar_pronostico, cargar_pronostico
ruta_g = guardar_pronostico(pred, horizon=3, ic=0.80, nombre='smoke')
p2 = cargar_pronostico(str(ruta_g))
assert len(p2) == len(pred)
print('OK')

print('\nTODO OK - el codigo esta listo para empaquetar.')
