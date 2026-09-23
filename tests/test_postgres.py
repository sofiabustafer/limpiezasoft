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
                            '#087F72' if campo.tipo == 'color' else
                            '2026-09-23T10:00:00-03:00' if campo.tipo == 'fecha' else
                            '5' if campo.tipo in ('decimal', 'entero') else
                            'persona@example.com' if campo.nombre == 'email' else
                            'Prueba12345')
                    if entidad.tabla == 'departamentos':
                        datos['nombre_departamento'] = 'Clientes'
                    elif entidad.tabla == 'roles':
                        datos['nombre_rol'] = 'Limpiador'
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

                # Límites inclusivo/exclusivo de semana y color actualizado por JOIN.
                from datetime import date, timedelta
                from limpiezasoft.negocio.servicios import limites_semana
                referencia = date(2026, 9, 23)
                inicio, fin = limites_semana(referencia)
                iniciales = servicio.agenda_semanal(referencia)['servicios']
                for fecha in (inicio - timedelta(seconds=1), inicio,
                              fin - timedelta(seconds=1), fin):
                    servicio.guardar('calendario_servicios', dict(cliente_id=1, servicio_id=1,
                                     limpiadora_id=1, estado_servicio_id=1, fecha_programada=fecha))
                semana = servicio.agenda_semanal(referencia)['servicios']
                self.assertEqual(len(semana), len(iniciales) + 2)
                self.assertEqual(semana[0]['fecha_programada'], inicio)
                self.assertEqual(semana[-1]['fecha_programada'], fin - timedelta(seconds=1))
                self.assertEqual(len({s['calendario_id'] for s in semana}), len(semana))
                self.assertTrue(any(s['factura_servicio_id'] is not None for s in semana))
                self.assertTrue(any(s['factura_servicio_id'] is None for s in semana))
                estado = servicio.listar('estados_servicio')[0][0]
                servicio.guardar('estados_servicio', dict(nombre_estado='Confirmado', color='#ffcc00'), estado)
                self.assertTrue(all(s['estado_color'] == '#FFCC00' for s in servicio.agenda_semanal(referencia)['servicios']))
                conn.execute((ROOT / 'migrations/001_color_estados_servicio.sql').read_text(encoding='utf-8'))
                self.assertEqual(servicio.listar('estados_servicio')[0][0]['color'], '#FFCC00')

                # La migración añade catálogos sin modificar empleados anteriores.
                from limpiezasoft.negocio.equipo import ROLES_DEPARTAMENTOS
                conn.execute("INSERT INTO departamentos(nombre_departamento) VALUES ('Administracion')")
                conn.execute("INSERT INTO empleados(departamento_id,cedula,nombre) VALUES (1,'LEGADO','Empleado anterior')")
                anteriores = conn.execute('SELECT * FROM empleados ORDER BY empleado_id').fetchall()
                migracion = (ROOT / 'migrations/002_roles_empleados.sql').read_text(encoding='utf-8')
                conn.execute(migracion)
                conn.execute(migracion)
                self.assertEqual(conn.execute('SELECT * FROM empleados ORDER BY empleado_id').fetchall(), anteriores)
                self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM departamentos WHERE nombre_departamento IN ('Administracion','Administración')").fetchone()['n'], 1)
                opciones = servicio.opciones_formulario('empleados')
                self.assertEqual([(r['nombre'], r['departamento_nombre']) for r in opciones['roles']], list(ROLES_DEPARTAMENTOS))
                for i, rol in enumerate(opciones['roles']):
                    servicio.guardar('empleados', dict(cedula=f'ROL-{i}', nombre='Empleado de prueba', rol_id=rol['id'], departamento_id=-1))
                    empleado = servicio.listar('empleados', f'ROL-{i}')[0][0]
                    self.assertEqual(empleado['rol_id'], rol['id'])
                    self.assertEqual(empleado['departamento_id'], rol['departamento_id'])
                primero = servicio.listar('empleados', 'ROL-0')[0][0]
                ultimo_rol = opciones['roles'][-1]
                servicio.guardar('empleados', dict(cedula='ROL-0',nombre='Empleado de prueba',rol_id=ultimo_rol['id']), primero)
                self.assertEqual(servicio.listar('empleados','ROL-0')[0][0]['departamento_id'], ultimo_rol['departamento_id'])
                self.assertEqual(conn.execute("SELECT rol_id FROM empleados WHERE cedula='LEGADO'").fetchone()['rol_id'], None)
