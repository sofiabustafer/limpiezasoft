"""Punto de composición: ensambla las tres capas."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description='LimpiezaSoft · Gestión de empresa')
    parser.add_argument('--init-db', action='store_true', help='Crear tablas en una base vacía ya existente')
    args = parser.parse_args()
    from limpiezasoft.datos.repositorio import Repositorio, ErrorDatos
    repo = Repositorio()
    if args.init_db:
        from limpiezasoft.config import ROOT
        try:
            with repo.sesion(escritura=True) as conn:
                conn.execute((ROOT / 'db.sql').read_text(encoding='utf-8'))
        except ErrorDatos as exc:
            print(f'No se pudo inicializar: {exc}', file=sys.stderr)
            return 1
        print('Tablas creadas correctamente en PostgreSQL.')
        return 0
    from PySide6.QtWidgets import QApplication
    from limpiezasoft.negocio.servicios import ServicioGestion
    from limpiezasoft.ui.ventana import VentanaPrincipal
    from limpiezasoft.ui.tema import TEMA
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(TEMA)
    ventana = VentanaPrincipal(ServicioGestion(repo))
    ventana.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
