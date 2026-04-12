# Generated manually — ampliar tipos de documento de compra (paridad con ventas).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compras", "0003_documento_compra_subtotal_igv"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentocompra",
            name="tipo",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("FACTURA_COMPRA", "Factura"),
                    ("BOLETA_COMPRA", "Boleta"),
                    ("NOTA_COMPRA", "Nota de venta"),
                    ("RESUMEN_COMPRAS", "Resumen de boletas"),
                    ("GUIA_REMISION_COMPRA", "Guía de remisión"),
                    ("NOTA_CREDITO_PROVEEDOR", "Nota de crédito (proveedor)"),
                ],
            ),
        ),
    ]
