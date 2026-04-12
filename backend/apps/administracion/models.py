from django.conf import settings
from django.db import models

from apps.core.models import Empresa, TimeStampedModel


class ConfiguracionSistema(TimeStampedModel):
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="configuraciones"
    )
    clave = models.CharField(max_length=100, db_index=True)
    valor = models.JSONField(default=dict)

    class Meta:
        unique_together = [["empresa", "clave"]]
        verbose_name_plural = "Configuraciones del sistema"


class Tarea(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tareas_gestor",
    )
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    completada = models.BooleanField(default=False)
    fecha_limite = models.DateField(null=True, blank=True)
    modulo = models.CharField(
        max_length=40,
        blank=True,
        help_text="Ej: ventas, tesoreria",
    )

    class Meta:
        ordering = ["completada", "fecha_limite", "-creado_en"]
