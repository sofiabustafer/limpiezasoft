
CREATE TABLE departamentos (
    departamento_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_departamento VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE roles (
    rol_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_rol VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE departamentos_roles (
    departamento_id INT NOT NULL REFERENCES departamentos(departamento_id) ON DELETE CASCADE,
    rol_id INT NOT NULL REFERENCES roles(rol_id) ON DELETE CASCADE,
    PRIMARY KEY (departamento_id, rol_id)
);

CREATE TABLE empleados (
    empleado_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    departamento_id INT NOT NULL REFERENCES departamentos(departamento_id),
    cedula VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    telefono VARCHAR(20)
);

CREATE TABLE usuarios (
    usuario_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    empleado_id INT UNIQUE NOT NULL REFERENCES empleados(empleado_id),
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE usuario_roles (
    usuario_id INT NOT NULL REFERENCES usuarios(usuario_id) ON DELETE CASCADE,
    rol_id INT NOT NULL REFERENCES roles(rol_id) ON DELETE CASCADE,
    PRIMARY KEY (usuario_id, rol_id)
);

CREATE TABLE categorias_clientes (
    categoria_cliente_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_categoria VARCHAR(50) UNIQUE NOT NULL,
    descuento_porcentaje NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (descuento_porcentaje BETWEEN 0 AND 100)
);

CREATE TABLE clientes (
    cliente_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria_cliente_id INT NOT NULL REFERENCES categorias_clientes(categoria_cliente_id), -- Corregido: solo FK
    ruc_ci VARCHAR(20) UNIQUE NOT NULL,
    nombre_razon_social VARCHAR(150) NOT NULL,
    telefono VARCHAR(20),
    direccion TEXT
);

CREATE TABLE proveedores (
    proveedor_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ruc VARCHAR(20) UNIQUE NOT NULL,
    razon_social VARCHAR(150) NOT NULL,
    contacto VARCHAR(100),
    telefono VARCHAR(20)
);

CREATE TABLE categorias_productos (
    categoria_prod_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_categoria VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE productos (
    producto_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria_prod_id INT NOT NULL REFERENCES categorias_productos(categoria_prod_id),
    codigo_barra VARCHAR(50) UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    precio_venta NUMERIC(12,2) NOT NULL CHECK (precio_venta >= 0)
);

CREATE TABLE depositos (
    deposito_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_deposito VARCHAR(100) UNIQUE NOT NULL,
    ubicacion VARCHAR(150)
);

CREATE TABLE inventario_stock (
    inventario_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto_id INT NOT NULL REFERENCES productos(producto_id),
    deposito_id INT NOT NULL REFERENCES depositos(deposito_id),
    cantidad_stock INT NOT NULL DEFAULT 0 CHECK (cantidad_stock >= 0),
    CONSTRAINT uq_producto_deposito UNIQUE (producto_id, deposito_id)
);

CREATE TABLE servicios_catalogo (
    servicio_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_servicio VARCHAR(100) UNIQUE NOT NULL,
    precio_base NUMERIC(12,2) NOT NULL CHECK (precio_base >= 0)
);

CREATE TABLE estados_servicio (
    estado_servicio_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_estado VARCHAR(30) UNIQUE NOT NULL
);

CREATE TABLE calendario_servicios (
    calendario_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id INT NOT NULL REFERENCES clientes(cliente_id),
    servicio_id INT NOT NULL REFERENCES servicios_catalogo(servicio_id),
    limpiadora_id INT NOT NULL REFERENCES empleados(empleado_id),
    estado_servicio_id INT NOT NULL REFERENCES estados_servicio(estado_servicio_id),
    fecha_programada TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE facturas_servicios (
    factura_servicio_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    calendario_id INT UNIQUE NOT NULL REFERENCES calendario_servicios(calendario_id),
    monto_total NUMERIC(12,2) NOT NULL CHECK (monto_total >= 0),
    fecha_emision TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ventas (
    venta_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id INT REFERENCES clientes(cliente_id),
    monto_total NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (monto_total >= 0),
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE detalle_ventas (
    detalle_venta_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    venta_id INT NOT NULL REFERENCES ventas(venta_id) ON DELETE CASCADE,
    producto_id INT NOT NULL REFERENCES productos(producto_id),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(12,2) NOT NULL CHECK (precio_unitario >= 0),
    subtotal NUMERIC(12,2) GENERATED ALWAYS AS (cantidad * precio_unitario) STORED
);

CREATE TABLE estados_orden (
    estado_orden_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_estado VARCHAR(30) UNIQUE NOT NULL
);

CREATE TABLE metodos_pago (
    metodo_pago_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_metodo VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE ordenes_compra (
    orden_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    proveedor_id INT NOT NULL REFERENCES proveedores(proveedor_id),
    estado_orden_id INT NOT NULL REFERENCES estados_orden(estado_orden_id),
    total NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (total >= 0),
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE detalle_compras (
    detalle_compra_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_id INT NOT NULL REFERENCES ordenes_compra(orden_id) ON DELETE CASCADE,
    producto_id INT NOT NULL REFERENCES productos(producto_id),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_costo NUMERIC(12,2) NOT NULL CHECK (precio_costo >= 0)
);

CREATE TABLE pagos_proveedores (
    pago_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_id INT NOT NULL REFERENCES ordenes_compra(orden_id),
    metodo_pago_id INT NOT NULL REFERENCES metodos_pago(metodo_pago_id),
    monto_pagado NUMERIC(12,2) NOT NULL CHECK (monto_pagado > 0),
    fecha_pago TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE conciliaciones_inventario (
    conciliacion_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    deposito_id INT NOT NULL REFERENCES depositos(deposito_id),
    producto_id INT NOT NULL REFERENCES productos(producto_id),
    stock_sistema INT NOT NULL CHECK (stock_sistema >= 0),
    stock_fisico INT NOT NULL CHECK (stock_fisico >= 0),
    diferencia INT GENERATED ALWAYS AS (stock_fisico - stock_sistema) STORED,
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
