from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("compras", "0004_documentocompra_tipos_ampliados"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentocompra",
            name="afecta_stock",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Si es False, al registrar (emitir) el documento no genera movimientos de inventario "
                    "(no aparece en kardex). Útil para compras contables sin mercadería."
                ),
            ),
        ),
    ]
