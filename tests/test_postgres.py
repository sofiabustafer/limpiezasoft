"""Integración optativa en un esquema aislado, eliminado por rollback."""
import os
import unittest
import uuid
from contextlib import contextmanager


@unittest.skipUnless(os.getenv('RUN_DB_TESTS') == '1', 'Requiere RUN_DB_TESTS=1 y PostgreSQL')
class PostgreSQLTests(unittest.TestCase):
    def test_error_campo_obligatorio_informa_columna(self):
        from limpiezasoft.datos.repositorio import Repositorio, ErrorDatos
        with self.assertRaisesRegex(ErrorDatos, 'limpiadora_id'):
            with Repositorio().sesion() as conn:
                conn.execute('CREATE TEMP TABLE prueba_campo_obligatorio (limpiadora_id INT NOT NULL)')
                conn.execute('INSERT INTO prueba_campo_obligatorio DEFAULT VALUES')

    def test_crud_totales_pago_y_esquema(self):
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
        from limpiezasoft.config import ROOT, database_settings
        from limpiezasoft.datos.repositorio import Repositorio
        from limpiezasoft.negocio.modelos import ENTIDADES
        from limpiezasoft.negocio.servicios import ServicioGestion, ErrorValidacion

        with psycopg.connect(**database_settings(), row_factory=dict_row) as conn:
            with conn.transaction(force_rollback=True):
                esquema = 'test_limpiezasoft_' + uuid.uuid4().hex
                conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(esquema)))
                conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(esquema)))
                conn.execute((ROOT / 'db.sql').read_text(encoding='utf-8'))

                class RepoAislado(Repositorio):
                    @contextmanager
                    def sesion(self, escritura=False):
                        with conn.transaction():
                            yield conn

                repo = RepoAislado()
                servicio = ServicioGestion(repo)
                for entidad in ENTIDADES.values():
                    columnas = conn.execute('SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position', (esquema, entidad.tabla)).fetchall()
                    self.assertEqual([c.nombre for c in entidad.campos], [c['column_name'] for c in columnas])
                    datos = {}
                    for campo in entidad.campos:
                        if campo.calculado:
                            continue
                        datos[campo.nombre] = (1 if campo.referencia else
                            True if campo.tipo == 'booleano' else
                            '2026-09-23T10:00:00-03:00' if campo.tipo == 'fecha' else
                            '5' if campo.tipo in ('decimal', 'entero') else
                            'persona@example.com' if campo.nombre == 'email' else
                            'Prueba12345')
                    servicio.guardar(entidad.tabla, datos)
                    filas, total = servicio.listar(entidad.tabla)
                    self.assertEqual(total, 1, entidad.tabla)
                    if entidad.tabla == 'usuarios':
                        self.assertNotIn('password_hash', filas[0])
                    servicio.guardar(entidad.tabla, datos, filas[0])
                    if len(entidad.clave) == 1:
                        self.assertEqual(len(servicio.opciones(entidad.tabla)), 1)

                venta = servicio.listar('ventas')[0][0]
                self.assertEqual(venta['monto_total'], 25)
                orden = servicio.listar('ordenes_compra')[0][0]
                self.assertEqual(orden['total'], 25)
                with self.assertRaises(ErrorValidacion):
                    servicio.guardar('pagos_proveedores', dict(orden_id=1, metodo_pago_id=1, monto_pagado=30, fecha_pago='2026-09-23T10:00:00-03:00'))
                self.assertEqual(servicio.listar('pagos_proveedores')[1], 1)
                detalle = servicio.listar('detalle_compras')[0][0]
                with self.assertRaises(ErrorValidacion):
                    servicio.eliminar('detalle_compras', detalle)
                self.assertEqual(servicio.listar('detalle_compras')[1], 1)
                detalle = servicio.listar('detalle_ventas')[0][0]
                servicio.eliminar('detalle_ventas', detalle)
                self.assertEqual(servicio.listar('ventas')[0][0]['monto_total'], 0)
                self.assertEqual(servicio.listar('clientes', "' OR 1=1 --")[1], 0)

                # Reproduce el guardado desde el formulario Qt, incluida la fecha local.
                os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
                from PySide6.QtCore import QDateTime
                from PySide6.QtWidgets import QApplication
                from limpiezasoft.ui.ventana import Formulario
                app = QApplication.instance() or QApplication([])
                entidad = ENTIDADES['calendario_servicios']
                opciones = {c.referencia: servicio.opciones(c.referencia)
                            for c in entidad.campos if c.referencia}
                formulario = Formulario(entidad, opciones)
                for nombre in ('cliente_id', 'servicio_id', 'limpiadora_id', 'estado_servicio_id'):
                    formulario.editores[nombre].setCurrentIndex(1)
                instante = 1790184600
                formulario.editores['fecha_programada'].setDateTime(QDateTime.fromSecsSinceEpoch(instante))
                servicio.guardar(entidad.tabla, formulario.valores())
                agenda = servicio.listar(entidad.tabla)[0][-1]
                self.assertEqual(agenda['limpiadora_id'], 1)
                self.assertEqual(agenda['fecha_programada'].timestamp(), instante)
                edicion = Formulario(entidad, opciones, agenda)
                servicio.guardar(entidad.tabla, edicion.valores(), agenda)
                self.assertEqual(servicio.listar(entidad.tabla)[0][-1]['fecha_programada'].timestamp(), instante)
                formulario.close()
                edicion.close()
