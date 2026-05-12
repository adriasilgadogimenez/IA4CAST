"""Pagina 1 - Carga de datos (Excel/CSV/ODS o PostgreSQL)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)
import os
from ..core.config import LOG, CONFIG
from .sesion import SESION
from .widgets import TarjetaKPI
from .workers import CargaWorker, lanzar_en_hilo


class PaginaCarga(QWidget):
    """Pantalla inicial: dos opciones grandes (fichero o PostgreSQL)."""

    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana = ventana_principal
        self._worker = None  # referencia para que el QThread no muera

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        h1 = QLabel('Carga de datos')
        h1.setObjectName('H1')
        layout.addWidget(h1)
        sub = QLabel('Selecciona una fuente de datos para empezar a trabajar. '
                     'Los campos sensibles se cifraran automaticamente con Fernet.')
        sub.setProperty('class', 'muted')
        sub.setWordWrap(True)
        layout.addWidget(sub)

        fila = QHBoxLayout()
        fila.setSpacing(20)
        fila.addWidget(self._tarjeta_fichero())
        fila.addWidget(self._tarjeta_postgresql())
        layout.addLayout(fila)

        self.lbl_estado = QLabel('Esperando carga...')
        self.lbl_estado.setProperty('class', 'muted')
        layout.addWidget(self.lbl_estado)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setVisible(False)
        layout.addWidget(self.barra)

        self.frame_kpis = QFrame()
        self.frame_kpis.setVisible(False)
        kpi_lay = QGridLayout(self.frame_kpis)
        kpi_lay.setSpacing(16)
        self.kpi_productos = TarjetaKPI('Productos cargados')
        self.kpi_meses = TarjetaKPI('Meses de historico')
        self.kpi_unidades = TarjetaKPI('Unidades totales')
        self.kpi_rango = TarjetaKPI('Rango temporal')
        kpi_lay.addWidget(self.kpi_productos, 0, 0)
        kpi_lay.addWidget(self.kpi_meses, 0, 1)
        kpi_lay.addWidget(self.kpi_unidades, 0, 2)
        kpi_lay.addWidget(self.kpi_rango, 0, 3)
        layout.addWidget(self.frame_kpis)

        self.frame_acciones = QFrame()
        self.frame_acciones.setVisible(False)
        acc_lay = QHBoxLayout(self.frame_acciones)
        acc_lay.addStretch()
        self.btn_exportar_class = QPushButton('Exportar clasificacion ABC-XYZ')
        self.btn_exportar_class.setProperty('class', 'secondary')
        self.btn_exportar_class.clicked.connect(self._exportar_clasificacion)
        acc_lay.addWidget(self.btn_exportar_class)
        self.btn_ir_dashboard = QPushButton('Ir al dashboard ->')
        self.btn_ir_dashboard.setProperty('class', 'accion')
        self.btn_ir_dashboard.clicked.connect(lambda: self.ventana.ir_a('dashboard'))
        acc_lay.addWidget(self.btn_ir_dashboard)
        layout.addWidget(self.frame_acciones)

        layout.addStretch()
        
        self.ruta_archivo = None
        self.usar_sql = False

    def _tarjeta_fichero(self) -> QFrame:
        f = QFrame()
        f.setObjectName('Tarjeta')
        f.setMinimumHeight(220)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(12)

        ico = QLabel('Fichero local')
        ico.setStyleSheet('font-size:10pt; font-weight:600; color:#2E86C1; '
                          'letter-spacing:1px; text-transform:uppercase;')
        lay.addWidget(ico)

        titulo = QLabel('Excel, CSV u ODS')
        titulo.setObjectName('H2')
        lay.addWidget(titulo)

        desc = QLabel('Carga datos desde un fichero local. '
                      'Formatos admitidos: .xlsx, .xls, .csv, .ods')
        desc.setProperty('class', 'muted')
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addStretch()
        btn = QPushButton('Seleccionar fichero...')
        btn.setMinimumHeight(40)
        btn.clicked.connect(self._elegir_fichero)
        lay.addWidget(btn)
        return f

    def _tarjeta_postgresql(self) -> QFrame:
        f = QFrame()
        f.setObjectName('Tarjeta')
        f.setMinimumHeight(220)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(12)

        ico = QLabel('Base de datos')
        ico.setStyleSheet('font-size:10pt; font-weight:600; color:#2E86C1; '
                          'letter-spacing:1px; text-transform:uppercase;')
        lay.addWidget(ico)

        titulo = QLabel('SQL Server corporativo')
        titulo.setObjectName('H2')
        lay.addWidget(titulo)
        print("CONFIG FILE REAL EN USO:", CONFIG)
        print("BASE DATOS:", CONFIG.get("base_dades"))
        print("HABILITAT:", CONFIG.get("base_dades", {}).get("habilitat"))
        print("APPDATA PATH:", os.getenv("APPDATA"))
        habilitada = CONFIG['base_dades'].get('habilitat', False)
        host = CONFIG['base_dades'].get('amfitrio', '?')
        if habilitada:
            desc = QLabel(f'Conectar a {host} para cargar datos masivos.')
        else:
            desc = QLabel('La conexion esta habilitada en config.yaml. '
                          'Desactiva "base_dades.habilitat: false" y configura '
                          'las credenciales para usarla.')
        desc.setProperty('class', 'muted')
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addStretch()
        btn = QPushButton('Cargar desde SQL Server')
        btn.setMinimumHeight(40)
        btn.setProperty('class', 'secondary')
        btn.setEnabled(habilitada)
        btn.clicked.connect(self._cargar_postgresql)
        lay.addWidget(btn)
        return f

    def _elegir_fichero(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, 'Seleccionar fichero de ventas', '',
            'Datos (*.xlsx *.xls *.csv *.ods)')
        if ruta:
            self.ruta_archivo = ruta
            self.lbl_estado.setText(
                f'Fichero añadido: {os.path.basename(ruta)}'
            )

            self._cargar_fuentes()

    def _cargar_postgresql(self):
        #self._iniciar_carga(desde_postgresql=True)
        self.usar_sql = True

        self.lbl_estado.setText(
            'SQL Server añadido como fuente'
        )

        self._cargar_fuentes()
        
    def _cargar_fuentes(self):

        if not self.ruta_archivo and not self.usar_sql:
            return

        self._iniciar_carga(
            ruta_archivo=self.ruta_archivo,
            desde_postgresql=self.usar_sql
        )
    def _iniciar_carga(self, ruta_archivo=None, desde_postgresql=False):
        self.barra.setValue(0)
        self.barra.setVisible(True)
        self.lbl_estado.setText('Iniciando carga...')
        self.frame_kpis.setVisible(False)
        self.frame_acciones.setVisible(False)
        LOG.info('Lanzando CargaWorker (ruta=%s, postgres=%s)',
                 ruta_archivo, desde_postgresql)
        worker = CargaWorker(ruta_archivo=ruta_archivo,
                             desde_postgresql=desde_postgresql)
        self._worker = lanzar_en_hilo(
            worker,
            on_finalizado=self._carga_ok,
            on_error=self._carga_error,
            on_progreso=self._actualizar_progreso,
        )

    def _actualizar_progreso(self, pct: int, mensaje: str):
        self.barra.setValue(pct)
        self.lbl_estado.setText(mensaje)

    def _carga_ok(self, df_full, df_class, fmin, fmax):
        SESION.df_full = df_full
        SESION.df_class = df_class
        SESION.fecha_min = fmin
        SESION.fecha_max = fmax
        self.lbl_estado.setText(
            f'Datos cargados correctamente. {df_class["unique_id"].nunique()} '
            f'productos, {df_full["ds"].nunique()} meses.'
        )
        self.barra.setVisible(False)
        self._actualizar_kpis()
        self.frame_kpis.setVisible(True)
        self.frame_acciones.setVisible(True)
        self.ventana.notificar_datos_cargados()

    def _carga_error(self, mensaje: str):
        self.barra.setVisible(False)
        self.lbl_estado.setText(f'Error: {mensaje[:200]}')
        QMessageBox.critical(self, 'Error al cargar datos', mensaje)

    def _actualizar_kpis(self):
        n_prod = SESION.df_class['unique_id'].nunique()
        n_meses = SESION.df_full['ds'].nunique()
        unidades = int(SESION.df_full['y'].sum())
        rango = (f'{SESION.fecha_min.strftime("%b %Y")} - '
                 f'{SESION.fecha_max.strftime("%b %Y")}')
        self.kpi_productos.actualizar(f'{n_prod:,}'.replace(',', '.'))
        self.kpi_meses.actualizar(str(n_meses))
        self.kpi_unidades.actualizar(f'{unidades:,}'.replace(',', '.'))
        self.kpi_rango.actualizar(rango)

    def _exportar_clasificacion(self):
        if SESION.df_class is None:
            QMessageBox.warning(self, 'Sin datos', 'Primero carga un fichero.')
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, 'Exportar clasificacion', 'clasificacion_abc_xyz.csv',
            'CSV (*.csv);;Excel (*.xlsx)'
        )
        if not ruta:
            return

        from ..core.security import descifrar_columnas
        df_exp = descifrar_columnas(SESION.df_class.copy(),
                                     CONFIG['seguretat']['xifrar_camps'])
        cols = ['unique_id', 'Product Name', 'Category', 'Sub-Category',
                'abc', 'xyz', 'abc_xyz', 'sbc_class',
                'n_activos', 'adi', 'cv', 'cv2', 'total', 'forecasteable']
        cols = [c for c in cols if c in df_exp.columns]
        df_exp = df_exp[cols]
        try:
            if ruta.endswith('.xlsx'):
                df_exp.to_excel(ruta, index=False)
            else:
                df_exp.to_csv(ruta, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, 'Exportacion completada',
                                    f'Clasificacion guardada en:\n{ruta}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            LOG.exception('Error al exportar clasificacion')
