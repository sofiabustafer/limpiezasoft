"""Calendario semanal y detalle de una cita; sin consultas SQL en la interfaz."""
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout, QHeaderView,
    QLabel, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from limpiezasoft.ui.colores import normalizar_color, texto_contraste

DIAS = ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo')


class TarjetaServicio(QPushButton):
    def __init__(self, servicio, pasado, parent=None):
        super().__init__(parent)
        self.servicio = servicio
        self.setObjectName('citaCalendario')
        self.setProperty('pasado', pasado)
        self.setFixedHeight(76)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        color = normalizar_color(servicio['estado_color'])
        texto = texto_contraste(color)
        self.setStyleSheet('QPushButton#citaCalendario { '
                          f'background: {color}; color: {texto}; '
                          'border: 1px solid #a6b9c6; text-align: left; padding: 7px; font-size: 12px; } '
                          'QPushButton#citaCalendario:hover { border: 2px solid #172c45; }')
        fecha = servicio['fecha_programada'].astimezone()
        self.lineas = (fecha.strftime('%H:%M') + ' · ' + ('Pasado' if pasado else servicio['nombre_estado']),
                       servicio['servicio_nombre'], servicio['cliente_nombre'])
        descripcion = (f"{fecha:%d/%m/%Y %H:%M} · {servicio['servicio_nombre']}\n"
                       f"Cliente: {servicio['cliente_nombre']}\n"
                       f"Limpiadora: {servicio['limpiadora_nombre'] or 'Sin asignar'}\n"
                       f"Estado: {servicio['nombre_estado']}")
        self.setToolTip(escape(descripcion))
        self.setAccessibleName(descripcion)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        ancho = max(20, self.width() - 20)
        self.setText('\n'.join(self.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideRight, ancho)
                               for texto in self.lineas))


class DetalleServicio(QDialog):
    def __init__(self, servicio, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalle del servicio · #{servicio['calendario_id']}")
        self.resize(640, 660)
        layout = QVBoxLayout(self)
        titulo = QLabel(servicio['servicio_nombre'])
        titulo.setTextFormat(Qt.TextFormat.PlainText)
        titulo.setObjectName('titulo')
        titulo.setWordWrap(True)
        layout.addWidget(titulo)
        fecha = servicio['fecha_programada'].astimezone()
        fecha_label = QLabel(f'{DIAS[fecha.weekday()]} {fecha:%d/%m/%Y} · {fecha:%H:%M} (hora local)')
        fecha_label.setObjectName('subtitulo')
        fecha_label.setWordWrap(True)
        layout.addWidget(fecha_label)

        scroll = QScrollArea()
        scroll.setObjectName('formularioScroll')
        scroll.setWidgetResizable(True)
        contenido = QWidget()
        contenido.setObjectName('formularioContenido')
        form = QFormLayout(contenido)
        form.setSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        def fila(titulo, valor):
            label = QLabel('Sin registrar' if valor is None or valor == '' else str(valor))
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse |
                                          Qt.TextInteractionFlag.TextSelectableByKeyboard)
            form.addRow(titulo, label)

        fila('N.º de agenda', servicio['calendario_id'])
        fila('Estado', servicio['nombre_estado'])
        fila('Cliente', servicio['cliente_nombre'])
        fila('RUC / CI', servicio['cliente_documento'])
        fila('Teléfono del cliente', servicio['cliente_telefono'])
        fila('Dirección', servicio['cliente_direccion'])
        fila('Limpiadora', servicio['limpiadora_nombre'] or 'Sin asignar')
        fila('Teléfono de limpiadora', servicio['limpiadora_telefono'])
        fila('Precio base del catálogo', f"{servicio['precio_base']:,.2f}")
        fila('Factura', servicio['factura_servicio_id'] if servicio['factura_servicio_id'] is not None else 'Sin factura registrada')
        if servicio['factura_servicio_id'] is not None:
            fila('Monto facturado', f"{servicio['factura_monto']:,.2f}")
            fila('Fecha de emisión', servicio['factura_fecha'].astimezone().strftime('%d/%m/%Y %H:%M'))
        scroll.setWidget(contenido)
        layout.addWidget(scroll, 1)
        botones = QDialogButtonBox()
        cerrar = botones.addButton('Cerrar', QDialogButtonBox.ButtonRole.RejectRole)
        cerrar.setObjectName('primario')
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)


class CalendarioSemanal(QWidget):
    servicioSeleccionado = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.titulo = QLabel('Agenda de la semana actual')
        self.titulo.setObjectName('tituloCalendario')
        self.descripcion = QLabel('Cargando servicios…')
        self.descripcion.setObjectName('subtitulo')
        self.descripcion.setWordWrap(True)
        layout.addWidget(self.titulo)
        layout.addWidget(self.descripcion)
        self.tabla = QTableWidget(24, 7)
        self.tabla.setObjectName('calendarioSemanal')
        self.tabla.setHorizontalHeaderLabels([dia[:3] for dia in DIAS])
        self.tabla.setVerticalHeaderLabels([f'{hora:02}:00' for hora in range(24)])
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tabla.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tabla.horizontalHeader().setMinimumSectionSize(120)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.tabla.verticalHeader().setDefaultSectionSize(88)
        self.tabla.verticalHeader().setMinimumWidth(52)
        self.tabla.setMinimumHeight(220)
        layout.addWidget(self.tabla, 1)
        pie = QLabel('Hora local · Haz clic en una cita para ver el detalle. La agenda registra la hora de inicio, sin duración.')
        pie.setObjectName('pieCalendario')
        pie.setWordWrap(True)
        layout.addWidget(pie)

    def limpiar(self):
        self.tabla.clearContents()
        self.descripcion.setText('Actualizando calendario…')

    def mostrar(self, agenda):
        self.tabla.clearContents()
        inicio = agenda['inicio'].date()
        fin = (agenda['fin'] - timedelta(days=1)).date()
        ahora = datetime.now().astimezone()
        self.titulo.setText(f'Semana actual · {inicio:%d/%m/%Y} — {fin:%d/%m/%Y}')
        self.tabla.setHorizontalHeaderLabels([
            f"{DIAS[dia][:3]}{' · Hoy' if inicio + timedelta(days=dia) == ahora.date() else ''}\n"
            f'{inicio + timedelta(days=dia):%d/%m}' for dia in range(7)])
        grupos = defaultdict(list)
        for servicio in agenda['servicios']:
            fecha = servicio['fecha_programada'].astimezone()
            dia = (fecha.date() - inicio).days
            if 0 <= dia < 7:
                grupos[(fecha.hour, dia)].append(servicio)
        cantidad = sum(len(citas) for citas in grupos.values())
        proximos = sum(s['fecha_programada'] >= ahora for citas in grupos.values() for s in citas)
        self.descripcion.setText(
            f'{cantidad} servicios esta semana · {proximos} por comenzar · Colores por estado; «Pasado» indica una hora anterior.'
            if cantidad else 'No hay servicios programados para esta semana. Usa Programar servicios para agregar uno.')
        for hora in range(24):
            maximo = max((len(grupos[(hora, dia)]) for dia in range(7)), default=0)
            self.tabla.setRowHeight(hora, max(88, maximo * 80 + 8))
            for dia in range(7):
                item = QTableWidgetItem()
                hoy = inicio + timedelta(days=dia) == ahora.date()
                item.setBackground(QColor('#eff8f4' if hoy else '#ffffff'))
                self.tabla.setItem(hora, dia, item)
                citas = grupos[(hora, dia)]
                if not citas:
                    continue
                celda = QWidget()
                celda.setObjectName('celdaCalendario')
                caja = QVBoxLayout(celda)
                caja.setContentsMargins(4, 4, 4, 4)
                caja.setSpacing(4)
                for servicio in sorted(citas, key=lambda s: (s['fecha_programada'], s['calendario_id'])):
                    boton = TarjetaServicio(servicio, servicio['fecha_programada'] < ahora)
                    boton.clicked.connect(lambda checked=False, s=servicio: self.servicioSeleccionado.emit(s))
                    caja.addWidget(boton)
                caja.addStretch()
                self.tabla.setCellWidget(hora, dia, celda)
        # Dejar visible el próximo servicio de la semana; sin citas, comenzar a las 07:00.
        futuros = [s['fecha_programada'].astimezone() for citas in grupos.values() for s in citas
                   if s['fecha_programada'] >= ahora]
        horas = [hora for (hora, dia), citas in grupos.items() if citas]
        hora = min(futuros).hour if futuros else min(horas, default=7)
        QTimer.singleShot(0, lambda: self.tabla.scrollToItem(
            self.tabla.item(hora, 0), QAbstractItemView.ScrollHint.PositionAtTop))
