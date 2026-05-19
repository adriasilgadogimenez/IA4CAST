"""Ventana principal con sidebar de navegacion."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget, QMainWindow,
)

from .styles import QSS_CORPORATIVO
from .pagina_carga import PaginaCarga
from .pagina_dashboard import PaginaDashboard
from .pagina_pronostico import PaginaPronostico
from .pagina_resultados import PaginaResultados
from .. import __version__


# Mapa: clave -> (titulo, icono opcional)
PAGINAS = [
    ('carga', '1. Cargar datos'),
    ('dashboard', '2. Dashboard exploratorio'),
    ('pronostico', '3. Generar pronostico'),
    ('resultados', '4. Resultados'),
]


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('IA4CAST - Sistema de pronostico de demanda')
        self.resize(1400, 880)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(QSS_CORPORATIVO)

        # Establecer el icono de la ventana (aparece en la barra de tareas
        # y en la esquina superior izquierda)
        self._configurar_icono()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ----- Sidebar -----
        self.sidebar = self._crear_sidebar()
        outer.addWidget(self.sidebar)

        # ----- Stack de paginas -----
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # Crear paginas
        self.paginas = {}
        self.paginas['carga'] = PaginaCarga(self)
        self.paginas['dashboard'] = PaginaDashboard(self)
        self.paginas['pronostico'] = PaginaPronostico(self)
        self.paginas['resultados'] = PaginaResultados(self)
        for clave, _ in PAGINAS:
            self.stack.addWidget(self.paginas[clave])

        self.ir_a('carga')

    # ------------------------------------------------------------
    def _crear_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName('Sidebar')
        side.setFixedWidth(240)

        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        titulo = QLabel('IA4CAST')
        titulo.setObjectName('SidebarTitulo')
        lay.addWidget(titulo)

        sub = QLabel(f'v{__version__} - Forecasting retail')
        sub.setObjectName('SidebarSubtitulo')
        lay.addWidget(sub)

        self.btn_grupo = QButtonGroup(self)
        self.btn_grupo.setExclusive(True)

        self._botones_nav = {}
        for clave, titulo_p in PAGINAS:
            b = QPushButton(titulo_p)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, c=clave: self.ir_a(c))
            self.btn_grupo.addButton(b)
            self._botones_nav[clave] = b
            lay.addWidget(b)

        lay.addStretch()

        # Footer con info de carpeta de datos
        from ..core.config import CARPETA_USUARIO
        footer = QLabel(f'Datos del usuario:\n{CARPETA_USUARIO}')
        footer.setStyleSheet('color: #B8CDDF; font-size:8pt; padding:12px 20px;')
        footer.setWordWrap(True)
        lay.addWidget(footer)

        return side

    # ------------------------------------------------------------
    def ir_a(self, clave: str):
        if clave not in self.paginas:
            return
        # Marcar boton
        if clave in self._botones_nav:
            self._botones_nav[clave].setChecked(True)
        # Mostrar pagina
        idx = list(self.paginas.keys()).index(clave)
        self.stack.setCurrentIndex(idx)
        # Notificar a la pagina (cada una sabe si tiene datos para refrescar)
        pag = self.paginas[clave]
        if hasattr(pag, 'refrescar'):
            pag.refrescar()

    # ------------------------------------------------------------
    # Notificaciones cross-page
    # ------------------------------------------------------------
    def notificar_datos_cargados(self):
        """Llamado por la pagina de carga al terminar."""
        self.paginas['dashboard'].refrescar()
        self.paginas['pronostico'].refrescar()

    def notificar_pronostico_generado(self):
        """Llamado por la pagina de pronostico al terminar."""
        self.paginas['resultados'].refrescar()
        # Cambia automaticamente a la pestana de resultados
        self.ir_a('resultados')

    def _configurar_icono(self):
        """
        Establece el icono de la ventana. Lo busca en varias ubicaciones
        para que funcione tanto en desarrollo como dentro del .exe empaquetado.
        """
        import sys
        from pathlib import Path

        # Posibles ubicaciones del icono
        candidatos = []
        if getattr(sys, 'frozen', False):
            # En el .exe empaquetado, PyInstaller extrae los datos a _MEIPASS
            base = Path(sys._MEIPASS)
            candidatos.append(base / 'ia4cast' / 'resources' / 'icono.ico')
            candidatos.append(Path(sys.executable).parent / 'icono.ico')
        else:
            # En desarrollo, relativo al fichero
            base = Path(__file__).parent.parent.parent
            candidatos.append(base / 'ia4cast' / 'resources' / 'icono.ico')

        for ruta in candidatos:
            if ruta.exists():
                self.setWindowIcon(QIcon(str(ruta)))
                return
