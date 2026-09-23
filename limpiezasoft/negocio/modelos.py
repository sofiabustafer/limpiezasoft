"""Metadatos del esquema original: formularios y validación sin dependencias GUI/SQL."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Campo:
    nombre: str
    tipo: str = 'texto'
    requerido: bool = True
    largo: int = 0
    referencia: str = ''
    calculado: bool = False


@dataclass(frozen=True)
class Entidad:
    tabla: str
    titulo: str
    grupo: str
    clave: tuple[str, ...]
    campos: tuple[Campo, ...]


def c(nombre, tipo='texto', requerido=True, largo=0, referencia='', calculado=False):
    return Campo(nombre, tipo, requerido, largo, referencia, calculado)


def fk(nombre, tabla, requerido=True):
    return c(nombre, 'entero', requerido, referencia=tabla)


ENTIDADES = {}


def entidad(tabla, titulo, grupo, clave, *campos):
    claves = (clave,) if isinstance(clave, str) else clave
    if len(claves) == 1:
        campos = (c(claves[0], 'entero', calculado=True),) + campos
    ENTIDADES[tabla] = Entidad(tabla, titulo, grupo, claves, campos)


entidad('departamentos', 'Departamentos', 'Equipo', 'departamento_id', c('nombre_departamento', largo=100))
entidad('roles', 'Roles', 'Equipo', 'rol_id', c('nombre_rol', largo=50))
entidad('departamentos_roles', 'Roles por departamento', 'Equipo', ('departamento_id', 'rol_id'), fk('departamento_id', 'departamentos'), fk('rol_id', 'roles'))
entidad('empleados', 'Empleados', 'Equipo', 'empleado_id', fk('departamento_id', 'departamentos'), c('cedula', largo=20), c('nombre', largo=100), c('telefono', requerido=False, largo=20))
entidad('usuarios', 'Usuarios', 'Equipo', 'usuario_id', fk('empleado_id', 'empleados'), c('email', largo=100), c('password_hash', 'password', largo=255), c('activo', 'booleano'))
entidad('usuario_roles', 'Roles por usuario', 'Equipo', ('usuario_id', 'rol_id'), fk('usuario_id', 'usuarios'), fk('rol_id', 'roles'))
entidad('categorias_clientes', 'Categorías de clientes', 'Clientes', 'categoria_cliente_id', c('nombre_categoria', largo=50), c('descuento_porcentaje', 'decimal'))
entidad('clientes', 'Clientes', 'Clientes', 'cliente_id', fk('categoria_cliente_id', 'categorias_clientes'), c('ruc_ci', largo=20), c('nombre_razon_social', largo=150), c('telefono', requerido=False, largo=20), c('direccion', requerido=False))
entidad('proveedores', 'Proveedores', 'Compras', 'proveedor_id', c('ruc', largo=20), c('razon_social', largo=150), c('contacto', requerido=False, largo=100), c('telefono', requerido=False, largo=20))
entidad('categorias_productos', 'Categorías de productos', 'Inventario', 'categoria_prod_id', c('nombre_categoria', largo=100))
entidad('productos', 'Productos', 'Inventario', 'producto_id', fk('categoria_prod_id', 'categorias_productos'), c('codigo_barra', requerido=False, largo=50), c('nombre', largo=100), c('precio_venta', 'decimal'))
entidad('depositos', 'Depósitos', 'Inventario', 'deposito_id', c('nombre_deposito', largo=100), c('ubicacion', requerido=False, largo=150))
entidad('inventario_stock', 'Stock por depósito', 'Inventario', 'inventario_id', fk('producto_id', 'productos'), fk('deposito_id', 'depositos'), c('cantidad_stock', 'entero'))
entidad('servicios_catalogo', 'Catálogo de servicios', 'Servicios', 'servicio_id', c('nombre_servicio', largo=100), c('precio_base', 'decimal'))
entidad('estados_servicio', 'Estados de servicio', 'Servicios', 'estado_servicio_id', c('nombre_estado', largo=30))
entidad('calendario_servicios', 'Agenda de servicios', 'Servicios', 'calendario_id', fk('cliente_id', 'clientes'), fk('servicio_id', 'servicios_catalogo'), fk('estado_servicio_id', 'estados_servicio'), c('fecha_programada', 'fecha'))
entidad('facturas_servicios', 'Facturas de servicios', 'Servicios', 'factura_servicio_id', fk('calendario_id', 'calendario_servicios'), c('monto_total', 'decimal'), c('fecha_emision', 'fecha'))
entidad('ventas', 'Ventas', 'Ventas', 'venta_id', fk('cliente_id', 'clientes', False), c('monto_total', 'decimal', calculado=True), c('fecha', 'fecha'))
entidad('detalle_ventas', 'Detalle de ventas', 'Ventas', 'detalle_venta_id', fk('venta_id', 'ventas'), fk('producto_id', 'productos'), c('cantidad', 'entero'), c('precio_unitario', 'decimal'), c('subtotal', 'decimal', calculado=True))
entidad('estados_orden', 'Estados de compra', 'Compras', 'estado_orden_id', c('nombre_estado', largo=30))
entidad('metodos_pago', 'Métodos de pago', 'Compras', 'metodo_pago_id', c('nombre_metodo', largo=50))
entidad('ordenes_compra', 'Órdenes de compra', 'Compras', 'orden_id', fk('proveedor_id', 'proveedores'), fk('estado_orden_id', 'estados_orden'), c('total', 'decimal', calculado=True), c('fecha', 'fecha'))
entidad('detalle_compras', 'Detalle de compras', 'Compras', 'detalle_compra_id', fk('orden_id', 'ordenes_compra'), fk('producto_id', 'productos'), c('cantidad', 'entero'), c('precio_costo', 'decimal'))
entidad('pagos_proveedores', 'Pagos a proveedores', 'Compras', 'pago_id', fk('orden_id', 'ordenes_compra'), fk('metodo_pago_id', 'metodos_pago'), c('monto_pagado', 'decimal'), c('fecha_pago', 'fecha'))
entidad('conciliaciones_inventario', 'Conciliaciones', 'Inventario', 'conciliacion_id', fk('deposito_id', 'depositos'), fk('producto_id', 'productos'), c('stock_sistema', 'entero'), c('stock_fisico', 'entero'), c('diferencia', 'entero', calculado=True), c('fecha', 'fecha'))


def etiqueta(nombre):
    if nombre == 'password_hash':
        return 'Contraseña'
    return nombre.removesuffix('_id').replace('_', ' ').capitalize()
