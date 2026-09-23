"""Consultas parametrizadas y unidad de trabajo PostgreSQL."""
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from limpiezasoft.config import database_settings


class ErrorDatos(Exception):
    pass


class Repositorio:
    @contextmanager
    def sesion(self, escritura=False):
        try:
            with psycopg.connect(**database_settings(), row_factory=dict_row) as conn:
                if escritura:
                    # Serializa las escrituras de esta aplicación, incluidos totales y pagos.
                    conn.execute('SELECT pg_advisory_xact_lock(20260923)')
                yield conn
        except psycopg.errors.UniqueViolation as exc:
            raise ErrorDatos('Ya existe un registro con esos datos únicos.') from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise ErrorDatos('Hay registros relacionados o la referencia ya no existe.') from exc
        except psycopg.errors.NotNullViolation as exc:
            campo = exc.diag.column_name
            detalle = f' «{campo}»' if campo else ''
            raise ErrorDatos(f'Falta completar un campo obligatorio{detalle}. '
                             'Si no aparece en el formulario, revisa que la aplicación y el esquema estén actualizados.') from exc
        except psycopg.errors.CheckViolation as exc:
            raise ErrorDatos('Los valores no cumplen las restricciones de la base de datos.') from exc
        except psycopg.errors.UndefinedTable as exc:
            raise ErrorDatos('Faltan tablas. Inicializa la base con python main.py --init-db.') from exc
        except psycopg.errors.DuplicateTable as exc:
            raise ErrorDatos('Las tablas ya existen. Omite --init-db y ejecuta python main.py.') from exc
        except psycopg.OperationalError as exc:
            raise ErrorDatos('No se pudo conectar o completar la operación. Revisa PostgreSQL y el archivo .env.') from exc
        except psycopg.Error as exc:
            raise ErrorDatos('PostgreSQL rechazó la operación. Revisa los datos y el esquema de db.sql.') from exc

    def listar(self, conn, entidad, busqueda='', limite=100, offset=0):
        columnas = [c.nombre for c in entidad.campos if c.tipo != 'password']
        filtro = sql.SQL(' OR ').join(
            sql.SQL('CAST({} AS TEXT) ILIKE %s').format(sql.Identifier(c)) for c in columnas)
        parametros = ['%' + busqueda + '%'] * len(columnas)
        base = sql.SQL(' FROM {} WHERE ({})').format(sql.Identifier(entidad.tabla), filtro)
        total = conn.execute(sql.SQL('SELECT COUNT(*) AS n') + base, parametros).fetchone()['n']
        consulta = (sql.SQL('SELECT {}').format(sql.SQL(', ').join(map(sql.Identifier, columnas)))
                    + base + sql.SQL(' ORDER BY {} LIMIT %s OFFSET %s').format(
                        sql.SQL(', ').join(map(sql.Identifier, entidad.clave))))
        return conn.execute(consulta, parametros + [limite, offset]).fetchall(), total

    def opciones(self, conn, entidad):
        campos = [c.nombre for c in entidad.campos if c.tipo == 'texto']
        nombre = next((c for c in campos if c.startswith('nombre') or c == 'razon_social'),
                      campos[0] if campos else entidad.clave[0])
        consulta = sql.SQL('SELECT {id} AS id, CAST({nombre} AS TEXT) AS nombre FROM {tabla} ORDER BY {id}').format(
            id=sql.Identifier(entidad.clave[0]), nombre=sql.Identifier(nombre), tabla=sql.Identifier(entidad.tabla))
        return conn.execute(consulta).fetchall()

    def asociaciones_roles(self, conn):
        return conn.execute('''
            SELECT r.rol_id AS id, r.nombre_rol AS nombre,
                   d.departamento_id, d.nombre_departamento AS departamento_nombre
            FROM roles r
            JOIN departamentos_roles dr ON dr.rol_id = r.rol_id
            JOIN departamentos d ON d.departamento_id = dr.departamento_id
            ORDER BY r.rol_id, d.departamento_id
        ''').fetchall()

    def guardar(self, conn, entidad, valores, anterior=None):
        campos = list(valores)
        if anterior is None:
            consulta = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                sql.Identifier(entidad.tabla), sql.SQL(', ').join(map(sql.Identifier, campos)),
                sql.SQL(', ').join(sql.Placeholder() for _ in campos))
            parametros = list(valores.values())
        else:
            consulta = sql.SQL('UPDATE {} SET {} WHERE {}').format(
                sql.Identifier(entidad.tabla),
                sql.SQL(', ').join(sql.SQL('{} = %s').format(sql.Identifier(c)) for c in campos),
                self._condicion(entidad))
            parametros = list(valores.values()) + [anterior[k] for k in entidad.clave]
        cursor = conn.execute(consulta, parametros)
        if anterior is not None and cursor.rowcount != 1:
            raise ErrorDatos('El registro ya no existe. Actualiza la lista.')

    def eliminar(self, conn, entidad, anterior):
        cursor = conn.execute(sql.SQL('DELETE FROM {} WHERE {}').format(
            sql.Identifier(entidad.tabla), self._condicion(entidad)),
            [anterior[k] for k in entidad.clave])
        if cursor.rowcount != 1:
            raise ErrorDatos('El registro ya no existe. Actualiza la lista.')

    @staticmethod
    def _condicion(entidad):
        return sql.SQL(' AND ').join(sql.SQL('{} = %s').format(sql.Identifier(k)) for k in entidad.clave)

    def recalcular(self, conn, tabla, id_padre):
        if tabla == 'detalle_ventas':
            conn.execute('UPDATE ventas SET monto_total = (SELECT COALESCE(SUM(subtotal), 0) '
                         'FROM detalle_ventas WHERE venta_id = %s) WHERE venta_id = %s', (id_padre, id_padre))
        elif tabla == 'detalle_compras':
            conn.execute('UPDATE ordenes_compra SET total = (SELECT COALESCE(SUM(cantidad * precio_costo), 0) '
                         'FROM detalle_compras WHERE orden_id = %s) WHERE orden_id = %s', (id_padre, id_padre))

    def saldo_orden(self, conn, orden_id):
        return conn.execute('SELECT o.total, COALESCE(SUM(p.monto_pagado), 0) AS pagado '
                            'FROM ordenes_compra o LEFT JOIN pagos_proveedores p USING (orden_id) '
                            'WHERE o.orden_id = %s GROUP BY o.orden_id', (orden_id,)).fetchone()

    def resumen(self, conn):
        return conn.execute('SELECT (SELECT COUNT(*) FROM clientes) AS clientes, '
                            '(SELECT COUNT(*) FROM empleados) AS empleados, '
                            '(SELECT COUNT(*) FROM calendario_servicios WHERE fecha_programada >= CURRENT_TIMESTAMP) AS agenda, '
                            '(SELECT COALESCE(SUM(monto_total), 0) FROM ventas) AS ventas').fetchone()

    def agenda_semanal(self, conn, inicio, fin):
        return conn.execute('''
            SELECT a.*, c.nombre_razon_social AS cliente_nombre,
                   c.ruc_ci AS cliente_documento, c.telefono AS cliente_telefono,
                   c.direccion AS cliente_direccion,
                   s.nombre_servicio AS servicio_nombre, s.precio_base,
                   e.nombre AS limpiadora_nombre, e.telefono AS limpiadora_telefono,
                   estado.nombre_estado, estado.color AS estado_color,
                   f.factura_servicio_id, f.monto_total AS factura_monto,
                   f.fecha_emision AS factura_fecha
            FROM calendario_servicios a
            JOIN clientes c ON c.cliente_id = a.cliente_id
            JOIN servicios_catalogo s ON s.servicio_id = a.servicio_id
            LEFT JOIN empleados e ON e.empleado_id = a.limpiadora_id
            JOIN estados_servicio estado ON estado.estado_servicio_id = a.estado_servicio_id
            LEFT JOIN facturas_servicios f ON f.calendario_id = a.calendario_id
            WHERE a.fecha_programada >= %s AND a.fecha_programada < %s
            ORDER BY a.fecha_programada, a.calendario_id
        ''', (inicio, fin)).fetchall()
