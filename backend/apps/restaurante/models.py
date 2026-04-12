from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import Sucursal, TimeStampedModel
from apps.inventario.models import Item


class EstadoComandaLinea(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    EN_PREPARACION = "EN_PREPARACION", "En preparación"
    LISTO = "LISTO", "Listo"
    ENTREGADO = "ENTREGADO", "Entregado"
    CANCELADO = "CANCELADO", "Cancelado"


class Comanda(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, related_name="comandas"
    )
    mesa = models.CharField(max_length=20, blank=True)
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-creado_en"]


class ComandaLinea(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    comanda = models.ForeignKey(
        Comanda, on_delete=models.CASCADE, related_name="lineas"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    cantidad = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )
    nota = models.TextField(blank=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoComandaLinea.choices,
        default=EstadoComandaLinea.PENDIENTE,
    )

    class Meta:
        ordering = ["creado_en"]
