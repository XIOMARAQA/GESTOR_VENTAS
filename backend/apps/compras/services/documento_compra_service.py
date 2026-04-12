from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.compras.models import DocumentoCompra, TipoDocumentoCompra
from apps.inventario.models import Almacen, MovimientoStock, TipoMovimientoStock
from apps.inventario.services.stock_service import StockInsuficienteError, StockService
from apps.tesoreria.models import CronogramaPago, EstadoCronogramaPago
from apps.ventas.models import CondicionPagoDocumento, EstadoDocumento


class DocumentoCompraService:
    """Al emitir: factura/boleta/nota de compra ingresan stock; N.C. proveedor sale; resumen/guía no mueven kardex."""

    _TIPOS_INGRESO_STOCK = frozenset(
        {
            TipoDocumentoCompra.FACTURA_COMPRA,
            TipoDocumentoCompra.BOLETA_COMPRA,
            TipoDocumentoCompra.NOTA_COMPRA,
        }
    )
    _TIPOS_SIN_MOVIMIENTO_STOCK = frozenset(
        {
            TipoDocumentoCompra.RESUMEN_COMPRAS,
            TipoDocumentoCompra.GUIA_REMISION_COMPRA,
        }
    )
    _TIPOS_CRONOGRAMA_CREDITO = _TIPOS_INGRESO_STOCK

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
        tipo_txt = documento.get_tipo_display()
        base = f"{tipo_txt} {ref}".strip() if ref else f"{tipo_txt} #{documento.id}"
        desc = base[:1024]
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
        glosa_ing = f"Ingreso por {documento.get_tipo_display()}"
        if documento.tipo in cls._TIPOS_INGRESO_STOCK:
            StockService.aplicar_ingreso(
                empresa_id=documento.empresa_id,
                almacen=almacen,
                lineas=lineas,
                referencia_tipo="DOCUMENTO_COMPRA",
                referencia_id=documento.id,
                usuario=usuario,
                glosa=glosa_ing,
            )
        elif documento.tipo == TipoDocumentoCompra.NOTA_CREDITO_PROVEEDOR:
            try:
                StockService.aplicar_salida(
                    empresa_id=documento.empresa_id,
                    almacen=almacen,
                    lineas=lineas,
                    referencia_tipo="DOCUMENTO_COMPRA",
                    referencia_id=documento.id,
                    usuario=usuario,
                    glosa="Salida por nota de crédito proveedor (devolución)",
                )
            except StockInsuficienteError:
                raise
        elif documento.tipo in cls._TIPOS_SIN_MOVIMIENTO_STOCK:
            pass
        else:
            raise ValueError(f"Tipo de compra no contemplado para stock: {documento.tipo}")
        documento.estado = EstadoDocumento.EMITIDO
        documento.save(update_fields=["estado", "actualizado_en"])
        if documento.tipo in cls._TIPOS_CRONOGRAMA_CREDITO:
            cls._crear_cronograma_credito(documento)
        return documento

    @classmethod
    @transaction.atomic
    def anular(
        cls,
        documento: DocumentoCompra,
        *,
        usuario=None,
    ) -> DocumentoCompra:
        """
        Borrador: pasa a ANULADO (sin tocar inventario).
        Emitido: revierte un movimiento de stock vinculado (si existe), elimina cronogramas
        solo si no hay pagos registrados, y marca ANULADO.
        """
        if documento.estado == EstadoDocumento.ANULADO:
            raise ValueError("El documento ya está anulado.")
        if documento.estado == EstadoDocumento.BORRADOR:
            documento.estado = EstadoDocumento.ANULADO
            documento.save(update_fields=["estado", "actualizado_en"])
            return documento
        if documento.estado != EstadoDocumento.EMITIDO:
            raise ValueError("Solo se pueden anular borradores o documentos registrados.")

        for cr in CronogramaPago.objects.filter(documento_compra=documento):
            if cr.estado == EstadoCronogramaPago.PAGADO or cr.pagos_registro.exists():
                raise ValueError(
                    "No se puede anular: hay obligaciones pagadas o pagos registrados en tesorería."
                )

        mov = (
            MovimientoStock.objects.filter(
                referencia_tipo="DOCUMENTO_COMPRA",
                referencia_id=documento.id,
            )
            .select_related("almacen")
            .prefetch_related("lineas__item")
            .order_by("-id")
            .first()
        )
        if mov is not None:
            lineas_tuples = [
                (ln.item, Decimal(ln.cantidad))
                for ln in mov.lineas.select_related("item").all()
            ]
            if mov.tipo == TipoMovimientoStock.INGRESO:
                StockService.aplicar_salida(
                    empresa_id=documento.empresa_id,
                    almacen=mov.almacen,
                    lineas=lineas_tuples,
                    referencia_tipo="ANULACION_DOCUMENTO_COMPRA",
                    referencia_id=documento.id,
                    usuario=usuario,
                    glosa=f"Anulación {documento.get_tipo_display()}",
                )
            elif mov.tipo == TipoMovimientoStock.SALIDA:
                StockService.aplicar_ingreso(
                    empresa_id=documento.empresa_id,
                    almacen=mov.almacen,
                    lineas=lineas_tuples,
                    referencia_tipo="ANULACION_DOCUMENTO_COMPRA",
                    referencia_id=documento.id,
                    usuario=usuario,
                    glosa="Anulación nota de crédito proveedor",
                )

        CronogramaPago.objects.filter(documento_compra=documento).delete()
        documento.estado = EstadoDocumento.ANULADO
        documento.save(update_fields=["estado", "actualizado_en"])
        return documento
