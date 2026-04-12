# Generated manually for NotificacionUsuario

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0004_empresa_registro_aprobado"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificacionUsuario",
            fields=[
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("titulo", models.CharField(max_length=200)),
                ("mensaje", models.TextField()),
                ("leida", models.BooleanField(default=False)),
                ("categoria", models.CharField(blank=True, db_index=True, max_length=40)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notificaciones_gestor",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "notificacion_usuario",
                "ordering": ["-creado_en"],
            },
        ),
    ]
