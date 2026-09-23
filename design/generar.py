"""Regenera documentación HTML y SVG sin dependencias externas ni acceso a la BD.

El diccionario y las relaciones se extraen del CREATE TABLE de db.sql.
Los casos de uso y secuencias describen la implementación revisada manualmente.
Ejecutar desde cualquier carpeta: python ruta/al/proyecto/design/generar.py
"""
from collections import defaultdict
from html import escape
from pathlib import Path
import re
import textwrap

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
SVG = BASE / 'svg'
SVG.mkdir(exist_ok=True)


def e(value):
    return escape(str(value), quote=True)


def read_schema():
    source = re.sub(r'--[^\n]*', '', (ROOT / 'db.sql').read_text(encoding='utf-8'))
    tables = {}
    relations = []
    for name, body in re.findall(r'CREATE TABLE\s+(\w+)\s*\((.*?)\n\);', source, re.S):
        columns = []
        constraints = []
        composite = re.search(r'^\s*PRIMARY KEY\s*\(([^)]+)\)', body, re.M)
        primary = [v.strip() for v in composite[1].split(',')] if composite else []
        for line in body.strip().splitlines():
            line = line.strip().rstrip(',')
            if line.startswith(('CONSTRAINT ', 'PRIMARY KEY ', 'UNIQUE ', 'CHECK ')):
                constraints.append(line)
                continue
            match = re.match(r'(\w+)\s+(TIMESTAMP WITH TIME ZONE|VARCHAR\(\d+\)|NUMERIC\(\d+,\d+\)|INT|TEXT|BOOLEAN)\s*(.*)', line)
            if not match:
                raise ValueError(f'Columna no reconocida en {name}: {line}')
            col, datatype, rules = match.groups()
            pk = 'PRIMARY KEY' in rules or col in primary
            ref = re.search(r'REFERENCES\s+(\w+)\((\w+)\)', rules)
            info = dict(name=col, datatype=datatype, rules=rules, pk=pk,
                        required=pk or 'NOT NULL' in rules, unique='UNIQUE' in rules,
                        generated='GENERATED ALWAYS AS (' in rules,
                        identity='AS IDENTITY' in rules, ref=ref.groups() if ref else None)
            columns.append(info)
            if ref:
                relations.append(dict(id=f'R{len(relations)+1:02}', parent=ref[1], child=name,
                                      column=col, target=ref[2], required=info['required'],
                                      unique=info['unique'], cascade='ON DELETE CASCADE' in rules))
        tables[name] = dict(name=name, columns=columns, constraints=constraints)
    if len(tables) != 25:
        raise ValueError('Se esperaban las 25 tablas del esquema revisado; actualizar el diseño.')
    return tables, relations


TABLES, RELATIONS = read_schema()


def text(x, y, value, size=14, color='#173047', anchor='start', weight='400'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{e(value)}</text>'


def rect(x, y, w, h, fill='#fff', stroke='#d7e4e9', radius=10):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def line(x1, y1, x2, y2, dashed=False, arrow=False, color='#6d8b98'):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.6"' + (' stroke-dasharray="6 5"' if dashed else '') + (' marker-end="url(#arrow)"' if arrow else '') + '/>'


def save_svg(name, title, description, width, height, content):
    document = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{e(title)}</title><desc id="desc">{e(description)}</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#087f72"/></marker></defs>
<rect width="100%" height="100%" fill="#fbfdfe"/>
<g font-family="Segoe UI, Arial, sans-serif">{''.join(content)}</g></svg>'''
    (SVG / name).write_text(document, encoding='utf-8')


NAV = [('index.html', 'Diseño'), ('casos-de-uso.html', 'Casos de uso'),
       ('entidad-relacion.html', 'Entidad–relación'), ('secuencias.html', 'Secuencias')]


def page(filename, title, subtitle, body):
    nav = ''.join(f'<a href="{file}"' + (' aria-current="page"' if file == filename else '') + f'>{label}</a>' for file, label in NAV)
    html = f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{e(subtitle)}"><title>{e(title)} · LimpiezaSoft</title><link rel="stylesheet" href="styles.css"></head>
<body><a class="skip" href="#contenido">Saltar al contenido</a><header class="top"><div class="top-inner"><a class="brand" href="index.html">LimpiezaSoft / design</a><nav aria-label="Documentos de diseño">{nav}</nav></div></header>
<div class="hero"><div class="eyebrow">Proyecto escolar · Equipo de Informática</div><h1>{e(title)}</h1><p class="lead">{e(subtitle)}</p></div>
<main id="contenido">{body}</main><footer>Diseño de la implementación actual · Fuente: <a href="../db.sql">db.sql</a> y código Python · <a href="../README.md">README del proyecto</a><br>HTML y SVG locales. No requieren conexión a Internet ni bibliotecas JavaScript. Usa Ctrl+P para imprimir.</footer></body></html>'''
    (BASE / filename).write_text(html, encoding='utf-8')


def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th scope="col">{e(v)}</th>' for v in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{v}</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def figure(filename, title, caption):
    return f'<figure class="figure"><div class="diagram" tabindex="0" aria-label="{e(title)}. Desplazamiento horizontal disponible."><img src="svg/{filename}" alt="{e(title)}"></div><figcaption>{caption}</figcaption><div class="tools"><a href="svg/{filename}" target="_blank" rel="noopener">Abrir SVG a tamaño completo ↗</a><a href="svg/{filename}" download>Descargar SVG</a></div></figure>'


def pills(items):
    return '<nav class="pills" aria-label="Secciones del documento">' + ''.join(f'<a href="#{id}">{label}</a>' for id, label in items) + '</nav>'


def architecture():
    parts = [text(40, 38, 'Arquitectura de ejecución · tres capas', 23, weight='700')]
    items = [('UI / PySide6', 'VentanaPrincipal · Formulario', 'Trabajo · QThreadPool', '#e6f3ef'),
             ('Negocio', 'ServicioGestion · validar', 'ENTIDADES · Campo · Entidad', '#eaf0f8'),
             ('Acceso a datos', 'Repositorio · sesion', 'Psycopg · SQL parametrizado', '#eaf0f8'),
             ('PostgreSQL', 'Base proyecto · 25 tablas', 'PK · FK · UNIQUE · CHECK', '#fff2d9')]
    for i, (name, sub, more, color) in enumerate(items):
        x = 40 + 310 * i
        parts += [rect(x, 90, 270, 150, color), text(x+18, 128, name, 22, weight='700'),
                  text(x+18, 165, sub, 13), text(x+18, 193, more, 13)]
        if i < 3:
            parts += [line(x+272, 144, x+306, 144, arrow=True), line(x+306, 193, x+272, 193, dashed=True, arrow=True)]
    parts += [rect(40, 285, 1200, 84, '#f0f5f8'), text(62, 316, 'main.py ensambla las capas e inyecta Repositorio en ServicioGestion.', 16, weight='600'),
              text(62, 345, 'config.py carga .env; start.bat inicia main.py. Los widgets nunca ejecutan SQL.', 15)]
    save_svg('arquitectura.svg', 'Arquitectura en tres capas', 'UI llama a Negocio, que llama al Repositorio. El repositorio se conecta con PostgreSQL. Main ensambla las capas.', 1280, 400, parts)


CASES = [
    ('CU01', 'Consultar resumen y calendario', 'general', 'PostgreSQL disponible y esquema inicializado.', 'Abrir Vista general o actualizar; consultar la semana por día y hora y pulsar una cita.', 'Mostrar indicadores y calendario de lunes a domingo, con color por estado y detalle de cada cita.', 'Semana sin citas: mostrar estado vacío. Conexión fallida: mostrar error y permitir reintentar.'),
    ('CU02', 'Gestionar clientes', 'general', 'Crear primero una categoría de cliente.', 'Consultar, buscar, crear, editar o eliminar clientes y categorías.', 'Persistir datos válidos; respetar unicidad de RUC/CI.', 'Categoría inexistente, duplicados o referencias que impiden eliminar.'),
    ('CU03', 'Gestionar equipo', 'general', 'Los seis roles laborales y sus departamentos deben estar configurados.', 'Crear o editar un empleado, elegir rol y consultar el departamento automático.', 'Guardar el rol y derivar el departamento en la misma transacción. Limpiador/Vendedor: Clientes; Informática: Informática; Manager/Contabilidad: Administración; Recursos humanos: HR.', 'Cédula duplicada, rol vacío o asociación no configurada. Los empleados históricos conservan su departamento hasta que se les asigne un rol al editar.'),
    ('CU04', 'Administrar usuarios y roles', 'general', 'Debe existir el empleado y, para asociar un rol, el usuario y el rol.', 'Registrar usuario, correo, contraseña y estado; administrar usuario_roles.', 'Guardar contraseña con PBKDF2; conservarla si queda vacía al editar.', 'Correo inválido, empleado ya asociado o contraseña de menos de 8 caracteres.'),
    ('CU05', 'Mantener catálogo de servicios', 'servicios', 'Esquema inicializado.', 'Administrar nombres, precios base y estados de servicio; elegir el color de cada estado con el selector.', 'Persistir el catálogo y el color hexadecimal del estado para mostrarlo en las citas del calendario.', 'Nombre duplicado, importe inválido o color que no cumple #RRGGBB.'),
    ('CU06', 'Programar un servicio', 'servicios', 'Deben existir cliente, servicio, empleada asignada y estado.', 'Seleccionar cliente, servicio, limpiadora, estado y fecha/hora; guardar la agenda.', 'Crear calendario_servicios con la empleada asignada, fecha y zona horaria.', 'Referencia inexistente, limpiadora sin seleccionar o fecha inválida. No se detectan solapamientos.'),
    ('CU07', 'Registrar factura de servicio', 'servicios', 'Debe existir una cita sin factura asociada.', 'Seleccionar la cita e ingresar monto y fecha de emisión.', 'Crear una factura interna por cita como máximo.', 'Cita ya facturada o monto negativo. No hay emisión fiscal.'),
    ('CU08', 'Gestionar productos y depósitos', 'servicios', 'Crear la categoría antes del producto.', 'Administrar categorías, productos, precios y depósitos.', 'Mantener catálogos para existencias, ventas y compras.', 'Código de barra duplicado o categoría inválida.'),
    ('CU09', 'Registrar stock y conciliaciones', 'operaciones', 'Deben existir producto y depósito.', 'Registrar stock; en conciliaciones ingresar stock del sistema y físico.', 'Guardar stock no negativo y diferencia generada por PostgreSQL.', 'Par producto/depósito duplicado en stock. Conciliar no ajusta las existencias.'),
    ('CU10', 'Registrar ventas y detalles', 'operaciones', 'Crear la venta y los productos antes de agregar detalles; cliente opcional.', 'Crear cabecera; agregar, editar o eliminar detalles con precio explícito.', 'Recalcular el total de las ventas afectadas dentro de la transacción.', 'Cantidad no positiva o importe inválido. No modifica stock ni aplica descuentos automáticamente.'),
    ('CU11', 'Registrar compras y detalles', 'operaciones', 'Crear proveedor, estado, orden y productos.', 'Administrar la orden y los detalles con cantidades y costos.', 'Recalcular el total; si se mueve un detalle, recalcular ambas órdenes.', 'Revertir si el nuevo total queda por debajo de los pagos existentes.'),
    ('CU12', 'Registrar pagos a proveedores', 'operaciones', 'Orden con total calculado y método de pago existente.', 'Ingresar orden, método, monto positivo y fecha; guardar.', 'Confirmar solamente si la suma de pagos no supera el total.', 'Sobrepago: ErrorValidacion y rollback, incluso al cambiar la orden de un pago.'),
]


def use_cases():
    sections = []
    groups = [('general', 'Administración general'), ('servicios', 'Servicios y catálogos'), ('operaciones', 'Operaciones comerciales')]
    for group, title in groups:
        selected = [c for c in CASES if c[2] == group]
        parts = [text(32, 36, title, 23, weight='700'), rect(290, 66, 700, 570, '#f3f8f7'), text(315, 99, 'Sistema LimpiezaSoft', 16, weight='600')]
        parts += [f'<circle cx="130" cy="275" r="22" fill="none" stroke="#173047" stroke-width="2"/>',
                  line(130, 297, 130, 360), line(85, 323, 175, 323), line(130, 360, 95, 402), line(130, 360, 165, 402),
                  text(130, 436, 'Operador', 18, anchor='middle', weight='700')]
        for i, case in enumerate(selected):
            y = 165 + i * 132
            parts.append(line(177, 323, 420, y))
            parts.append(f'<ellipse cx="650" cy="{y}" rx="230" ry="48" fill="#fff" stroke="#087f72" stroke-width="1.8"/>')
            parts += [text(650, y-8, case[0], 12, '#087f72', 'middle', '700'), text(650, y+15, case[1], 17, anchor='middle')]
        name = f'casos-{group}.svg'
        save_svg(name, title, 'El operador se asocia con ' + ', '.join(c[1] for c in selected) + '. El borde delimita el sistema.', 1030, 670, parts)
        sections.append(f'<section id="{group}"><h2>{title}</h2>' + figure(name, title, 'Notación UML: actor externo, límite del sistema y óvalos de casos de uso. Las líneas representan participación del operador.') + '</section>')
    details = ''
    for id, title, group, pre, flow, post, alternative in CASES:
        details += f'<details id="{id}" open><summary>{id} · {title}</summary><dl><dt>Actor</dt><dd>Operador de la aplicación.</dd><dt>Precondición</dt><dd>{pre}</dd><dt>Flujo principal</dt><dd>{flow}</dd><dt>Resultado esperado</dt><dd>{post}</dd><dt>Alternativas y restricciones</dt><dd>{alternative}</dd></dl></details>'
    page('casos-de-uso.html', 'Casos de uso', '12 casos de uso que describen las funciones disponibles para el operador de escritorio.',
         pills(groups + [('fichas', 'Fichas de casos')]) +
         '<section id="actores"><h2>Actor y alcance</h2><p><strong>Operador:</strong> persona que utiliza LimpiezaSoft para administrar los registros de la empresa. Clientes y proveedores son entidades del dominio; no interactúan directamente con esta aplicación.</p><div class="note">Esta versión administra usuarios y roles como datos. No implementa inicio de sesión ni restricciones de acceso por rol. No se representan actores con permisos que el programa todavía no aplica.</div><p>En las operaciones de mantenimiento, la consulta y la escritura son alternativas. No se utiliza «include» entre ellas porque consultar no exige guardar ni validar un formulario.</p></section>' + ''.join(sections) + '<section id="fichas"><h2>Especificación de los casos</h2>' + details + '</section>')


DOMAINS = [
    ('equipo', 'Equipo y usuarios', ['departamentos', 'roles', 'empleados', 'departamentos_roles', 'usuarios', 'usuario_roles']),
    ('servicios', 'Clientes y servicios', ['categorias_clientes', 'clientes', 'servicios_catalogo', 'empleados', 'estados_servicio', 'calendario_servicios', 'facturas_servicios']),
    ('inventario', 'Productos e inventario', ['categorias_productos', 'productos', 'depositos', 'inventario_stock', 'conciliaciones_inventario']),
    ('ventas', 'Ventas', ['clientes', 'productos', 'ventas', 'detalle_ventas']),
    ('compras', 'Compras y pagos', ['proveedores', 'estados_orden', 'metodos_pago', 'productos', 'ordenes_compra', 'detalle_compras', 'pagos_proveedores']),
]


def relationship_rows(relations):
    return [[r['id'], f"<code>{r['parent']}</code>", f"<code>{r['child']}.{r['column']}</code>",
             '1' if r['required'] else '0..1', '0..1' if r['unique'] else '0..N',
             'CASCADE' if r['cascade'] else 'NO ACTION'] for r in relations]


def er_diagram(slug, title, names):
    links = [r for r in RELATIONS if r['parent'] in names and r['child'] in names]
    depth = {}
    def rank(name):
        if name not in depth:
            parents = [r['parent'] for r in links if r['child'] == name]
            depth[name] = max((rank(p) + 1 for p in parents), default=0)
        return depth[name]
    groups = defaultdict(list)
    for name in names:
        groups[rank(name)].append(name)
    positions = {}
    box_w = 350
    col_w = 570
    for col, members in groups.items():
        for row, name in enumerate(members):
            positions[name] = (35 + col*col_w, 140 + row*320)
    width = max(x for x, y in positions.values()) + box_w + 35
    height = max(y+72+24*len(TABLES[n]['columns']) for n, (x, y) in positions.items()) + 55
    parts = [text(35, 32, title, 23, weight='700'), text(35, 57, 'PK primaria · FK foránea · U única · * obligatoria · G generada · I identidad', 13)]
    outgoing = defaultdict(int)
    incoming = defaultdict(int)
    edge_labels = []
    for i, r in enumerate(links):
        sx, sy = positions[r['parent']]
        tx, ty = positions[r['child']]
        source_y = sy+44+outgoing[r['parent']]*18
        target_y = ty+44+incoming[r['child']]*27
        outgoing[r['parent']] += 1
        incoming[r['child']] += 1
        source_x = sx+box_w
        if rank(r['child']) - rank(r['parent']) == 1:
            bend = source_x+55+(i%4)*22
            path = f'M {source_x} {source_y} H {bend} V {target_y} H {tx}'
        else:
            lane = 83+(i%4)*12
            path = f'M {source_x} {source_y} H {source_x+30} V {lane} H {tx-185} V {target_y} H {tx}'
        parts.append(f'<path d="{path}" fill="none" stroke="#087f72" stroke-width="1.6" marker-end="url(#arrow)"/>')
        label = f"{r['id']} · {'1' if r['required'] else '0..1'} : {'0..1' if r['unique'] else '0..N'}"
        edge_labels += [rect(tx-170, target_y-17, 152, 18, '#fbfdfe', '#fbfdfe', 2), text(tx-163, target_y-4, label, 12, '#075f56')]
    parts.extend(edge_labels)
    for name, (x, y) in positions.items():
        cols = TABLES[name]['columns']
        h = 55 + len(cols)*24
        parts += [rect(x, y, box_w, h), rect(x, y, box_w, 35, '#173047', '#173047', 8),
                  text(x+13, y+24, name, 16, '#fff', weight='600')]
        for i, c in enumerate(cols):
            marks = ('PK ' if c['pk'] else '') + ('FK ' if c['ref'] else '') + ('U ' if c['unique'] else '') + ('G ' if c['generated'] else '') + ('I ' if c['identity'] else '')
            parts += [text(x+13, y+57+i*24, c['name']+(' *' if c['required'] else ''), 12),
                      text(x+box_w-12, y+57+i*24, marks.strip(), 11, '#087f72', 'end', '700')]
    save_svg(f'er-{slug}.svg', title, 'Modelo relacional. Flechas de tabla referenciada a tabla dependiente. Las cardinalidades y claves foráneas están detalladas en la tabla de relaciones del documento.', width, height, parts)
    return links


def entity_relationship():
    sections = []
    covered = set()
    for slug, title, names in DOMAINS:
        links = er_diagram(slug, title, names)
        covered.update(r['id'] for r in links)
        sections.append(f'<section id="{slug}"><h2>{title}</h2>' + figure(f'er-{slug}.svg', title, 'La flecha va de la tabla referenciada a la dependiente. Etiqueta: identificador de relación · padres por hijo : hijos por padre. Consulta el detalle exacto debajo.') + table(['ID', 'Padre', 'Hijo / clave foránea', 'Padres por hijo', 'Hijos por padre', 'Al borrar padre'], relationship_rows(links)) + '</section>')
    if covered != {r['id'] for r in RELATIONS}:
        raise ValueError('Hay relaciones sin representar en los diagramas')
    dictionary = ''
    for name, t in TABLES.items():
        rows = []
        for c in t['columns']:
            constraints = c['rules'] or 'Sin restricciones adicionales.'
            if c['pk'] and 'PRIMARY KEY' not in constraints:
                constraints += ' · Parte de la clave primaria compuesta.'
            rows.append([f"<code>{c['name']}</code>", f"<code>{c['datatype']}</code>", 'No' if c['required'] else 'Sí', f'<code>{e(constraints)}</code>'])
        dictionary += f'<details id="tabla-{name}"><summary>{name} <span class="badge">{len(t["columns"])} campos</span></summary>' + table(['Campo', 'Tipo SQL', 'Acepta NULL', 'Restricciones / valor por defecto'], rows)
        dictionary += ''.join(f'<p><code>{e(c)}</code></p>' for c in t['constraints']) + '</details>'
    page('entidad-relacion.html', 'Modelo entidad–relación', f'Las 25 tablas y las {len(RELATIONS)} claves foráneas de db.sql, organizadas en cinco vistas para facilitar su lectura.',
         pills([(s, t) for s, t, _ in DOMAINS] + [('diccionario', 'Diccionario de datos')]) +
         '<section id="notacion"><h2>Cómo leer el modelo</h2><div class="note">Se utiliza notación relacional con cardinalidades mínimas y máximas explícitas. <strong>1</strong>: exactamente uno; <strong>0..1</strong>: opcional y único; <strong>0..N</strong>: cero o varios. La columna «Padres por hijo» indica la obligatoriedad de la FK; «Hijos por padre» indica si puede repetirse.</div><p>Una FK <code>NOT NULL</code> no obliga al padre a tener hijos. Las relaciones empleado–usuario y cita–factura admiten cero o un hijo por su FK única. El cliente de una venta es opcional. Las asociaciones departamento–rol y usuario–rol resuelven relaciones muchos a muchos mediante claves primarias compuestas.</p><p>Los nodos de clientes y productos aparecen en varias vistas como referencia a la misma tabla. Los tipos SQL, valores por defecto y restricciones completas están en el diccionario inferior. Las flechas son conectores del modelo relacional, no una secuencia de ejecución.</p></section>' + ''.join(sections) +
         '<section id="reglas"><h2>Reglas que preserva PostgreSQL</h2><ul><li>Identificadores de las entidades generados como identidad; asociaciones con claves compuestas.</li><li>Stock único por producto y depósito; existencias no negativas.</li><li><code>detalle_ventas.subtotal = cantidad × precio_unitario</code> y <code>conciliaciones_inventario.diferencia = stock_fisico − stock_sistema</code> son columnas generadas.</li><li>Totales de ventas y compras se recalculan en la aplicación; el esquema no define triggers para ello.</li><li>Las referencias sin CASCADE usan NO ACTION por defecto: una eliminación incompatible se rechaza.</li></ul></section><section id="diccionario"><h2>Diccionario de datos completo</h2><p>Extraído del archivo SQL. Abre cada tabla para consultar sus campos y restricciones.</p>' + dictionary + '</section>')


# Mensajes: (origen, destino, etiqueta, retorno). Notas: texto. Alternativas: dict.
def msg(source, target, label, reply=False):
    return (source, target, label, reply)


SEQUENCES = [
    ('calendario', 'SQ07 · Consultar calendario y detalle', 'CU01 / CU05', [
        msg(0, 1, 'Abrir Vista general o actualizar'),
        'El trabajador obtiene los indicadores de resumen y luego el calendario semanal.',
        msg(1, 2, 'agenda_semanal()'), msg(2, 2, 'Calcular lunes local y lunes siguiente'),
        msg(2, 3, 'sesion() / agenda_semanal(inicio, fin)'),
        msg(3, 4, 'SELECT por rango con JOIN de detalles'),
        msg(4, 3, 'Citas, nombres, color del estado y factura', True),
        msg(3, 2, 'Resultados; cerrar conexión', True), msg(2, 1, 'Semana y servicios', True),
        msg(1, 1, 'Agrupar por día y hora; pintar colores'),
        msg(0, 1, 'Hacer clic en una cita'), msg(1, 1, 'Abrir DetalleServicio con datos cargados'),
        msg(1, 0, 'Mostrar detalle de cita y contactos', True),
    ], 'Rango: lunes 00:00 inclusivo a lunes siguiente 00:00 exclusivo, según hora local. Se incluyen todas las citas de la semana y se identifican las pasadas. Los colores se leen del estado actual al recargar; la ventana de detalle utiliza los datos ya consultados.'),
    ('consulta', 'SQ01 · Buscar y paginar registros', 'CU02–CU12', [
        msg(0, 1, 'Buscar texto / cambiar página'),
        'La UI deshabilita acciones y envía Trabajo a QThreadPool; la ventana sigue procesando eventos.',
        msg(1, 2, 'listar(tabla, búsqueda, página)'), msg(2, 3, 'sesion() / listar(...)'),
        msg(3, 4, 'Conectar; COUNT y SELECT con parámetros'), msg(4, 3, 'Filas sin password_hash y cantidad total', True),
        msg(3, 2, 'Cerrar conexión; devolver resultados', True), msg(2, 1, '(filas, total)', True),
        'Se consultan los catálogos de las FK mediante opciones() para mostrar nombres e identificadores.',
        msg(1, 0, 'Señal de finalización; tabla y paginación', True),
    ], 'El límite es 100 filas; el desplazamiento es página × 100. Ante ErrorDatos la UI vuelve a habilitar acciones, informa el error y permite reintentar.'),
    ('guardar', 'SQ02 · Guardar un registro', 'CU02–CU09', [
        msg(0, 1, 'Completar formulario y pulsar Guardar'), msg(1, 2, 'guardar(tabla, valores, anterior)'),
        msg(2, 2, 'validar(): tipos, requeridos y longitudes'),
        {'alt': [('[datos inválidos]', [msg(2, 1, 'ErrorValidacion', True), msg(1, 0, 'Mostrar error; conservar formulario', True)]),
                 ('[datos válidos]', [msg(2, 3, 'sesion(escritura=True)'), msg(3, 4, 'Conectar y adquirir bloqueo transaccional'),
                    msg(2, 3, 'guardar(): alta o edición'), msg(3, 4, 'INSERT / UPDATE parametrizado'), msg(4, 3, 'Restricciones satisfechas', True),
                    msg(3, 4, 'COMMIT y cerrar conexión'), msg(3, 2, 'Fin de sesión', True), msg(2, 1, 'Operación completada', True), msg(1, 0, 'Cerrar formulario y recargar lista', True)])]},
    ], 'Si PostgreSQL rechaza la escritura, la sesión hace rollback y traduce el error a ErrorDatos; se conserva el formulario. En empleados, antes de guardar se consulta la asociación del rol laboral y se deriva el departamento; el valor enviado por la UI no decide esa asignación. En usuarios, validar() genera el hash antes de abrir la sesión. Para detalles y pagos se agregan las reglas de SQ03 y SQ04.'),
    ('venta', 'SQ03 · Modificar un detalle de venta', 'CU10', [
        msg(0, 1, 'Guardar detalle de venta'), msg(1, 2, 'guardar(detalle_ventas, valores, anterior)'),
        msg(2, 2, 'Validar cantidad > 0 y precio ≥ 0'), msg(2, 3, 'Abrir sesión de escritura'),
        msg(3, 4, 'Adquirir bloqueo transaccional'), msg(2, 3, 'guardar(detalle)'), msg(3, 4, 'INSERT / UPDATE del detalle'),
        msg(4, 3, 'Calcular subtotal generado', True), msg(2, 2, '_actualizar_totales(): padres afectados'),
        'Repetir para cada venta afectada: la anterior y la nueva si se movió el detalle.',
        msg(2, 3, 'recalcular(detalle_ventas, venta_id)'), msg(3, 4, 'UPDATE ventas: SUM(subtotal) o cero'),
        msg(3, 4, 'COMMIT de detalle y totales'), msg(2, 1, 'Operación completada', True), msg(1, 0, 'Recargar detalle de ventas', True),
    ], 'Al eliminar un detalle se ejecuta DELETE y después el mismo recálculo. Cabecera y detalles se crean en operaciones separadas. No se aplican descuentos ni se descuentan existencias.'),
    ('pago', 'SQ04 · Guardar un pago y controlar el saldo', 'CU12', [
        msg(0, 1, 'Guardar pago a proveedor'), msg(1, 2, 'guardar(pagos_proveedores, ...)'), msg(2, 2, 'Validar monto positivo y fecha'),
        msg(2, 3, 'Abrir sesión de escritura'), msg(3, 4, 'Adquirir bloqueo transaccional'), msg(2, 3, 'guardar(pago)'), msg(3, 4, 'INSERT / UPDATE del pago provisional'),
        msg(2, 3, 'saldo_orden() para órdenes afectadas'), msg(3, 4, 'SELECT total y SUM(monto_pagado)'), msg(4, 3, 'Total y pagos acumulados', True), msg(3, 2, 'Devolver saldo de la orden', True),
        {'alt': [('[pagado ≤ total en cada orden]', [msg(3, 4, 'COMMIT y cerrar conexión'), msg(2, 1, 'Operación completada', True), msg(1, 0, 'Cerrar formulario y recargar lista', True)]),
                 ('[pagado > total en alguna orden]', [msg(2, 3, 'ErrorValidacion al salir de sesion()'), msg(3, 4, 'ROLLBACK y cerrar conexión'), msg(2, 1, 'Informar sobrepago', True), msg(1, 0, 'Mostrar error; conservar formulario', True)])]},
    ], 'El pago se escribe provisionalmente y se valida dentro de la misma transacción. Un pago inválido no queda persistido. Si cambia de orden, se revisan ambas. El bloqueo coordina las escrituras de esta aplicación, no clientes SQL externos.'),
    ('compra', 'SQ05 · Cambiar un detalle de compra', 'CU11', [
        msg(0, 1, 'Editar o eliminar detalle de compra'), msg(1, 2, 'guardar(...) o eliminar(...)'),
        'La edición valida los campos; la eliminación parte del registro seleccionado y confirmado.',
        msg(2, 3, 'Abrir sesión de escritura'), msg(3, 4, 'Adquirir bloqueo transaccional'), msg(2, 3, 'Guardar o eliminar detalle'), msg(3, 4, 'INSERT / UPDATE / DELETE provisional'),
        msg(2, 2, 'Identificar órdenes anterior y nueva'), msg(2, 3, 'recalcular() por cada orden'), msg(3, 4, 'UPDATE total = SUM(cantidad × costo)'),
        msg(2, 3, 'saldo_orden() por cada orden'), msg(3, 4, 'Consultar total y pagos acumulados'),
        {'alt': [('[ninguna orden queda sobrepagada]', [msg(3, 4, 'COMMIT'), msg(2, 1, 'Completar y recargar lista', True)]),
                 ('[alguna orden queda sobrepagada]', [msg(2, 3, 'ErrorValidacion'), msg(3, 4, 'ROLLBACK: restaurar detalles y totales'), msg(2, 1, 'Informar que los pagos superan el total', True)])]},
    ], 'La validación evita reducir una orden por debajo de lo ya pagado. Un error en cualquiera de las órdenes revierte toda la operación. Registrar una compra no aumenta automáticamente el stock.'),
    ('eliminar', 'SQ06 · Eliminar un registro', 'CU02–CU12', [
        msg(0, 1, 'Seleccionar fila y pulsar Eliminar'), msg(1, 0, 'Solicitar confirmación y advertir cascadas', True),
        {'alt': [('[usuario cancela]', [msg(0, 1, 'No: cerrar confirmación sin escribir')]),
                 ('[usuario confirma]', [msg(0, 1, 'Sí'), msg(1, 2, 'eliminar(tabla, registro)'), msg(2, 3, 'Abrir sesión de escritura'),
                    msg(3, 4, 'Adquirir bloqueo; DELETE por PK'), msg(4, 3, 'Aplicar FK y CASCADE', True),
                    msg(2, 2, 'Actualizar totales si corresponde'), msg(3, 4, 'COMMIT'), msg(2, 1, 'Recargar lista', True)])]},
    ], 'Una FK incompatible, un registro inexistente o una regla de saldo impiden completar la operación: se revierte y se informa el error. Las cascadas están definidas en db.sql, no se inventan en la UI.'),
]


def sequence_diagram(slug, title, events):
    x = [90, 340, 630, 935, 1230]
    labels = [('Operador', 'Actor'), ('UI / Trabajo', 'Qt + QThreadPool'), ('ServicioGestion', 'Negocio'), ('Repositorio', 'Acceso a datos'), ('PostgreSQL', 'Persistencia')]
    parts = []
    y = 140
    step = 0

    def draw(events):
        nonlocal y, step
        for item in events:
            if isinstance(item, str):
                lines = textwrap.wrap(item, width=132)
                h = len(lines)*21+22
                parts.append(rect(220, y, 1080, h, '#fff5df', '#ecdfb9', 5))
                for i, value in enumerate(lines):
                    parts.append(text(237, y+24+i*21, value, 13))
                y += h+24
            elif isinstance(item, dict):
                top = y
                slot = len(parts)
                parts.append('')
                for idx, (guard, branch) in enumerate(item['alt']):
                    if idx:
                        parts.append(line(30, y, 1370, y, dashed=True))
                    parts.append(text(48, y+24, ('alt ' if idx == 0 else '') + guard, 14, '#087f72', weight='700'))
                    y += 57
                    draw(branch)
                parts[slot] = rect(30, top, 1340, y-top, 'none', '#9db7bf', 0)
                y += 25
            else:
                source, target, label, reply = item
                step += 1
                left = min(x[source], x[target])
                distance = abs(x[target]-x[source])
                lines = textwrap.wrap(f'{step}. {label}', width=max(29, int(distance/7)))
                y += len(lines)*18
                if source == target:
                    parts.append(f'<path d="M {x[source]} {y} h 205 v 23 h -205" fill="none" stroke="#087f72" marker-end="url(#arrow)"/>')
                    for i, value in enumerate(lines):
                        parts.append(text(x[source]+10, y-(len(lines)-i)*18+2, value, 12))
                    y += 24
                else:
                    parts.append(line(x[source], y, x[target], y, dashed=reply, arrow=True, color='#087f72'))
                    for i, value in enumerate(lines):
                        parts.append(text(left+10, y-(len(lines)-i)*18+2, value, 12))
                y += 32
    draw(events)
    end = y+20
    background = [text(30, 33, title, 23, weight='700')]
    for pos, (label, sub) in zip(x, labels):
        background += [line(pos, 113, pos, end, dashed=True, color='#bfd0d7'), rect(pos-80, 62, 160, 56, '#e9f3f0'),
                       text(pos, 85, label, 16, anchor='middle', weight='600'), text(pos, 105, sub, 11, anchor='middle')]
    save_svg(f'secuencia-{slug}.svg', title, 'Diagrama UML de secuencia entre Operador, UI, Negocio, Repositorio y PostgreSQL. Los fragmentos alt muestran caminos excluyentes; líneas discontinuas indican retornos.', 1400, end+30, background+parts)


def sequences():
    body = pills([(slug, title.split(' · ')[0]) for slug, title, *_ in SEQUENCES])
    body += '<section id="lectura"><h2>Lectura y responsabilidades</h2><p>El tiempo avanza hacia abajo. Las flechas continuas indican llamadas o mensajes; las discontinuas representan respuestas. Los marcos <code>alt</code> son alternativas excluyentes con su condición entre corchetes. Las notas amarillas explican trabajo repetido o responsabilidades resumidas.</p><p>El participante <strong>UI / Trabajo</strong> reúne el hilo principal de Qt y la tarea del pool para mantener legibles las tres capas. Las llamadas al servicio se ejecutan en el trabajador; la señal de finalización actualiza los widgets en la UI. La conexión se abre y cierra dentro de la sesión del repositorio.</p><div class="note">Los diagramas son vistas lógicas del código actual. El COMMIT ocurre al salir normalmente del contexto de conexión; una excepción provoca ROLLBACK. No hay una llamada pública independiente a commit() desde la UI.</div></section>'
    for slug, title, cases, events, note in SEQUENCES:
        sequence_diagram(slug, title, events)
        body += f'<section id="{slug}"><h2>{title}</h2><p class="muted">Trazabilidad: {cases} · <code>ServicioGestion</code> y <code>Repositorio</code>.</p>' + figure(f'secuencia-{slug}.svg', title, 'Vista lógica por capas. Los números ordenan los mensajes del dibujo; solo se ejecuta una rama de cada alt.') + f'<div class="note">{note}</div></section>'
    body += '<section id="fuentes"><h2>Fuentes de implementación</h2><ul class="sources"><li><a href="../limpiezasoft/ui/ventana.py">ventana.py</a>: ejecutar, cargar_tabla, formulario y eliminar.</li><li><a href="../limpiezasoft/negocio/servicios.py">servicios.py</a>: validar, guardar, eliminar y _actualizar_totales.</li><li><a href="../limpiezasoft/datos/repositorio.py">repositorio.py</a>: sesion, listar, guardar, eliminar, recalcular y saldo_orden.</li></ul></section>'
    page('secuencias.html', 'Diagramas de secuencia', f'{len(SEQUENCES)} recorridos que conectan las acciones del operador con validaciones, consultas y transacciones PostgreSQL.', body)


def index():
    architecture()
    rows = [
        ['Presentación', '<code>ui/ventana.py</code> y <code>ui/tema.py</code>', 'Navegación, formularios, listados, confirmaciones y mensajes; tareas en segundo plano.'],
        ['Negocio', '<code>negocio/modelos.py</code> y <code>negocio/servicios.py</code>', 'Metadatos, validación, hashes, casos de uso, solicitud de recálculos y control de sobrepagos.'],
        ['Acceso a datos', '<code>datos/repositorio.py</code>', 'Consultas parametrizadas, proyecciones SQL de totales, conexiones, transacciones y traducción de errores.'],
        ['Composición', '<code>main.py</code>, <code>config.py</code> y <code>start.bat</code>', 'Inyectar dependencias, cargar configuración y arrancar la aplicación desde su carpeta.'],
    ]
    body = '<div class="grid"><a class="card" href="casos-de-uso.html"><small>01 / FUNCIONAL</small><b>Casos de uso</b><p>Actor, límites del sistema y 12 fichas de operaciones.</p></a><a class="card" href="entidad-relacion.html"><small>02 / DATOS</small><b>Entidad–relación</b><p>25 tablas, cinco diagramas y diccionario completo de campos.</p></a><a class="card" href="secuencias.html"><small>03 / COMPORTAMIENTO</small><b>Secuencias</b><p>Calendario, consultas, guardado, ventas, pagos, compras y eliminación.</p></a></div>'
    body += f'<section id="alcance"><h2>Diseño de la versión implementada</h2><div class="stats"><div><strong>3</strong><span>capas de aplicación</span></div><div><strong>25</strong><span>tablas PostgreSQL</span></div><div><strong>{len(RELATIONS)}</strong><span>claves foráneas</span></div><div><strong>{9 + len(SEQUENCES)}</strong><span>diagramas SVG</span></div></div><p>LimpiezaSoft es un proyecto escolar de gestión de una empresa de limpieza. Esta documentación describe los archivos existentes y las reglas efectivamente implementadas. El esquema de referencia es <a href="../db.sql">db.sql</a>.</p><div class="note">Usuarios y roles no constituyen un sistema de autenticación. Compras y ventas no actualizan stock automáticamente porque sus detalles no identifican depósito. Los descuentos de categoría se almacenan, pero no se aplican automáticamente. Las facturas son registros internos.</div></section>'
    body += '<section id="arquitectura"><h2>Arquitectura en tres capas</h2>' + figure('arquitectura.svg', 'Arquitectura de tres capas con PostgreSQL', 'Las flechas continuas indican llamadas; las discontinuas, resultados o errores. Main conecta las dependencias.') + table(['Responsabilidad', 'Archivos', 'Descripción'], rows) + '<p>El servicio recibe un repositorio por inyección. El repositorio recibe metadatos de entidad y no importa widgets Qt. La UI invoca casos de uso y no construye SQL. La configuración se mantiene fuera de los formularios y las credenciales no forman parte de estos documentos.</p></section>'
    body += '<section id="decisiones"><h2>Decisiones de diseño</h2><ul><li><strong>Formularios por metadatos:</strong> los 25 módulos comparten la misma UI y reglas por tipo de campo.</li><li><strong>Exactitud monetaria:</strong> Decimal en negocio y NUMERIC en PostgreSQL; hasta dos decimales.</li><li><strong>Atomicidad:</strong> detalle, recálculo y validación de saldo se confirman o revierten juntos.</li><li><strong>Concurrencia:</strong> bloqueo transaccional compartido por las escrituras de esta aplicación. Ediciones externas por SQL no ejecutan sus reglas Python.</li><li><strong>Relaciones:</strong> los selectores muestran nombres e identificadores; PostgreSQL conserva la integridad referencial.</li><li><strong>Secretos:</strong> .env local fuera de Git; contraseñas de usuarios con hash y sin exposición en listados.</li><li><strong>Escala escolar:</strong> listados de 100 registros y catálogos completos en selectores.</li></ul></section>'
    body += '<section id="trazabilidad"><h2>Trazabilidad y verificación</h2>' + table(['Documento', 'Fuente', 'Qué verificar'], [
        ['Casos de uso', '<a href="../limpiezasoft/ui/ventana.py">UI</a> y <a href="../limpiezasoft/negocio/modelos.py">entidades</a>', 'Acciones visibles, actor único y límites de alcance.'],
        ['Entidad–relación', '<a href="../db.sql">Esquema SQL</a>', '25 tablas, todas las FK, nulabilidad, unicidad, cascadas y columnas generadas.'],
        ['Secuencias', '<a href="../limpiezasoft/negocio/servicios.py">Servicios</a> y <a href="../limpiezasoft/datos/repositorio.py">repositorio</a>', 'Validación previa, transacciones, recálculos y rollback ante sobrepago.'],
        ['Pruebas existentes', '<a href="../tests/test_negocio.py">Negocio</a> y <a href="../tests/test_postgres.py">integración</a>', 'Reglas unitarias y comportamiento en un esquema PostgreSQL aislado.'],
    ]) + '</section>'
    body += '<section id="inicio"><h2>Iniciar la aplicación</h2><p>Desde la raíz del proyecto, abre <a href="../start.bat">start.bat</a> con doble clic o ejecuta:</p><pre><code>.\\start.bat</code></pre><p>El script cambia a su propia carpeta, verifica el entorno <code>.venv</code> y las dependencias e inicia <code>main.py</code>. Si falta algo, muestra los comandos de instalación. No instala paquetes ni cambia la base de datos automáticamente.</p></section>'
    body += '<section id="mantenimiento"><h2>Consultar y mantener estos documentos</h2><p>Abre <code>design/index.html</code> en un navegador. Los HTML y SVG funcionan sin Internet. En GitHub los HTML se muestran como archivos fuente: descarga o clona el repositorio para visualizarlos como páginas; los SVG también se pueden abrir individualmente.</p><p>Los entregables están pre-generados. Para actualizarlos después de cambiar el esquema:</p><pre><code>.\\.venv\\Scripts\\python.exe design\\generar.py</code></pre><p><code>generar.py</code> usa solo la biblioteca estándar de Python y lee <code>db.sql</code>, sin conectarse a la base. Genera el diccionario, relaciones y páginas; los casos de uso y secuencias se mantienen en sus datos declarativos. Si cambia el comportamiento, revisa esas descripciones además de regenerar.</p></section>'
    page('index.html', 'Documentación de diseño', 'Una guía del alcance funcional, la estructura de datos y el comportamiento de LimpiezaSoft.', body)


if __name__ == '__main__':
    use_cases()
    entity_relationship()
    sequences()
    index()
    print(f'Generados 4 HTML y {9 + len(SEQUENCES)} SVG: {len(TABLES)} tablas y {len(RELATIONS)} relaciones.')
