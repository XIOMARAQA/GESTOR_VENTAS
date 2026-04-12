# Tablas físicas: script docs/sql/schema_negocio_bigint.sql (+ auth de Django).
# Esta migración solo actualiza el estado del ORM; no ejecuta CREATE TABLE.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Empresa",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("razon_social", models.CharField(max_length=255)),
                        (
                            "ruc",
                            models.CharField(blank=True, db_index=True, max_length=11),
                        ),
                        ("activo", models.BooleanField(default=True)),
                        (
                            "creado_en",
                            models.DateTimeField(auto_now_add=True),
                        ),
                    ],
                    options={
                        "db_table": "empresa",
                        "constraints": [
                            models.UniqueConstraint(
                                condition=models.Q(("ruc", ""), _negated=True),
                                fields=("ruc",),
                                name="uniq_empresa_ruc_no_vacio",
                            ),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name="Sucursal",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("nombre", models.CharField(max_length=120)),
                        ("direccion", models.TextField(blank=True)),
                        ("activo", models.BooleanField(default=True)),
                        (
                            "empresa",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="sucursales",
                                to="core.empresa",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "sucursal",
                    },
                ),
                migrations.CreateModel(
                    name="Proveedor",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("razon_social", models.CharField(max_length=255)),
                        (
                            "documento",
                            models.CharField(blank=True, db_index=True, max_length=20),
                        ),
                        ("activo", models.BooleanField(default=True)),
                        (
                            "empresa",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="proveedores",
                                to="core.empresa",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "proveedor",
                        "ordering": ["razon_social"],
                    },
                ),
                migrations.CreateModel(
                    name="Cliente",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("razon_social", models.CharField(blank=True, max_length=255)),
                        (
                            "documento",
                            models.CharField(blank=True, db_index=True, max_length=20),
                        ),
                        ("email", models.EmailField(blank=True, max_length=254)),
                        ("telefono", models.CharField(blank=True, max_length=40)),
                        ("activo", models.BooleanField(default=True)),
                        (
                            "empresa",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="clientes",
                                to="core.empresa",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "cliente",
                        "ordering": ["razon_social"],
                        "constraints": [
                            models.UniqueConstraint(
                                condition=models.Q(("documento", ""), _negated=True),
                                fields=("empresa", "documento"),
                                name="uniq_cliente_documento_por_empresa",
                            ),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name="Usuario",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "ruc",
                            models.CharField(db_index=True, max_length=11, unique=True),
                        ),
                        ("apellido_paterno", models.CharField(max_length=50)),
                        ("apellido_materno", models.CharField(max_length=50)),
                        ("nombre", models.CharField(max_length=100)),
                        ("email", models.EmailField(max_length=255, unique=True)),
                        ("password_hash", models.CharField(max_length=255)),
                        ("activo", models.BooleanField(default=True)),
                        (
                            "creado_en",
                            models.DateTimeField(auto_now_add=True),
                        ),
                        (
                            "empresa",
                            models.ForeignKey(
                                db_column="empresa_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="usuarios_legacy",
                                to="core.empresa",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "usuario",
                    },
                ),
                migrations.CreateModel(
                    name="PerfilUsuario",
                    fields=[
                        (
                            "creado_en",
                            models.DateTimeField(auto_now_add=True),
                        ),
                        (
                            "actualizado_en",
                            models.DateTimeField(auto_now=True),
                        ),
                        (
                            "id",
                            models.BigAutoField(
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("nombres", models.CharField(blank=True, max_length=120)),
                        (
                            "apellido_paterno",
                            models.CharField(blank=True, max_length=80),
                        ),
                        (
                            "apellido_materno",
                            models.CharField(blank=True, max_length=80),
                        ),
                        (
                            "empresa",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="usuarios_perfil",
                                to="core.empresa",
                            ),
                        ),
                        (
                            "user",
                            models.OneToOneField(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="perfil_gestor",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            "sucursal_default",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="usuarios_default",
                                to="core.sucursal",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "perfil_usuario",
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
