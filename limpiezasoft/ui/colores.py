"""Selector de colores y contraste para texto sobre colores elegidos por el usuario."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QColorDialog, QDialog, QPushButton

COLOR_INICIAL = '#087F72'


def normalizar_color(valor):
    color = QColor(valor or COLOR_INICIAL)
    return color.name().upper() if color.isValid() else COLOR_INICIAL


def texto_contraste(valor):
    def luminancia(color):
        componentes = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
                       for v in (color.redF(), color.greenF(), color.blueF())]
        return sum(v * peso for v, peso in zip(componentes, (.2126, .7152, .0722)))
    fondo = luminancia(QColor(normalizar_color(valor)))
    return '#FFFFFF' if (1.05 / (fondo + .05)) > ((fondo + .05) / .05) else '#000000'


class SelectorColor(QPushButton):
    def __init__(self, valor=None, parent=None):
        super().__init__(parent)
        self.setObjectName('selectorColor')
        self.establecer_color(valor)
        self.clicked.connect(self.elegir)

    def establecer_color(self, valor):
        self.color = normalizar_color(valor)
        self.setText(f'{self.color} · Elegir color…')
        self.setAccessibleName(f'Color del estado {self.color}. Abrir selector de color.')
        self.setStyleSheet('QPushButton#selectorColor { '
                          f'background: {self.color}; color: {texto_contraste(self.color)}; '
                          'border: 1px solid #64748b; }')

    def elegir(self):
        dialogo = QColorDialog(QColor(self.color), self)
        dialogo.setWindowTitle('Seleccionar color del estado')
        dialogo.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        paleta = dialogo.palette()
        for rol, color in ((QPalette.ColorRole.Window, '#f3f6fa'),
                           (QPalette.ColorRole.Base, '#ffffff'),
                           (QPalette.ColorRole.Button, '#f3f6fa'),
                           (QPalette.ColorRole.Text, '#172c45'),
                           (QPalette.ColorRole.WindowText, '#172c45'),
                           (QPalette.ColorRole.ButtonText, '#172c45')):
            paleta.setColor(rol, QColor(color))
        dialogo.setPalette(paleta)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.establecer_color(dialogo.selectedColor().name())
