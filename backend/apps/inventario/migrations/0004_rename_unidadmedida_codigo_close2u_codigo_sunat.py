from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0003_unidad_medida_item_fk"),
    ]

    operations = [
        migrations.RenameField(
            model_name="unidadmedida",
            old_name="codigo_close2u",
            new_name="codigo_sunat",
        ),
    ]
