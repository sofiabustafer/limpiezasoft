-- Mantener NULL para los empleados anteriores: no inferir su rol laboral.
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS rol_id INT REFERENCES roles(rol_id);

-- Reutilizar nombres existentes con diferencias de mayúsculas o acentos.
-- No renombrar ni eliminar departamentos, roles o asociaciones anteriores.
DO $$
DECLARE
    asignacion RECORD;
    id_departamento INT;
    id_rol INT;
BEGIN
    FOR asignacion IN
        SELECT * FROM (VALUES
            ('Limpiador', 'Clientes'),
            ('Informática', 'Informática'),
            ('Vendedor', 'Clientes'),
            ('Manager', 'Administración'),
            ('Contabilidad', 'Administración'),
            ('Recursos humanos', 'HR')
        ) AS vinculos(rol, departamento)
    LOOP
        SELECT departamento_id INTO id_departamento FROM departamentos
        WHERE lower(translate(btrim(nombre_departamento), 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou')) =
              lower(translate(asignacion.departamento, 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou'))
        ORDER BY departamento_id LIMIT 1;
        IF id_departamento IS NULL THEN
            INSERT INTO departamentos(nombre_departamento) VALUES (asignacion.departamento)
            RETURNING departamento_id INTO id_departamento;
        END IF;

        SELECT rol_id INTO id_rol FROM roles
        WHERE lower(translate(btrim(nombre_rol), 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou')) =
              lower(translate(asignacion.rol, 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou'))
        ORDER BY rol_id LIMIT 1;
        IF id_rol IS NULL THEN
            INSERT INTO roles(nombre_rol) VALUES (asignacion.rol)
            RETURNING rol_id INTO id_rol;
        END IF;

        INSERT INTO departamentos_roles(departamento_id, rol_id)
        VALUES (id_departamento, id_rol) ON CONFLICT DO NOTHING;
    END LOOP;
END $$;
