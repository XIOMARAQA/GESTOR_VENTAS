from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import Empresa, Proveedor, Sucursal, TimeStampedModel
from apps.ventas.models import DocumentoVenta


class EstadoCronogramaPago(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    PAGADO = "PAGADO", "Pagado"


class CuentaBancaria(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="cuentas_bancarias"
    )
    banco = models.CharField(max_length=100, blank=True)
    numero = models.CharField(max_length=40, blank=True)
    moneda = models.CharField(max_length=3, default="PEN")
    saldo = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Cuentas bancarias"


class Caja(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="cajas",
    )
    nombre = models.CharField(max_length=80)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class EstadoCobranza(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    PAGADO_PARCIAL = "PAGADO_PARCIAL", "Pagado parcial"
    PAGADO = "PAGADO", "Pagado"
    VENCIDO = "VENCIDO", "Vencido"


class Cobranza(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="cobranzas"
    )
    documento_venta = models.ForeignKey(
        DocumentoVenta,
        on_delete=models.CASCADE,
        related_name="cobranzas",
    )
    monto_total = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )
    monto_pagado = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoCobranza.choices,
        default=EstadoCobranza.PENDIENTE,
    )

    class Meta:
        # Recientes primero: al paginar, la emisión de hoy aparece arriba (antes quedaba al final por vencimiento).
        ordering = ["-creado_en", "-id"]


class PagoRecibido(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="pagos_recibidos"
    )
    cobranza = models.ForeignKey(
        Cobranza,
        on_delete=models.CASCADE,
        related_name="pagos",
        null=True,
        blank=True,
    )
    monto = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )
    metodo = models.CharField(max_length=30)
    cuenta_bancaria = models.ForeignKey(
        CuentaBancaria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    caja = models.ForeignKey(
        Caja,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    usuario = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-creado_en"]


class CronogramaPago(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="cronograma_pagos"
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cronograma_pagos",
    )
    documento_compra = models.ForeignKey(
        "compras.DocumentoCompra",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cronograma_pagos",
    )
    descripcion = models.TextField(blank=True)
    monto = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )
    fecha_vencimiento = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=EstadoCronogramaPago.choices,
        default=EstadoCronogramaPago.PENDIENTE,
    )

    class Meta:
        ordering = ["fecha_vencimiento"]


class PagoRealizadoProveedor(TimeStampedModel):
    """Registro de cada pago a proveedor (equivalente a PagoRecibido en ventas)."""

    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="pagos_realizados_proveedor"
    )
    cronograma_pago = models.ForeignKey(
        CronogramaPago,
        on_delete=models.CASCADE,
        related_name="pagos_registro",
    )
    monto = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )
    metodo = models.CharField(max_length=30)
    usuario = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-creado_en"]


class ConciliacionBancaria(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    cuenta = models.ForeignKey(
        CuentaBancaria,
        on_delete=models.CASCADE,
        related_name="conciliaciones",
    )
    periodo = models.CharField(max_length=7, help_text="YYYY-MM")
    saldo_libro = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    saldo_banco = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    cerrada = models.BooleanField(default=False)

    class Meta:
        unique_together = [["cuenta", "periodo"]]
        verbose_name_plural = "Conciliaciones bancarias"
