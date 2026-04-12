from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0005_categoria_activo"),
    ]

    operations = [
        migrations.AddField(
            model_name="almacen",
            name="activo",
            field=models.BooleanField(
                default=True,
                help_text="Si es False, el almacén no se ofrece en nuevos movimientos pero conserva historial.",
            ),
        ),
    ]
