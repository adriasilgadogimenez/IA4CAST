"""
Punto de entrada de IA4CAST.

Ejecucion en desarrollo:
    python main.py

Empaquetado a .exe:
    pyinstaller IA4CAST.spec
"""
from __future__ import annotations

import multiprocessing
import sys
import traceback


# ══════════════════════════════════════════════════════════════════════
# CRITICO: freeze_support() debe ir LO ANTES POSIBLE, antes de cualquier
# otro import, para evitar que PyInstaller relance el .exe N veces
# (una por cada nucleo de CPU) cuando se usa multiprocessing/joblib.
#
# Sin esta linea, al pulsar "Generar pronostico" se abren multiples
# ventanas de la app porque lightgbm/joblib intentan crear procesos
# hijo y cada uno relanza el .exe entero.
# ══════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    multiprocessing.freeze_support()


from PySide6.QtWidgets import QApplication, QMessageBox

from ia4cast.core.config import LOG, CARPETA_USUARIO
from ia4cast.core.db_test import procesar_datos_instalacion
from ia4cast.ui.ventana_principal import VentanaPrincipal


def main():
    LOG.info('=' * 60)
    LOG.info('Iniciando IA4CAST')
    LOG.info('Carpeta de usuario: %s', CARPETA_USUARIO)
    LOG.info('=' * 60)

    app = QApplication(sys.argv)
    app.setApplicationName('IA4CAST')
    app.setOrganizationName('Projecte IA4CAST')

    def _excepthook(tipo, valor, tb):
        msg = ''.join(traceback.format_exception(tipo, valor, tb))
        LOG.error('Excepcion no controlada: %s', msg)
        QMessageBox.critical(None, 'Error inesperado',
            f'Se ha producido un error inesperado:\n\n{valor}\n\n'
            f'Consulta el log en {CARPETA_USUARIO}/logs para mas detalles.')
    sys.excepthook = _excepthook

    # Procesar datos de instalacion (si existen)
    resultado = procesar_datos_instalacion()
    if resultado is not None:
        if resultado['ok']:
            QMessageBox.information(
                None, 'Configuracion SQL Server',
                f'Conexion a SQL Server configurada correctamente.\n\n'
                f'Servidor: {resultado.get("host", "?")}\n'
                f'Base de datos: {resultado.get("database", "?")}\n\n'
                f'Ya puedes usar SQL Server como fuente de datos desde la app.'
            )
        else:
            QMessageBox.warning(
                None, 'Configuracion SQL Server fallida',
                f'No se ha podido conectar a SQL Server con los datos '
                f'introducidos durante la instalacion.\n\n'
                f'Detalle: {resultado["mensaje"]}\n\n'
                f'La aplicacion funcionara con ficheros Excel/CSV/ODS. '
                f'Puedes reconfigurar la conexion editando manualmente '
                f'{CARPETA_USUARIO}/config.yaml.'
            )

    ventana = VentanaPrincipal()
    ventana.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
