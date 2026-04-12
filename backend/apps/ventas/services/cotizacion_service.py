from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from apps.ventas.models import Cotizacion, DocumentoVenta, EstadoDocumento


def cotizacion_bloqueada_por_comprobante_emitido(cot: Cotizacion) -> bool:
    """True si hay documento de venta vinculado y ya no está en BORRADOR (emitido SUNAT / stock, etc.)."""
    doc = (
        DocumentoVenta.objects.filter(cotizacion_origen_id=cot.pk).only("estado").first()
    )
    if doc is None:
        return False
    return doc.estado != EstadoDocumento.BORRADOR


class CotizacionService:
    @staticmethod
    @transaction.atomic
    def recalcular_totales(cot: Cotizacion) -> None:
        subtotal = sum((ln.subtotal for ln in cot.lineas.all()), Decimal("0"))
        cot.subtotal = subtotal
        cot.igv = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        cot.total = cot.subtotal + cot.igv
        cot.save(update_fields=["subtotal", "igv", "total", "actualizado_en"])

    @staticmethod
    def serie_interna_default() -> str:
        raw = (getattr(settings, "COTIZACION_SERIE_INTERNA", None) or "COT1") or "COT1"
        return (raw.strip() or "COT1")[:10]

    @classmethod
    def siguiente_correlativo(cls, empresa_id: int, serie: str) -> int:
        m = Cotizacion.objects.filter(empresa_id=empresa_id, serie=serie).aggregate(
            x=Max("correlativo")
        )
        return (m["x"] or 0) + 1

    @classmethod
    @transaction.atomic
    def emitir_interna(cls, cot: Cotizacion) -> Cotizacion:
        if cot.estado != EstadoDocumento.BORRADOR:
            raise ValueError("Solo se pueden emitir cotizaciones en borrador.")
        lineas = list(cot.lineas.select_related("item").all())
        if not lineas:
            raise ValueError("La cotización debe tener al menos una línea.")
        for ln in lineas:
            if ln.cantidad <= 0:
                raise ValueError("Todas las cantidades deben ser mayores que cero.")
            if ln.item.empresa_id != cot.empresa_id:
                raise ValueError("El ítem no pertenece a la empresa de la cotización.")

        serie = cls.serie_interna_default()
        next_c = cls.siguiente_correlativo(cot.empresa_id, serie)
        cot.serie = serie
        cot.correlativo = next_c
        cot.numero = str(next_c).zfill(4)
        cot.estado = EstadoDocumento.EMITIDO
        cot.save(
            update_fields=[
                "serie",
                "correlativo",
                "numero",
                "estado",
                "actualizado_en",
            ]
        )
        return cot
