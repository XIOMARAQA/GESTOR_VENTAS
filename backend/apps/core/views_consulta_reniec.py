"""
Consulta DNI (RENIEC) vía Decolecta — mismo token Bearer que consulta RUC (APIS_NET_PE_TOKEN).

GET ?numero=12345678  →  autocompletar nombres en formulario de cliente (razón social / nombre completo).
"""

from __future__ import annotations

import logging
import re

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.decolecta_client import decolecta_get_reniec_dni
from apps.core.views_consulta_ruc import (
    _humanize_provider_error,
    _normalize_bearer_token,
    _provider_error_detail,
)

logger = logging.getLogger(__name__)

DNI_RE = re.compile(r"^\d{8}$")


def _reniec_data_dict(body: dict) -> dict:
    """Payload útil (Decolecta suele anidar en ``data``)."""
    if not isinstance(body, dict):
        return {}
    inner = body.get("data")
    if isinstance(inner, dict):
        return inner
    return body


def _partes_nombres_reniec(body: dict) -> tuple[str, str, str]:
    """Apellido paterno, materno y nombres si vienen explícitos en el JSON."""
    d = _reniec_data_dict(body)
    ap1 = (
        d.get("first_last_name")
        or d.get("apellidoPaterno")
        or d.get("apellido_paterno")
        or ""
    )
    ap2 = (
        d.get("second_last_name")
        or d.get("apellidoMaterno")
        or d.get("apellido_materno")
        or ""
    )
    fn = d.get("first_name") or d.get("nombres") or ""
    ap1 = ap1.strip() if isinstance(ap1, str) else ""
    ap2 = ap2.strip() if isinstance(ap2, str) else ""
    fn = fn.strip() if isinstance(fn, str) else ""
    return ap1, ap2, fn


def _nombre_desde_reniec(data: dict) -> str:
    """Arma texto para el campo único ``razon_social`` del cliente (persona natural).

    Decolecta documentación típica (200):
      ``full_name``, ``first_name``, ``first_last_name``, ``second_last_name``, ``document_number``.
    """
    data = _reniec_data_dict(data)

    for key in (
        "full_name",
        "nombreCompleto",
        "nombre_completo",
        "nombreCompletoReniec",
    ):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # Decolecta RENIEC DNI (snake_case)
    fn = data.get("first_name")
    fn = fn.strip() if isinstance(fn, str) else ""
    ap1 = (
        data.get("first_last_name")
        or data.get("apellidoPaterno")
        or data.get("apellido_paterno")
        or ""
    )
    ap2 = (
        data.get("second_last_name")
        or data.get("apellidoMaterno")
        or data.get("apellido_materno")
        or ""
    )
    ap1 = ap1.strip() if isinstance(ap1, str) else ""
    ap2 = ap2.strip() if isinstance(ap2, str) else ""
    parts = [p for p in (ap1, ap2, fn) if p]
    if parts:
        return " ".join(parts).strip()

    nom = data.get("nombres")
    nom = nom.strip() if isinstance(nom, str) else ""
    ap1 = data.get("apellidoPaterno") or data.get("apellido_paterno") or ""
    ap2 = data.get("apellidoMaterno") or data.get("apellido_materno") or ""
    ap1 = ap1.strip() if isinstance(ap1, str) else ""
    ap2 = ap2.strip() if isinstance(ap2, str) else ""

    parts = [p for p in (ap1, ap2, nom) if p]
    if parts:
        return " ".join(parts).strip()
    return ""


class ConsultarReniecDniView(APIView):
    """
    GET ?numero=12345678

    Respuesta OK: ``ok``, ``dni``, ``nombre_completo``, ``razon_social``;
    si el proveedor devuelve campos estructurados, también ``apellido_paterno``,
    ``apellido_materno`` y ``nombres`` (para formularios de vendedor).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = _normalize_bearer_token(getattr(settings, "APIS_NET_PE_TOKEN", "") or "")
        if not token:
            return Response(
                {
                    "ok": False,
                    "detail": (
                        "Consulta RENIEC no configurada. Agregue APIS_NET_PE_TOKEN (Decolecta) en "
                        "backend/.env y reinicie el servidor."
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        numero = (request.query_params.get("numero") or "").strip()
        if not DNI_RE.match(numero):
            return Response(
                {"ok": False, "detail": "Ingrese un DNI de 8 dígitos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code, body = decolecta_get_reniec_dni(numero, token)
        if code == 0:
            return Response(
                {
                    "ok": False,
                    "detail": "Error de conexión con el servicio de consulta. Intente más tarde.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if body is None:
            if code == 404:
                return Response(
                    {"ok": False, "detail": "DNI no encontrado en la consulta."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {
                    "ok": False,
                    "detail": "No se pudo consultar el DNI en este momento. Intente de nuevo.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if code != 200:
            err_detail = _provider_error_detail(body) if isinstance(body, dict) else None
            if err_detail:
                return Response(
                    {"ok": False, "detail": _humanize_provider_error(err_detail)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if code == 404:
                return Response(
                    {"ok": False, "detail": "DNI no encontrado en la consulta."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {
                    "ok": False,
                    "detail": "No se pudo consultar el DNI en este momento.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        nombre = _nombre_desde_reniec(body)
        if not nombre:
            if settings.DEBUG:
                logger.warning(
                    "RENIEC sin nombre en JSON (keys=%s)",
                    list(body.keys())[:30] if isinstance(body, dict) else body,
                )
            return Response(
                {
                    "ok": False,
                    "detail": "No se obtuvo nombre en la respuesta para este DNI.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        ap1, ap2, fn = _partes_nombres_reniec(body)
        return Response(
            {
                "ok": True,
                "dni": numero,
                "nombre_completo": nombre,
                "razon_social": nombre,
                "apellido_paterno": ap1 or None,
                "apellido_materno": ap2 or None,
                "nombres": fn or None,
            }
        )
