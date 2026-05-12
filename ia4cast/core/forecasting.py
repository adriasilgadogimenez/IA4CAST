"""
Motor de forecasting con 3 rutas segun la clasificacion SBC del producto.

Ruta 1 (REGULARES, productos Smooth/Erratic)
    Modelo: LightGBM (gradient boosting) con features de lag.
    El IC se calcula con BOOTSTRAP RESIDUAL:
      1) Se entrena el modelo y se hace una prediccion sobre los ultimos
         meses del historico (validacion).
      2) Se calculan los errores (residuos) entre prediccion y realidad.
      3) Se usa la desviacion de esos errores para construir el IC:
            yhat_max = yhat + factor * desviacion
            yhat_min = yhat - factor * desviacion
         El factor depende del nivel de confianza (1.28 para IC 80%).

Ruta 2 (INTERMITENTES, productos Intermittent/Lumpy)
    Modelo: promedio de CrostonSBA y TSB.
    El IC se calcula con la desviacion historica de la propia serie.

Ruta 3 (LONG-TAIL, productos no forecasteables individualmente)
    Modelo: AutoETS a nivel Sub-Category, despues se reparte entre
    los productos segun su proporcion en los ultimos 12 meses (top-down).
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from statsforecast import StatsForecast
from statsforecast.models import AutoETS, CrostonSBA, TSB

from .config import LOG, CONFIG


# Lags que vamos a usar como features: ventas de hace 1, 2, 3, 6 y 12 meses
LAGS = [1, 2, 3, 6, 12]

# Factor del IC segun el nivel de confianza (de la distribucion normal)
# Para IC del 80% -> z = 1.28 (cubre el 80% central de los errores)
# Para IC del 90% -> z = 1.64
# Para IC del 95% -> z = 1.96
FACTORES_IC = {0.50: 0.67, 0.80: 1.28, 0.90: 1.64, 0.95: 1.96}


# ======================================================================
# Helpers
# ======================================================================
def _factor_ic(nivel: float) -> float:
    """Devuelve el factor multiplicador para el nivel de confianza pedido."""
    return FACTORES_IC.get(round(nivel, 2), 1.28)


def _crear_lags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Anade columnas lag_1, lag_2, lag_3, lag_6, lag_12 al DataFrame.
    Cada lag_N contiene la venta del mismo producto N meses antes.
    """
    df = df.sort_values(['unique_id', 'ds']).copy()
    for L in LAGS:
        df[f'lag_{L}'] = df.groupby('unique_id')['y'].shift(L)
    # Mes y trimestre como features adicionales (para captar estacionalidad)
    df['mes'] = df['ds'].dt.month
    df['trimestre'] = df['ds'].dt.quarter
    return df


# ======================================================================
# RUTA 1: LightGBM para productos REGULARES
# ======================================================================
def _forecast_regulares(df_train, ids, horizon, ic):
    """
    Entrena un LightGBM sobre todos los productos regulares juntos
    y predice mes a mes de forma recursiva.

    El IC se calcula con bootstrap residual:
      - Se hace una validacion sobre los ultimos 3 meses del historico.
      - La desviacion estandar de los errores ahi -> IC futuro.
    """
    # 1) Preparar datos de entrenamiento con sus lags
    df = df_train[df_train['unique_id'].isin(ids)].copy()
    df = _crear_lags(df)

    # Las columnas que el modelo usara como features
    cols_features = [f'lag_{L}' for L in LAGS] + ['mes', 'trimestre']

    # 2) Quitar filas con NaN en los lags (los primeros 12 meses de cada producto)
    df_clean = df.dropna(subset=cols_features)

    # 3) Reservar los ultimos 3 meses para validacion (para estimar el IC)
    fecha_max_train = df_clean['ds'].max()
    fecha_corte = fecha_max_train - pd.DateOffset(months=3)

    df_train_real = df_clean[df_clean['ds'] <= fecha_corte]
    df_val = df_clean[df_clean['ds'] > fecha_corte]

    X_train = df_train_real[cols_features]
    y_train = df_train_real['y']

    # 4) Entrenar el modelo LightGBM
    modelo = lgb.LGBMRegressor(
        objective='regression',     # regresion estandar
        n_estimators=200,            # 200 arboles
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
        verbose=-1,
        n_jobs=-1,
    )
    modelo.fit(X_train, y_train)

    # 5) Calcular el IC con bootstrap residual
    #    Predecimos sobre la validacion y miramos los errores
    if len(df_val) > 0:
        yhat_val = modelo.predict(df_val[cols_features])
        errores = df_val['y'].values - yhat_val
        desviacion_error = float(np.std(errores))
    else:
        # Si no hay validacion, usamos la desviacion de la propia y
        desviacion_error = float(y_train.std() * 0.3)

    factor = _factor_ic(ic)

    # 6) Re-entrenar con TODOS los datos (validacion incluida) para predecir el futuro
    X_full = df_clean[cols_features]
    y_full = df_clean['y']
    modelo.fit(X_full, y_full)

    # 7) Prediccion recursiva mes a mes
    #    Para predecir el mes t+1 necesitamos los lags 1, 2, 3, 6, 12 -> historico
    #    Para predecir el mes t+2 necesitamos lag_1 = prediccion de t+1, etc.
    historico = df.copy()
    fecha_max = historico['ds'].max()
    predicciones = []

    for paso in range(1, horizon + 1):
        fecha_futura = fecha_max + pd.DateOffset(months=paso)

        # Construir las filas con los lags para cada producto
        nuevas_filas = []
        for pid in ids:
            hist_p = historico[historico['unique_id'] == pid].sort_values('ds')
            if len(hist_p) == 0:
                continue
            ys = hist_p['y'].values
            fila = {
                'unique_id': pid,
                'ds': fecha_futura,
                'mes': fecha_futura.month,
                'trimestre': ((fecha_futura.month - 1) // 3) + 1,
            }
            for L in LAGS:
                fila[f'lag_{L}'] = ys[-L] if len(ys) >= L else np.nan
            nuevas_filas.append(fila)

        if not nuevas_filas:
            break

        df_nuevas = pd.DataFrame(nuevas_filas)

        # Rellenar lags faltantes con la media (caso raro: productos cortos)
        for L in LAGS:
            df_nuevas[f'lag_{L}'] = df_nuevas[f'lag_{L}'].fillna(
                df_nuevas[[f'lag_{l}' for l in LAGS]].mean(axis=1)
            )
        df_nuevas = df_nuevas.fillna(0)

        # Predecir
        yhat = modelo.predict(df_nuevas[cols_features])
        yhat = np.clip(yhat, 0, None)  # no permitir negativos

        # Construir el IC con el factor calculado
        df_nuevas['yhat'] = yhat
        df_nuevas['yhat_min'] = np.clip(yhat - factor * desviacion_error, 0, None)
        df_nuevas['yhat_max'] = yhat + factor * desviacion_error

        predicciones.append(df_nuevas[['unique_id', 'ds', 'yhat', 'yhat_min', 'yhat_max']])

        # Anadir las predicciones al historico para alimentar el siguiente paso
        df_alim = df_nuevas[['unique_id', 'ds']].copy()
        df_alim['y'] = yhat
        historico = pd.concat([historico, df_alim], ignore_index=True)

    if not predicciones:
        return pd.DataFrame(columns=['unique_id', 'ds', 'yhat', 'yhat_min', 'yhat_max'])
    return pd.concat(predicciones, ignore_index=True)


# ======================================================================
# RUTA 2: Croston SBA + TSB para productos INTERMITENTES
# ======================================================================
def _forecast_intermitentes(df_train, ids, horizon, ic):
    """
    Para productos con ventas esporadicas (Intermittent/Lumpy) usamos los
    dos modelos clasicos: Croston SBA y TSB. La prediccion final es la
    media de ambos.

    El IC se construye con la desviacion historica de las ventas de cada
    producto.
    """
    df_int = df_train[df_train['unique_id'].isin(ids)][['unique_id', 'ds', 'y']]
    if df_int.empty:
        return pd.DataFrame(columns=['unique_id', 'ds', 'yhat', 'yhat_min', 'yhat_max'])

    # Entrenar los dos modelos a la vez con statsforecast
    sf = StatsForecast(
        models=[CrostonSBA(), TSB(alpha_d=0.2, alpha_p=0.2)],
        freq='MS',
        n_jobs=1,
    )
    sf.fit(df_int)
    pred = sf.predict(h=horizon)
    if 'unique_id' not in pred.columns:
        pred = pred.reset_index()

    # La prediccion final es la media de los dos modelos
    cols_modelos = [c for c in pred.columns if c not in ('unique_id', 'ds')]
    pred['yhat'] = pred[cols_modelos].mean(axis=1).clip(lower=0)

    # IC: factor * desviacion historica de las ventas del producto
    factor = _factor_ic(ic)
    desv_por_producto = df_int.groupby('unique_id')['y'].std().fillna(0)
    pred = pred.merge(
        desv_por_producto.rename('desv'),
        left_on='unique_id', right_index=True, how='left'
    )
    pred['desv'] = pred['desv'].fillna(0)
    pred['yhat_min'] = (pred['yhat'] - factor * pred['desv']).clip(lower=0)
    pred['yhat_max'] = (pred['yhat'] + factor * pred['desv']).clip(lower=0)

    return pred[['unique_id', 'ds', 'yhat', 'yhat_min', 'yhat_max']]


# ======================================================================
# RUTA 3: Top-down con AutoETS para productos LONG-TAIL
# ======================================================================
def _forecast_longtail(df_train, ids, df_class, horizon, fecha_max, ic):
    """
    Para productos con poco historico individual, pronosticamos a nivel
    Sub-Category con AutoETS y luego repartimos entre los productos
    segun su proporcion en los ultimos 12 meses.
    """
    if not ids:
        return pd.DataFrame(columns=['unique_id', 'ds', 'yhat', 'yhat_min', 'yhat_max'])

    # 1) Pronostico por Sub-Category
    df_subcat = (df_train.groupby(['Sub-Category', 'ds'], as_index=False)['y'].sum()
                          .rename(columns={'Sub-Category': 'unique_id'}))
    sf = StatsForecast(models=[AutoETS(season_length=12)], freq='MS', n_jobs=1)
    sf.fit(df_subcat)
    pred_sub = sf.predict(h=horizon)
    if 'unique_id' not in pred_sub.columns:
        pred_sub = pred_sub.reset_index()
    pred_sub['SUBCAT_PRED'] = pred_sub['AutoETS'].clip(lower=0)
    pred_sub = pred_sub.rename(columns={'unique_id': 'Sub-Category'})

    # 2) Calcular la proporcion de cada producto en los ultimos 12 meses
    desde = fecha_max - pd.DateOffset(months=12)
    df_recent = df_train[df_train['ds'] > desde]
    total_producto = df_recent.groupby('unique_id')['y'].sum().reset_index(name='ventas_prod')
    total_subcat = df_recent.groupby('Sub-Category')['y'].sum().reset_index(name='ventas_sub')

    proporciones = (total_producto
                    .merge(df_class[['unique_id', 'Sub-Category']], on='unique_id')
                    .merge(total_subcat, on='Sub-Category'))
    proporciones['proporcion'] = np.where(
        proporciones['ventas_sub'] > 0,
        proporciones['ventas_prod'] / proporciones['ventas_sub'],
        0
    )
    proporciones = proporciones[proporciones['unique_id'].isin(ids)]
    proporciones = proporciones[['unique_id', 'Sub-Category', 'proporcion']]

    # 3) Asignar a cada producto su parte del pronostico de la subcategoria
    pred_lt = proporciones.merge(pred_sub[['Sub-Category', 'ds', 'SUBCAT_PRED']],
                                 on='Sub-Category')
    pred_lt['yhat'] = (pred_lt['SUBCAT_PRED'] * pred_lt['proporcion']).clip(lower=0)

    # 4) IC: factor por la desviacion historica de cada producto
    factor = _factor_ic(ic)
    desv = df_train.groupby('unique_id')['y'].std().fillna(0)
    pred_lt = pred_lt.merge(desv.rename('desv'), left_on='unique_id',
                            right_index=True, how='left')
    pred_lt['desv'] = pred_lt['desv'].fillna(0)
    pred_lt['yhat_min'] = (pred_lt['yhat'] - factor * pred_lt['desv']).clip(lower=0)
    pred_lt['yhat_max'] = (pred_lt['yhat'] + factor * pred_lt['desv']).clip(lower=0)

    return pred_lt[['unique_id', 'ds', 'yhat', 'yhat_min', 'yhat_max']]


# ======================================================================
# ORQUESTADOR: dirige cada producto a su ruta segun su clasificacion SBC
# ======================================================================
def ejecutar_forecast(df_full, df_class, horizon_meses, ic=None):
    """
    Funcion principal. Para cada producto:
      - Si es Smooth o Erratic y tiene >= 12 meses de venta -> Ruta 1 (LightGBM)
      - Si es Intermittent o Lumpy con >= 12 meses de venta -> Ruta 2 (Croston/TSB)
      - Si no cumple los requisitos -> Ruta 3 (top-down)
    """
    if ic is None:
        ic = CONFIG['forecast'].get('intervalo_confianza', 0.80)

    LOG.info('Forecast: horizonte=%d meses, IC=%.0f%%', horizon_meses, ic * 100)
    fecha_max = df_full['ds'].max()

    # Asignar productos a cada ruta segun su clasificacion SBC
    ids_regulares = df_class[
        df_class['forecasteable'] &
        df_class['sbc_class'].isin(['Smooth', 'Erratic'])
    ]['unique_id'].tolist()

    ids_intermitentes = df_class[
        df_class['forecasteable'] &
        df_class['sbc_class'].isin(['Intermittent', 'Lumpy'])
    ]['unique_id'].tolist()

    ids_longtail = df_class[~df_class['forecasteable']]['unique_id'].tolist()

    LOG.info('Productos por ruta -> regulares: %d, intermitentes: %d, long-tail: %d',
             len(ids_regulares), len(ids_intermitentes), len(ids_longtail))

    # Ejecutar las 3 rutas y unir resultados
    resultados = []

    if ids_regulares:
        LOG.info('Ruta 1: LightGBM para %d productos regulares', len(ids_regulares))
        r1 = _forecast_regulares(df_full, ids_regulares, horizon_meses, ic)
        r1['ruta'] = 'lgbm_regular'
        resultados.append(r1)

    if ids_intermitentes:
        LOG.info('Ruta 2: Croston/TSB para %d productos intermitentes', len(ids_intermitentes))
        r2 = _forecast_intermitentes(df_full, ids_intermitentes, horizon_meses, ic)
        r2['ruta'] = 'croston_tsb'
        resultados.append(r2)

    if ids_longtail:
        LOG.info('Ruta 3: Top-down para %d productos long-tail', len(ids_longtail))
        r3 = _forecast_longtail(df_full, ids_longtail, df_class, horizon_meses, fecha_max, ic)
        r3['ruta'] = 'topdown_subcat'
        resultados.append(r3)

    if not resultados:
        return pd.DataFrame()

    # Unir y enriquecer con metadatos
    pred = pd.concat(resultados, ignore_index=True)
    pred = pred.merge(
        df_class[['unique_id', 'Product Name', 'Category', 'Sub-Category',
                  'abc', 'xyz', 'abc_xyz', 'sbc_class', 'forecasteable']],
        on='unique_id', how='left'
    )

    # Redondear a enteros (no se pueden vender 2.37 unidades)
    pred['yhat']     = pred['yhat'].round().clip(lower=0).astype(int)
    pred['yhat_min'] = pred['yhat_min'].apply(np.floor).clip(lower=0).astype(int)
    pred['yhat_max'] = pred['yhat_max'].apply(np.ceil).clip(lower=0).astype(int)

    # Garantizar coherencia min <= mid <= max
    pred['yhat_min'] = np.minimum(pred['yhat_min'], pred['yhat'])
    pred['yhat_max'] = np.maximum(pred['yhat_max'], pred['yhat'])

    LOG.info('Forecast completo: %d filas', len(pred))
    return pred


# ======================================================================
# BACKTEST: dejar los ultimos meses fuera y medir el error real
# ======================================================================
def backtest_por_producto(df_full, df_class, meses_holdout=3):
    """
    Quita los ultimos `meses_holdout` meses del entrenamiento, predice esos
    meses y compara con la realidad. Devuelve WAPE, MASE y bias por producto.
    """
    fecha_max = df_full['ds'].max()
    fecha_corte = fecha_max - pd.DateOffset(months=meses_holdout)

    df_train = df_full[df_full['ds'] <= fecha_corte]
    df_test = df_full[df_full['ds'] > fecha_corte]
    if df_train.empty or df_test.empty:
        return pd.DataFrame(columns=['unique_id', 'wape_pct', 'mase', 'bias_pct', 'ruta'])

    pred = ejecutar_forecast(df_train, df_class, meses_holdout)
    if pred.empty:
        return pd.DataFrame(columns=['unique_id', 'wape_pct', 'mase', 'bias_pct', 'ruta'])

    # Unir prediccion con la realidad
    merged = (df_test[['unique_id', 'ds', 'y']]
              .merge(pred[['unique_id', 'ds', 'yhat', 'ruta']],
                     on=['unique_id', 'ds'], how='inner'))

    # Para MASE necesitamos la serie de entrenamiento de cada producto
    train_por_prod = df_train.groupby('unique_id')['y'].apply(list).to_dict()

    metricas = []
    for pid, g in merged.groupby('unique_id'):
        y_real = g['y'].values
        y_pred = g['yhat'].values
        suma_real = np.sum(np.abs(y_real))

        if suma_real == 0:
            # No hubo ventas en el holdout, no se puede medir WAPE
            continue

        # WAPE: error porcentual ponderado
        wape = np.sum(np.abs(y_real - y_pred)) / suma_real * 100
        # Bias: sesgo (positivo=sobreestimacion, negativo=infraestimacion)
        bias = np.sum(y_pred - y_real) / suma_real * 100

        # MASE: error escalado por el naive estacional (anual)
        y_train_p = np.asarray(train_por_prod.get(pid, []))
        if len(y_train_p) > 12:
            # Diferencias entre meses separados por un anio (naive estacional)
            scale = np.mean(np.abs(y_train_p[12:] - y_train_p[:-12]))
        elif len(y_train_p) > 1:
            scale = np.mean(np.abs(np.diff(y_train_p)))
        else:
            scale = 0

        if scale > 0:
            mase = float(np.mean(np.abs(y_real - y_pred)) / scale)
        else:
            mase = float('nan')

        metricas.append({
            'unique_id': pid,
            'wape_pct': float(wape),
            'mase': mase,
            'bias_pct': float(bias),
            'ruta': g['ruta'].iloc[0],
            'n_test': int(len(g)),
        })

    return pd.DataFrame(metricas)
