from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Qt, QDateTime, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QDialog,
    QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from limpiezasoft.negocio.modelos import ENTIDADES, etiqueta


class Senales(QObject):
    terminado = Signal(object, object)


class Trabajo(QRunnable):
    def __init__(self, funcion):
        super().__init__()
        self.funcion = funcion
        self.senales = Senales()

    def run(self):
        try:
            resultado = self.funcion()
        except Exception as exc:
            self.senales.terminado.emit(None, exc)
        else:
            self.senales.terminado.emit(resultado, None)


class Formulario(QDialog):
    def __init__(self, entidad, opciones, registro=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(('Editar · ' if registro else 'Nuevo · ') + entidad.titulo)
        self.resize(570, 520)
        self.editores = {}
        self.entidad = entidad
        layout = QVBoxLayout(self)
        titulo = QLabel(self.windowTitle())
        titulo.setObjectName('titulo')
        layout.addWidget(titulo)
        ayuda = QLabel('Los campos con * son obligatorios. Los importes admiten 2 decimales.')
        ayuda.setWordWrap(True)
        layout.addWidget(ayuda)
        scroll = QScrollArea()
        scroll.setObjectName('formularioScroll')
        scroll.setWidgetResizable(True)
        cuerpo = QWidget()
        cuerpo.setObjectName('formularioContenido')
        form = QFormLayout(cuerpo)
        form.setSpacing(14)
        for campo in entidad.campos:
            if campo.calculado:
                continue
            valor = (registro or {}).get(campo.nombre)
            if campo.referencia:
                editor = QComboBox()
                editor.addItem('Seleccionar…' if campo.requerido else 'Sin asignar', None)
                if campo.requerido and not opciones[campo.referencia]:
                    referencia = ENTIDADES[campo.referencia]
                    editor.setItemText(0, f'Sin registros: crea en {referencia.titulo}')
                    editor.setToolTip(f'Registra primero los datos en {referencia.grupo} → {referencia.titulo}.')
                for opcion in opciones[campo.referencia]:
                    editor.addItem(f"{opcion['nombre']} · #{opcion['id']}", opcion['id'])
                editor.setCurrentIndex(max(0, editor.findData(valor)))
            elif campo.tipo == 'booleano':
                editor = QCheckBox('Sí')
                editor.setChecked(True if valor is None else bool(valor))
            elif campo.tipo == 'fecha':
                editor = QDateTimeEdit()
                editor.setCalendarPopup(True)
                editor.setDisplayFormat('dd/MM/yyyy HH:mm')
                fecha = QDateTime.fromMSecsSinceEpoch(int(valor.timestamp() * 1000)) if valor else QDateTime.currentDateTime()
                editor.setDateTime(fecha)
                editor.setToolTip('Hora local del equipo. Se guarda con su zona horaria.')
            else:
                editor = QLineEdit('' if valor is None else str(valor))
                if campo.largo:
                    editor.setMaxLength(campo.largo)
                if campo.tipo == 'password':
                    editor.clear()
                    editor.setEchoMode(QLineEdit.EchoMode.Password)
                    editor.setPlaceholderText('Dejar vacío para conservar' if registro else 'Mínimo 8 caracteres')
                elif campo.tipo in ('entero', 'decimal'):
                    editor.setPlaceholderText('0' if campo.tipo == 'entero' else '0.00')
                    if valor is None and campo.nombre not in ('cantidad', 'monto_pagado'):
                        editor.setText('0')
            form.addRow(etiqueta(campo.nombre) + (' *' if campo.requerido else ''), editor)
            self.editores[campo.nombre] = editor
        scroll.setWidget(cuerpo)
        layout.addWidget(scroll)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #b83e49;')
        layout.addWidget(self.error)
        botones = QDialogButtonBox()
        self.guardar = botones.addButton('Guardar', QDialogButtonBox.ButtonRole.AcceptRole)
        self.guardar.setObjectName('primario')
        botones.addButton('Cancelar', QDialogButtonBox.ButtonRole.RejectRole)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def valores(self):
        valores = {}
        for nombre, editor in self.editores.items():
            if isinstance(editor, QComboBox):
                valor = editor.currentData()
            elif isinstance(editor, QCheckBox):
                valor = editor.isChecked()
            elif isinstance(editor, QDateTimeEdit):
                valor = datetime.fromtimestamp(editor.dateTime().toSecsSinceEpoch()).astimezone()
            else:
                valor = editor.text()
            valores[nombre] = valor
        return valores


class VentanaPrincipal(QMainWindow):
    def __init__(self, servicio):
        super().__init__()
        self.servicio = servicio
        self.tabla_actual = None
        self.pagina = 0
        self.registros = []
        self.trabajos = set()
        self.pool = QThreadPool(self)
        self.setWindowTitle('LimpiezaSoft · Gestión de empresa')
        self.resize(1320, 820)
        self.setMinimumSize(1000, 650)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 24, 16)
        layout.setSpacing(26)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(252)
        lateral = QVBoxLayout(sidebar)
        marca = QLabel('LimpiezaSoft')
        marca.setObjectName('marca')
        lateral.addWidget(marca)
        self.nav = QTreeWidget()
        self.nav.setHeaderHidden(True)
        self.nav.setIndentation(12)
        inicio = QTreeWidgetItem(['Vista general'])
        self.nav.addTopLevelItem(inicio)
        grupos = {}
        orden_grupos = ['Clientes', 'Servicios', 'Inventario', 'Ventas', 'Compras', 'Equipo']
        for entidad in sorted(ENTIDADES.values(), key=lambda e: orden_grupos.index(e.grupo)):
            if entidad.grupo not in grupos:
                item = QTreeWidgetItem([entidad.grupo])
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                grupos[entidad.grupo] = item
                self.nav.addTopLevelItem(item)
            item = QTreeWidgetItem([entidad.titulo])
            item.setData(0, Qt.ItemDataRole.UserRole, entidad.tabla)
            grupos[entidad.grupo].addChild(item)
        grupos['Clientes'].setExpanded(True)
        grupos['Servicios'].setExpanded(True)
        self.nav.setCurrentItem(inicio)
        self.nav.itemClicked.connect(self.navegar)
        lateral.addWidget(self.nav)
        pie = QLabel('PROYECTO ESCOLAR\nEquipo de Informática · 2026')
        pie.setObjectName('marcaPie')
        lateral.addWidget(pie)
        layout.addWidget(sidebar)
        contenido = QVBoxLayout()
        contenido.setSpacing(18)
        self.titulo = QLabel('Tu empresa, organizada')
        self.titulo.setObjectName('titulo')
        self.subtitulo = QLabel('Una vista clara de clientes, equipo y operaciones.')
        self.subtitulo.setObjectName('subtitulo')
        contenido.addWidget(self.titulo)
        contenido.addWidget(self.subtitulo)
        self.paginas = QStackedWidget()
        self.inicio = QWidget()
        panel = QVBoxLayout(self.inicio)
        panel.setContentsMargins(0, 16, 0, 0)
        tarjetas = QHBoxLayout()
        self.indicadores = {}
        for clave, nombre in [('clientes', 'Clientes registrados'), ('empleados', 'Personas del equipo'), ('agenda', 'Servicios próximos'), ('ventas', 'Ventas acumuladas')]:
            tarjeta = QFrame()
            tarjeta.setObjectName('tarjeta')
            caja = QVBoxLayout(tarjeta)
            caja.setContentsMargins(20, 22, 20, 22)
            caja.addWidget(QLabel(nombre))
            valor = QLabel('—')
            valor.setObjectName('numero')
            caja.addWidget(valor)
            tarjetas.addWidget(tarjeta)
            self.indicadores[clave] = valor
        panel.addLayout(tarjetas)
        bienvenida = QLabel('Todo listo para trabajar\n\nGestiona tus clientes, programa servicios y mantén tus registros al día.\nSelecciona un módulo en el menú para comenzar.')
        bienvenida.setWordWrap(True)
        bienvenida.setStyleSheet('font-size: 18px; padding: 30px; background: #e3f1ed; border-radius: 12px;')
        panel.addWidget(bienvenida)
        accesos = QHBoxLayout()
        for nombre, tabla in [('Ver clientes', 'clientes'), ('Programar servicios', 'calendario_servicios'), ('Consultar stock', 'inventario_stock')]:
            boton = QPushButton(nombre)
            boton.clicked.connect(lambda checked=False, t=tabla: self.abrir_tabla(t))
            accesos.addWidget(boton)
        panel.addLayout(accesos)
        actualizar = QPushButton('Actualizar resumen / Reintentar conexión')
        actualizar.clicked.connect(self.cargar_resumen)
        panel.addWidget(actualizar)
        panel.addStretch()
        self.paginas.addWidget(self.inicio)
        listado = QWidget()
        lista = QVBoxLayout(listado)
        lista.setContentsMargins(0, 0, 0, 0)
        barra = QHBoxLayout()
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText('Buscar en los registros… (Enter)')
        self.buscar.returnPressed.connect(self.buscar_registros)
        barra.addWidget(self.buscar, 1)
        for texto, accion, estilo in [('Buscar', self.buscar_registros, ''), ('Actualizar', self.cargar_tabla, ''), ('+ Nuevo', self.nuevo, 'primario')]:
            boton = QPushButton(texto)
            boton.setObjectName(estilo)
            boton.clicked.connect(accion)
            barra.addWidget(boton)
        lista.addLayout(barra)
        self.tabla = QTableWidget()
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(42)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.cellDoubleClicked.connect(lambda *_: self.editar())
        lista.addWidget(self.tabla)
        abajo = QHBoxLayout()
        self.contador = QLabel()
        abajo.addWidget(self.contador, 1)
        self.anterior = QPushButton('← Anterior')
        self.siguiente = QPushButton('Siguiente →')
        self.anterior.clicked.connect(lambda: self.cambiar_pagina(-1))
        self.siguiente.clicked.connect(lambda: self.cambiar_pagina(1))
        abajo.addWidget(self.anterior)
        abajo.addWidget(self.siguiente)
        editar = QPushButton('Editar selección')
        editar.clicked.connect(self.editar)
        eliminar = QPushButton('Eliminar')
        eliminar.setObjectName('peligro')
        eliminar.clicked.connect(self.eliminar)
        abajo.addWidget(editar)
        abajo.addWidget(eliminar)
        lista.addLayout(abajo)
        self.paginas.addWidget(listado)
        contenido.addWidget(self.paginas, 1)
        layout.addLayout(contenido, 1)
        self.statusBar().showMessage('Preparando conexión…')
        QTimer.singleShot(0, self.cargar_resumen)

    def ejecutar(self, funcion, resultado, dialogo=None):
        self.centralWidget().setEnabled(False)
        if dialogo:
            dialogo.setEnabled(False)
        self.statusBar().showMessage('Procesando…')
        trabajo = Trabajo(funcion)
        self.trabajos.add(trabajo)

        def terminado(valor, error):
            self.trabajos.discard(trabajo)
            self.centralWidget().setEnabled(True)
            if dialogo:
                dialogo.setEnabled(True)
            if error:
                self.statusBar().showMessage('No se completó la operación. Puedes reintentar.')
                if dialogo:
                    dialogo.error.setText(str(error))
                else:
                    QMessageBox.warning(self, 'LimpiezaSoft', str(error))
            else:
                self.statusBar().showMessage('Conectado a PostgreSQL · Datos actualizados')
                resultado(valor)
        trabajo.senales.terminado.connect(terminado)
        self.pool.start(trabajo)

    def navegar(self, item, columna):
        tabla = item.data(0, Qt.ItemDataRole.UserRole)
        if tabla:
            self.abrir_tabla(tabla)
        elif item.parent() is None and item.text(0) == 'Vista general':
            self.tabla_actual = None
            self.paginas.setCurrentIndex(0)
            self.titulo.setText('Tu empresa, organizada')
            self.subtitulo.setText('Una vista clara de clientes, equipo y operaciones.')
            self.cargar_resumen()

    def cargar_resumen(self):
        def mostrar(datos):
            for clave, valor in datos.items():
                self.indicadores[clave].setText(f'{valor:,.2f}' if clave == 'ventas' else str(valor))
        self.ejecutar(self.servicio.resumen, mostrar)

    def abrir_tabla(self, tabla):
        self.tabla_actual = tabla
        self.pagina = 0
        self.buscar.clear()
        self.paginas.setCurrentIndex(1)
        self.titulo.setText(ENTIDADES[tabla].titulo)
        self.subtitulo.setText('Consulta, agrega y actualiza los registros de tu empresa.')
        self.cargar_tabla()

    def buscar_registros(self):
        self.pagina = 0
        self.cargar_tabla()

    def cambiar_pagina(self, cambio):
        self.pagina = max(0, self.pagina + cambio)
        self.cargar_tabla()

    def cargar_tabla(self):
        tabla, busqueda, pagina = self.tabla_actual, self.buscar.text(), self.pagina
        entidad = ENTIDADES[tabla]
        self.registros = []
        self.tabla.clearContents()
        self.tabla.setRowCount(0)
        self.contador.setText('Cargando registros…')
        def obtener():
            filas, total = self.servicio.listar(tabla, busqueda, pagina)
            opciones = {c.referencia: self.servicio.opciones(c.referencia) for c in entidad.campos if c.referencia}
            return filas, total, opciones
        def mostrar(datos):
            self.registros, total, self.opciones = datos
            columnas = [c for c in entidad.campos if c.tipo != 'password']
            self.tabla.setRowCount(len(self.registros))
            self.tabla.setColumnCount(len(columnas))
            self.tabla.setHorizontalHeaderLabels([etiqueta(c.nombre) for c in columnas])
            for i, registro in enumerate(self.registros):
                for j, campo in enumerate(columnas):
                    valor = registro[campo.nombre]
                    if campo.referencia and valor is not None:
                        nombre = next((o['nombre'] for o in self.opciones[campo.referencia] if o['id'] == valor), '')
                        texto = f'{nombre} · #{valor}'
                    elif isinstance(valor, datetime):
                        texto = valor.astimezone().strftime('%d/%m/%Y %H:%M')
                    elif isinstance(valor, bool):
                        texto = 'Sí' if valor else 'No'
                    else:
                        texto = '—' if valor is None else str(valor)
                    self.tabla.setItem(i, j, QTableWidgetItem(texto))
            self.contador.setText(f'{total} registros · Página {self.pagina + 1}' if total else 'Sin registros. Usa + Nuevo para comenzar.')
            self.anterior.setEnabled(self.pagina > 0)
            self.siguiente.setEnabled((self.pagina + 1) * 100 < total)
        self.ejecutar(obtener, mostrar)

    def seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.information(self, 'Selecciona un registro', 'Selecciona primero una fila de la tabla.')
            return None
        return self.registros[fila]

    def nuevo(self):
        self.formulario()

    def editar(self):
        registro = self.seleccionado()
        if registro is not None:
            self.formulario(registro)

    def formulario(self, registro=None):
        tabla = self.tabla_actual
        entidad = ENTIDADES[tabla]
        def abrir(opciones):
            dialogo = Formulario(entidad, opciones, registro, self)
            def guardar():
                valores = dialogo.valores()
                def listo(_):
                    dialogo.accept()
                    self.cargar_tabla()
                self.ejecutar(lambda: self.servicio.guardar(tabla, valores, registro), listo, dialogo)
            dialogo.guardar.clicked.connect(guardar)
            dialogo.exec()
        self.ejecutar(lambda: {c.referencia: self.servicio.opciones(c.referencia) for c in entidad.campos if c.referencia}, abrir)

    def eliminar(self):
        registro = self.seleccionado()
        if registro is None:
            return
        respuesta = QMessageBox.question(self, 'Confirmar eliminación',
            '¿Eliminar el registro seleccionado? Esta acción también elimina los detalles o asociaciones que el esquema define en cascada.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if respuesta == QMessageBox.StandardButton.Yes:
            tabla = self.tabla_actual
            self.ejecutar(lambda: self.servicio.eliminar(tabla, registro), lambda _: self.cargar_tabla())

    def closeEvent(self, event):
        if self.trabajos:
            event.ignore()
            self.statusBar().showMessage('Espera a que termine la operación antes de cerrar.')
        else:
            super().closeEvent(event)
