"""Pagina 1 - Carga de datos (Excel/CSV/ODS o SQL, o ambos a la vez)."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from ..core.config import LOG, CONFIG
from .sesion import SESION
from .widgets import TarjetaKPI
from .workers import CargaWorker, lanzar_en_hilo


class PaginaCarga(QWidget):
    """
    Pantalla de carga. Permite seleccionar fichero, SQL Server, o ambos.

    Flujo:
      - Cada tarjeta MARCA la fuente como activa (no carga todavia).
      - El boton central "Cargar datos" lanza la carga con TODO lo marcado.
      - Si hay fichero + SQL, el data_loader los fusiona en un unico panel.
    """

    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana = ventana_principal
        self._hilo = None

        # Estado de las fuentes seleccionadas
        self.ruta_archivo = None
        self.usar_sql = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)

        h1 = QLabel('Carga de datos')
        h1.setObjectName('H1')
        layout.addWidget(h1)

        sub = QLabel(
            'Selecciona una o las dos fuentes. '
            'Si seleccionas fichero y SQL Server a la vez, los datos se fusionaran. '
            'Los campos sensibles se cifraran automaticamente con Fernet.'
        )
        sub.setProperty('class', 'muted')
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Tarjetas lado a lado
        fila = QHBoxLayout()
        fila.setSpacing(20)
        fila.addWidget(self._tarjeta_fichero())
        fila.addWidget(self._tarjeta_postgresql())
        layout.addLayout(fila)

        # Estado de las fuentes activas
        self.lbl_fuentes = QLabel('Ninguna fuente seleccionada.')
        self.lbl_fuentes.setProperty('class', 'muted')
        layout.addWidget(self.lbl_fuentes)

        # Boton principal de carga (desactivado hasta que haya al menos 1 fuente)
        self.btn_cargar = QPushButton('Cargar datos')
        self.btn_cargar.setMinimumHeight(46)
        self.btn_cargar.setProperty('class', 'accion')
        self.btn_cargar.setEnabled(False)
        self.btn_cargar.clicked.connect(self._lanzar_carga)
        layout.addWidget(self.btn_cargar)

        # Estado y barra de progreso
        self.lbl_estado = QLabel('')
        self.lbl_estado.setProperty('class', 'muted')
        layout.addWidget(self.lbl_estado)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setVisible(False)
        layout.addWidget(self.barra)

        # KPIs post-carga
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

        # Acciones post-carga
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

    # ----------------------------------------------------------------
    # Tarjetas
    # ----------------------------------------------------------------
    def _tarjeta_fichero(self) -> QFrame:
        f = QFrame()
        f.setObjectName('Tarjeta')
        f.setMinimumHeight(240)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(12)

        ico = QLabel('Fichero local')
        ico.setStyleSheet('font-size:10pt; font-weight:600; color:#2E86C1; '
                          'letter-spacing:1px;')
        lay.addWidget(ico)

        titulo = QLabel('Excel, CSV u ODS')
        titulo.setObjectName('H2')
        lay.addWidget(titulo)

        desc = QLabel('Formatos admitidos: .xlsx, .xls, .csv, .ods')
        desc.setProperty('class', 'muted')
        desc.setWordWrap(True)
        lay.addWidget(desc)

        self.lbl_fichero_activo = QLabel('Sin fichero seleccionado.')
        self.lbl_fichero_activo.setProperty('class', 'muted')
        self.lbl_fichero_activo.setWordWrap(True)
        lay.addWidget(self.lbl_fichero_activo)

        lay.addStretch()

        self.btn_elegir = QPushButton('Seleccionar fichero...')
        self.btn_elegir.setMinimumHeight(40)
        self.btn_elegir.clicked.connect(self._elegir_fichero)
        lay.addWidget(self.btn_elegir)

        self.btn_quitar_fichero = QPushButton('Quitar fichero')
        self.btn_quitar_fichero.setProperty('class', 'secondary')
        self.btn_quitar_fichero.setMinimumHeight(32)
        self.btn_quitar_fichero.setVisible(False)
        self.btn_quitar_fichero.clicked.connect(self._quitar_fichero)
        lay.addWidget(self.btn_quitar_fichero)

        return f

    def _tarjeta_postgresql(self) -> QFrame:
        f = QFrame()
        f.setObjectName('Tarjeta')
        f.setMinimumHeight(240)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(12)

        ico = QLabel('Base de datos')
        ico.setStyleSheet('font-size:10pt; font-weight:600; color:#2E86C1; '
                          'letter-spacing:1px;')
        lay.addWidget(ico)

        titulo = QLabel('SQL Server corporativo')
        titulo.setObjectName('H2')
        lay.addWidget(titulo)

        self.lbl_sql_desc = QLabel('')
        self.lbl_sql_desc.setProperty('class', 'muted')
        self.lbl_sql_desc.setWordWrap(True)
        lay.addWidget(self.lbl_sql_desc)

        lay.addStretch()

        self.btn_configurar_sql = QPushButton('Configurar conexion...')
        self.btn_configurar_sql.setMinimumHeight(36)
        self.btn_configurar_sql.clicked.connect(self._abrir_dialogo_sql)
        lay.addWidget(self.btn_configurar_sql)

        self.btn_anadir_sql = QPushButton('Anadir SQL Server como fuente')
        self.btn_anadir_sql.setMinimumHeight(40)
        self.btn_anadir_sql.setProperty('class', 'secondary')
        self.btn_anadir_sql.clicked.connect(self._anadir_sql)
        lay.addWidget(self.btn_anadir_sql)

        self.btn_quitar_sql = QPushButton('Quitar SQL Server')
        self.btn_quitar_sql.setProperty('class', 'secondary')
        self.btn_quitar_sql.setMinimumHeight(32)
        self.btn_quitar_sql.setVisible(False)
        self.btn_quitar_sql.clicked.connect(self._quitar_sql)
        lay.addWidget(self.btn_quitar_sql)

        self._actualizar_estado_sql()
        return f

    # ----------------------------------------------------------------
    # Gestion del estado de las fuentes
    # ----------------------------------------------------------------
    def _elegir_fichero(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, 'Seleccionar fichero de ventas', '',
            'Datos (*.xlsx *.xls *.csv *.ods)')
        if not ruta:
            return
        self.ruta_archivo = ruta
        nombre = os.path.basename(ruta)
        self.lbl_fichero_activo.setText(f'✓ {nombre}')
        self.lbl_fichero_activo.setStyleSheet('color: #27AE60; font-weight: 600;')
        self.btn_elegir.setText('Cambiar fichero...')
        self.btn_quitar_fichero.setVisible(True)
        self._actualizar_boton_cargar()

    def _quitar_fichero(self):
        self.ruta_archivo = None
        self.lbl_fichero_activo.setText('Sin fichero seleccionado.')
        self.lbl_fichero_activo.setStyleSheet('')
        self.btn_elegir.setText('Seleccionar fichero...')
        self.btn_quitar_fichero.setVisible(False)
        self._actualizar_boton_cargar()

    def _anadir_sql(self):
        habilitada = CONFIG['base_dades'].get('habilitat', False)
        if not habilitada:
            QMessageBox.warning(
                self, 'SQL Server no configurado',
                'Primero configura la conexion con el boton '
                '"Configurar conexion...".'
            )
            return
        self.usar_sql = True
        host = CONFIG['base_dades'].get('amfitrio', '?')
        self.lbl_sql_desc.setText(f'✓ {host} activo como fuente.')
        self.lbl_sql_desc.setStyleSheet('color: #27AE60; font-weight: 600;')
        self.btn_anadir_sql.setVisible(False)
        self.btn_quitar_sql.setVisible(True)
        self._actualizar_boton_cargar()

    def _quitar_sql(self):
        self.usar_sql = False
        self.btn_anadir_sql.setVisible(True)
        self.btn_quitar_sql.setVisible(False)
        self._actualizar_estado_sql()
        self._actualizar_boton_cargar()

    def _actualizar_estado_sql(self):
        habilitada = CONFIG['base_dades'].get('habilitat', False)
        host = CONFIG['base_dades'].get('amfitrio', '?')
        if habilitada:
            self.lbl_sql_desc.setText(
                f'Conexion configurada a {host}. '
                f'Pulsa "Anadir" para incluirla en la carga.'
            )
            self.lbl_sql_desc.setStyleSheet('')
            self.btn_anadir_sql.setEnabled(True)
        else:
            self.lbl_sql_desc.setText(
                'No hay conexion configurada. '
                'Pulsa "Configurar conexion..." para anadir tu servidor.'
            )
            self.lbl_sql_desc.setStyleSheet('')
            self.btn_anadir_sql.setEnabled(False)

    def _abrir_dialogo_sql(self):
        from .dialogo_sql import DialogoConfigSQL
        dialogo = DialogoConfigSQL(self)
        dialogo.exec()
        self._actualizar_estado_sql()

    def _actualizar_boton_cargar(self):
        hay_fuente = bool(self.ruta_archivo) or self.usar_sql
        self.btn_cargar.setEnabled(hay_fuente)

        if not hay_fuente:
            self.lbl_fuentes.setText('Ninguna fuente seleccionada.')
            self.lbl_fuentes.setStyleSheet('')
        elif self.ruta_archivo and self.usar_sql:
            nombre = os.path.basename(self.ruta_archivo)
            host = CONFIG['base_dades'].get('amfitrio', '?')
            self.lbl_fuentes.setText(
                f'Fuentes activas: "{nombre}" + SQL Server ({host}). '
                f'Los datos se fusionaran.'
            )
            self.lbl_fuentes.setStyleSheet('color: #1F4E79; font-weight: 600;')
        elif self.ruta_archivo:
            self.lbl_fuentes.setText(
                f'Fuente activa: "{os.path.basename(self.ruta_archivo)}"'
            )
            self.lbl_fuentes.setStyleSheet('color: #1F4E79;')
        else:
            host = CONFIG['base_dades'].get('amfitrio', '?')
            self.lbl_fuentes.setText(f'Fuente activa: SQL Server ({host})')
            self.lbl_fuentes.setStyleSheet('color: #1F4E79;')

    # ----------------------------------------------------------------
    # Carga
    # ----------------------------------------------------------------
    def _lanzar_carga(self):
        """Lanza la carga con TODAS las fuentes activas a la vez."""
        if not self.ruta_archivo and not self.usar_sql:
            QMessageBox.warning(self, 'Sin fuentes',
                                'Selecciona al menos un fichero o SQL Server.')
            return

        self.barra.setValue(0)
        self.barra.setVisible(True)
        self.lbl_estado.setText('Iniciando carga...')
        self.frame_kpis.setVisible(False)
        self.frame_acciones.setVisible(False)
        self.btn_cargar.setEnabled(False)

        LOG.info('CargaWorker: ruta=%s, sql=%s', self.ruta_archivo, self.usar_sql)

        worker = CargaWorker(
            ruta_archivo=self.ruta_archivo,
            desde_sql=self.usar_sql,
        )
        self._hilo = lanzar_en_hilo(
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
        fuentes = []
        if self.ruta_archivo:
            fuentes.append('fichero')
        if self.usar_sql:
            fuentes.append('SQL Server')
        self.lbl_estado.setText(
            f'Datos cargados desde {" + ".join(fuentes)}: '
            f'{df_class["unique_id"].nunique()} productos, '
            f'{df_full["ds"].nunique()} meses.'
        )
        self.barra.setVisible(False)
        self.btn_cargar.setEnabled(True)
        self._actualizar_kpis()
        self.frame_kpis.setVisible(True)
        self.frame_acciones.setVisible(True)
        self.ventana.notificar_datos_cargados()

    def _carga_error(self, mensaje: str):
        self.barra.setVisible(False)
        self.btn_cargar.setEnabled(True)
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
        if not SESION.datos_listos:
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
