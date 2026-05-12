"""Pagina 3 - Generacion de pronostico (filtros y disparo)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from ..core.config import CONFIG, LOG
from ..core.security import descifrar_texto
from ..core.alerts import evaluar_alertas
from ..core.metrics import wape, bias as bias_metric
from .sesion import SESION
from .widgets import Badge
from .workers import ForecastWorker, lanzar_en_hilo


# Mapeo de horizontes al numero de meses que entrenamos
MAP_HORIZONTE = {
    'Proximo dia': 1,
    'Proxima semana': 1,
    'Proximo mes': 1,
    '3 meses': 3,
    '6 meses': 6,
    '12 meses': 12,
    'Personalizado': None,  # se toma del spinbox
}


class PaginaPronostico(QWidget):
    """Configuracion de filtros + boton de disparo."""

    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana = ventana_principal
        self._hilo = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        h = QLabel('Generar pronostico')
        h.setObjectName('H1')
        layout.addWidget(h)
        sub = QLabel('Configura el horizonte temporal, el intervalo de confianza '
                     'y los filtros sobre los productos a pronosticar.')
        sub.setProperty('class', 'muted')
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Mensaje cuando no hay datos
        self.lbl_vacio = QLabel('Aun no hay datos cargados. '
                                'Ve a "Cargar datos" para empezar.')
        self.lbl_vacio.setProperty('class', 'muted')
        self.lbl_vacio.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_vacio)

        # Contenedor con los controles (visible cuando hay datos)
        self.frame_controles = QFrame()
        ctrls = QHBoxLayout(self.frame_controles)
        ctrls.setSpacing(16)

        # --- Columna izquierda: horizonte e IC ---
        gb_horiz = QGroupBox('Horizonte temporal')
        gh = QVBoxLayout(gb_horiz)
        self.radios_horiz = {}
        for h_nombre in MAP_HORIZONTE.keys():
            rb = QRadioButton(h_nombre)
            self.radios_horiz[h_nombre] = rb
            gh.addWidget(rb)
        self.radios_horiz['3 meses'].setChecked(True)

        h_pers = QHBoxLayout()
        h_pers.addWidget(QLabel('Meses (si "Personalizado"):'))
        self.spin_meses = QSpinBox()
        self.spin_meses.setRange(1, 36)
        self.spin_meses.setValue(6)
        h_pers.addWidget(self.spin_meses)
        gh.addLayout(h_pers)

        gb_ic = QGroupBox('Intervalo de confianza')
        gic = QVBoxLayout(gb_ic)
        self.lbl_ic = QLabel('IC: 80%')
        self.lbl_ic.setObjectName('H3')
        gic.addWidget(self.lbl_ic)
        self.slider_ic = QSlider(Qt.Horizontal)
        self.slider_ic.setRange(50, 95)
        self.slider_ic.setSingleStep(5)
        self.slider_ic.setPageStep(5)
        self.slider_ic.setValue(int(CONFIG['forecast'].get('intervalo_confianza', 0.80) * 100))
        self.slider_ic.valueChanged.connect(
            lambda v: self.lbl_ic.setText(f'IC: {v}%')
        )
        gic.addWidget(self.slider_ic)
        gic.addWidget(QLabel('Quantile regression con LightGBM (q_low / q_med / q_high).'))

        col_izq = QVBoxLayout()
        col_izq.addWidget(gb_horiz)
        col_izq.addWidget(gb_ic)
        col_izq.addStretch()
        ctrls.addLayout(col_izq, 1)

        # --- Columna central: filtros sobre productos ---
        gb_filtros = QGroupBox('Filtros sobre productos')
        gf = QGridLayout(gb_filtros)
        gf.addWidget(QLabel('Categoria:'), 0, 0)
        self.cb_cat = QComboBox(); self.cb_cat.addItem('Todos')
        gf.addWidget(self.cb_cat, 0, 1)
        gf.addWidget(QLabel('Sub-categoria:'), 1, 0)
        self.cb_sub = QComboBox(); self.cb_sub.addItem('Todos')
        gf.addWidget(self.cb_sub, 1, 1)
        gf.addWidget(QLabel('Producto:'), 2, 0)
        self.cb_prod = QComboBox(); self.cb_prod.addItem('Todos')
        self.cb_prod.setEditable(True)  # permite buscar escribiendo
        gf.addWidget(self.cb_prod, 2, 1)
        gf.addWidget(QLabel('Clase ABC-XYZ:'), 3, 0)
        self.cb_abc = QComboBox(); self.cb_abc.addItem('Todos')
        gf.addWidget(self.cb_abc, 3, 1)
        self.chk_solo_forec = QCheckBox(
            'Solo productos forecasteables individualmente')
        self.chk_solo_forec.setChecked(True)
        gf.addWidget(self.chk_solo_forec, 4, 0, 1, 2)
        ctrls.addWidget(gb_filtros, 2)

        # --- Columna derecha: resumen + boton ---
        col_der = QVBoxLayout()
        gb_info = QGroupBox('Resumen')
        gi = QVBoxLayout(gb_info)
        self.lbl_info = QLabel('Selecciona los filtros para ver el resumen.')
        self.lbl_info.setWordWrap(True)
        gi.addWidget(self.lbl_info)
        col_der.addWidget(gb_info)

        self.btn_pronosticar = QPushButton('Generar pronostico')
        self.btn_pronosticar.setProperty('class', 'accion')
        self.btn_pronosticar.setMinimumHeight(46)
        self.btn_pronosticar.clicked.connect(self._on_pronosticar)
        col_der.addWidget(self.btn_pronosticar)
        col_der.addStretch()
        ctrls.addLayout(col_der, 1)

        layout.addWidget(self.frame_controles)

        # --- Progreso ---
        self.lbl_estado = QLabel('')
        self.lbl_estado.setProperty('class', 'muted')
        layout.addWidget(self.lbl_estado)
        self.barra = QProgressBar()
        self.barra.setVisible(False)
        layout.addWidget(self.barra)

        # --- Alertas (panel post-pronostico) ---
        self.frame_alertas = QFrame()
        self.frame_alertas.setObjectName('Tarjeta')
        self.frame_alertas.setVisible(False)
        self.lay_alertas = QVBoxLayout(self.frame_alertas)
        layout.addWidget(self.frame_alertas)

        layout.addStretch()
        self.frame_controles.setVisible(False)

        # Conexiones de filtros
        self.cb_cat.currentTextChanged.connect(self._refrescar_subcats)
        self.cb_cat.currentTextChanged.connect(self._refrescar_productos)
        self.cb_sub.currentTextChanged.connect(self._refrescar_productos)
        for cb in (self.cb_cat, self.cb_sub, self.cb_prod, self.cb_abc):
            cb.currentTextChanged.connect(self._actualizar_resumen)
        self.chk_solo_forec.stateChanged.connect(self._actualizar_resumen)

    # ------------------------------------------------------------
    def refrescar(self):
        """Llamado cuando cambian los datos cargados."""
        if not SESION.datos_listos:
            self.lbl_vacio.setVisible(True)
            self.frame_controles.setVisible(False)
            return
        self.lbl_vacio.setVisible(False)
        self.frame_controles.setVisible(True)
        self._cargar_combos()
        self._actualizar_resumen()

    def _cargar_combos(self):
        df_full = SESION.df_full
        df_class = SESION.df_class
        cats = ['Todos'] + sorted(df_full['Category'].unique().tolist())
        subs = ['Todos'] + sorted(df_full['Sub-Category'].unique().tolist())
        prods_descif = sorted(set(descifrar_texto(p)
                                  for p in df_class['Product Name'].unique()))
        prods = ['Todos'] + prods_descif
        abcs = ['Todos'] + sorted(df_class['abc_xyz'].unique().tolist())

        self._set_items(self.cb_cat, cats)
        self._set_items(self.cb_sub, subs)
        self._set_items(self.cb_prod, prods)
        self._set_items(self.cb_abc, abcs)

    @staticmethod
    def _set_items(cb: QComboBox, items: list):
        cb.blockSignals(True)
        cb.clear()
        cb.addItems(items)
        cb.setCurrentIndex(0)
        cb.blockSignals(False)

    def _refrescar_subcats(self, cat_sel: str):
        if SESION.df_full is None:
            return
        df = SESION.df_full
        if cat_sel and cat_sel != 'Todos':
            subs = sorted(df[df['Category'] == cat_sel]['Sub-Category'].unique().tolist())
        else:
            subs = sorted(df['Sub-Category'].unique().tolist())
        self._set_items(self.cb_sub, ['Todos'] + subs)

    def _refrescar_productos(self):
        if SESION.df_full is None:
            return
        df = SESION.df_full
        cat_sel = self.cb_cat.currentText()
        sub_sel = self.cb_sub.currentText()
        mask = df.index == df.index  # all True
        if cat_sel and cat_sel != 'Todos':
            mask &= df['Category'] == cat_sel
        if sub_sel and sub_sel != 'Todos':
            mask &= df['Sub-Category'] == sub_sel
        nombres_cifrados = df[mask]['Product Name'].unique().tolist()
        prods = sorted(set(descifrar_texto(p) for p in nombres_cifrados))
        self._set_items(self.cb_prod, ['Todos'] + prods)

    # ------------------------------------------------------------
    def _aplicar_filtros(self):
        """Devuelve el subconjunto de df_class que cumple los filtros."""
        df_c = SESION.df_class.copy()
        cat = self.cb_cat.currentText()
        sub = self.cb_sub.currentText()
        prod = self.cb_prod.currentText()
        abc = self.cb_abc.currentText()
        if cat and cat != 'Todos':
            df_c = df_c[df_c['Category'] == cat]
        if sub and sub != 'Todos':
            df_c = df_c[df_c['Sub-Category'] == sub]
        if abc and abc != 'Todos':
            df_c = df_c[df_c['abc_xyz'] == abc]
        if prod and prod != 'Todos':
            df_c = df_c.copy()
            df_c['_pn_des'] = df_c['Product Name'].apply(descifrar_texto)
            df_c = df_c[df_c['_pn_des'] == prod].drop(columns='_pn_des')
        if self.chk_solo_forec.isChecked():
            df_c = df_c[df_c['forecasteable']]
        return df_c

    def _actualizar_resumen(self):
        if not SESION.datos_listos:
            return
        df_c = self._aplicar_filtros()
        forec = int(df_c['forecasteable'].sum()) if not df_c.empty else 0
        n = len(df_c)
        if n == 0:
            self.lbl_info.setText('Ningun producto coincide con los filtros.')
        else:
            txt = (f'<b>{n}</b> productos seleccionados.<br>'
                   f'Forecasteables individualmente: <b>{forec}</b>.<br>'
                   f'Resto se pronostica con top-down.')
            self.lbl_info.setText(txt)

    # ------------------------------------------------------------
    def _on_pronosticar(self):
        if not SESION.datos_listos:
            QMessageBox.warning(self, 'Sin datos', 'Carga datos primero.')
            return
        df_c = self._aplicar_filtros()
        if df_c.empty:
            QMessageBox.warning(self, 'Sin productos',
                                'Ningun producto coincide con los filtros.')
            return

        # Determinar horizonte y granularidad
        horiz_sel = next(n for n, rb in self.radios_horiz.items() if rb.isChecked())
        h = MAP_HORIZONTE[horiz_sel]
        if h is None:
            h = self.spin_meses.value()
        granularidad = ('diario' if horiz_sel == 'Proximo dia' else
                        'semanal' if horiz_sel == 'Proxima semana' else 'mensual')

        ic = self.slider_ic.value() / 100.0

        # Filtrar df_full a los productos seleccionados
        df_full_filtrado = SESION.df_full[
            SESION.df_full['unique_id'].isin(df_c['unique_id'])
        ].copy()

        # Guardar filtros para mostrar luego en otras paginas
        SESION.pred_horizon = h
        SESION.pred_ic = ic
        SESION.pred_filtros = {
            'horizonte_label': horiz_sel,
            'granularidad': granularidad,
            'categoria': self.cb_cat.currentText(),
            'subcategoria': self.cb_sub.currentText(),
            'producto': self.cb_prod.currentText(),
            'abc_xyz': self.cb_abc.currentText(),
            'solo_forecasteables': self.chk_solo_forec.isChecked(),
        }

        # Lanzar worker
        self.btn_pronosticar.setEnabled(False)
        self.barra.setVisible(True); self.barra.setValue(0)
        self.lbl_estado.setText('Iniciando pronostico...')
        self.frame_alertas.setVisible(False)

        worker = ForecastWorker(df_full_filtrado, df_c, h, ic)
        self._hilo = lanzar_en_hilo(
            worker,
            on_finalizado=self._forecast_ok,
            on_error=self._forecast_error,
            on_progreso=self._on_progreso,
        )

    def _on_progreso(self, pct: int, msg: str):
        self.barra.setValue(pct)
        self.lbl_estado.setText(msg)

    def _forecast_ok(self, pred):
        self.btn_pronosticar.setEnabled(True)
        self.barra.setVisible(False)
        if pred is None or pred.empty:
            self.lbl_estado.setText('No se generaron predicciones.')
            QMessageBox.warning(self, 'Sin predicciones',
                                'El motor no devolvio ninguna prediccion.')
            return

        # Aplicar desagregacion si hace falta
        granularidad = SESION.pred_filtros.get('granularidad', 'mensual')
        if granularidad != 'mensual':
            pred = self._desagregar(pred, granularidad)

        SESION.pred = pred
        self.lbl_estado.setText(
            f'Pronostico generado: {pred["unique_id"].nunique()} productos, '
            f'{len(pred)} filas.'
        )
        self._mostrar_alertas(pred)
        self.ventana.notificar_pronostico_generado()

        # Pequena ayuda al usuario para que sepa donde mirar
        QMessageBox.information(
            self, 'Pronostico listo',
            'El pronostico se ha generado. Revisa las pestanas de '
            '"Resultados" para ver tabla, graficos y comparativa historica.'
        )

    def _forecast_error(self, msg: str):
        self.btn_pronosticar.setEnabled(True)
        self.barra.setVisible(False)
        self.lbl_estado.setText(f'Error: {msg}')
        QMessageBox.critical(self, 'Error en el pronostico', msg)

    # ------------------------------------------------------------
    def _desagregar(self, pred, granularidad):
        """Desagregacion proporcional mensual -> semanal/diario."""
        import calendar
        import numpy as np
        import pandas as pd

        filas = []
        for _, row in pred.iterrows():
            anio, mes = row['ds'].year, row['ds'].month
            dias_mes = calendar.monthrange(anio, mes)[1]
            yhat_m = row['yhat']
            yhmin_m = row.get('yhat_min', yhat_m)
            yhmax_m = row.get('yhat_max', yhat_m)

            if granularidad == 'semanal':
                n = int(np.ceil(dias_mes / 7))
                semanas = pd.date_range(start=row['ds'], periods=n, freq='W-MON')
                pesos = np.array(
                    [7 if i < n - 1 else dias_mes - 7 * (n - 1) for i in range(n)],
                    dtype=float,
                )
                pesos = pesos / pesos.sum()
                for s, p in zip(semanas, pesos):
                    r = row.copy()
                    r['ds'] = s
                    r['yhat'] = round(yhat_m * p, 2)
                    r['yhat_min'] = round(yhmin_m * p, 2)
                    r['yhat_max'] = round(yhmax_m * p, 2)
                    filas.append(r)
            elif granularidad == 'diario':
                dias = pd.date_range(start=row['ds'], periods=dias_mes, freq='D')
                yd = round(yhat_m / dias_mes, 4)
                ymd = round(yhmin_m / dias_mes, 4)
                yMd = round(yhmax_m / dias_mes, 4)
                for d in dias:
                    r = row.copy()
                    r['ds'] = d
                    r['yhat'] = yd
                    r['yhat_min'] = ymd
                    r['yhat_max'] = yMd
                    filas.append(r)
        return pd.DataFrame(filas)

    # ------------------------------------------------------------
    def _mostrar_alertas(self, pred):
        """Si hay metricas de backtest, evaluar alertas y mostrarlas."""
        # Limpiamos panel anterior
        while self.lay_alertas.count():
            w = self.lay_alertas.takeAt(0).widget()
            if w:
                w.deleteLater()

        # Metricas globales aproximadas a partir del backtest in-sample
        # (lo hacemos con fecha_corte = fecha_max - 3, comparando con datos reales)
        df_full = SESION.df_full
        if df_full is None:
            return
        fecha_max = df_full['ds'].max()
        import pandas as pd
        fecha_corte = fecha_max - pd.DateOffset(months=3)
        dt = df_full[df_full['ds'] > fecha_corte]
        if dt.empty:
            return

        # Comparamos las predicciones del propio pred contra lo real solo donde haya overlap
        merged = (dt[['unique_id', 'ds', 'y']]
                  .merge(pred[['unique_id', 'ds', 'yhat']],
                         on=['unique_id', 'ds'], how='inner'))
        if merged.empty:
            return

        w = wape(merged['y'].values, merged['yhat'].values)
        b = bias_metric(merged['y'].values, merged['yhat'].values)

        alertas = evaluar_alertas(w, b, wape_anterior=None)

        titulo = QLabel('Alertas de calidad')
        titulo.setObjectName('H3')
        self.lay_alertas.addWidget(titulo)

        if not alertas:
            ok = Badge(f'Calidad correcta - WAPE={w:.1f}%, bias={b:+.1f}%', tipo='ok')
            self.lay_alertas.addWidget(ok)
        else:
            for a in alertas:
                tipo = 'err' if a['nivel'] == 'CRITICA' else 'warn'
                self.lay_alertas.addWidget(
                    Badge(f'[{a["nivel"]}] {a["mensaje"]}', tipo=tipo))

        self.frame_alertas.setVisible(True)
