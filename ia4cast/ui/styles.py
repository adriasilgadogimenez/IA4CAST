"""
Hoja de estilos QSS - tema corporativo moderno.

Paleta:
    Primario:    #1F4E79 (azul corporativo profundo)
    Acento:      #2E86C1 (azul brillante para botones de accion)
    Exito:       #27AE60
    Aviso:       #E67E22
    Critica:     #C0392B
    Fondo:       #F4F6F8 (gris muy claro)
    Tarjetas:    #FFFFFF
    Texto:       #2C3E50
    Bordes:      #DDE2E8

Tipografia: Segoe UI / system-ui (cae a la fuente del sistema en cada plataforma).
"""

QSS_CORPORATIVO = """
/* ============== Globales ============== */
* {
    font-family: 'Segoe UI', 'San Francisco', 'Helvetica Neue', Arial, sans-serif;
    font-size: 10pt;
    color: #2C3E50;
}

QMainWindow, QWidget {
    background-color: #F4F6F8;
}

QLabel {
    background-color: transparent;
}

/* ============== Sidebar (navegacion) ============== */
#Sidebar {
    background-color: #1F4E79;
    border: none;
}
#Sidebar QPushButton {
    color: #E8F0F8;
    background-color: transparent;
    border: none;
    border-left: 3px solid transparent;
    text-align: left;
    padding: 14px 20px 14px 20px;
    font-size: 10.5pt;
}
#Sidebar QPushButton:hover {
    background-color: #2C5F8C;
    color: white;
}
#Sidebar QPushButton:checked {
    background-color: #2C5F8C;
    border-left: 3px solid #2E86C1;
    color: white;
    font-weight: 600;
}
#SidebarTitulo {
    color: white;
    font-size: 16pt;
    font-weight: 600;
    padding: 24px 20px 12px 20px;
    background-color: #1F4E79;
}
#SidebarSubtitulo {
    color: #B8CDDF;
    font-size: 9pt;
    padding: 0 20px 24px 20px;
    background-color: #1F4E79;
}

/* ============== Tarjetas (KPI / contenedores) ============== */
#Tarjeta {
    background-color: white;
    border: 1px solid #DDE2E8;
    border-radius: 8px;
    padding: 16px;
}
#TarjetaTitulo {
    color: #5D6D7E;
    font-size: 9.5pt;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
#TarjetaValor {
    color: #1F4E79;
    font-size: 22pt;
    font-weight: 600;
}
#TarjetaSubvalor {
    color: #7F8C8D;
    font-size: 9pt;
}

/* ============== Botones ============== */
QPushButton {
    background-color: #2E86C1;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 9px 18px;
    font-size: 10pt;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #2874A6;
}
QPushButton:pressed {
    background-color: #21618C;
}
QPushButton:disabled {
    background-color: #BDC3C7;
    color: #ECF0F1;
}

QPushButton[class="secondary"] {
    background-color: white;
    color: #1F4E79;
    border: 1px solid #1F4E79;
}
QPushButton[class="secondary"]:hover {
    background-color: #EBF2F9;
}

QPushButton[class="accion"] {
    background-color: #27AE60;
}
QPushButton[class="accion"]:hover {
    background-color: #229954;
}

QPushButton[class="peligro"] {
    background-color: #C0392B;
}
QPushButton[class="peligro"]:hover {
    background-color: #A93226;
}

/* ============== Inputs ============== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background-color: white;
    border: 1px solid #DDE2E8;
    border-radius: 4px;
    padding: 7px 10px;
    selection-background-color: #2E86C1;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {
    border: 1px solid #2E86C1;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: white;
    border: 1px solid #DDE2E8;
    selection-background-color: #2E86C1;
    selection-color: white;
}

QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #BDC3C7;
    border-radius: 3px;
    background-color: white;
}
QCheckBox::indicator:checked {
    background-color: #2E86C1;
    border-color: #2E86C1;
    image: none;
}

QRadioButton {
    spacing: 8px;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 8px;
    border: 1px solid #BDC3C7;
    background-color: white;
}
QRadioButton::indicator:checked {
    background-color: #2E86C1;
    border: 4px solid white;
    outline: 1px solid #2E86C1;
}

/* ============== Tablas ============== */
QTableView, QTableWidget {
    background-color: white;
    alternate-background-color: #F8FAFC;
    border: 1px solid #DDE2E8;
    border-radius: 5px;
    gridline-color: #ECEFF3;
    selection-background-color: #D6EAF8;
    selection-color: #1F4E79;
}
QHeaderView::section {
    background-color: #EBF2F9;
    color: #1F4E79;
    padding: 8px;
    border: none;
    border-right: 1px solid #DDE2E8;
    border-bottom: 2px solid #1F4E79;
    font-weight: 600;
}

/* ============== Sliders ============== */
QSlider::groove:horizontal {
    height: 4px;
    background: #DDE2E8;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #2E86C1;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #2E86C1;
    border-radius: 2px;
}

/* ============== Progress bars ============== */
QProgressBar {
    background-color: #ECEFF3;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #1F4E79;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #2E86C1;
    border-radius: 4px;
}

/* ============== Etiquetas semanticas ============== */
QLabel#H1 {
    font-size: 18pt;
    font-weight: 600;
    color: #1F4E79;
}
QLabel#H2 {
    font-size: 13pt;
    font-weight: 600;
    color: #1F4E79;
}
QLabel#H3 {
    font-size: 11pt;
    font-weight: 600;
    color: #34495E;
}
QLabel[class="muted"] {
    color: #7F8C8D;
    font-size: 9pt;
}
QLabel[class="badge-ok"] {
    background-color: #D5F5E3;
    color: #1E8449;
    border-radius: 4px;
    padding: 3px 10px;
    font-weight: 500;
}
QLabel[class="badge-warn"] {
    background-color: #FCF3CF;
    color: #7E5109;
    border-radius: 4px;
    padding: 3px 10px;
    font-weight: 500;
}
QLabel[class="badge-err"] {
    background-color: #FADBD8;
    color: #922B21;
    border-radius: 4px;
    padding: 3px 10px;
    font-weight: 500;
}

/* ============== Group boxes ============== */
QGroupBox {
    background-color: white;
    border: 1px solid #DDE2E8;
    border-radius: 6px;
    margin-top: 16px;
    padding: 12px;
    font-weight: 500;
    color: #1F4E79;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background-color: white;
}

/* ============== Scrollbars ============== */
QScrollBar:vertical {
    background: #F4F6F8;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #BDC3C7;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #95A5A6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #F4F6F8;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #BDC3C7;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #95A5A6;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ============== Tooltips ============== */
QToolTip {
    background-color: #2C3E50;
    color: white;
    border: none;
    border-radius: 3px;
    padding: 5px 8px;
}
"""
