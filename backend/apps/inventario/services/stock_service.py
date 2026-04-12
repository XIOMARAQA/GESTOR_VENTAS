from decimal import Decimal

from django.db import transaction

from apps.inventario.models import (
    Almacen,
    Item,
    MovimientoStock,
    MovimientoStockLinea,
    Stock,
    TipoMovimientoStock,
)


class StockInsuficienteError(ValueError):
    pass


class StockService:
    """Capa de dominio: movimientos de inventario e integridad de stock."""

    @staticmethod
    def _get_or_create_stock(item: Item, almacen: Almacen) -> Stock:
        stock, _ = Stock.objects.select_for_update().get_or_create(
            item=item,
            almacen=almacen,
            defaults={"cantidad": Decimal("0")},
        )
        return stock

    @classmethod
    @transaction.atomic
    def aplicar_salida(
        cls,
        *,
        empresa_id,
        almacen: Almacen,
        lineas: list[tuple[Item, Decimal]],
        referencia_tipo: str,
        referencia_id,
        usuario=None,
        glosa: str = "",
    ) -> MovimientoStock | None:
        to_process = [(item, cantidad) for item, cantidad in lineas if not item.es_servicio]
        if not to_process:
            return None
        mov = MovimientoStock.objects.create(
            empresa_id=empresa_id,
            almacen=almacen,
            tipo=TipoMovimientoStock.SALIDA,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            glosa=glosa,
            usuario=usuario,
        )
        for item, cantidad in to_process:
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor que cero.")
            stock = cls._get_or_create_stock(item, almacen)
            if stock.cantidad < cantidad:
                raise StockInsuficienteError(
                    f"Stock insuficiente para {item.nombre} en {almacen.nombre}."
                )
            stock.cantidad -= cantidad
            stock.save(update_fields=["cantidad"])
            MovimientoStockLinea.objects.create(
                movimiento=mov, item=item, cantidad=cantidad
            )
        return mov

    @classmethod
    @transaction.atomic
    def aplicar_ingreso(
        cls,
        *,
        empresa_id,
        almacen: Almacen,
        lineas: list[tuple[Item, Decimal]],
        referencia_tipo: str,
        referencia_id,
        usuario=None,
        glosa: str = "",
    ) -> MovimientoStock | None:
        to_process = [(item, cantidad) for item, cantidad in lineas if not item.es_servicio]
        if not to_process:
            return None
        mov = MovimientoStock.objects.create(
            empresa_id=empresa_id,
            almacen=almacen,
            tipo=TipoMovimientoStock.INGRESO,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            glosa=glosa,
            usuario=usuario,
        )
        for item, cantidad in to_process:
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor que cero.")
            stock = cls._get_or_create_stock(item, almacen)
            stock.cantidad += cantidad
            stock.save(update_fields=["cantidad"])
            MovimientoStockLinea.objects.create(
                movimiento=mov, item=item, cantidad=cantidad
            )
        return mov
