-- Cambio aditivo: conserva los estados existentes y les asigna un color inicial.
ALTER TABLE estados_servicio
    ADD COLUMN IF NOT EXISTS color TEXT NOT NULL DEFAULT '#087F72'
    CHECK (color ~ '^#[0-9A-Fa-f]{6}$');
