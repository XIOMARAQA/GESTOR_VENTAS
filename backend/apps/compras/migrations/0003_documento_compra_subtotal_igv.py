from decimal import Decimal

from django.db import migrations, models
import django.core.validators
from django.db.models import Sum


def backfill_subtotal_igv_total(apps, schema_editor):
    DocumentoCompra = apps.get_model("compras", "DocumentoCompra")
    for doc in DocumentoCompra.objects.all():
        agg = doc.lineas.aggregate(s=Sum("subtotal"))
        raw = agg.get("s")
        grav = Decimal("0") if raw is None else Decimal(str(raw))
        if grav == 0 and doc.total:
            grav = Decimal(str(doc.total))
        igv = (grav * Decimal("0.18")).quantize(Decimal("0.01"))
        doc.subtotal = grav.quantize(Decimal("0.01"))
        doc.igv = igv
        doc.total = (grav + igv).quantize(Decimal("0.01"))
        doc.save(update_fields=["subtotal", "igv", "total"])


class Migration(migrations.Migration):

    dependencies = [
        ("compras", "0002_condicion_pago_tesoreria"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentocompra",
            name="subtotal",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Base imponible (suma de líneas sin IGV).",
                max_digits=18,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="documentocompra",
            name="igv",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="IGV 18% sobre la base imponible.",
                max_digits=18,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="documentocompra",
            name="precio_incluye_igv",
            field=models.BooleanField(
                default=False,
                help_text="Si es True, el precio unitario capturado al crear el documento incluía IGV.",
            ),
        ),
        migrations.RunPython(backfill_subtotal_igv_total, migrations.RunPython.noop),
    ]
