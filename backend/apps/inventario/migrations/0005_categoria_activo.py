from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0004_rename_unidadmedida_codigo_close2u_codigo_sunat"),
    ]

    operations = [
        migrations.AddField(
            model_name="categoria",
            name="activo",
            field=models.BooleanField(default=True),
        ),
    ]
