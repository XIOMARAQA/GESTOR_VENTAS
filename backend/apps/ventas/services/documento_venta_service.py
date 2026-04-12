from decimal import Decimal

from django.db import transaction

from apps.inventario.models import Almacen
from apps.inventario.services.stock_service import StockInsuficienteError, StockService
from apps.tesoreria.services.cobranza_service import CobranzaService
from apps.ventas.models import CondicionPagoDocumento, DocumentoVenta, EstadoDocumento


class DocumentoVentaService:
    """
    Flujo: validar líneas → EMITIDO → descuenta stock (no servicios) → crea cobranza.
    Validaciones: al menos una línea, cantidades > 0, items de la misma empresa, almacén de la misma empresa/sucursal.
    """

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
        if almacen.sucursal.empresa_id != documento.empresa_id:
            raise ValueError("El almacén no pertenece a la empresa del documento.")
        lineas = [
            (ln.item, Decimal(ln.cantidad))
            for ln in documento.lineas.select_related(
                "item", "item__unidad_medida"
            ).all()
        ]
        try:
            StockService.aplicar_salida(
                empresa_id=documento.empresa_id,
                almacen=almacen,
                lineas=lineas,
                referencia_tipo="DOCUMENTO_VENTA",
                referencia_id=documento.id,
                usuario=usuario,
                glosa=f"Emisión {documento.tipo}",
            )
        except StockInsuficienteError:
            raise
        documento.estado = EstadoDocumento.EMITIDO
        documento.save(update_fields=["estado", "actualizado_en"])
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
