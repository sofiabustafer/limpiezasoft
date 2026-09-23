"""Prueba visual sin abrir ventanas ni modificar datos reales."""
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from limpiezasoft.negocio.modelos import ENTIDADES
from limpiezasoft.ui.tema import TEMA
from limpiezasoft.ui.ventana import Formulario, VentanaPrincipal


class ServicioVacio:
    def resumen(self):
        return dict(clientes=0, empleados=0, agenda=0, ventas=0)

    def listar(self, *args):
        return [], 0

    def opciones(self, *args):
        return []


app = QApplication([])
# El backend offscreen de Windows necesita cargar explícitamente las fuentes.
for archivo in ('segoeui.ttf', 'segoeuib.ttf'):
    fuente = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / archivo
    if fuente.exists():
        QFontDatabase.addApplicationFont(str(fuente))
app.setStyle('Fusion')
app.setStyleSheet(TEMA)
ventana = VentanaPrincipal(ServicioVacio())
ventana.show()
fallos = []


def verificar():
    try:
        assert not ventana.trabajos, 'El panel no terminó de cargar'
        salida = Path(__file__).resolve().parents[1] / 'docs'
        salida.mkdir(exist_ok=True)
        assert ventana.grab().save(str(salida / 'interfaz.png'))
        for entidad in ENTIDADES.values():
            opciones = {c.referencia: [] for c in entidad.campos if c.referencia}
            dialogo = Formulario(entidad, opciones, parent=ventana)
            assert len(dialogo.valores()) == sum(not c.calculado for c in entidad.campos)
            dialogo.close()
        ventana.abrir_tabla('clientes')
        QTimer.singleShot(500, finalizar)
    except Exception as exc:
        fallos.append(exc)
        app.quit()


def finalizar():
    try:
        assert not ventana.trabajos
        assert ventana.tabla.rowCount() == 0
        assert ventana.tabla.columnCount() == 6
        assert not ventana.siguiente.isEnabled()
    except Exception as exc:
        fallos.append(exc)
    app.quit()


QTimer.singleShot(1000, verificar)
app.exec()
if fallos:
    raise AssertionError(fallos)
print('UI OK: panel, listado vacío y formularios de las 25 entidades.')
