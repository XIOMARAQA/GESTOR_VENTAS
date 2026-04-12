"""Agregados para panel tipo dashboard (documento_venta)."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api_multitenancy import empresa_scope_for_request
from apps.ventas.models import (
    DocumentoVenta,
    DocumentoVentaLinea,
    EstadoDocumento,
    MonedaDocumento,
    TipoDocumentoVenta,
)

# Tipos mostrados en las tarjetas superiores del panel
TIPOS_PANEL = (
    TipoDocumentoVenta.FACTURA,
    TipoDocumentoVenta.BOLETA,
    TipoDocumentoVenta.NOTA_CREDITO_CLIENTE,
)

SUNAT_ACEPTADO = Q(nubefact_sunat_codigo="0")


def _parse_days(mapping: dict[str, int], key: str, default: int) -> int:
    if not key:
        return default
    k = key.strip().lower()
    return mapping.get(k, default)


def _vendedor_etiqueta(
    nombres: str | None,
    apellido_paterno: str | None,
    apellido_materno: str | None,
) -> str:
    parts = [
        (apellido_paterno or "").strip(),
        (apellido_materno or "").strip(),
        (nombres or "").strip(),
    ]
    s = ", ".join(p for p in parts if p)
    return s or "Sin nombre"


class VentasDashboardView(APIView):
    """
    GET ?empresa=<id>&period=7d|30d|90d|1s|1m|3m
        &evolucion=6m|9m|12m
        &detalle=m1|m6|m12
        &detalle_moneda=PEN|USD

    Resumen por tipo (subtotal sin IGV), comprobantes y aceptados SUNAT (código 0);
    evolución mensual en PEN y USD; top 5 productos y ventas por vendedor.
    """

    def get(self, request):
        scope = empresa_scope_for_request(request)
        if scope == -1:
            return Response(
                {"detail": "Usuario sin empresa asignada."},
                status=403,
            )
        if scope is not None:
            empresa_id = scope
        else:
            empresa_raw = request.query_params.get("empresa")
            if not empresa_raw:
                return Response(
                    {
                        "detail": "Parámetro query 'empresa' (ID numérico) es obligatorio "
                        "para administradores o modo sin autenticación."
                    },
                    status=400,
                )
            try:
                empresa_id = int(empresa_raw)
            except ValueError:
                return Response(
                    {"detail": "Parámetro 'empresa' debe ser un ID numérico válido."},
                    status=400,
                )

        period = request.query_params.get("period", "30d")
        days = _parse_days(
            {"7d": 7, "1s": 7, "30d": 30, "1m": 30, "90d": 90, "3m": 90},
            period,
            30,
        )
        start = timezone.localdate() - timedelta(days=days)

        evo_key = request.query_params.get("evolucion", "12m")
        evo_days = _parse_days(
            {"6m": 180, "9m": 270, "12m": 365, "180d": 180, "270d": 270, "365d": 365},
            evo_key,
            365,
        )
        start_evo = timezone.localdate() - timedelta(days=evo_days)

        det_key = request.query_params.get("detalle", "m6")
        det_days = _parse_days(
            {"m1": 30, "m6": 180, "m12": 365, "30d": 30, "180d": 180, "365d": 365},
            det_key,
            180,
        )
        start_detalle = timezone.localdate() - timedelta(days=det_days)

        moneda_raw = (request.query_params.get("detalle_moneda") or "PEN").upper()
        if moneda_raw not in (MonedaDocumento.PEN, MonedaDocumento.USD):
            moneda_raw = MonedaDocumento.PEN

        qs = DocumentoVenta.objects.filter(
            empresa_id=empresa_id,
            fecha_emision__gte=start,
            estado=EstadoDocumento.EMITIDO,
        )

        por_tipo_rows = {
            row["tipo"]: row
            for row in qs.values("tipo")
            .annotate(
                total_sin_igv=Sum("subtotal"),
                comprobantes=Count("id"),
                comprobantes_aceptados=Count("id", filter=SUNAT_ACEPTADO),
            )
        }

        etiquetas = {c.value: c.label for c in TipoDocumentoVenta}
        por_tipo = []
        for tipo in TIPOS_PANEL:
            row = por_tipo_rows.get(tipo)
            por_tipo.append(
                {
                    "tipo": tipo,
                    "etiqueta": etiquetas.get(tipo, tipo),
                    "total_sin_igv": str(row["total_sin_igv"] if row else Decimal(0)),
                    "comprobantes": row["comprobantes"] if row else 0,
                    "comprobantes_aceptados": row["comprobantes_aceptados"]
                    if row
                    else 0,
                }
            )

        qs_evo = DocumentoVenta.objects.filter(
            empresa_id=empresa_id,
            fecha_emision__gte=start_evo,
            estado=EstadoDocumento.EMITIDO,
        )
        evo_raw = list(
            qs_evo.annotate(mes=TruncMonth("fecha_emision"))
            .values("mes", "moneda")
            .annotate(total_sin_igv=Sum("subtotal"))
            .order_by("mes", "moneda")
        )
        by_month: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"pen": Decimal(0), "usd": Decimal(0)}
        )
        for row in evo_raw:
            mes = row["mes"]
            if not mes:
                continue
            key = mes.strftime("%Y-%m")
            amt = row["total_sin_igv"] or Decimal(0)
            if row["moneda"] == MonedaDocumento.USD:
                by_month[key]["usd"] += amt
            else:
                by_month[key]["pen"] += amt
        evolucion_mensual = [
            {
                "periodo": k,
                "pen": str(v["pen"]),
                "usd": str(v["usd"]),
            }
            for k, v in sorted(by_month.items())
        ]

        doc_detalle_filter = dict(
            documento__empresa_id=empresa_id,
            documento__fecha_emision__gte=start_detalle,
            documento__estado=EstadoDocumento.EMITIDO,
            documento__moneda=moneda_raw,
        )

        top_qs = (
            DocumentoVentaLinea.objects.filter(**doc_detalle_filter)
            .values("item_id", "item__nombre")
            .annotate(
                cantidad=Sum("cantidad"),
                monto_sin_igv=Sum("subtotal"),
            )
            .order_by("-cantidad", "-monto_sin_igv")[:5]
        )
        top_productos = [
            {
                "item_id": row["item_id"],
                "nombre": row["item__nombre"] or "",
                "cantidad": str(row["cantidad"] or 0),
                "monto_sin_igv": str(row["monto_sin_igv"] or 0),
            }
            for row in top_qs
        ]

        vend_rows = list(
            DocumentoVenta.objects.filter(
                empresa_id=empresa_id,
                fecha_emision__gte=start_detalle,
                estado=EstadoDocumento.EMITIDO,
                moneda=moneda_raw,
                vendedor_id__isnull=False,
            )
            .values(
                "vendedor_id",
                "vendedor__nombres",
                "vendedor__apellido_paterno",
                "vendedor__apellido_materno",
            )
            .annotate(
                total_sin_igv=Sum("subtotal"),
                comprobantes=Count("id"),
            )
            .order_by("-total_sin_igv")[:20]
        )
        por_vendedor = [
            {
                "vendedor_id": row["vendedor_id"],
                "nombre": _vendedor_etiqueta(
                    row["vendedor__nombres"],
                    row["vendedor__apellido_paterno"],
                    row["vendedor__apellido_materno"],
                ),
                "total_sin_igv": str(row["total_sin_igv"] or 0),
                "comprobantes": row["comprobantes"],
            }
            for row in vend_rows
        ]

        return Response(
            {
                "periodo_dias": days,
                "evolucion_periodo_dias": evo_days,
                "detalle_periodo_dias": det_days,
                "detalle_moneda": moneda_raw,
                "desde": str(start),
                "desde_evolucion": str(start_evo),
                "desde_detalle": str(start_detalle),
                "por_tipo": por_tipo,
                "evolucion_mensual": evolucion_mensual,
                "top_productos": top_productos,
                "por_vendedor": por_vendedor,
            }
        )
