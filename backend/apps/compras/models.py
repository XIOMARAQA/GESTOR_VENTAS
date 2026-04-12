from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import Empresa, Proveedor, TimeStampedModel
from apps.inventario.models import Item
from apps.ventas.models import CondicionPagoDocumento, EstadoDocumento


class TipoDocumentoCompra(models.TextChoices):
    FACTURA_COMPRA = "FACTURA_COMPRA", "Factura de compra"
    NOTA_CREDITO_PROVEEDOR = "NOTA_CREDITO_PROVEEDOR", "Nota de crédito proveedor"


class OrdenCompra(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="ordenes_compra"
    )
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT, related_name="ordenes_compra"
    )
    numero = models.CharField(max_length=30, blank=True)
    fecha = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.BORRADOR,
    )
    total = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["-fecha", "-creado_en"]


class OrdenCompraLinea(models.Model):
    id = models.BigAutoField(primary_key=True)
    orden = models.ForeignKey(
        OrdenCompra, on_delete=models.CASCADE, related_name="lineas"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    cantidad = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )
    precio_unit = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )


class DocumentoCompra(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="documentos_compra"
    )
    tipo = models.CharField(max_length=30, choices=TipoDocumentoCompra.choices)
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT, related_name="documentos_compra"
    )
    serie = models.CharField(max_length=10, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    fecha = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.BORRADOR,
    )
    subtotal = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Base imponible (suma de líneas sin IGV).",
    )
    igv = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="IGV 18% sobre la base imponible.",
    )
    total = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    precio_incluye_igv = models.BooleanField(
        default=False,
        help_text="Si es True, el precio unitario capturado al crear el documento incluía IGV.",
    )
    condicion_pago = models.CharField(
        max_length=10,
        choices=CondicionPagoDocumento.choices,
        default=CondicionPagoDocumento.CONTADO,
    )
    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        help_text="Obligatoria si la compra es a crédito (genera obligación en tesorería).",
    )
    es_electronica = models.BooleanField(default=False)
    hash_xml = models.CharField(max_length=64, blank=True)
    ruta_archivo = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]


class DocumentoCompraLinea(models.Model):
    id = models.BigAutoField(primary_key=True)
    documento = models.ForeignKey(
        DocumentoCompra, on_delete=models.CASCADE, related_name="lineas"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    cantidad = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )
    precio_unit = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )
    subtotal = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )


class GastoRecurrente(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="gastos_recurrentes"
    )
    concepto = models.CharField(max_length=255)
    monto = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )
    periodicidad = models.CharField(
        max_length=20,
        help_text="Ej: MENSUAL, SEMANAL",
    )
    dia_ejecucion = models.PositiveSmallIntegerField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    proxima_fecha = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["concepto"]
