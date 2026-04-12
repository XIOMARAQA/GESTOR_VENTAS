from decimal import Decimal

from django.db import transaction

from apps.inventario.models import Almacen, Stock
from apps.inventario.services.stock_service import StockInsuficienteError, StockService
from apps.tesoreria.services.cobranza_service import CobranzaService
from apps.ventas.models import (
    CondicionPagoDocumento,
    DocumentoVenta,
    EstadoDocumento,
    TipoDocumentoVenta,
)


class DocumentoVentaService:
    """
    Flujo: validar líneas → EMITIDO → movimiento de stock según tipo → cobranza (si aplica).

    Inventario al emitir:
    - Restan stock: factura, boleta, nota de venta (ventas que despachan mercadería).
    - Suman stock: nota de crédito cliente (devolución).
    - Sin movimiento de stock: resumen de boletas, guía de remisión (no consolidan kardex aquí).

    Validaciones: al menos una línea, cantidades > 0, ítems de la misma empresa, almacén de la misma empresa.
    """

    _TIPOS_STOCK_SALIDA = frozenset(
        {
            TipoDocumentoVenta.FACTURA,
            TipoDocumentoVenta.BOLETA,
            TipoDocumentoVenta.NOTA_VENTA,
        }
    )

    @classmethod
    def tipo_requiere_almacen_inventario(cls, tipo: str) -> bool:
        return tipo in cls._TIPOS_STOCK_SALIDA or tipo == TipoDocumentoVenta.NOTA_CREDITO_CLIENTE

    @classmethod
    def verificar_suficiencia_stock(cls, documento: DocumentoVenta, almacen: Almacen) -> None:
        """Solo salidas con mercadería; evita llamar a SUNAT si no hay stock (sin bloqueo fuerte)."""
        if documento.tipo not in cls._TIPOS_STOCK_SALIDA:
            return
        for ln in documento.lineas.select_related("item").all():
            if ln.item.es_servicio:
                continue
            cant = Decimal(ln.cantidad)
            row = Stock.objects.filter(item_id=ln.item_id, almacen_id=almacen.pk).first()
            disp = Decimal(row.cantidad) if row else Decimal("0")
            if disp < cant:
                raise StockInsuficienteError(
                    f"Stock insuficiente para {ln.item.nombre} en {almacen.nombre}."
                )

    @classmethod
    def aplicar_movimiento_inventario(
        cls,
        documento: DocumentoVenta,
        *,
        almacen: Almacen,
        usuario=None,
    ) -> None:
        """Salida (F/B/NV) o ingreso (NCC) según tipo; no modifica estado ni cobranza."""
        if almacen.sucursal.empresa_id != documento.empresa_id:
            raise ValueError("El almacén no pertenece a la empresa del documento.")
        lineas = [
            (ln.item, Decimal(ln.cantidad))
            for ln in documento.lineas.select_related(
                "item", "item__unidad_medida"
            ).all()
        ]
        tipo = documento.tipo
        if tipo == TipoDocumentoVenta.NOTA_CREDITO_CLIENTE:
            StockService.aplicar_ingreso(
                empresa_id=documento.empresa_id,
                almacen=almacen,
                lineas=lineas,
                referencia_tipo="DOCUMENTO_VENTA",
                referencia_id=documento.id,
                usuario=usuario,
                glosa="Ingreso por nota de crédito cliente (devolución)",
            )
        elif tipo in cls._TIPOS_STOCK_SALIDA:
            try:
                StockService.aplicar_salida(
                    empresa_id=documento.empresa_id,
                    almacen=almacen,
                    lineas=lineas,
                    referencia_tipo="DOCUMENTO_VENTA",
                    referencia_id=documento.id,
                    usuario=usuario,
                    glosa=f"Salida por emisión {tipo}",
                )
            except StockInsuficienteError:
                raise
        elif tipo in (
            TipoDocumentoVenta.RESUMEN_BOLETAS,
            TipoDocumentoVenta.GUIA_REMISION,
        ):
            return
        else:
            raise ValueError(f"Tipo de venta no contemplado para inventario: {tipo}")

    @staticmethod
    def _validar_antes_emitir(documento: DocumentoVenta) -> None:
        if documento.estado != EstadoDocumento.BORRADOR:
            raise ValueError("Solo se pueden emitir documentos en borrador.")
        lineas = list(
            documento.lineas.select_related("item", "item__unidad_medida").all()
        )
        if not lineas:
            raise ValueError("El documento debe tener al menos una línea.")
        for ln in lineas:
            if ln.cantidad <= 0:
                raise ValueError("Todas las cantidades deben ser mayores que cero.")
            if ln.item.empresa_id != documento.empresa_id:
                raise ValueError("El ítem no pertenece a la empresa del documento.")
        if documento.condicion_pago == CondicionPagoDocumento.CREDITO:
            if not documento.fecha_vencimiento:
                raise ValueError("En venta a crédito indique la fecha de vencimiento.")
            if documento.fecha_vencimiento < documento.fecha_emision:
                raise ValueError(
                    "La fecha de vencimiento no puede ser anterior a la fecha de emisión."
                )

    @classmethod
    @transaction.atomic
    def emitir(
        cls,
        documento: DocumentoVenta,
        *,
        almacen: Almacen,
        usuario=None,
    ) -> DocumentoVenta:
        cls._validar_antes_emitir(documento)
        cls.aplicar_movimiento_inventario(
            documento, almacen=almacen, usuario=usuario
        )
        documento.almacen = almacen
        documento.estado = EstadoDocumento.EMITIDO
        documento.save(update_fields=["almacen", "estado", "actualizado_en"])
        if documento.tipo != TipoDocumentoVenta.NOTA_CREDITO_CLIENTE:
            CobranzaService.crear_desde_documento(documento, usuario=usuario)
        return documento

    @staticmethod
    @transaction.atomic
    def recalcular_totales(documento: DocumentoVenta) -> None:
        subtotal = sum((ln.subtotal for ln in documento.lineas.all()), Decimal("0"))
        documento.subtotal = subtotal
        documento.igv = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        documento.total = documento.subtotal + documento.igv
        documento.save(update_fields=["subtotal", "igv", "total", "actualizado_en"])
