import os
import unittest
from pathlib import Path
from datetime import date, timedelta, timezone
from decimal import Decimal

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt, QTimer, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QColorDialog, QLabel
from PySide6.QtGui import QColor, QFontDatabase

from limpiezasoft.negocio.servicios import limites_semana
from limpiezasoft.negocio.modelos import ENTIDADES
from limpiezasoft.ui.calendario import CalendarioSemanal, DetalleServicio, TarjetaServicio
from limpiezasoft.ui.colores import SelectorColor, texto_contraste
from limpiezasoft.ui.tema import TEMA
from limpiezasoft.ui.ventana import Formulario


class CalendarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        for archivo in ('segoeui.ttf', 'segoeuib.ttf'):
            fuente = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / archivo
            if fuente.exists():
                QFontDatabase.addApplicationFont(str(fuente))
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet(TEMA)

    def tearDown(self):
        for ventana in self.app.topLevelWidgets():
            ventana.close()
            ventana.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def cita(self, id, fecha):
        return dict(calendario_id=id, fecha_programada=fecha, cliente_nombre=f'Cliente {id}',
                    servicio_nombre='Limpieza general', nombre_estado='Pendiente',
                    estado_color='#AA33BB', limpiadora_nombre='Persona asignada',
                    cliente_documento='123', cliente_telefono=None, cliente_direccion='Dirección de prueba',
                    limpiadora_telefono=None, precio_base=Decimal('25000'),
                    factura_servicio_id=None, factura_monto=None, factura_fecha=None)

    def test_citas_simultaneas_click_detalle_y_limpiar(self):
        inicio, fin = limites_semana(date(2026, 9, 23))
        primera = self.cita(1, inicio + timedelta(days=2, hours=9, minutes=15))
        segunda = self.cita(2, inicio + timedelta(days=2, hours=9, minutes=45))
        calendario = CalendarioSemanal()
        calendario.resize(1000, 600)
        calendario.show()
        seleccionadas = []
        calendario.servicioSeleccionado.connect(seleccionadas.append)
        calendario.mostrar(dict(inicio=inicio, fin=fin, servicios=[segunda, primera]))
        self.app.processEvents()
        celda = calendario.tabla.cellWidget(9, 2)
        botones = celda.findChildren(TarjetaServicio)
        self.assertEqual([b.servicio['calendario_id'] for b in botones], [1, 2])
        self.assertGreaterEqual(calendario.tabla.rowHeight(9), 168)
        self.assertIn('#AA33BB', botones[0].styleSheet())
        QTest.mouseClick(botones[1], Qt.MouseButton.LeftButton)
        self.assertEqual(seleccionadas, [segunda])
        detalle = DetalleServicio(seleccionadas[0])
        textos = [label.text() for label in detalle.findChildren(QLabel)]
        self.assertIn('Cliente 2', textos)
        self.assertIn('Dirección de prueba', textos)
        self.assertIn('Sin factura registrada', textos)
        detalle.close()
        calendario.mostrar(dict(inicio=inicio, fin=fin, servicios=[]))
        self.assertIsNone(calendario.tabla.cellWidget(9, 2))
        self.assertIn('No hay servicios', calendario.descripcion.text())
        self.app.processEvents()
        calendario.close()

    def test_ubicacion_por_hora_local_y_fin_de_semana(self):
        inicio, fin = limites_semana(date(2026, 9, 23))
        domingo = self.cita(3, (fin - timedelta(minutes=1)).astimezone(timezone.utc))
        fuera = self.cita(4, fin)
        calendario = CalendarioSemanal()
        calendario.mostrar(dict(inicio=inicio, fin=fin, servicios=[domingo, fuera]))
        self.assertIsNotNone(calendario.tabla.cellWidget(23, 6))
        self.assertIn('1 servicios', calendario.descripcion.text())
        self.app.processEvents()
        calendario.close()

    def test_selector_guarda_color_y_cancelar_conserva(self):
        formulario = Formulario(ENTIDADES['estados_servicio'], {})
        editor = formulario.editores['color']
        self.assertIsInstance(editor, SelectorColor)
        def aceptar():
            dialogo = self.app.activeModalWidget()
            self.assertIsInstance(dialogo, QColorDialog)
            dialogo.setCurrentColor(QColor('#FFFF00'))
            dialogo.accept()
        QTimer.singleShot(50, aceptar)
        editor.elegir()
        self.assertEqual(formulario.valores()['color'], '#FFFF00')
        QTimer.singleShot(50, lambda: self.app.activeModalWidget().reject())
        editor.elegir()
        self.assertEqual(formulario.valores()['color'], '#FFFF00')
        self.assertEqual(texto_contraste('#FFFF00'), '#000000')
        self.assertEqual(texto_contraste('#000033'), '#FFFFFF')
        formulario.close()
