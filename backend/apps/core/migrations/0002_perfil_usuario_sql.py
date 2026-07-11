from django.db import migrations


SQL = """
CREATE TABLE IF NOT EXISTS perfil_usuario (
    id                   BIGSERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,
    empresa_id           INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    sucursal_default_id  INTEGER REFERENCES sucursal(id) ON DELETE SET NULL,
    nombres              VARCHAR(120) NOT NULL DEFAULT '',
    apellido_paterno     VARCHAR(80) NOT NULL DEFAULT '',
    apellido_materno     VARCHAR(80) NOT NULL DEFAULT '',
    creado_en            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _create_perfil_usuario(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(_create_perfil_usuario, migrations.RunPython.noop),
    ]
