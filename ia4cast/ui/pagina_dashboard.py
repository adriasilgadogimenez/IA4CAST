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
        c.axes.set_xlabel('Mes'); c.axes.set_ylabel('Ano')
        c.figure.colorbar(im, ax=c.axes, fraction=0.046, pad=0.04)
        c.draw()
        return c

    # ------------------------------------------------------------
    def _exportar_png(self):
        if not SESION.datos_listos:
            QMessageBox.warning(self, 'Sin datos', 'Carga datos primero.')
            return
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

            # Componer una figura GRANDE con TODOS los graficos del dashboard
            # Layout: 4 filas x 2 columnas para que entre todo
            fig = Figure(figsize=(20, 22), facecolor='white')

            # 1. Top 10 productos
            ax1 = fig.add_subplot(4, 2, 1)
            top = df_class_vis.head(10).copy()
            top['nombre_corto'] = top['Product Name'].apply(
                lambda s: s[:30] + '...' if len(s) > 30 else s)
            ax1.barh(top['nombre_corto'][::-1], top['total'][::-1], color='#2E86C1')
            ax1.set_title('Top 10 productos por volumen',
                          fontsize=12, fontweight='bold', color='#1F4E79')
            ax1.set_xlabel('Unidades vendidas')
            ax1.tick_params(axis='y', labelsize=9)
            ax1.grid(axis='x', alpha=0.3)

            # 2. Ventas por categoria
            ax2 = fig.add_subplot(4, 2, 2)
            v = df_full.groupby('Category')['y'].sum().sort_values()
            ax2.barh(v.index, v.values, color='#1F4E79')
            ax2.set_title('Ventas por categoria',
                          fontsize=12, fontweight='bold', color='#1F4E79')
            ax2.set_xlabel('Unidades vendidas')
            ax2.grid(axis='x', alpha=0.3)

            # 3. Evolucion temporal
            ax3 = fig.add_subplot(4, 2, 3)
            evol = df_full.groupby('ds')['y'].sum()
            ax3.plot(evol.index, evol.values, color='#2E86C1', lw=2,
                     marker='o', ms=4)
            ax3.fill_between(evol.index, evol.values, alpha=0.2, color='#2E86C1')
            ax3.set_title('Evolucion temporal global',
                          fontsize=12, fontweight='bold', color='#1F4E79')
            ax3.set_ylabel('Unidades / mes')
            ax3.grid(alpha=0.3)
            for label in ax3.get_xticklabels():
                label.set_rotation(30)
                label.set_ha('right')

            # 4. ABC-XYZ
            ax4 = fig.add_subplot(4, 2, 4)
            cross = pd.crosstab(df_class['abc'], df_class['xyz'])
            cross = cross.reindex(index=['A', 'B', 'C'],
                                  columns=['X', 'Y', 'Z'], fill_value=0)
            im = ax4.imshow(cross.values, cmap='Blues', aspect='auto')
            ax4.set_xticks(range(3)); ax4.set_xticklabels(['X', 'Y', 'Z'])
            ax4.set_yticks(range(3)); ax4.set_yticklabels(['A', 'B', 'C'])
            for i in range(3):
                for j in range(3):
                    ax4.text(j, i, str(cross.values[i, j]),
                             ha='center', va='center', fontweight='bold',
                             color='white' if cross.values[i, j] > cross.values.max() / 2
                                          else 'black')
            ax4.set_title('Distribucion ABC-XYZ',
                          fontsize=12, fontweight='bold', color='#1F4E79')
            ax4.set_xlabel('XYZ (variabilidad)')
            ax4.set_ylabel('ABC (volumen)')
            fig.colorbar(im, ax=ax4, fraction=0.046, pad=0.04)

            # 5. SBC
            ax5 = fig.add_subplot(4, 2, 5)
            sbc = df_class['sbc_class'].value_counts()
            orden = ['Smooth', 'Erratic', 'Intermittent', 'Lumpy']
            sbc = sbc.reindex(orden).fillna(0)
            colores = ['#27AE60', '#F39C12', '#3498DB', '#C0392B']
            ax5.bar(sbc.index, sbc.values, color=colores)
            ax5.set_title('Distribucion patrones SBC',
                          fontsize=12, fontweight='bold', color='#1F4E79')
            ax5.set_ylabel('Numero de productos')
            ax5.grid(axis='y', alpha=0.3)
            if max(sbc.values) > 0:
                for i, val in enumerate(sbc.values):
                    ax5.text(i, val + max(sbc.values) * 0.01, str(int(val)),
                             ha='center', fontweight='bold')

            # 6. Heatmap estacional
            ax6 = fig.add_subplot(4, 2, 6)
            df = df_full.copy()
            df['anio'] = df['ds'].dt.year
            df['mes'] = df['ds'].dt.month
            pivot = df.pivot_table(index='anio', columns='mes', values='y',
                                   aggfunc='sum', fill_value=0)
            if not pivot.empty:
                im2 = ax6.imshow(pivot.values, cmap='YlOrRd', aspect='auto')
                ax6.set_yticks(range(len(pivot.index)))
                ax6.set_yticklabels(pivot.index)
                ax6.set_xticks(range(12))
                ax6.set_xticklabels(['E', 'F', 'M', 'A', 'M', 'J',
                                     'J', 'A', 'S', 'O', 'N', 'D'])
                ax6.set_xlabel('Mes')
                ax6.set_ylabel('Anio')
                fig.colorbar(im2, ax=ax6, fraction=0.046, pad=0.04)
            ax6.set_title('Patron estacional (heatmap)',
                          fontsize=12, fontweight='bold', color='#1F4E79')

            # 7-8. Anomalias (panel inferior, ocupando 2 columnas)
            anomalias = detectar_anomalias(df_full, umbral_z=3.0)
            ax7 = fig.add_subplot(4, 1, 4)
            if anomalias.empty:
                ax7.text(0.5, 0.5,
                         'No se han detectado anomalias significativas.',
                         ha='center', va='center', fontsize=11,
                         transform=ax7.transAxes)
                ax7.set_axis_off()
            else:
                anomalias = descifrar_columnas(anomalias, ['Product Name'])
                top10 = anomalias.assign(z_abs=anomalias['z_score'].abs()) \
                                  .sort_values('z_abs', ascending=False).head(10)
                etiquetas = [f"{r['Product Name'][:30]} ({r['ds'].strftime('%Y-%m')})"
                             for _, r in top10.iterrows()]
                colores_a = ['#C0392B' if z > 0 else '#2E86C1'
                             for z in top10['z_score'].values]
                ax7.barh(etiquetas[::-1], top10['z_score'].values[::-1],
                         color=colores_a[::-1])
                ax7.axvline(0, color='black', lw=0.5)
                ax7.set_xlabel('Z-score (rojo=pico, azul=caida)')
                ax7.set_title(f'Top 10 anomalias (de {len(anomalias)} detectadas)',
                              fontsize=12, fontweight='bold', color='#1F4E79')
                ax7.tick_params(axis='y', labelsize=9)
                ax7.grid(axis='x', alpha=0.3)

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

            QMessageBox.information(self, 'Exportado',
                                    f'Dashboard exportado en:\n{ruta}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            LOG.exception('Error al exportar dashboard')
