# Tabla usuario: core.0001 solo actualiza estado ORM; esta migración la crea en PostgreSQL.

from django.db import migrations

SQL = """
CREATE TABLE IF NOT EXISTS usuario (
    id                  BIGSERIAL PRIMARY KEY,
    empresa_id          BIGINT NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    ruc                 VARCHAR(11) NOT NULL UNIQUE,
    apellido_paterno    VARCHAR(50) NOT NULL,
    apellido_materno    VARCHAR(50) NOT NULL,
    nombre              VARCHAR(100) NOT NULL,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS usuario_empresa_id_idx ON usuario (empresa_id);
CREATE INDEX IF NOT EXISTS usuario_ruc_idx ON usuario (ruc);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_proveedor_contacto"),
    ]

    operations = [
        migrations.RunSQL(SQL, migrations.RunSQL.noop),
    ]
