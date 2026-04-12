from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.compras.models import DocumentoCompra
from apps.inventario.models import Almacen
from apps.inventario.services.stock_service import StockService
from apps.tesoreria.models import CronogramaPago, EstadoCronogramaPago
from apps.ventas.models import CondicionPagoDocumento, EstadoDocumento


class DocumentoCompraService:
    """Al emitir compra: ingreso a inventario (mismo flujo inverso a venta)."""

    @staticmethod
    def recalcular_totales(documento: DocumentoCompra) -> None:
        agg = documento.lineas.aggregate(s=Sum("subtotal"))
        raw = agg.get("s")
        subtotal = Decimal("0") if raw is None else Decimal(str(raw))
        subtotal = subtotal.quantize(Decimal("0.01"))
        igv = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        total = (subtotal + igv).quantize(Decimal("0.01"))
        documento.subtotal = subtotal
        documento.igv = igv
        documento.total = total
        documento.save(
            update_fields=["subtotal", "igv", "total", "actualizado_en"],
        )

    @staticmethod
    def _validar(documento: DocumentoCompra) -> None:
        if documento.estado != EstadoDocumento.BORRADOR:
            raise ValueError("Solo se pueden registrar compras en borrador.")
        lineas = list(documento.lineas.select_related("item").all())
        if not lineas:
            raise ValueError("El documento debe tener al menos una línea.")
        for ln in lineas:
            if ln.cantidad <= 0:
                raise ValueError("Cantidades deben ser mayores que cero.")
            if ln.item.empresa_id != documento.empresa_id:
                raise ValueError("El ítem no pertenece a la empresa del documento.")
        if documento.condicion_pago == CondicionPagoDocumento.CREDITO:
            if not documento.fecha_vencimiento:
                raise ValueError(
                    "En compra a crédito indique la fecha de vencimiento del pago al proveedor."
                )
            if documento.fecha_vencimiento < documento.fecha:
                raise ValueError(
                    "La fecha de vencimiento no puede ser anterior a la fecha del documento."
                )

    @staticmethod
    def _crear_cronograma_credito(documento: DocumentoCompra) -> None:
        """Solo crédito: obligación pendiente en tesorería (cronograma). Contado no genera fila."""
        if documento.condicion_pago != CondicionPagoDocumento.CREDITO:
            return
        if CronogramaPago.objects.filter(documento_compra=documento).exists():
            return
        s = (documento.serie or "").strip()
        n = (documento.numero or "").strip()
        ref = f"{s}-{n}".strip("-") if (s or n) else ""
        desc = (f"Factura compra {ref}".strip() if ref else f"Compra proveedor #{documento.id}")[:1024]
        CronogramaPago.objects.create(
            empresa=documento.empresa,
            proveedor=documento.proveedor,
            documento_compra=documento,
            descripcion=desc,
            monto=documento.total,
            fecha_vencimiento=documento.fecha_vencimiento,
            estado=EstadoCronogramaPago.PENDIENTE,
        )

    @classmethod
    @transaction.atomic
    def emitir(
        cls,
        documento: DocumentoCompra,
        *,
        almacen: Almacen,
        usuario=None,
    ) -> DocumentoCompra:
        cls._validar(documento)
        if almacen.sucursal.empresa_id != documento.empresa_id:
            raise ValueError("El almacén no pertenece a la empresa del documento.")
        lineas = [
            (ln.item, Decimal(ln.cantidad))
            for ln in documento.lineas.select_related("item").all()
        ]
        StockService.aplicar_ingreso(
            empresa_id=documento.empresa_id,
            almacen=almacen,
            lineas=lineas,
            referencia_tipo="DOCUMENTO_COMPRA",
            referencia_id=documento.id,
            usuario=usuario,
            glosa="Ingreso por compra",
        )
        documento.estado = EstadoDocumento.EMITIDO
        documento.save(update_fields=["estado", "actualizado_en"])
        cls._crear_cronograma_credito(documento)
        return documento
