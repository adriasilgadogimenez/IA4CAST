"""
Dialogo modal para configurar la conexion a SQL Server.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from ..core.db_config import (
    probar_conexion, guardar_configuracion_sql, leer_configuracion_sql,
    deshabilitar_sql,
)


class DialogoConfigSQL(QDialog):
    """Formulario para configurar SQL Server con boton de prueba."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Configurar conexion a SQL Server')
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabecera
        titulo = QLabel('Configuracion de SQL Server')
        titulo.setStyleSheet('font-size: 14pt; font-weight: bold; color: #1F4E79;')
        layout.addWidget(titulo)

        desc = QLabel(
            'Configura aqui los datos de conexion a tu servidor SQL Server '
            'corporativo. La contrasena se guarda cifrada con Fernet.'
        )
        desc.setWordWrap(True)
        desc.setStyleSheet('color: #5D6D7E;')
        layout.addWidget(desc)

        # Formulario
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText('192.168.1.10  o  servidor.empresa.local')
        form.addRow('Servidor (host):', self.txt_host)

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(1433)
        form.addRow('Puerto:', self.spin_port)

        self.txt_database = QLineEdit()
        self.txt_database.setPlaceholderText('nom_de_la_base_de_dades')
        form.addRow('Base de datos:', self.txt_database)

        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText('ia4cast_ro')
        form.addRow('Usuario:', self.txt_user)

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText('...')
        form.addRow('Contrasena:', self.txt_password)

        # Mostrar contrasena en claro (toggle)
        self.chk_mostrar = QCheckBox('Mostrar contrasena')
        self.chk_mostrar.stateChanged.connect(self._toggle_password_visibility)
        form.addRow('', self.chk_mostrar)

        layout.addLayout(form)

        # Boton probar conexion
        fila_prueba = QHBoxLayout()
        self.btn_probar = QPushButton('Probar conexion')
        self.btn_probar.setMinimumHeight(36)
        self.btn_probar.clicked.connect(self._probar)
        fila_prueba.addWidget(self.btn_probar)
        fila_prueba.addStretch()
        layout.addLayout(fila_prueba)

        # Etiqueta de resultado de la prueba
        self.lbl_resultado = QLabel('')
        self.lbl_resultado.setWordWrap(True)
        self.lbl_resultado.setMinimumHeight(40)
        layout.addWidget(self.lbl_resultado)

        # Botones inferiores
        self.btn_box = QDialogButtonBox()
        self.btn_guardar = self.btn_box.addButton(
            'Guardar y habilitar', QDialogButtonBox.AcceptRole)
        self.btn_deshabilitar = self.btn_box.addButton(
            'Deshabilitar SQL', QDialogButtonBox.ActionRole)
        self.btn_cancelar = self.btn_box.addButton(
            'Cancelar', QDialogButtonBox.RejectRole)
        self.btn_box.accepted.connect(self._guardar)
        self.btn_box.rejected.connect(self.reject)
        self.btn_deshabilitar.clicked.connect(self._deshabilitar)
        layout.addWidget(self.btn_box)

        # Cargar valores actuales
        self._cargar_actual()

    def _cargar_actual(self):
        cfg = leer_configuracion_sql()
        self.txt_host.setText(cfg['host'])
        self.spin_port.setValue(cfg['port'])
        self.txt_database.setText(cfg['database'])
        self.txt_user.setText(cfg['user'])
        self.txt_password.setText(cfg['password'])
        if cfg['habilitada']:
            self.lbl_resultado.setText(
                '[i] Hay una conexion ya configurada y habilitada.')
            self.lbl_resultado.setStyleSheet('color: #27AE60;')

    def _toggle_password_visibility(self, state):
        if state == Qt.Checked.value:
            self.txt_password.setEchoMode(QLineEdit.Normal)
        else:
            self.txt_password.setEchoMode(QLineEdit.Password)

    def _datos_formulario(self):
        return {
            'host': self.txt_host.text().strip(),
            'port': self.spin_port.value(),
            'database': self.txt_database.text().strip(),
            'user': self.txt_user.text().strip(),
            'password': self.txt_password.text(),
        }

    def _validar(self) -> bool:
        d = self._datos_formulario()
        if not d['host']:
            self._mostrar_error('Falta el servidor (host).')
            return False
        if not d['database']:
            self._mostrar_error('Falta el nombre de la base de datos.')
            return False
        if not d['user']:
            self._mostrar_error('Falta el usuario.')
            return False
        return True

    def _mostrar_error(self, msg):
        self.lbl_resultado.setText(f'[ERROR] {msg}')
        self.lbl_resultado.setStyleSheet('color: #C0392B; font-weight: 600;')

    def _mostrar_ok(self, msg):
        self.lbl_resultado.setText(f'[OK] {msg}')
        self.lbl_resultado.setStyleSheet('color: #27AE60; font-weight: 600;')

    def _mostrar_warning(self, msg):
        self.lbl_resultado.setText(f'[!] {msg}')
        self.lbl_resultado.setStyleSheet('color: #E67E22; font-weight: 600;')

    def _probar(self):
        if not self._validar():
            return

        d = self._datos_formulario()
        self.btn_probar.setEnabled(False)
        self.lbl_resultado.setText('Probando conexion...')
        self.lbl_resultado.setStyleSheet('color: #5D6D7E;')
        # Forzar refresco visual antes de bloquear con la conexion
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        ok, msg = probar_conexion(
            d['host'], d['port'], d['database'], d['user'], d['password'])

        if ok:
            self._mostrar_ok(msg)
        else:
            self._mostrar_error(msg)

        self.btn_probar.setEnabled(True)

    def _guardar(self):
        if not self._validar():
            return

        d = self._datos_formulario()

        # Probar siempre antes de guardar como habilitado
        ok, msg = probar_conexion(
            d['host'], d['port'], d['database'], d['user'], d['password'])

        if ok:
            guardar_configuracion_sql(
                d['host'], d['port'], d['database'], d['user'], d['password'],
                habilitada=True)
            QMessageBox.information(
                self, 'Configuracion guardada',
                f'Conexion a SQL Server guardada y habilitada correctamente.\n\n'
                f'{msg}'
            )
            self.accept()
        else:
            respuesta = QMessageBox.question(
                self, 'Conexion fallida',
                f'La prueba de conexion ha fallado:\n\n{msg}\n\n'
                f'¿Quieres guardar los datos de todas formas '
                f'(con SQL deshabilitado)?',
                QMessageBox.Yes | QMessageBox.No
            )
            if respuesta == QMessageBox.Yes:
                guardar_configuracion_sql(
                    d['host'], d['port'], d['database'], d['user'], d['password'],
                    habilitada=False)
                QMessageBox.information(
                    self, 'Datos guardados',
                    'Los datos se han guardado pero SQL Server queda deshabilitado. '
                    'Puedes volver a esta pantalla cuando el servidor este accesible.'
                )
                self.accept()

    def _deshabilitar(self):
        respuesta = QMessageBox.question(
            self, 'Deshabilitar SQL',
            '¿Seguro que quieres deshabilitar la conexion a SQL Server?\n\n'
            'Los datos quedaran guardados, solo se marcara como deshabilitada.',
            QMessageBox.Yes | QMessageBox.No
        )
        if respuesta == QMessageBox.Yes:
            deshabilitar_sql()
            QMessageBox.information(
                self, 'SQL deshabilitado',
                'La conexion a SQL Server ha sido deshabilitada.'
            )
            self.accept()
