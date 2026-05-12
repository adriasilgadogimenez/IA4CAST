"""Widgets reutilizables: tarjetas KPI, canvas matplotlib, badges, etc."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
from matplotlib.figure import Figure


class TarjetaKPI(QFrame):
    """Tarjeta con titulo, valor grande y subtexto. Para el dashboard."""

    def __init__(self, titulo: str, valor: str = '-', subvalor: str = '', parent=None):
        super().__init__(parent)
        self.setObjectName('Tarjeta')
        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setObjectName('TarjetaTitulo')
        self.lbl_valor = QLabel(valor)
        self.lbl_valor.setObjectName('TarjetaValor')
        self.lbl_subvalor = QLabel(subvalor)
        self.lbl_subvalor.setObjectName('TarjetaSubvalor')

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(4)
        lay.addWidget(self.lbl_titulo)
        lay.addWidget(self.lbl_valor)
        lay.addWidget(self.lbl_subvalor)

    def actualizar(self, valor: str, subvalor: str = ''):
        self.lbl_valor.setText(valor)
        self.lbl_subvalor.setText(subvalor)


class MplCanvas(FigureCanvas):
    """Canvas matplotlib con barra de navegacion opcional."""

    def __init__(self, parent=None, width=8, height=4, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi,
                             facecolor='white', tight_layout=True)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setParent(parent)

    def limpiar(self):
        self.figure.clf()
        self.axes = self.figure.add_subplot(111)


class Badge(QLabel):
    """Etiqueta con estilo de badge (ok/warn/err)."""

    def __init__(self, texto: str = '', tipo: str = 'ok', parent=None):
        super().__init__(texto, parent)
        self.setProperty('class', f'badge-{tipo}')
        self.setAlignment(Qt.AlignCenter)
