"""
Pagina 4 - Resultados del pronostico (varias subvistas en tabs).

Subvistas:
  1. Tabla ordenable y exportable.
  2. Grafico individual con IC y filtros producto/sub-cat/categoria.
  3. Comparativa historica vs pronostico (barras por ano).
  4. Metricas por producto (backtest interno).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QTableView, QTabWidget, QVBoxLayout, QWidget,
)

from ..core.config import CONFIG, LOG
from ..core.security import descifrar_columnas, descifrar_texto
from ..core.comparison import comparativa_historica
from ..core.forecast_store import (guardar_pronostico, listar_pronosticos,
                                    cargar_pronostico, comparar_pronosticos)
from .sesion import SESION
from .widgets import MplCanvas
from .workers import BacktestWorker, lanzar_en_hilo


# ============================================================
# Tab 1 - Tabla
# ============================================================
class _TabTabla(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        lay = QVBoxLayout(self)

        # Filtros sobre la tabla (NO sobre el modelo, solo visualizacion)
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Categoria:'))
        self.cb_cat = QComboBox(); self.cb_cat.addItem('Todos')
        self.cb_cat.currentTextChanged.connect(self._actualizar_subcats)
        self.cb_cat.currentTextChanged.connect(self._refrescar_tabla)
        ctrl.addWidget(self.cb_cat)

        ctrl.addWidget(QLabel('Sub-categoria:'))
        self.cb_sub = QComboBox(); self.cb_sub.addItem('Todos')
        self.cb_sub.currentTextChanged.connect(self._refrescar_tabla)
        ctrl.addWidget(self.cb_sub)

        ctrl.addWidget(QLabel('Clase ABC-XYZ:'))
        self.cb_abc = QComboBox(); self.cb_abc.addItem('Todos')
        self.cb_abc.currentTextChanged.connect(self._refrescar_tabla)
        ctrl.addWidget(self.cb_abc)

        ctrl.addStretch()
        self.btn_export = QPushButton('Exportar tabla')
        self.btn_export.setProperty('class', 'secondary')
        self.btn_export.clicked.connect(self._exportar)
        ctrl.addWidget(self.btn_export)

        self.btn_guardar = QPushButton('Guardar pronostico')
        self.btn_guardar.setProperty('class', 'secondary')
        self.btn_guardar.clicked.connect(self._guardar)
        ctrl.addWidget(self.btn_guardar)
        lay.addLayout(ctrl)

        self.tabla = QTableView()
        self.tabla.setSortingEnabled(True)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        lay.addWidget(self.tabla)

        self.lbl_resumen = QLabel('')
        self.lbl_resumen.setProperty('class', 'muted')
        lay.addWidget(self.lbl_resumen)

    def refrescar(self):
        if not SESION.pronostico_listo:
            self._set_modelo(pd.DataFrame())
            return
        # Llenar combos
        pred = SESION.pred
        cats = ['Todos'] + sorted(pred['Category'].dropna().unique().tolist())
        subs = ['Todos'] + sorted(pred['Sub-Category'].dropna().unique().tolist())
        abcs = ['Todos'] + sorted(pred['abc_xyz'].dropna().unique().tolist())
        for cb, items in [(self.cb_cat, cats), (self.cb_sub, subs),
                          (self.cb_abc, abcs)]:
            cb.blockSignals(True)
            cb.clear(); cb.addItems(items); cb.setCurrentIndex(0)
            cb.blockSignals(False)
        self._refrescar_tabla()

    def _actualizar_subcats(self, cat):
        if not SESION.pronostico_listo:
            return
        pred = SESION.pred
        if cat and cat != 'Todos':
            subs = sorted(pred[pred['Category'] == cat]['Sub-Category']
                                .dropna().unique().tolist())
        else:
            subs = sorted(pred['Sub-Category'].dropna().unique().tolist())
        self.cb_sub.blockSignals(True)
        self.cb_sub.clear()
        self.cb_sub.addItems(['Todos'] + subs)
        self.cb_sub.blockSignals(False)

    def _refrescar_tabla(self):
        if not SESION.pronostico_listo:
            return
        pred = SESION.pred.copy()
        cat = self.cb_cat.currentText()
        sub = self.cb_sub.currentText()
        abc = self.cb_abc.currentText()
        if cat and cat != 'Todos': pred = pred[pred['Category'] == cat]
        if sub and sub != 'Todos': pred = pred[pred['Sub-Category'] == sub]
        if abc and abc != 'Todos': pred = pred[pred['abc_xyz'] == abc]

        # Descifrar nombres
        pred = descifrar_columnas(pred, CONFIG['seguretat']['xifrar_camps'])

        granularidad = SESION.pred_filtros.get('granularidad', 'mensual')
        fmt = '%Y-%m-%d' if granularidad in ('diario', 'semanal') else '%Y-%m'

        cols_orden = ['unique_id', 'Product Name', 'Category', 'Sub-Category',
                      'abc_xyz', 'sbc_class', 'ruta', 'ds',
                      'yhat_min', 'yhat', 'yhat_max']
        cols_orden = [c for c in cols_orden if c in pred.columns]
        df_v = pred[cols_orden].copy()
        df_v['ds'] = pd.to_datetime(df_v['ds']).dt.strftime(fmt)
        for c in ('yhat', 'yhat_min', 'yhat_max'):
            if c in df_v.columns:
                df_v[c] = df_v[c].round(2)

        # Renombrar para visualizacion
        renombre = {
            'unique_id': 'ID', 'Product Name': 'Nombre',
            'Category': 'Categoria', 'Sub-Category': 'Sub-Categoria',
            'abc_xyz': 'ABC-XYZ', 'sbc_class': 'SBC',
            'ruta': 'Modelo', 'ds': 'Fecha',
            'yhat_min': 'Min (IC)', 'yhat': 'Pronostico',
            'yhat_max': 'Max (IC)',
        }
        df_v = df_v.rename(columns=renombre)
        self._set_modelo(df_v)
        self.lbl_resumen.setText(f'{len(df_v)} filas mostradas.')

    def _set_modelo(self, df):
        modelo = QStandardItemModel(len(df), len(df.columns))
        modelo.setHorizontalHeaderLabels(list(df.columns))
        for i, (_, row) in enumerate(df.iterrows()):
            for j, val in enumerate(row):
                item = QStandardItem(str(val))
                item.setEditable(False)
                # Alineacion: numericos a la derecha
                if isinstance(val, (int, float, np.integer, np.floating)):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                modelo.setItem(i, j, item)
        self.tabla.setModel(modelo)
        self.tabla.resizeColumnsToContents()

    def _exportar(self):
        if not SESION.pronostico_listo:
            QMessageBox.warning(self, 'Sin pronostico', 'Genera primero un pronostico.')
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, 'Exportar tabla', 'pronostico.csv',
            'CSV (*.csv);;Excel (*.xlsx)')
        if not ruta:
            return
        modelo = self.tabla.model()
        if modelo is None:
            return
        cols = [modelo.headerData(i, Qt.Horizontal) for i in range(modelo.columnCount())]
        filas = []
        for r in range(modelo.rowCount()):
            filas.append([modelo.data(modelo.index(r, c)) for c in range(modelo.columnCount())])
        df = pd.DataFrame(filas, columns=cols)
        try:
            if ruta.endswith('.xlsx'):
                df.to_excel(ruta, index=False)
            else:
                df.to_csv(ruta, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, 'Exportado',
                                    f'Tabla exportada en:\n{ruta}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

    def _guardar(self):
        if not SESION.pronostico_listo:
            QMessageBox.warning(self, 'Sin pronostico', 'Genera primero un pronostico.')
            return
        try:
            ruta = guardar_pronostico(
                SESION.pred,
                horizon=SESION.pred_horizon,
                ic=SESION.pred_ic,
                filtros=SESION.pred_filtros,
            )
            QMessageBox.information(self, 'Pronostico guardado',
                                    f'Guardado en:\n{ruta}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))


# ============================================================
# Tab 2 - Grafico individual con IC
# ============================================================
class _TabGrafico(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        lay = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Nivel:'))
        self.cb_nivel = QComboBox()
        self.cb_nivel.addItems(['Todos', 'Categoria', 'Sub-categoria', 'Producto'])
        self.cb_nivel.currentTextChanged.connect(self._refrescar_valores)
        ctrl.addWidget(self.cb_nivel)

        ctrl.addWidget(QLabel('Valor:'))
        self.cb_valor = QComboBox(); self.cb_valor.addItem('-')
        self.cb_valor.currentTextChanged.connect(self._dibujar)
        ctrl.addWidget(self.cb_valor)

        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.canvas = MplCanvas(width=10, height=4)
        lay.addWidget(self.canvas)

    def refrescar(self):
        self._refrescar_valores(self.cb_nivel.currentText())

    def _refrescar_valores(self, nivel):
        if not SESION.datos_listos:
            return
        valores = ['-']
        if nivel == 'Todos':
            valores = ['Todos']
        elif nivel == 'Categoria':
            valores = sorted(SESION.df_full['Category'].dropna().unique().tolist())
        elif nivel == 'Sub-categoria':
            valores = sorted(SESION.df_full['Sub-Category'].dropna().unique().tolist())
        elif nivel == 'Producto':
            nombres = SESION.df_full['Product Name'].unique().tolist()
            valores = sorted(set(descifrar_texto(n) for n in nombres))
        self.cb_valor.blockSignals(True)
        self.cb_valor.clear()
        self.cb_valor.addItems(valores)
        self.cb_valor.blockSignals(False)
        self._dibujar()

    def _dibujar(self):
        if not SESION.datos_listos:
            return
        self.canvas.limpiar()
        ax = self.canvas.axes

        nivel = self.cb_nivel.currentText()
        valor = self.cb_valor.currentText()

        # Filtrar historico y pronostico
        df_h = SESION.df_full.copy()
        df_p = SESION.pred.copy() if SESION.pronostico_listo else None

        if nivel == 'Categoria' and valor not in ('-', 'Todos'):
            df_h = df_h[df_h['Category'] == valor]
            if df_p is not None:
                df_p = df_p[df_p['Category'] == valor]
            titulo = f'Categoria: {valor}'
        elif nivel == 'Sub-categoria' and valor not in ('-', 'Todos'):
            df_h = df_h[df_h['Sub-Category'] == valor]
            if df_p is not None:
                df_p = df_p[df_p['Sub-Category'] == valor]
            titulo = f'Sub-categoria: {valor}'
        elif nivel == 'Producto' and valor not in ('-', 'Todos'):
            df_h = df_h.copy()
            df_h['_pn'] = df_h['Product Name'].apply(descifrar_texto)
            df_h = df_h[df_h['_pn'] == valor].drop(columns='_pn')
            if df_p is not None:
                df_p = df_p.copy()
                df_p['_pn'] = df_p['Product Name'].apply(descifrar_texto)
                df_p = df_p[df_p['_pn'] == valor].drop(columns='_pn')
            titulo = f'Producto: {valor}'
        else:
            titulo = 'Total agregado'

        if df_h.empty:
            ax.text(0.5, 0.5, 'Sin datos para esta seleccion',
                    ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw(); return

        hist = df_h.groupby('ds')['y'].sum().reset_index()
        ax.plot(hist['ds'], hist['y'], color='#1F4E79', lw=2, label='Historico')

        if df_p is not None and not df_p.empty:
            grup = df_p.groupby('ds').agg({
                'yhat': 'sum',
                'yhat_min': 'sum',
                'yhat_max': 'sum',
            }).reset_index()
            ax.plot(grup['ds'], grup['yhat'], color='#E67E22',
                    lw=2, ls='--', marker='o', ms=5, label='Pronostico')
            ax.fill_between(grup['ds'], grup['yhat_min'], grup['yhat_max'],
                            color='#E67E22', alpha=0.20,
                            label=f'IC {int(SESION.pred_ic*100)}%')
            if not hist.empty:
                ax.axvline(hist['ds'].max(), color='gray', ls=':', lw=1)

        ax.set_title(titulo, fontweight='bold')
        ax.set_ylabel('Unidades')
        ax.legend(loc='best')
        ax.grid(alpha=0.3)
        for label in ax.get_xticklabels():
            label.set_rotation(30); label.set_ha('right')
        self.canvas.draw()


# ============================================================
# Tab 3 - Comparativa historica
# ============================================================
class _TabComparativa(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        lay = QVBoxLayout(self)

        info = QLabel(
            'Compara las unidades pronosticadas (en el rango futuro) con las '
            'unidades realmente vendidas en el mismo rango de meses de anos anteriores.'
        )
        info.setProperty('class', 'muted')
        info.setWordWrap(True)
        lay.addWidget(info)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Nivel:'))
        self.cb_nivel = QComboBox()
        self.cb_nivel.addItems(['Todos', 'Categoria', 'Sub-categoria', 'Producto'])
        self.cb_nivel.currentTextChanged.connect(self._refrescar_valores)
        ctrl.addWidget(self.cb_nivel)

        ctrl.addWidget(QLabel('Valor:'))
        self.cb_valor = QComboBox(); self.cb_valor.addItem('-')
        self.cb_valor.currentTextChanged.connect(self._dibujar)
        ctrl.addWidget(self.cb_valor)

        ctrl.addWidget(QLabel('Años historicos:'))
        self.spin_anios = QSpinBox()
        self.spin_anios.setRange(1, 6)
        self.spin_anios.setValue(4)
        self.spin_anios.valueChanged.connect(self._dibujar)
        ctrl.addWidget(self.spin_anios)

        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.canvas = MplCanvas(width=10, height=4)
        lay.addWidget(self.canvas)

    def refrescar(self):
        self._refrescar_valores(self.cb_nivel.currentText())

    def _refrescar_valores(self, nivel):
        if not SESION.datos_listos:
            return
        if nivel == 'Todos':
            valores = ['Todos']
        elif nivel == 'Categoria':
            valores = sorted(SESION.df_full['Category'].dropna().unique().tolist())
        elif nivel == 'Sub-categoria':
            valores = sorted(SESION.df_full['Sub-Category'].dropna().unique().tolist())
        elif nivel == 'Producto':
            nombres = SESION.df_full['Product Name'].unique().tolist()
            valores = sorted(set(descifrar_texto(n) for n in nombres))
        else:
            valores = ['-']
        self.cb_valor.blockSignals(True)
        self.cb_valor.clear()
        self.cb_valor.addItems(valores)
        self.cb_valor.blockSignals(False)
        self._dibujar()

    def _dibujar(self):
        self.canvas.limpiar()
        ax = self.canvas.axes
        if not SESION.pronostico_listo:
            ax.text(0.5, 0.5, 'Genera primero un pronostico',
                    ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw(); return

        nivel_map = {'Todos': 'todos', 'Categoria': 'categoria',
                     'Sub-categoria': 'sub-categoria', 'Producto': 'producto'}
        nivel_n = nivel_map.get(self.cb_nivel.currentText(), 'todos')
        valor = self.cb_valor.currentText() if self.cb_valor.currentText() != '-' else None

        df_comp = comparativa_historica(
            SESION.df_full, SESION.pred,
            nivel=nivel_n, valor=valor,
            n_anios_historicos=self.spin_anios.value(),
        )
        if df_comp.empty:
            ax.text(0.5, 0.5, 'Sin datos para esta comparativa',
                    ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw(); return

        colores = ['#1F4E79' if not e else '#E67E22'
                   for e in df_comp['es_pronostico']]
        ax.bar(df_comp['etiqueta'], df_comp['unidades'], color=colores)
        for i, v in enumerate(df_comp['unidades']):
            ax.text(i, v + max(df_comp['unidades']) * 0.01,
                    f'{int(v):,}'.replace(',', '.'),
                    ha='center', fontsize=9)

        rango = (f'{SESION.pred["ds"].min().strftime("%b")} - '
                 f'{SESION.pred["ds"].max().strftime("%b %Y")}')
        ax.set_title(f'Comparativa de unidades - {rango}',
                     fontweight='bold')
        ax.set_ylabel('Unidades')
        ax.grid(axis='y', alpha=0.3)
        for label in ax.get_xticklabels():
            label.set_rotation(20); label.set_ha('right')
        self.canvas.draw()


# ============================================================
# Tab 4 - Metricas por producto (backtest interno)
# ============================================================
class _TabMetricas(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        self._hilo = None
        lay = QVBoxLayout(self)

        info = QLabel(
            'Backtest interno: entrena el modelo dejando los ultimos meses fuera '
            'y compara la prediccion con la venta real, producto a producto.\n\n'
            '- WAPE % : error porcentual ponderado. Cuanto mas bajo, mejor.\n'
            '- MASE   : compara con la prediccion naive (copiar el ano pasado). '
            'Si MASE < 1, el modelo bate al naive. Si MASE > 1, no merece la pena.\n'
            '- Bias % : sesgo. Positivo = sobreestimacion, negativo = infraestimacion.\n\n'
            'Para datos retail con muchos ceros (productos intermitentes), MASE es '
            'la metrica mas fiable. El WAPE puede dispararse aunque las predicciones '
            'sean razonables.'
        )
        info.setProperty('class', 'muted')
        info.setWordWrap(True)
        lay.addWidget(info)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Meses de holdout:'))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 12)
        self.spin_h.setValue(3)
        ctrl.addWidget(self.spin_h)
        self.btn_run = QPushButton('Ejecutar backtest')
        self.btn_run.clicked.connect(self._ejecutar)
        ctrl.addWidget(self.btn_run)
        self.btn_export = QPushButton('Exportar metricas')
        self.btn_export.setProperty('class', 'secondary')
        self.btn_export.clicked.connect(self._exportar)
        ctrl.addWidget(self.btn_export)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.barra = QProgressBar(); self.barra.setVisible(False)
        lay.addWidget(self.barra)

        self.lbl_resumen = QLabel('')
        self.lbl_resumen.setProperty('class', 'muted')
        lay.addWidget(self.lbl_resumen)

        self.tabla = QTableView()
        self.tabla.setSortingEnabled(True)
        self.tabla.setAlternatingRowColors(True)
        lay.addWidget(self.tabla)

    def refrescar(self):
        # Si ya tenemos metricas calculadas, mostramos
        if SESION.metricas_producto is not None:
            self._pintar(SESION.metricas_producto)

    def _ejecutar(self):
        if not SESION.datos_listos:
            QMessageBox.warning(self, 'Sin datos', 'Carga datos primero.')
            return
        self.btn_run.setEnabled(False)
        self.barra.setVisible(True); self.barra.setValue(0)
        worker = BacktestWorker(SESION.df_full, SESION.df_class,
                                meses_holdout=self.spin_h.value())
        self._hilo = lanzar_en_hilo(
            worker, on_finalizado=self._ok, on_error=self._err,
            on_progreso=lambda p, m: (self.barra.setValue(p),
                                       self.lbl_resumen.setText(m)),
        )

    def _ok(self, df):
        self.btn_run.setEnabled(True)
        self.barra.setVisible(False)
        SESION.metricas_producto = df
        self._pintar(df)

    def _err(self, msg):
        self.btn_run.setEnabled(True)
        self.barra.setVisible(False)
        QMessageBox.critical(self, 'Error', msg)

    def _pintar(self, df):
        if df is None or df.empty:
            self.lbl_resumen.setText('No hay metricas (insuficientes datos para backtest).')
            self.tabla.setModel(QStandardItemModel())
            return
        # Anadir nombre descifrado y categoria
        meta = SESION.df_class[['unique_id', 'Product Name',
                                'Category', 'Sub-Category', 'abc_xyz']].copy()
        meta['Product Name'] = meta['Product Name'].apply(descifrar_texto)
        df_v = df.merge(meta, on='unique_id', how='left')
        df_v = df_v.sort_values('wape_pct')

        # Resumen con interpretacion
        wape_med = df_v['wape_pct'].median()
        bias_med = df_v['bias_pct'].abs().median()
        mase_med = df_v['mase'].median() if 'mase' in df_v.columns else float('nan')

        # Interpretacion del MASE para el usuario
        if not pd.isna(mase_med):
            if mase_med < 1:
                interp_mase = f' (MASE<1: el modelo bate al naive estacional)'
            elif mase_med < 1.5:
                interp_mase = f' (MASE~1: similar al naive estacional)'
            else:
                interp_mase = f' (MASE>1.5: peor que el naive estacional)'
            mase_txt = f'MASE mediano: {mase_med:.2f}{interp_mase} | '
        else:
            mase_txt = ''

        self.lbl_resumen.setText(
            f'{mase_txt}WAPE mediano: {wape_med:.1f}% | '
            f'bias absoluto mediano: {bias_med:.1f}%'
        )

        df_v['wape_pct'] = df_v['wape_pct'].round(1)
        df_v['bias_pct'] = df_v['bias_pct'].round(1)
        if 'mase' in df_v.columns:
            df_v['mase'] = df_v['mase'].round(2)

        cols = ['unique_id', 'Product Name', 'Category', 'Sub-Category',
                'abc_xyz', 'ruta', 'n_test', 'wape_pct', 'mase', 'bias_pct']
        df_v = df_v[[c for c in cols if c in df_v.columns]]
        df_v = df_v.rename(columns={
            'unique_id': 'ID', 'Product Name': 'Nombre',
            'Category': 'Categoria', 'Sub-Category': 'Sub-Categoria',
            'abc_xyz': 'ABC-XYZ', 'ruta': 'Modelo',
            'n_test': 'N test', 'wape_pct': 'WAPE %',
            'mase': 'MASE', 'bias_pct': 'Bias %',
        })

        modelo = QStandardItemModel(len(df_v), len(df_v.columns))
        modelo.setHorizontalHeaderLabels(list(df_v.columns))
        for i, (_, row) in enumerate(df_v.iterrows()):
            for j, val in enumerate(row):
                it = QStandardItem(str(val))
                it.setEditable(False)
                modelo.setItem(i, j, it)
        self.tabla.setModel(modelo)
        self.tabla.resizeColumnsToContents()

    def _exportar(self):
        if SESION.metricas_producto is None:
            QMessageBox.warning(self, 'Sin metricas', 'Ejecuta primero el backtest.')
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, 'Exportar metricas', 'metricas_producto.csv',
            'CSV (*.csv);;Excel (*.xlsx)')
        if not ruta:
            return
        df = SESION.metricas_producto.copy()
        try:
            if ruta.endswith('.xlsx'):
                df.to_excel(ruta, index=False)
            else:
                df.to_csv(ruta, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, 'Exportado', f'Metricas guardadas en:\n{ruta}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))


# ============================================================
# Tab 5 - Comparativa entre pronosticos guardados
# ============================================================
class _TabComparativaPron(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        lay = QVBoxLayout(self)

        info = QLabel(
            'Compara dos pronosticos guardados (por ejemplo, el del mes pasado '
            'frente al de este mes) para ver como ha evolucionado.'
        )
        info.setProperty('class', 'muted')
        info.setWordWrap(True)
        lay.addWidget(info)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Pronostico A:'))
        self.cb_a = QComboBox()
        ctrl.addWidget(self.cb_a)
        ctrl.addWidget(QLabel('Pronostico B:'))
        self.cb_b = QComboBox()
        ctrl.addWidget(self.cb_b)
        self.btn_recargar = QPushButton('Recargar lista')
        self.btn_recargar.setProperty('class', 'secondary')
        self.btn_recargar.clicked.connect(self.refrescar)
        ctrl.addWidget(self.btn_recargar)
        self.btn_comparar = QPushButton('Comparar')
        self.btn_comparar.setProperty('class', 'accion')
        self.btn_comparar.clicked.connect(self._comparar)
        ctrl.addWidget(self.btn_comparar)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.canvas = MplCanvas(width=10, height=4)
        lay.addWidget(self.canvas)
        self.lbl_resumen = QLabel('')
        lay.addWidget(self.lbl_resumen)

    def refrescar(self):
        items = listar_pronosticos()
        etiquetas = [
            f'{m["timestamp"]} | h={m["horizon"]} | {m["n_productos"]} prod.'
            + (f' | {m["nombre"]}' if m.get('nombre') else '')
            for m in items
        ]
        for cb in (self.cb_a, self.cb_b):
            cb.clear()
            for et, m in zip(etiquetas, items):
                cb.addItem(et, userData=m['ruta'])

    def _comparar(self):
        if self.cb_a.count() < 2 or self.cb_b.count() < 2:
            QMessageBox.information(self, 'Pocos pronosticos',
                'Necesitas al menos 2 pronosticos guardados para comparar. '
                'Genera y guarda dos desde la pestana Tabla.')
            return
        ruta_a = self.cb_a.currentData()
        ruta_b = self.cb_b.currentData()
        if ruta_a == ruta_b:
            QMessageBox.warning(self, 'Misma seleccion',
                                'Selecciona dos pronosticos distintos.')
            return
        try:
            pa = cargar_pronostico(ruta_a)
            pb = cargar_pronostico(ruta_b)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            return

        df_cmp = comparar_pronosticos(pa, pb)
        # Plot agregado
        self.canvas.limpiar(); ax = self.canvas.axes
        agg_a = pa.groupby('ds')['yhat'].sum()
        agg_b = pb.groupby('ds')['yhat'].sum()
        ax.plot(agg_a.index, agg_a.values, label='Pronostico A',
                color='#1F4E79', marker='o')
        ax.plot(agg_b.index, agg_b.values, label='Pronostico B',
                color='#E67E22', marker='s')
        ax.set_title('Comparativa entre pronosticos guardados',
                     fontweight='bold')
        ax.set_ylabel('Unidades agregadas')
        ax.legend(); ax.grid(alpha=0.3)
        for label in ax.get_xticklabels():
            label.set_rotation(30); label.set_ha('right')
        self.canvas.draw()

        delta = float(df_cmp['delta'].sum())
        self.lbl_resumen.setText(
            f'Diferencia agregada B - A: {delta:+,.0f} unidades '
            f'sobre {len(df_cmp)} filas comunes.'.replace(',', '.')
        )


# ============================================================
# Pagina contenedora
# ============================================================
class PaginaResultados(QWidget):
    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana = ventana_principal

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)

        cab = QLabel('Resultados del pronostico')
        cab.setObjectName('H1')
        lay.addWidget(cab)

        self.tabs = QTabWidget()
        self.tab_tabla = _TabTabla(ventana_principal)
        self.tab_grafico = _TabGrafico(ventana_principal)
        self.tab_comparativa = _TabComparativa(ventana_principal)
        self.tab_metricas = _TabMetricas(ventana_principal)
        self.tab_compar_pron = _TabComparativaPron(ventana_principal)

        self.tabs.addTab(self.tab_tabla, 'Tabla')
        self.tabs.addTab(self.tab_grafico, 'Grafico individual')
        self.tabs.addTab(self.tab_comparativa, 'Comparativa historica')
        self.tabs.addTab(self.tab_metricas, 'Metricas por producto')
        self.tabs.addTab(self.tab_compar_pron, 'Comparar pronosticos guardados')
        lay.addWidget(self.tabs)

    def refrescar(self):
        self.tab_tabla.refrescar()
        self.tab_grafico.refrescar()
        self.tab_comparativa.refrescar()
        self.tab_metricas.refrescar()
        self.tab_compar_pron.refrescar()
