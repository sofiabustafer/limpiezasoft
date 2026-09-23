import unittest
from contextlib import contextmanager
from decimal import Decimal
from datetime import date

from limpiezasoft.negocio.modelos import ENTIDADES
from limpiezasoft.negocio.servicios import ErrorValidacion, ServicioGestion, validar, limites_semana


class ValidacionTests(unittest.TestCase):
    def test_color_hexadecimal(self):
        salida = validar(ENTIDADES['estados_servicio'], dict(nombre_estado='Pendiente', color='#ab12ef'))
        self.assertEqual(salida['color'], '#AB12EF')
        for color in ('rojo', '#123', '#12345678', '#GG1122', ''):
            with self.subTest(color=color), self.assertRaises(ErrorValidacion):
                validar(ENTIDADES['estados_servicio'], dict(nombre_estado='Pendiente', color=color))

    def test_semana_lunes_domingo_y_cambio_de_ano(self):
        for referencia, esperado in ((date(2026, 9, 21), date(2026, 9, 21)),
                                    (date(2026, 9, 27), date(2026, 9, 21)),
                                    (date(2027, 1, 1), date(2026, 12, 28))):
            inicio, fin = limites_semana(referencia)
            self.assertEqual(inicio.date(), esperado)
            self.assertEqual((fin.date() - inicio.date()).days, 7)
            self.assertEqual((inicio.hour, inicio.minute, fin.hour, fin.minute), (0, 0, 0, 0))
            self.assertIsNotNone(inicio.utcoffset())

    def test_importe_exacto_y_coma_decimal(self):
        datos = validar(ENTIDADES['productos'], dict(categoria_prod_id=1, nombre='Jabón', precio_venta='12,35'))
        self.assertEqual(datos['precio_venta'], Decimal('12.35'))
        self.assertIsNone(datos['codigo_barra'])

    def test_rechaza_importes_invalidos(self):
        for valor in ['-1', 'NaN', 'Infinity', '1.001', '10000000000']:
            with self.subTest(valor=valor), self.assertRaises(ErrorValidacion):
                validar(ENTIDADES['servicios_catalogo'], dict(nombre_servicio='Limpieza', precio_base=valor))

    def test_descuento_limites(self):
        for valor in ['-1', '100.01']:
            with self.assertRaises(ErrorValidacion):
                validar(ENTIDADES['categorias_clientes'], dict(nombre_categoria='Especial', descuento_porcentaje=valor))

    def test_cantidad_no_puede_ser_cero_ni_fraccion(self):
        for valor in ['0', '1.5']:
            with self.assertRaises(ErrorValidacion):
                validar(ENTIDADES['detalle_ventas'], dict(venta_id=1, producto_id=2, cantidad=valor, precio_unitario='20'))

    def test_campos_generados_no_se_escriben(self):
        datos = validar(ENTIDADES['ventas'], dict(venta_id=4, monto_total=999, fecha='2026-09-23T10:00:00-03:00'))
        self.assertNotIn('venta_id', datos)
        self.assertNotIn('monto_total', datos)

    def test_fecha_debe_tener_zona(self):
        with self.assertRaises(ErrorValidacion):
            validar(ENTIDADES['ventas'], dict(fecha='2026-09-23T10:00:00'))

    def test_agenda_exige_limpiadora_y_conserva_fecha(self):
        entrada = dict(cliente_id=1, servicio_id=2, estado_servicio_id=1,
                       fecha_programada='2026-09-23T14:30:00-03:00')
        with self.assertRaisesRegex(ErrorValidacion, 'Limpiadora es obligatorio'):
            validar(ENTIDADES['calendario_servicios'], entrada)
        entrada['limpiadora_id'] = 3
        salida = validar(ENTIDADES['calendario_servicios'], entrada)
        self.assertEqual(salida['limpiadora_id'], 3)
        self.assertEqual(salida['fecha_programada'].isoformat(), entrada['fecha_programada'])

    def test_password_se_hashea_y_se_conserva_al_editar(self):
        entrada = dict(empleado_id=1, email='persona@example.com', password_hash='ClaveDePrueba123', activo=True)
        salida = validar(ENTIDADES['usuarios'], entrada)
        self.assertTrue(salida['password_hash'].startswith('pbkdf2_sha256$600000$'))
        self.assertNotIn(entrada['password_hash'], salida['password_hash'])
        entrada['password_hash'] = ''
        self.assertNotIn('password_hash', validar(ENTIDADES['usuarios'], entrada, editando=True))


class RepoPrueba:
    def __init__(self):
        self.padres = []
        self.rollback = False

    @contextmanager
    def sesion(self, escritura=False):
        try:
            yield self
        except Exception:
            self.rollback = True
            raise

    def guardar(self, *args):
        pass

    def recalcular(self, conn, tabla, padre):
        self.padres.append(padre)

    def saldo_orden(self, conn, padre):
        return dict(total=Decimal('100'), pagado=Decimal('110'))


class TransaccionTests(unittest.TestCase):
    def test_recalcula_padre_original_y_nuevo(self):
        repo = RepoPrueba()
        ServicioGestion(repo).guardar('detalle_ventas', dict(venta_id=2, producto_id=1, cantidad=1, precio_unitario=10), dict(detalle_venta_id=1, venta_id=1))
        self.assertEqual(repo.padres, [1, 2])

    def test_sobrepago_aborta_transaccion(self):
        repo = RepoPrueba()
        with self.assertRaises(ErrorValidacion):
            ServicioGestion(repo).guardar('pagos_proveedores', dict(orden_id=1, metodo_pago_id=1, monto_pagado=110, fecha_pago='2026-09-23T10:00:00-03:00'))
        self.assertTrue(repo.rollback)


if __name__ == '__main__':
    unittest.main()
