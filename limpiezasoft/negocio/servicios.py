"""Casos de uso: valida primero y persiste dentro de una única transacción."""
import hashlib
import re
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from limpiezasoft.negocio.modelos import ENTIDADES, etiqueta
from limpiezasoft.negocio.equipo import roles_laborales


class ErrorValidacion(ValueError):
    pass


def limites_semana(referencia=None):
    """Lunes inclusivo a lunes siguiente exclusivo, según la hora local del equipo."""
    referencia = referencia or date.today()
    lunes = referencia - timedelta(days=referencia.weekday())
    # Convertir ambos límites por separado respeta cambios de huso entre fechas.
    inicio = datetime.combine(lunes, time.min).astimezone()
    fin = datetime.combine(lunes + timedelta(days=7), time.min).astimezone()
    return inicio, fin


def validar(entidad, entrada, editando=False):
    salida = {}
    for campo in entidad.campos:
        if campo.calculado:
            continue
        valor = entrada.get(campo.nombre)
        if isinstance(valor, str):
            valor = valor if campo.tipo == 'password' else valor.strip()
        if campo.tipo == 'password' and editando and not valor:
            continue
        if valor is None or valor == '':
            if campo.requerido:
                raise ErrorValidacion(f'{etiqueta(campo.nombre)} es obligatorio.')
            salida[campo.nombre] = None
            continue
        try:
            if campo.tipo in ('decimal', 'entero'):
                numero = Decimal(str(valor).replace(',', '.'))
                if not numero.is_finite():
                    raise ValueError()
                if campo.tipo == 'entero':
                    if numero != numero.to_integral_value() or not 0 <= numero <= 2147483647:
                        raise ValueError()
                    valor = int(numero)
                else:
                    if numero < 0 or numero > Decimal('9999999999.99') or numero != numero.quantize(Decimal('.01')):
                        raise ValueError()
                    valor = numero
            elif campo.tipo == 'fecha':
                valor = valor if isinstance(valor, datetime) else datetime.fromisoformat(valor)
                if valor.tzinfo is None or valor.utcoffset() is None:
                    raise ErrorValidacion('La fecha debe incluir zona horaria, por ejemplo -03:00.')
            elif campo.tipo == 'booleano':
                if not isinstance(valor, bool):
                    raise ValueError()
            elif campo.tipo == 'color':
                if not isinstance(valor, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', valor):
                    raise ErrorValidacion('Selecciona un color válido en formato #RRGGBB.')
                valor = valor.upper()
            elif campo.tipo == 'password':
                if len(valor) < 8:
                    raise ErrorValidacion('La contraseña debe tener al menos 8 caracteres.')
                salt = secrets.token_hex(16)
                digest = hashlib.pbkdf2_hmac('sha256', valor.encode(), bytes.fromhex(salt), 600000).hex()
                valor = f'pbkdf2_sha256$600000${salt}${digest}'
            if campo.largo and len(str(valor)) > campo.largo:
                raise ErrorValidacion(f'{etiqueta(campo.nombre)} admite hasta {campo.largo} caracteres.')
        except (InvalidOperation, ValueError, TypeError) as exc:
            if isinstance(exc, ErrorValidacion):
                raise
            raise ErrorValidacion(f'{etiqueta(campo.nombre)}: introduce un valor válido, no negativo y con hasta 2 decimales.') from exc
        if campo.nombre in ('cantidad', 'monto_pagado') and valor <= 0:
            raise ErrorValidacion(f'{etiqueta(campo.nombre)} debe ser mayor que cero.')
        if campo.nombre == 'descuento_porcentaje' and not 0 <= valor <= 100:
            raise ErrorValidacion('El descuento debe estar entre 0 y 100.')
        if campo.nombre == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', valor):
            raise ErrorValidacion('Introduce un correo electrónico válido.')
        salida[campo.nombre] = valor
    return salida


class ServicioGestion:
    def __init__(self, repositorio):
        self.repo = repositorio

    def listar(self, tabla, busqueda='', pagina=0):
        with self.repo.sesion() as conn:
            return self.repo.listar(conn, ENTIDADES[tabla], busqueda, 100, pagina * 100)

    def opciones(self, tabla):
        with self.repo.sesion() as conn:
            return self.repo.opciones(conn, ENTIDADES[tabla])

    def opciones_formulario(self, tabla):
        referencias = {c.referencia for c in ENTIDADES[tabla].campos if c.referencia}
        with self.repo.sesion() as conn:
            opciones = {ref: self.repo.opciones(conn, ENTIDADES[ref]) for ref in referencias}
            if tabla == 'empleados':
                opciones['roles'] = roles_laborales(self.repo.asociaciones_roles(conn))
            return opciones

    def resumen(self):
        with self.repo.sesion() as conn:
            return self.repo.resumen(conn)

    def agenda_semanal(self, referencia=None):
        inicio, fin = limites_semana(referencia)
        with self.repo.sesion() as conn:
            servicios = self.repo.agenda_semanal(conn, inicio, fin)
        return dict(inicio=inicio, fin=fin, servicios=servicios)

    def guardar(self, tabla, entrada, anterior=None):
        entidad = ENTIDADES[tabla]
        valores = validar(entidad, entrada, anterior is not None)
        with self.repo.sesion(escritura=True) as conn:
            if tabla == 'empleados':
                roles = roles_laborales(self.repo.asociaciones_roles(conn))
                asignacion = next((r for r in roles if r['id'] == valores['rol_id']), None)
                if asignacion is None:
                    raise ErrorValidacion('El rol elegido no tiene el departamento configurado. '
                                          'Actualiza los catálogos con la migración de roles de empleados.')
                # El departamento se deriva aquí, sin confiar en el valor enviado por la UI.
                valores['departamento_id'] = asignacion['departamento_id']
            self.repo.guardar(conn, entidad, valores, anterior)
            self._actualizar_totales(conn, tabla, valores, anterior)

    def eliminar(self, tabla, anterior):
        with self.repo.sesion(escritura=True) as conn:
            self.repo.eliminar(conn, ENTIDADES[tabla], anterior)
            self._actualizar_totales(conn, tabla, {}, anterior)

    def _actualizar_totales(self, conn, tabla, valores, anterior):
        campo = {'detalle_ventas': 'venta_id', 'detalle_compras': 'orden_id',
                 'pagos_proveedores': 'orden_id'}.get(tabla)
        if not campo:
            return
        padres = {registro[campo] for registro in (valores, anterior or {}) if campo in registro}
        for padre in sorted(padres):
            self.repo.recalcular(conn, tabla, padre)
            if campo == 'orden_id':
                saldo = self.repo.saldo_orden(conn, padre)
                if saldo and saldo['pagado'] > saldo['total']:
                    raise ErrorValidacion('La operación dejaría pagos superiores al total de la orden.')
