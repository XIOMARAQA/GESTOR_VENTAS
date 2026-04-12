"""Agregados para panel tipo dashboard (documento_venta)."""

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api_multitenancy import empresa_scope_for_request
from apps.ventas.models import DocumentoVenta, EstadoDocumento, TipoDocumentoVenta


class VentasDashboardView(APIView):
    """
    GET ?empresa=<id_empresa>&period=7d|30d|90d
    Resumen por tipo (subtotal = sin IGV) y conteo de comprobantes; evolución diaria.
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
        days = {"7d": 7, "1s": 7, "30d": 30, "1m": 30, "90d": 90, "3m": 90}.get(
            period, 30
        )
        start = timezone.localdate() - timedelta(days=days)
        qs = DocumentoVenta.objects.filter(
            empresa_id=empresa_id,
            fecha_emision__gte=start,
            estado=EstadoDocumento.EMITIDO,
        )

        por_tipo = list(
            qs.values("tipo")
            .annotate(
                total_sin_igv=Sum("subtotal"),
                comprobantes=Count("id"),
            )
            .order_by("tipo")
        )

        evolucion = list(
            qs.values("fecha_emision")
            .annotate(total_sin_igv=Sum("subtotal"))
            .order_by("fecha_emision")
        )

        etiquetas = {c.value: c.label for c in TipoDocumentoVenta}

        return Response(
            {
                "periodo_dias": days,
                "desde": str(start),
                "por_tipo": [
                    {
                        "tipo": row["tipo"],
                        "etiqueta": etiquetas.get(row["tipo"], row["tipo"]),
                        "total_sin_igv": str(row["total_sin_igv"] or 0),
                        "comprobantes": row["comprobantes"],
                    }
                    for row in por_tipo
                ],
                "evolucion": [
                    {
                        "fecha": str(row["fecha_emision"]),
                        "total_sin_igv": str(row["total_sin_igv"] or 0),
                    }
                    for row in evolucion
                ],
            }
        )
