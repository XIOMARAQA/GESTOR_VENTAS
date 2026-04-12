from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import Empresa, Sucursal, TimeStampedModel


class Categoria(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="categorias"
    )
    nombre = models.CharField(max_length=120)
    padre = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hijos",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Marca(TimeStampedModel):
    """Catálogo de marcas por empresa; opcional en ítems (marca NULL, típico en servicios)."""

    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="marcas"
    )
    nombre = models.CharField(max_length=120)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "Marcas"
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "nombre"],
                name="uniq_marca_nombre_por_empresa",
            ),
        ]

    def __str__(self):
        return self.nombre


class UnidadMedida(TimeStampedModel):
    """Catálogo de unidades por empresa: código operativo interno + código SUNAT Tabla 6 para comprobantes."""

    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="unidades_medida"
    )
    codigo = models.CharField(
        max_length=20,
        help_text="Código corto interno (p. ej. UND, KG, PAR); puede abreviarse según la empresa.",
    )
    nombre = models.CharField(max_length=120)
    codigo_sunat = models.CharField(
        max_length=80,
        blank=True,
        default="",
        verbose_name="código SUNAT (Tabla 6)",
        help_text="Código oficial SUNAT Tabla 6 (p. ej. NIU, KGM, ZZ) para comprobantes electrónicos.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo", "nombre"]
        verbose_name_plural = "Unidades de medida"
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "codigo"],
                name="uniq_unidad_medida_codigo_por_empresa",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"


class Atributo(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="atributos_item"
    )
    nombre = models.CharField(max_length=80)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Item(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="items")
    codigo = models.CharField(max_length=50, blank=True, db_index=True)
    nombre = models.CharField(max_length=255)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    marca = models.ForeignKey(
        Marca,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        related_name="items",
    )
    es_servicio = models.BooleanField(
        default=False,
        help_text="Si es True, no descuenta stock en ventas.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "codigo"],
                name="uniq_item_codigo_por_empresa",
                condition=~models.Q(codigo=""),
            ),
        ]

    def __str__(self):
        return self.nombre


class ItemAtributoValor(models.Model):
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="atributos_valor"
    )
    atributo = models.ForeignKey(Atributo, on_delete=models.CASCADE)
    valor = models.CharField(max_length=255)

    class Meta:
        unique_together = [["item", "atributo"]]

    def __str__(self):
        return f"{self.atributo}: {self.valor}"


class Almacen(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, related_name="almacenes"
    )
    nombre = models.CharField(max_length=120)
    es_principal = models.BooleanField(default=False)
    activo = models.BooleanField(
        default=True,
        help_text="Si es False, el almacén no se ofrece en nuevos movimientos pero conserva historial.",
    )

    class Meta:
        verbose_name_plural = "Almacenes"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.sucursal})"


class Stock(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stocks")
    almacen = models.ForeignKey(
        Almacen, on_delete=models.CASCADE, related_name="stocks"
    )
    cantidad = models.DecimalField(
        max_digits=18, decimal_places=4, default=0, validators=[MinValueValidator(0)]
    )

    class Meta:
        unique_together = [["item", "almacen"]]

    def __str__(self):
        return f"{self.item} @ {self.almacen}: {self.cantidad}"


class TipoMovimientoStock(models.TextChoices):
    INGRESO = "INGRESO", "Ingreso"
    SALIDA = "SALIDA", "Salida"
    AJUSTE = "AJUSTE", "Ajuste"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"


class MovimientoStock(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="movimientos_stock"
    )
    almacen = models.ForeignKey(
        Almacen, on_delete=models.CASCADE, related_name="movimientos"
    )
    tipo = models.CharField(max_length=20, choices=TipoMovimientoStock.choices)
    referencia_tipo = models.CharField(max_length=50, blank=True)
    referencia_id = models.BigIntegerField(null=True, blank=True)
    glosa = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-creado_en"]


class MovimientoStockLinea(models.Model):
    id = models.BigAutoField(primary_key=True)
    movimiento = models.ForeignKey(
        MovimientoStock, on_delete=models.CASCADE, related_name="lineas"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    cantidad = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )


class ListaPrecio(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="listas_precio"
    )
    nombre = models.CharField(max_length=120)
    moneda = models.CharField(max_length=3, default="PEN")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Listas de precio"

    def __str__(self):
        return self.nombre


class ListaPrecioItem(models.Model):
    lista = models.ForeignKey(
        ListaPrecio, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    precio = models.DecimalField(
        max_digits=18, decimal_places=4, validators=[MinValueValidator(0)]
    )

    class Meta:
        unique_together = [["lista", "item"]]
