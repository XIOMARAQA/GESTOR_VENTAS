-- Unidad de medida (catálogo por empresa) y FK en ítem.
-- En aplicaciones Django la fuente de verdad es la migración
-- inventario.0003_unidad_medida_item_fk; ejecutar: python manage.py migrate
--
-- Este script sirve como referencia DBA / greenfield fuera de Django.

-- Catálogo (tabla Django: inventario_unidadmedida)
CREATE TABLE IF NOT EXISTS inventario_unidadmedida (
    id                BIGSERIAL PRIMARY KEY,
    creado_en         TIMESTAMPTZ NOT NULL,
    actualizado_en    TIMESTAMPTZ NOT NULL,
    codigo            VARCHAR(20) NOT NULL,
    nombre            VARCHAR(120) NOT NULL,
    codigo_sunat      VARCHAR(80) NOT NULL DEFAULT '',
    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    empresa_id        BIGINT NOT NULL REFERENCES empresa (id) ON DELETE CASCADE,
    CONSTRAINT uniq_unidad_medida_codigo_por_empresa UNIQUE (empresa_id, codigo)
);

CREATE INDEX IF NOT EXISTS inventario_unidadmedida_empresa_id_codigo
    ON inventario_unidadmedida (empresa_id, codigo);

-- Ítem: columna Django inventario_item.unidad_medida_id (PROTECT → RESTRICT en SQL)
-- En bases ya migradas por Django, esta columna ya existe y reemplaza al antiguo VARCHAR.
-- Ejemplo greenfield (omitir si la tabla ya está creada):
-- ALTER TABLE inventario_item
--     ADD COLUMN unidad_medida_id BIGINT NOT NULL
--     REFERENCES inventario_unidadmedida (id) ON DELETE RESTRICT;

COMMENT ON TABLE inventario_unidadmedida IS 'Unidades de medida por empresa; productos referencian unidad_medida_id.';
