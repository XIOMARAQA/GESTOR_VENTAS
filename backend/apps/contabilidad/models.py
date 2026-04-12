from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import Empresa, TimeStampedModel


class PlanCuenta(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="plan_cuentas"
    )
    codigo = models.CharField(max_length=20, db_index=True)
    nombre = models.CharField(max_length=255)
    tipo = models.CharField(max_length=30)
    es_activo = models.BooleanField(
        default=False,
        help_text="Marcar si representa un activo fijo / cuenta de activo.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Plan de cuentas"
        ordering = ["codigo"]
        unique_together = [["empresa", "codigo"]]


class AsientoContable(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="asientos"
    )
    fecha = models.DateField()
    glosa = models.TextField(blank=True)
    origen_tipo = models.CharField(max_length=50, blank=True)
    origen_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]


class AsientoLinea(models.Model):
    id = models.BigAutoField(primary_key=True)
    asiento = models.ForeignKey(
        AsientoContable, on_delete=models.CASCADE, related_name="lineas"
    )
    cuenta = models.ForeignKey(
        PlanCuenta, on_delete=models.PROTECT, related_name="lineas_asiento"
    )
    debe = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    haber = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )


class ComunicacionBaja(TimeStampedModel):
    """Registro de comunicaciones de baja (fiscal / documentos)."""

    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="comunicaciones_baja"
    )
    fecha = models.DateField()
    descripcion = models.TextField(blank=True)
    referencia_tipo = models.CharField(max_length=50, blank=True)
    referencia_id = models.BigIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, default="REGISTRADO")

    class Meta:
        ordering = ["-fecha"]
