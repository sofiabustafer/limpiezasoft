"""Roles laborales admitidos y su asignación de departamento."""
import unicodedata

ROLES_DEPARTAMENTOS = (
    ('Limpiador', 'Clientes'),
    ('Informática', 'Informática'),
    ('Vendedor', 'Clientes'),
    ('Manager', 'Administración'),
    ('Contabilidad', 'Administración'),
    ('Recursos humanos', 'HR'),
)


def normalizar_nombre(valor):
    return ''.join(c for c in unicodedata.normalize('NFD', valor.strip().casefold())
                   if not unicodedata.combining(c))


def roles_laborales(asociaciones):
    """Filtra las asociaciones del catálogo según las asignaciones autorizadas."""
    resultado = []
    for rol, departamento in ROLES_DEPARTAMENTOS:
        compatibles = [a for a in asociaciones
                       if normalizar_nombre(a['nombre']) == normalizar_nombre(rol)
                       and normalizar_nombre(a['departamento_nombre']) == normalizar_nombre(departamento)]
        if compatibles:
            # Reutiliza el identificador más antiguo si el catálogo contiene alias.
            elegido = min(compatibles, key=lambda a: (a['id'], a['departamento_id']))
            resultado.append(dict(elegido, nombre=rol, departamento_nombre=departamento))
    return resultado
