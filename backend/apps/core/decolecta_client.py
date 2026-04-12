"""
Cliente HTTP para api.decolecta.com (mismo patrón que DecolectaAPIClient del gist).

GET con ``Authorization: Bearer`` y ``Referer: python-decolecta``; ``numero`` va en query
(``params``), no obliga a armar la URL a mano.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def decolecta_get_ruc(numero: str, token: str, *, timeout: int = 18) -> tuple[int, dict[str, Any] | None]:
    """
    Consulta RUC básico SUNAT vía Decolecta.

    Returns:
        (status_code, body_dict) o (0, None) si falla la red / JSON inválido.
    """
    url = f"{(getattr(settings, 'SUNAT_RUC_API_BASE', '') or 'https://api.decolecta.com').rstrip('/')}"
    path = getattr(settings, "SUNAT_RUC_API_PATH", "") or "/v1/sunat/ruc"
    if not path.startswith("/"):
        path = f"/{path}"
    endpoint = f"{url}{path}"

    params: dict[str, str] = {"numero": numero}
    if getattr(settings, "SUNAT_RUC_TOKEN_IN_QUERY", False):
        params["token"] = token

    referer = getattr(settings, "SUNAT_RUC_DECOLECTA_REFERER", "") or "python-decolecta"
    headers = {
        "Authorization": f"Bearer {token}",
        "Referer": referer,
        "Accept": "application/json",
    }

    try:
        r = requests.get(endpoint, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as e:
        logger.warning("Decolecta RUC request error: %s", e)
        return 0, None

    if not r.content:
        return r.status_code, {}

    try:
        body = r.json()
    except ValueError:
        logger.warning("Decolecta RUC no JSON (HTTP %s): %s", r.status_code, r.text[:400])
        return r.status_code, None

    if not isinstance(body, dict):
        return r.status_code, None

    return r.status_code, body


def decolecta_get_reniec_dni(
    numero: str, token: str, *, timeout: int = 18
) -> tuple[int, dict[str, Any] | None]:
    """
    Consulta DNI (RENIEC) vía Decolecta: ``GET /v1/reniec/dni?numero=``.

    Mismo ``Authorization: Bearer`` y ``Referer`` que la consulta RUC.
    """
    # RENIEC solo en Decolecta (no apis.net.pe); base independiente de SUNAT_RUC_API_BASE.
    base = (getattr(settings, "DECOLECTA_API_BASE", "") or "").strip().rstrip("/")
    url = base or "https://api.decolecta.com"
    path = getattr(settings, "DECOLECTA_RENIEC_DNI_PATH", "") or "/v1/reniec/dni"
    if not path.startswith("/"):
        path = f"/{path}"
    endpoint = f"{url}{path}"

    params: dict[str, str] = {"numero": numero}
    if getattr(settings, "SUNAT_RUC_TOKEN_IN_QUERY", False):
        params["token"] = token

    referer = getattr(settings, "SUNAT_RUC_DECOLECTA_REFERER", "") or "python-decolecta"
    headers = {
        "Authorization": f"Bearer {token}",
        "Referer": referer,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        r = requests.get(endpoint, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as e:
        logger.warning("Decolecta RENIEC DNI request error: %s", e)
        return 0, None

    if not r.content:
        return r.status_code, {}

    try:
        body = r.json()
    except ValueError:
        logger.warning(
            "Decolecta RENIEC DNI no JSON (HTTP %s): %s", r.status_code, r.text[:400]
        )
        return r.status_code, None

    if not isinstance(body, dict):
        return r.status_code, None

    return r.status_code, body
