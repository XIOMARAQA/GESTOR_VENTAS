from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import Cliente, Empresa, Sucursal, TimeStampedModel, Vendedor
from apps.inventario.models import Almacen, Item


class TipoDocumentoVenta(models.TextChoices):
    FACTURA = "FACTURA", "Factura"
    BOLETA = "BOLETA", "Boleta"
    NOTA_VENTA = "NOTA_VENTA", "Nota de venta"
    RESUMEN_BOLETAS = "RESUMEN_BOLETAS", "Resumen de boletas"
    GUIA_REMISION = "GUIA_REMISION", "Guía de remisión"
    NOTA_CREDITO_CLIENTE = "NOTA_CREDITO_CLIENTE", "Nota de crédito (cliente)"


class EstadoDocumento(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    EMITIDO = "EMITIDO", "Emitido"
    ANULADO = "ANULADO", "Anulado"
    PAGADO_PARCIAL = "PAGADO_PARCIAL", "Pagado parcial"
    PAGADO = "PAGADO", "Pagado"


class OrigenPedido(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    CARGA_MASIVA = "CARGA_MASIVA", "Carga masiva"
    POS_ALEGRA = "POS_ALEGRA", "POS Alegra ventas"
    POS_GRIFOS = "POS_GRIFOS", "PDV Grifos"


class MonedaDocumento(models.TextChoices):
    PEN = "PEN", "PEN (S/)"
    USD = "USD", "USD ($)"


class CondicionPagoDocumento(models.TextChoices):
    CONTADO = "CONTADO", "Contado"
    CREDITO = "CREDITO", "Crédito"


class MedioPagoDocumento(models.TextChoices):
    EFECTIVO = "EFECTIVO", "Efectivo"
    DEPOSITO_CUENTA = "DEPOSITO_CUENTA", "Depósito en cuenta"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferencia bancaria"
    TARJETA_DEBITO = "TARJETA_DEBITO", "Tarjeta de débito"
    OTROS = "OTROS", "Otros medios de pago"
    TARJETA_CREDITO = "TARJETA_CREDITO", "Tarjeta de crédito"
    YAPE = "YAPE", "Yape"
    PLIN = "PLIN", "Plin"


class TipoOperacionSunat(models.TextChoices):
    VENTA_INTERNA = "VENTA_INTERNA", "Venta interna"
    ANTICIPO = "ANTICIPO", "Anticipo"
    REGULARIZACION_ANTICIPO = "REGULARIZACION_ANTICIPO", "Regularización de anticipo"
    EXPORTACION = "EXPORTACION", "Exportación"
    NO_DOMICILIADOS = "NO_DOMICILIADOS", "No domiciliados"
    VENTA_ITINERANTE = "VENTA_ITINERANTE", "Venta itinerante"


class Cotizacion(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="cotizaciones"
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cotizaciones",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cotizaciones",
    )
    """Serie interna (ej. COT1). Vacío en borrador hasta emitir cotización."""
    serie = models.CharField(max_length=10, blank=True, default="")
    """Parte numérica interna (ej. 0001). Vacío en borrador."""
    numero = models.CharField(max_length=20, blank=True, default="")
    correlativo = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Número secuencial interno por empresa+serie al emitir la cotización.",
    )
    fecha = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.BORRADOR,
    )
    subtotal = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    igv = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    observacion = models.TextField(blank=True, default="")
    moneda = models.CharField(
        max_length=3,
        choices=MonedaDocumento.choices,
        default=MonedaDocumento.PEN,
    )
    precio_incluye_igv = models.BooleanField(
        default=False,
        help_text="Si es True, el precio unitario en UI incluye IGV; se almacena línea sin IGV.",
    )
    condicion_pago = models.CharField(
        max_length=10,
        choices=CondicionPagoDocumento.choices,
        default=CondicionPagoDocumento.CONTADO,
    )
    fecha_vencimiento = models.DateField(null=True, blank=True)
    medio_pago = models.CharField(
        max_length=24,
        choices=MedioPagoDocumento.choices,
        blank=True,
        default="",
    )
    tipo_operacion = models.CharField(
        max_length=40,
        choices=TipoOperacionSunat.choices,
        default=TipoOperacionSunat.VENTA_INTERNA,
    )
    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cotizaciones",
    )

    class Meta:
        ordering = ["-fecha", "-creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "serie", "correlativo"],
                name="uniq_cotizacion_correlativo",
                condition=models.Q(correlativo__isnull=False) & ~models.Q(serie=""),
            ),
        ]


class CotizacionLinea(models.Model):
    id = models.BigAutoField(primary_key=True)
    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name="lineas"
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


class DocumentoVenta(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="documentos_venta"
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_venta",
    )
    tipo = models.CharField(max_length=30, choices=TipoDocumentoVenta.choices)
    serie = models.CharField(max_length=10, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_venta",
    )
    fecha_emision = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.BORRADOR,
    )
    subtotal = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    igv = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    nubefact_enlace = models.CharField(
        max_length=512,
        blank=True,
        help_text="URL del PDF/XML devuelta por Nubefact tras emitir.",
    )
    nubefact_sunat_codigo = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Código de respuesta SUNAT devuelto por Nubefact (p. ej. sunat_responsecode).",
    )
    nubefact_sunat_descripcion = models.TextField(
        blank=True,
        default="",
        help_text="Mensaje / descripción SUNAT devuelta por Nubefact (p. ej. sunat_description).",
    )
    observacion = models.TextField(blank=True)
    moneda = models.CharField(
        max_length=3,
        choices=MonedaDocumento.choices,
        default=MonedaDocumento.PEN,
    )
    precio_incluye_igv = models.BooleanField(
        default=False,
        help_text="Si es True, el precio unitario capturado en UI incluye IGV; se almacena línea sin IGV.",
    )
    condicion_pago = models.CharField(
        max_length=10,
        choices=CondicionPagoDocumento.choices,
        default=CondicionPagoDocumento.CONTADO,
    )
    fecha_vencimiento = models.DateField(null=True, blank=True)
    medio_pago = models.CharField(
        max_length=24,
        choices=MedioPagoDocumento.choices,
        blank=True,
        default="",
    )
    tipo_operacion = models.CharField(
        max_length=40,
        choices=TipoOperacionSunat.choices,
        default=TipoOperacionSunat.VENTA_INTERNA,
    )
    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_venta",
    )
    almacen = models.ForeignKey(
        Almacen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_venta",
        help_text="Almacén del movimiento de inventario al emitir (salida en F/B/NV; ingreso en NCC).",
    )
    cotizacion_origen = models.OneToOneField(
        "Cotizacion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documento_convertido",
        help_text="Si se generó este borrador desde una cotización interna emitida.",
    )

    class Meta:
        ordering = ["-fecha_emision", "-creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "tipo", "serie", "numero"],
                name="uniq_documento_venta_correlativo",
                condition=~models.Q(serie="") & ~models.Q(numero=""),
            ),
        ]


class DocumentoVentaLinea(models.Model):
    id = models.BigAutoField(primary_key=True)
    documento = models.ForeignKey(
        DocumentoVenta, on_delete=models.CASCADE, related_name="lineas"
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


class Pedido(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="pedidos"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    origen = models.CharField(
        max_length=20,
        choices=OrigenPedido.choices,
        default=OrigenPedido.MANUAL,
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.BORRADOR,
    )
    referencia_externa = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-creado_en"]


class PedidoLinea(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="lineas")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    cantidad = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )
    precio_unit = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
