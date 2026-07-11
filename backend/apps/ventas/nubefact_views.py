import logging

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventario.models import Almacen
from apps.inventario.services.stock_service import StockInsuficienteError
from apps.tesoreria.services.cobranza_service import CobranzaService
from apps.ventas.models import (
    CondicionPagoDocumento,
    DocumentoVenta,
    EstadoDocumento,
    TipoDocumentoVenta,
)
from apps.ventas.serializers import DocumentoVentaSerializer, EmitirNubefactSerializer
from apps.ventas.services.documento_venta_service import DocumentoVentaService
from apps.ventas.services.nubefact_service import (
    construir_payload,
    enviar_a_nubefact,
    extraer_sunat_desde_respuesta_nubefact,
)

logger = logging.getLogger(__name__)


def _empresa_usuario(request):
    if not request.user.is_authenticated:
        return None
    if getattr(request.user, "is_superuser", False):
        return None
    perfil = getattr(request.user, "perfil_gestor", None)
    return perfil.empresa_id if perfil else None


def _respuesta_tiene_errors(resp: dict) -> bool:
    e = resp.get("errors")
    if e is None or e == "":
        return False
    if isinstance(e, (list, dict)) and len(e) == 0:
        return False
    return True


class NubefactConfigView(APIView):
    """Configuración no sensible: prueba URL y series (solo lo definido en .env)."""

    def get(self, request):
        url = getattr(settings, "NUBEFACT_PRUEBA_API_URL", "") or ""
        return Response(
            {
                "prueba_url_configurada": bool(url.strip()),
                "mensaje": "Configure NUBEFACT_PRUEBA_API_URL en .env para usar solo token + checkbox de prueba.",
                "series": {
                    "COTIZACION": getattr(settings, "COTIZACION_SERIE_INTERNA", "") or "",
                    "FACTURA": getattr(settings, "NUBEFACT_SERIE_FACTURA", "") or "",
                    "BOLETA": getattr(settings, "NUBEFACT_SERIE_BOLETA", "") or "",
                    "NOTA_CREDITO_FACTURA": getattr(
                        settings, "NUBEFACT_SERIE_NOTA_CREDITO_FACTURA", ""
                    )
                    or "",
                    "NOTA_DEBITO_FACTURA": getattr(
                        settings, "NUBEFACT_SERIE_NOTA_DEBITO_FACTURA", ""
                    )
                    or "",
                    "NOTA_CREDITO_BOLETA": getattr(
                        settings, "NUBEFACT_SERIE_NOTA_CREDITO_BOLETA", ""
                    )
                    or "",
                    "NOTA_DEBITO_BOLETA": getattr(
                        settings, "NUBEFACT_SERIE_NOTA_DEBITO_BOLETA", ""
                    )
                    or "",
                },
            }
        )


class EmitirNubefactView(APIView):
    """
    POST: emite un `documento_venta` en borrador vía Nubefact (generar_comprobante).

    Cuerpo mínimo: ``documento_id`` (usa ``NUBEFACT_API_URL`` y ``NUBEFACT_TOKEN`` del servidor).
    Opcional: ``api_url``, ``token`` para sobrescribir; o ``entorno_prueba`` + ``NUBEFACT_PRUEBA_API_URL``.
    """

    def post(self, request):
        ser = EmitirNubefactSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        api_url = ser.validated_data["api_url"]
        token = ser.validated_data["token"]
        doc_id = ser.validated_data["documento_id"]
        almacen_id = ser.validated_data.get("almacen_id")

        empresa_id = _empresa_usuario(request)
        qs = DocumentoVenta.objects.select_related("cliente", "empresa").prefetch_related(
            "lineas__item"
        )
        doc = get_object_or_404(qs, pk=doc_id)
        if empresa_id is not None and doc.empresa_id != empresa_id:
            return Response(
                {"detail": "No tiene acceso a este documento."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if doc.estado != EstadoDocumento.BORRADOR:
            return Response(
                {"detail": "Solo se pueden enviar a Nubefact documentos en estado BORRADOR."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if doc.condicion_pago == CondicionPagoDocumento.CREDITO:
            if not doc.fecha_vencimiento:
                return Response(
                    {
                        "detail": "En venta a crédito indique la fecha de vencimiento antes de emitir.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if doc.fecha_vencimiento < doc.fecha_emision:
                return Response(
                    {
                        "detail": "La fecha de vencimiento no puede ser anterior a la fecha de emisión.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        almacen = None
        if DocumentoVentaService.tipo_requiere_almacen_inventario(doc.tipo):
            if not almacen_id:
                return Response(
                    {
                        "detail": "Indique almacen_id para vincular la salida o ingreso de inventario al emitir este comprobante.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            almacen = get_object_or_404(
                Almacen.objects.select_related("sucursal"), pk=almacen_id
            )
            if almacen.sucursal.empresa_id != doc.empresa_id:
                return Response(
                    {"detail": "El almacén no pertenece a la empresa del documento."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                DocumentoVentaService.verificar_suficiencia_stock(doc, almacen)
            except StockInsuficienteError as e:
                return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        try:
            payload = construir_payload(doc)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        logger.info("Nubefact: enviando documento_id=%s tipo=%s", doc.pk, doc.tipo)
        resp = enviar_a_nubefact(api_url, token, payload)

        if _respuesta_tiene_errors(resp):
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        doc.estado = EstadoDocumento.EMITIDO
        update_fields = ["estado", "actualizado_en"]
        if resp.get("serie"):
            doc.serie = str(resp["serie"])[:10]
            update_fields.append("serie")
        if resp.get("numero"):
            doc.numero = str(resp["numero"])[:20]
            update_fields.append("numero")
        enlace = resp.get("enlace") or resp.get("enlace_del_pdf") or ""
        if enlace:
            doc.nubefact_enlace = str(enlace)[:512]
            update_fields.append("nubefact_enlace")
        sunat_cod, sunat_desc = extraer_sunat_desde_respuesta_nubefact(resp)
        doc.nubefact_sunat_codigo = sunat_cod
        doc.nubefact_sunat_descripcion = sunat_desc
        update_fields.extend(["nubefact_sunat_codigo", "nubefact_sunat_descripcion"])
        if almacen is not None:
            doc.almacen = almacen
            update_fields.append("almacen")

        user = request.user if request.user.is_authenticated else None
        try:
            with transaction.atomic():
                if almacen is not None:
                    DocumentoVentaService.aplicar_movimiento_inventario(
                        doc, almacen=almacen, usuario=user
                    )
                doc.save(update_fields=update_fields)
                if doc.tipo != TipoDocumentoVenta.NOTA_CREDITO_CLIENTE:
                    CobranzaService.crear_desde_documento(doc, usuario=user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except StockInsuficienteError as e:
            return Response(
                {
                    "detail": f"{e} El comprobante ya fue aceptado en SUNAT; revise stock o contacte soporte.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "ok": True,
                "nubefact": resp,
                "documento": DocumentoVentaSerializer(doc).data,
            },
            status=status.HTTP_200_OK,
        )
