"""
Consulta RUC SUNAT vía proveedor HTTP (Bearer).

Por defecto:
  - Token que empieza por ``sk_`` → ``https://api.decolecta.com/v1/sunat/ruc`` (panel Decolecta).
  - Otros tokens → ``https://api.apis.net.pe/v2/sunat/ruc`` (panel apis.net.pe).

Sobrescribir con SUNAT_RUC_API_BASE, SUNAT_RUC_API_PATH y SUNAT_RUC_API_REFERER en settings/.env.

El secreto va solo en el servidor: APIS_NET_PE_TOKEN (no exponer al frontend).

Decolecta usa el mismo patrón que el cliente de referencia (``requests`` + ``Referer: python-decolecta``).
Opcional: ``SUNAT_RUC_TOKEN_IN_QUERY=true`` para enviar también ``token`` en query.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

RUC_RE = re.compile(r"^\d{11}$")


def _sunat_ruc_url_and_referer(numero: str) -> tuple[str, str]:
    """
    URL y Referer según proveedor.

    - Si SUNAT_RUC_API_BASE + SUNAT_RUC_API_PATH están en settings, se usan tal cual.
    - Si el token parece de Decolecta (prefijo sk_), se usa api.decolecta.com/v1/sunat/ruc.
    - En caso contrario, apis.net.pe v2 (documentación oficial del snippet Laravel).
    """
    q = urllib.parse.quote(numero)
    base = getattr(settings, "SUNAT_RUC_API_BASE", "") or ""
    path = getattr(settings, "SUNAT_RUC_API_PATH", "") or ""
    ref = getattr(settings, "SUNAT_RUC_API_REFERER", "") or ""
    if base and path:
        path_norm = path if path.startswith("/") else f"/{path}"
        if "decolecta.com" in base:
            default_ref = getattr(settings, "SUNAT_RUC_DECOLECTA_REFERER", "") or "python-decolecta"
        else:
            default_ref = "https://apis.net.pe/api-consulta-ruc"
        return f"{base}{path_norm}?numero={q}", ref or default_ref

    token = _normalize_bearer_token(getattr(settings, "APIS_NET_PE_TOKEN", "") or "")
    if token.startswith("sk_"):
        return (
            f"https://api.decolecta.com/v1/sunat/ruc?numero={q}",
            getattr(settings, "SUNAT_RUC_DECOLECTA_REFERER", "") or "python-decolecta",
        )
    return (
        f"https://api.apis.net.pe/v2/sunat/ruc?numero={q}",
        "https://apis.net.pe/api-consulta-ruc",
    )


def _es_persona_juridica_ruc(numero: str) -> bool:
    """En Perú, RUC de persona jurídica suele iniciar en 20."""
    return len(numero) == 11 and numero.startswith("20")


def _normalize_bearer_token(raw: str) -> str:
    t = (raw or "").strip()
    if len(t) >= 2 and ((t[0] == t[-1] == '"') or (t[0] == t[-1] == "'")):
        t = t[1:-1].strip()
    return t


def _decolecta_url(url: str) -> bool:
    return "api.decolecta.com" in url


def _humanize_provider_error(msg: str) -> str:
    """Traduce mensajes frecuentes de Decolecta / proveedor."""
    m = msg.strip()
    low = m.lower()
    if ("apikey" in low or "api key" in low) and "limit" in low:
        return (
            "Decolecta indica problema de API key o de cupo: (1) En backend/.env, APIS_NET_PE_TOKEN debe ser el "
            "token completo actual (sk_…), sin comillas ni espacios; reinicie runserver al guardar. "
            "(2) En el panel de Decolecta compruebe peticiones disponibles del mes y el plan (aunque muestre 0/1000, "
            "una clave regenerada antigua en .env provoca 'Apikey Required')."
        )
    if "limit exceeded" in low or "límite" in low:
        return (
            "Límite de consultas de tu plan en Decolecta agotado o sin peticiones disponibles este mes. "
            "Revise el panel de Decolecta y, si hace falta, suba de plan o espere el renovado del cupo."
        )
    if "apikey" in low or "api key" in low or "api-key" in low:
        return (
            "Decolecta no aceptó la API key: verifica APIS_NET_PE_TOKEN en backend/.env (sin comillas, "
            "sin espacios al final, línea completa del token sk_…). Reinicia runserver tras guardar. "
            "Si regeneró la clave en el panel, debe pegar la nueva en .env."
        )
    return m


def _provider_error_detail(data: dict) -> str | None:
    for key in ("error", "detail", "message"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return _humanize_provider_error(v.strip())
    return None


def _str_clean(v: object) -> str:
    if isinstance(v, str):
        return v.strip()
    return ""


def _get_field_ci(d: dict, *keys: str) -> str:
    """Obtiene el primer valor string no vacío entre varias claves (y variantes en minúsculas)."""
    for k in keys:
        s = _str_clean(d.get(k))
        if s:
            return s
    lower_map = {str(a).lower(): a for a in d}
    for k in keys:
        orig = lower_map.get(k.lower())
        if orig is not None:
            s = _str_clean(d.get(orig))
            if s:
                return s
    return ""


def _walk_nested_dicts(root: dict, seen: set[int], out: list[dict]) -> None:
    i = id(root)
    if i in seen:
        return
    seen.add(i)
    out.append(root)
    for k in ("data", "Data", "result", "resultado", "contribuyente", "payload", "body"):
        n = root.get(k)
        if isinstance(n, dict):
            _walk_nested_dicts(n, seen, out)


def _all_dict_nodes(data: dict) -> list[dict]:
    out: list[dict] = []
    _walk_nested_dicts(data, set(), out)
    return out


def _compose_direccion_desde_partes_sunat(d: dict) -> str:
    """Arma texto tipo padrón SUNAT (viaTipo + viaNombre + NRO + distrito/provincia/departamento)."""
    via_t = _get_field_ci(d, "viaTipo", "via_tipo", "tipoVia", "tipo_via")
    via_n = _get_field_ci(d, "viaNombre", "via_nombre", "nombreVia", "nombre_via")
    nro = _get_field_ci(d, "numero", "nro", "Nro", "Numero")
    inter = _get_field_ci(d, "interior", "int", "Interior")
    dpto_int = _get_field_ci(d, "dpto", "Dpto")
    zona_t = _get_field_ci(d, "zonaTipo", "zona_tipo")
    zona_c = _get_field_ci(d, "zonaCodigo", "zona_codigo")
    lote = _get_field_ci(d, "lote", "Lote")
    mza = _get_field_ci(d, "manzana", "Manzana")

    calle = f"{via_t} {via_n}".strip()
    parts: list[str] = []
    if calle:
        parts.append(calle)
    if nro:
        parts.append(f"NRO. {nro}")
    for bit in (inter, dpto_int, lote, mza):
        if bit:
            parts.append(bit)
    z = f"{zona_t} {zona_c}".strip()
    if z:
        parts.append(z)
    head = " ".join(parts).strip()

    dist = _get_field_ci(d, "distrito", "Distrito")
    prov = _get_field_ci(d, "provincia", "Provincia")
    dep = _get_field_ci(d, "departamento", "Departamento")
    geo = " — ".join(x for x in (dist, prov, dep) if x)
    ubi = _get_field_ci(d, "ubigeo", "Ubigeo")
    if geo and ubi:
        geo = f"{geo} (Ubigeo {ubi})"
    elif ubi and not geo:
        geo = f"Ubigeo {ubi}"

    if head and geo:
        return f"{head} — {geo}"
    return head or geo


def direccion_desde_respuesta_proveedor_ruc(data: dict) -> str:
    """
    Extrae domicilio fiscal / dirección del JSON del proveedor (apis.net.pe, Decolecta, etc.).
    """
    for node in _all_dict_nodes(data):
        direct = _get_field_ci(
            node,
            "direccion",
            "direccion_completa",
            "direccionCompleta",
            "domicilio_fiscal",
            "domicilioFiscal",
            "domicilio",
            "Direccion",
            "direccion_establecimiento",
            "direccionEstablecimiento",
            "direccion_fiscal",
            "direccionFiscal",
        )
        if direct:
            return direct[:2000]
    for node in _all_dict_nodes(data):
        comp = _compose_direccion_desde_partes_sunat(node)
        if comp:
            return comp[:2000]
    return ""


class ConsultarRucSunatView(APIView):
    """
    GET ?numero=20123456789

    Éxito (HTTP 200):
      - es_persona_juridica: true si RUC inicia en 20
      - razon_social: nombre de empresa (solo sentido para PJ; rellenado con el texto del padrón)
      - nombre_padron: texto tal cual en padrón (razonSocial o nombre)
      - direccion: domicilio fiscal si el proveedor lo devuelve (apis.net.pe / Decolecta)
    Persona natural: usar nombre_padron y repartir apellidos/nombres en el cliente.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        token = _normalize_bearer_token(getattr(settings, "APIS_NET_PE_TOKEN", "") or "")
        if not token:
            return Response(
                {
                    "ok": False,
                    "detail": (
                        "Consulta SUNAT no configurada. Agregue APIS_NET_PE_TOKEN en backend/.env "
                        "(token en https://apis.net.pe/api-ruc) y reinicie el servidor."
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        numero = (request.query_params.get("numero") or "").strip()
        if not RUC_RE.match(numero):
            return Response(
                {"ok": False, "detail": "Ingrese un RUC de 11 dígitos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        url, referer = _sunat_ruc_url_and_referer(numero)

        if _decolecta_url(url):
            from .decolecta_client import decolecta_get_ruc

            code, data = decolecta_get_ruc(numero, token)
            if code == 0:
                return Response(
                    {
                        "ok": False,
                        "detail": "Error de conexión con el servicio de consulta. Intente más tarde.",
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            if data is None:
                if code == 404:
                    return Response(
                        {"ok": False, "detail": "El RUC no existe en el padrón consultado."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                return Response(
                    {
                        "ok": False,
                        "detail": "No se pudo consultar el RUC en este momento. Intente de nuevo.",
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            if code != 200:
                return self._map_api_response(numero, data, from_error=True, http_status=code)
            return self._map_api_response(numero, data, from_error=False, http_status=200)

        if settings.SUNAT_RUC_TOKEN_IN_QUERY and "?" in url:
            url = f"{url}&token={urllib.parse.quote(token, safe='')}"

        req = urllib.request.Request(
            url,
            headers={
                "Referer": referer,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "GestorVentas/1.0 (Django)",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=18) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                data = json.loads(err_body)
            except (json.JSONDecodeError, ValueError):
                logger.warning("SUNAT RUC HTTP %s sin JSON: %s", code, e.reason)
                if code == 404:
                    return Response(
                        {
                            "ok": False,
                            "detail": "El RUC no existe en el padrón consultado.",
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
                return Response(
                    {
                        "ok": False,
                        "detail": "No se pudo consultar el RUC en este momento. Intente de nuevo.",
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            if not isinstance(data, dict):
                return Response(
                    {"ok": False, "detail": "Respuesta inválida del servicio de consulta."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return self._map_api_response(numero, data, from_error=True, http_status=code)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            logger.warning("SUNAT RUC error: %s", e)
            return Response(
                {
                    "ok": False,
                    "detail": "Error de conexión con el servicio de consulta. Intente más tarde.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return self._map_api_response(numero, data, from_error=False, http_status=200)

    def _map_api_response(
        self,
        numero: str,
        data: object,
        *,
        from_error: bool,
        http_status: int | None,
    ) -> Response:
        if not isinstance(data, dict):
            return Response(
                {"ok": False, "detail": "Respuesta inválida del servicio de consulta."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if from_error:
            err_detail = _provider_error_detail(data)
            if err_detail:
                return Response(
                    {"ok": False, "detail": err_detail},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if http_status == 404:
                return Response(
                    {"ok": False, "detail": "El RUC no existe en el padrón consultado."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if http_status == 422:
                return Response(
                    {
                        "ok": False,
                        "detail": "RUC no válido (longitud, formato o dígito verificador).",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        msg = data.get("message")
        if isinstance(msg, str) and "no valid" in msg.lower():
            return Response(
                {"ok": False, "detail": "RUC no válido o no encontrado en SUNAT."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Padrón: persona jurídica suele traer razonSocial; persona natural suele traer nombre.
        nombre_padron = (
            data.get("razonSocial")
            or data.get("razon_social")
            or data.get("nombre")
            or data.get("nombre_completo")
            or data.get("razonSocialCompleta")
        )
        if isinstance(nombre_padron, str):
            nombre_padron = nombre_padron.strip()
        else:
            nombre_padron = ""

        if not nombre_padron:
            if settings.DEBUG:
                logger.warning(
                    "SUNAT RUC sin nombre en JSON (keys=%s): %s",
                    list(data.keys())[:25],
                    json.dumps(data, ensure_ascii=False)[:800],
                )
            if from_error:
                return Response(
                    {"ok": False, "detail": "RUC no válido o no encontrado en SUNAT."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"ok": False, "detail": "No se obtuvo nombre en el padrón para este RUC."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        es_pj = _es_persona_juridica_ruc(numero)

        payload: dict = {
            "ok": True,
            "ruc": numero,
            "es_persona_juridica": es_pj,
            "nombre_padron": nombre_padron,
            # PJ: misma cadena en razón social. PN: vacío (el formulario usa apellidos/nombres + opcional padrón).
            "razon_social": nombre_padron if es_pj else "",
        }

        estado = data.get("estado")
        condicion = data.get("condicion")
        if isinstance(estado, str) and estado.strip():
            payload["sunat_estado"] = estado.strip()
        if isinstance(condicion, str) and condicion.strip():
            payload["sunat_condicion"] = condicion.strip()

        dir_padron = direccion_desde_respuesta_proveedor_ruc(data)
        payload["direccion"] = dir_padron

        return Response(payload)
