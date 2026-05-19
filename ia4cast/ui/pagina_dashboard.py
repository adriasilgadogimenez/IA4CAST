"""Pagina 2 - Dashboard exploratorio post-carga."""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from ..core.config import CONFIG, LOG
from ..core.security import descifrar_columnas, descifrar_texto
from ..core.classification import detectar_anomalias
from .sesion import SESION
from .widgets import MplCanvas


class PaginaDashboard(QWidget):
    """Vista de exploracion: KPIs + 6 graficos."""

    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana = ventana_principal

        contenedor = QWidget()
        self._lay = QVBoxLayout(contenedor)
        self._lay.setContentsMargins(30, 30, 30, 30)
        self._lay.setSpacing(20)

        # Cabecera con boton de exportacion
        h = QHBoxLayout()
        titulo = QLabel('Dashboard exploratorio')
        titulo.setObjectName('H1')
        h.addWidget(titulo)
        h.addStretch()
        self.btn_exportar = QPushButton('Exportar dashboard (PNG)')
        self.btn_exportar.setProperty('class', 'secondary')
        self.btn_exportar.clicked.connect(self._exportar_png)
        h.addWidget(self.btn_exportar)
        self._lay.addLayout(h)

        # Mensaje cuando no hay datos
        self.lbl_vacio = QLabel(
            'Aun no hay datos cargados. Ve a la pestana "Cargar datos" para empezar.')
        self.lbl_vacio.setProperty('class', 'muted')
        self.lbl_vacio.setAlignment(Qt.AlignCenter)
        self._lay.addWidget(self.lbl_vacio)

        # Grid de graficos (se rellena al refrescar)
        self.grid_graficos = QGridLayout()
        self.grid_graficos.setSpacing(16)
        self._wrap_graf = QWidget()
        self._wrap_graf.setLayout(self.grid_graficos)
        self._wrap_graf.setVisible(False)
        self._lay.addWidget(self._wrap_graf)

        self._lay.addStretch()

        # Wrap en scroll area
        scroll = QScrollArea()
        scroll.setWidget(contenedor)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._canvases = []  # para reusar referencias y liberar al refrescar

    # ------------------------------------------------------------
    def refrescar(self):
        """Reconstruye graficos cuando hay datos cargados."""
        if not SESION.datos_listos:
            self.lbl_vacio.setVisible(True)
            self._wrap_graf.setVisible(False)
            return

        self.lbl_vacio.setVisible(False)
        self._wrap_graf.setVisible(True)

        # Limpiar grid anterior
        while self.grid_graficos.count():
            item = self.grid_graficos.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._canvases.clear()

        df_full = SESION.df_full
        df_class = SESION.df_class

        # Descifrar nombres solo para visualizacion
        df_class_vis = descifrar_columnas(df_class.copy(),
                                          CONFIG['seguretat']['xifrar_camps'])

        c1 = self._grafico_top_productos(df_class_vis)
        c2 = self._grafico_ventas_categoria(df_full, df_class_vis)
        c3 = self._grafico_evolucion_temporal(df_full)
        c4 = self._grafico_distribucion_abc_xyz(df_class)
        c5 = self._grafico_distribucion_sbc(df_class)
        c6 = self._grafico_heatmap_estacional(df_full)

        # 3x2 grid
        self.grid_graficos.addWidget(self._envolver(c1, 'Top 10 productos por volumen'), 0, 0)
        self.grid_graficos.addWidget(self._envolver(c2, 'Ventas por categoria'), 0, 1)
        self.grid_graficos.addWidget(self._envolver(c3, 'Evolucion temporal global'), 1, 0)
        self.grid_graficos.addWidget(self._envolver(c4, 'Distribucion ABC-XYZ'), 1, 1)
        self.grid_graficos.addWidget(self._envolver(c5, 'Distribucion patrones SBC'), 2, 0)
        self.grid_graficos.addWidget(self._envolver(c6, 'Patron estacional (heatmap)'), 2, 1)

        # Anomalias detectadas
        anomalias = detectar_anomalias(df_full, umbral_z=3.0)
        if not anomalias.empty:
            anomalias = descifrar_columnas(anomalias, ['Product Name'])
            tarjeta = QWidget()
            tarjeta.setObjectName('Tarjeta')
            tlay = QVBoxLayout(tarjeta)
            t = QLabel(f'Anomalias detectadas en el historico: {len(anomalias)} eventos '
                       f'(en {anomalias["unique_id"].nunique()} productos)')
            t.setObjectName('H3')
            tlay.addWidget(t)
            top5 = anomalias.assign(z_abs=anomalias['z_score'].abs()) \
                            .sort_values('z_abs', ascending=False).head(5)
            for _, r in top5.iterrows():
                txt = (f'  - {r["Product Name"][:50]} en {r["ds"].strftime("%Y-%m")}: '
                       f'{r["tipo"]} (z={r["z_score"]:+.2f}, y={r["y"]:.0f})')
                tlay.addWidget(QLabel(txt))
            self.grid_graficos.addWidget(tarjeta, 3, 0, 1, 2)

    # ------------------------------------------------------------
    def _envolver(self, canvas: MplCanvas, titulo: str) -> QWidget:
        cont = QWidget()
        cont.setObjectName('Tarjeta')
        lay = QVBoxLayout(cont)
        lab = QLabel(titulo)
        lab.setObjectName('H3')
        lay.addWidget(lab)
        canvas.setMinimumHeight(260)
        lay.addWidget(canvas)
        self._canvases.append(canvas)
        return cont

    # ------------------------------------------------------------
    def _grafico_top_productos(self, df_class_vis):
        c = MplCanvas(width=6, height=3)
        top = df_class_vis.head(10).copy()
        top['nombre_corto'] = top['Product Name'].apply(
            lambda s: s[:30] + '...' if len(s) > 30 else s)
        c.axes.barh(top['nombre_corto'][::-1], top['total'][::-1], color='#2E86C1')
        c.axes.set_xlabel('Unidades vendidas')
        c.axes.tick_params(axis='y', labelsize=8)
        c.axes.grid(axis='x', alpha=0.3)
        c.draw()
        return c

    def _grafico_ventas_categoria(self, df_full, df_class_vis):
        c = MplCanvas(width=6, height=3)
        ventas_cat = df_full.groupby('Category')['y'].sum().sort_values(ascending=True)
        c.axes.barh(ventas_cat.index, ventas_cat.values, color='#1F4E79')
        c.axes.set_xlabel('Unidades vendidas')
        c.axes.grid(axis='x', alpha=0.3)
        c.draw()
        return c

    def _grafico_evolucion_temporal(self, df_full):
        c = MplCanvas(width=6, height=3)
        evol = df_full.groupby('ds')['y'].sum()
        c.axes.plot(evol.index, evol.values, color='#2E86C1', lw=2, marker='o', ms=4)
        c.axes.fill_between(evol.index, evol.values, alpha=0.2, color='#2E86C1')
        c.axes.set_ylabel('Unidades / mes')
        c.axes.grid(alpha=0.3)
        for label in c.axes.get_xticklabels():
            label.set_rotation(30)
            label.set_ha('right')
        c.draw()
        return c

    def _grafico_distribucion_abc_xyz(self, df_class):
        c = MplCanvas(width=6, height=3)
        cross = pd.crosstab(df_class['abc'], df_class['xyz'])
        cross = cross.reindex(index=['A', 'B', 'C'], columns=['X', 'Y', 'Z'], fill_value=0)
        im = c.axes.imshow(cross.values, cmap='Blues', aspect='auto')
        c.axes.set_xticks(range(3)); c.axes.set_xticklabels(['X', 'Y', 'Z'])
        c.axes.set_yticks(range(3)); c.axes.set_yticklabels(['A', 'B', 'C'])
        for i in range(3):
            for j in range(3):
                c.axes.text(j, i, str(cross.values[i, j]),
                            ha='center', va='center',
                            color='white' if cross.values[i, j] > cross.values.max() / 2 else 'black',
                            fontweight='bold')
        c.axes.set_xlabel('XYZ (variabilidad)')
        c.axes.set_ylabel('ABC (volumen)')
        c.figure.colorbar(im, ax=c.axes, fraction=0.046, pad=0.04)
        c.draw()
        return c

    def _grafico_distribucion_sbc(self, df_class):
        c = MplCanvas(width=6, height=3)
        sbc = df_class['sbc_class'].value_counts()
        # Asegurar orden consistente
        orden = ['Smooth', 'Erratic', 'Intermittent', 'Lumpy']
        sbc = sbc.reindex(orden).fillna(0)
        colores = ['#27AE60', '#F39C12', '#3498DB', '#C0392B']
        c.axes.bar(sbc.index, sbc.values, color=colores)
        c.axes.set_ylabel('Numero de productos')
        c.axes.grid(axis='y', alpha=0.3)
        for i, v in enumerate(sbc.values):
            c.axes.text(i, v + max(sbc.values) * 0.01, str(int(v)),
                        ha='center', fontweight='bold')
        c.draw()
        return c

    def _grafico_heatmap_estacional(self, df_full):
        c = MplCanvas(width=6, height=3)
        df = df_full.copy()
        df['anio'] = df['ds'].dt.year
        df['mes'] = df['ds'].dt.month
        pivot = df.pivot_table(index='anio', columns='mes', values='y',
                               aggfunc='sum', fill_value=0)
        if pivot.empty:
            c.axes.text(0.5, 0.5, 'Sin datos', ha='center', va='center')
            c.draw(); return c
        im = c.axes.imshow(pivot.values, cmap='YlOrRd', aspect='auto')
        c.axes.set_yticks(range(len(pivot.index)))
        c.axes.set_yticklabels(pivot.index)
        c.axes.set_xticks(range(12))
        c.axes.set_xticklabels(['E', 'F', 'M', 'A', 'M', 'J',
                                'J', 'A', 'S', 'O', 'N', 'D'])
        c.axes.set_xlabel('Mes'); c.axes.set_ylabel('Año')
        c.figure.colorbar(im, ax=c.axes, fraction=0.046, pad=0.04)
        c.draw()
        return c

    # ------------------------------------------------------------
    def _exportar_png(self):
        if not SESION.datos_listos:
            QMessageBox.warning(self, 'Sin datos', 'Carga datos primero.')
            return

        # Paso 1: dialogo para que el usuario seleccione que graficos exportar
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QCheckBox, QVBoxLayout, QLabel
        )
        dialogo = QDialog(self)
        dialogo.setWindowTitle('Seleccionar graficos a exportar')
        dialogo.setMinimumWidth(420)
        dl = QVBoxLayout(dialogo)

        titulo = QLabel('Selecciona los graficos que quieres incluir:')
        titulo.setStyleSheet('font-weight: bold; color: #1F4E79; font-size: 11pt;')
        dl.addWidget(titulo)

        # Definicion de los graficos disponibles
        opciones = [
            ('top10', 'Top 10 productos por volumen'),
            ('ventas_cat', 'Ventas por categoria'),
            ('evolucion', 'Evolucion temporal global'),
            ('abc_xyz', 'Distribucion ABC-XYZ'),
            ('sbc', 'Distribucion patrones SBC'),
            ('heatmap', 'Patron estacional (heatmap)'),
            ('anomalias', 'Top 10 anomalias detectadas'),
        ]
        checkboxes = {}
        for clave, etiqueta in opciones:
            chk = QCheckBox(etiqueta)
            chk.setChecked(True)  # por defecto todos marcados
            chk.setStyleSheet('padding: 4px;')
            checkboxes[clave] = chk
            dl.addWidget(chk)

        # Botones de seleccion rapida
        from PySide6.QtWidgets import QHBoxLayout
        fila_rapidos = QHBoxLayout()
        btn_todos = QPushButton('Todos')
        btn_todos.clicked.connect(lambda: [c.setChecked(True) for c in checkboxes.values()])
        btn_ninguno = QPushButton('Ninguno')
        btn_ninguno.clicked.connect(lambda: [c.setChecked(False) for c in checkboxes.values()])
        fila_rapidos.addWidget(btn_todos)
        fila_rapidos.addWidget(btn_ninguno)
        fila_rapidos.addStretch()
        dl.addLayout(fila_rapidos)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        dl.addWidget(botones)

        if dialogo.exec() != QDialog.Accepted:
            return  # usuario cancelo

        seleccionados = [c for c, chk in checkboxes.items() if chk.isChecked()]
        if not seleccionados:
            QMessageBox.warning(self, 'Sin seleccion',
                                'No has seleccionado ningun grafico.')
            return

        # Paso 2: pedir ruta de guardado
        ruta, _ = QFileDialog.getSaveFileName(
            self, 'Exportar dashboard', 'dashboard_ia4cast.png', 'PNG (*.png)'
        )
        if not ruta:
            return

        try:
            from ..core.classification import detectar_anomalias

            df_class_vis = descifrar_columnas(SESION.df_class.copy(),
                                              CONFIG['seguretat']['xifrar_camps'])
            df_full = SESION.df_full
            df_class = SESION.df_class

            # Calcular layout segun numero de graficos seleccionados
            n = len(seleccionados)
            # Si las anomalias estan seleccionadas, ocupan toda una fila aparte
            tiene_anomalias = 'anomalias' in seleccionados
            n_graficos_normales = n - (1 if tiene_anomalias else 0)

            if n_graficos_normales == 0:
                n_filas = 1
            else:
                n_filas = (n_graficos_normales + 1) // 2  # 2 por fila
            if tiene_anomalias:
                n_filas += 1
            n_filas = max(n_filas, 1)

            # Altura proporcional al numero de filas
            fig = Figure(figsize=(20, max(6, n_filas * 5)), facecolor='white')

            # Construir cada grafico solo si esta seleccionado
            pos = 0  # posicion en la cuadricula

            def siguiente_subplot():
                nonlocal pos
                pos += 1
                return fig.add_subplot(n_filas, 2, pos)

            if 'top10' in seleccionados:
                ax = siguiente_subplot()
                top = df_class_vis.head(10).copy()
                top['nombre_corto'] = top['Product Name'].apply(
                    lambda s: s[:30] + '...' if len(s) > 30 else s)
                ax.barh(top['nombre_corto'][::-1], top['total'][::-1], color='#2E86C1')
                ax.set_title('Top 10 productos por volumen',
                             fontsize=12, fontweight='bold', color='#1F4E79')
                ax.set_xlabel('Unidades vendidas')
                ax.tick_params(axis='y', labelsize=9)
                ax.grid(axis='x', alpha=0.3)

            if 'ventas_cat' in seleccionados:
                ax = siguiente_subplot()
                v = df_full.groupby('Category')['y'].sum().sort_values()
                ax.barh(v.index, v.values, color='#1F4E79')
                ax.set_title('Ventas por categoria',
                             fontsize=12, fontweight='bold', color='#1F4E79')
                ax.set_xlabel('Unidades vendidas')
                ax.grid(axis='x', alpha=0.3)

            if 'evolucion' in seleccionados:
                ax = siguiente_subplot()
                evol = df_full.groupby('ds')['y'].sum()
                ax.plot(evol.index, evol.values, color='#2E86C1', lw=2,
                        marker='o', ms=4)
                ax.fill_between(evol.index, evol.values, alpha=0.2, color='#2E86C1')
                ax.set_title('Evolucion temporal global',
                             fontsize=12, fontweight='bold', color='#1F4E79')
                ax.set_ylabel('Unidades / mes')
                ax.grid(alpha=0.3)
                for label in ax.get_xticklabels():
                    label.set_rotation(30)
                    label.set_ha('right')

            if 'abc_xyz' in seleccionados:
                ax = siguiente_subplot()
                cross = pd.crosstab(df_class['abc'], df_class['xyz'])
                cross = cross.reindex(index=['A', 'B', 'C'],
                                      columns=['X', 'Y', 'Z'], fill_value=0)
                im = ax.imshow(cross.values, cmap='Blues', aspect='auto')
                ax.set_xticks(range(3)); ax.set_xticklabels(['X', 'Y', 'Z'])
                ax.set_yticks(range(3)); ax.set_yticklabels(['A', 'B', 'C'])
                for i in range(3):
                    for j in range(3):
                        ax.text(j, i, str(cross.values[i, j]),
                                ha='center', va='center', fontweight='bold',
                                color='white' if cross.values[i, j] > cross.values.max() / 2
                                             else 'black')
                ax.set_title('Distribucion ABC-XYZ',
                             fontsize=12, fontweight='bold', color='#1F4E79')
                ax.set_xlabel('XYZ (variabilidad)')
                ax.set_ylabel('ABC (volumen)')
                fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

            if 'sbc' in seleccionados:
                ax = siguiente_subplot()
                sbc = df_class['sbc_class'].value_counts()
                orden = ['Smooth', 'Erratic', 'Intermittent', 'Lumpy']
                sbc = sbc.reindex(orden).fillna(0)
                colores = ['#27AE60', '#F39C12', '#3498DB', '#C0392B']
                ax.bar(sbc.index, sbc.values, color=colores)
                ax.set_title('Distribucion patrones SBC',
                             fontsize=12, fontweight='bold', color='#1F4E79')
                ax.set_ylabel('Numero de productos')
                ax.grid(axis='y', alpha=0.3)
                if max(sbc.values) > 0:
                    for i, val in enumerate(sbc.values):
                        ax.text(i, val + max(sbc.values) * 0.01, str(int(val)),
                                ha='center', fontweight='bold')

            if 'heatmap' in seleccionados:
                ax = siguiente_subplot()
                df = df_full.copy()
                df['anio'] = df['ds'].dt.year
                df['mes'] = df['ds'].dt.month
                pivot = df.pivot_table(index='anio', columns='mes', values='y',
                                       aggfunc='sum', fill_value=0)
                if not pivot.empty:
                    im2 = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto')
                    ax.set_yticks(range(len(pivot.index)))
                    ax.set_yticklabels(pivot.index)
                    ax.set_xticks(range(12))
                    ax.set_xticklabels(['E', 'F', 'M', 'A', 'M', 'J',
                                         'J', 'A', 'S', 'O', 'N', 'D'])
                    ax.set_xlabel('Mes')
                    ax.set_ylabel('Anio')
                    fig.colorbar(im2, ax=ax, fraction=0.046, pad=0.04)
                ax.set_title('Patron estacional (heatmap)',
                             fontsize=12, fontweight='bold', color='#1F4E79')

            # Si el numero de graficos normales es impar, llenamos el hueco
            # para que el grafico de anomalias quede en su propia fila
            if tiene_anomalias and n_graficos_normales % 2 == 1:
                pos += 1  # saltar el hueco

            if tiene_anomalias:
                anomalias = detectar_anomalias(df_full, umbral_z=3.0)
                # Anomalias siempre ocupa una fila entera (2 columnas)
                ax = fig.add_subplot(n_filas, 1, n_filas)
                if anomalias.empty:
                    ax.text(0.5, 0.5,
                            'No se han detectado anomalias significativas.',
                            ha='center', va='center', fontsize=11,
                            transform=ax.transAxes)
                    ax.set_axis_off()
                else:
                    anomalias = descifrar_columnas(anomalias, ['Product Name'])
                    top10 = anomalias.assign(z_abs=anomalias['z_score'].abs()) \
                                      .sort_values('z_abs', ascending=False).head(10)
                    etiquetas = [f"{r['Product Name'][:30]} ({r['ds'].strftime('%Y-%m')})"
                                 for _, r in top10.iterrows()]
                    colores_a = ['#C0392B' if z > 0 else '#2E86C1'
                                 for z in top10['z_score'].values]
                    ax.barh(etiquetas[::-1], top10['z_score'].values[::-1],
                            color=colores_a[::-1])
                    ax.axvline(0, color='black', lw=0.5)
                    ax.set_xlabel('Z-score (rojo=pico, azul=caida)')
                    ax.set_title(f'Top 10 anomalias (de {len(anomalias)} detectadas)',
                                 fontsize=12, fontweight='bold', color='#1F4E79')
                    ax.tick_params(axis='y', labelsize=9)
                    ax.grid(axis='x', alpha=0.3)

            # Titulo general
            n_prod = SESION.df_class['unique_id'].nunique()
            n_meses = SESION.df_full['ds'].nunique()
            rango = (f'{SESION.fecha_min.strftime("%b %Y")} - '
                     f'{SESION.fecha_max.strftime("%b %Y")}')
            fig.suptitle(
                f'IA4CAST - Dashboard exploratorio  |  {n_prod} productos '
                f'|  {n_meses} meses ({rango})',
                fontsize=15, fontweight='bold', color='#1F4E79', y=0.995
            )
            fig.tight_layout(rect=[0, 0, 1, 0.985])
            fig.savefig(ruta, dpi=120, bbox_inches='tight', facecolor='white')

            QMessageBox.information(
                self, 'Exportado',
                f'Dashboard exportado en:\n{ruta}\n\n'
                f'{len(seleccionados)} graficos incluidos.'
            )
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            LOG.exception('Error al exportar dashboard')
