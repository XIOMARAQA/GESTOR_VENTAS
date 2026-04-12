"""
Construcción de payload y llamada HTTP a Nubefact (generar_comprobante).
Documentación: https://api.nubefact.com — misma forma que integraciones PHP habituales.
"""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

from apps.inventario.sunat_tabla6 import CODIGOS_SUNAT_TABLA6
from apps.ventas.models import (
    CondicionPagoDocumento,
    DocumentoVenta,
    MedioPagoDocumento,
    MonedaDocumento,
    TipoDocumentoVenta,
    TipoOperacionSunat,
)

logger = logging.getLogger(__name__)

IGV_PCT = Decimal("0.18")

NUBEFACT_PDF_FORMATOS_CLAVE = "nubefact_pdf_formatos"


def obtener_formato_pdf_nubefact(empresa_id: int | None, tipo: str) -> str:
    """
    Formato del PDF enviado a Nubefact (A4 o TICKET), configurable por empresa en administracion.
    Por defecto: factura → A4, boleta → TICKET.
    """
    if tipo == TipoDocumentoVenta.FACTURA:
        default = "A4"
        key = "factura"
    elif tipo == TipoDocumentoVenta.BOLETA:
        default = "TICKET"
        key = "boleta"
    else:
        default = "A4"
        key = "factura"
    if not empresa_id:
        return default
    try:
        from apps.administracion.models import ConfiguracionSistema

        row = ConfiguracionSistema.objects.filter(
            empresa_id=int(empresa_id),
            clave=NUBEFACT_PDF_FORMATOS_CLAVE,
        ).first()
        if not row or not isinstance(row.valor, dict):
            return default
        raw = row.valor.get(key)
        if raw is None:
            return default
        v = str(raw).strip().upper()
        if v in ("A4", "TICKET"):
            return v
    except (TypeError, ValueError):
        pass
    return default


def _s_money(d: Decimal) -> str:
    return str(d.quantize(Decimal("0.01")))


def _s_unit(d: Decimal) -> str:
    return str(d.quantize(Decimal("0.0001")))


def _unidad_nubefact(um: str) -> str:
    u = (um or "UND").strip().upper()
    if u == "UND":
        return "NIU"
    if u in CODIGOS_SUNAT_TABLA6:
        return u
    if u in ("NIU", "ZZ"):
        return u
    return "NIU"


def _item_unidad_codigo(item) -> str:
    um = getattr(item, "unidad_medida", None)
    if um is None:
        return "UND"
    sunat = (getattr(um, "codigo_sunat", None) or "").strip().upper()
    if sunat and sunat in CODIGOS_SUNAT_TABLA6:
        return sunat
    c = getattr(um, "codigo", None) or ""
    return (str(c).strip() or "UND").upper()


def _nubefact_moneda_codigo(moneda: str) -> str:
    return "2" if (moneda or "").upper() == MonedaDocumento.USD else "1"


def _medio_pago_etiqueta(codigo: str) -> str:
    for k, label in MedioPagoDocumento.choices:
        if k == codigo:
            return label
    return ""


def _sunat_transaction_codigo(tipo_op: str) -> str:
    """Códigos habituales Nubefact/SUNAT (1 venta interna; 2 exportación)."""
    m = {
        TipoOperacionSunat.VENTA_INTERNA: "1",
        TipoOperacionSunat.ANTICIPO: "1",
        TipoOperacionSunat.REGULARIZACION_ANTICIPO: "1",
        TipoOperacionSunat.EXPORTACION: "2",
        TipoOperacionSunat.NO_DOMICILIADOS: "1",
        TipoOperacionSunat.VENTA_ITINERANTE: "1",
    }
    return m.get((tipo_op or "").strip(), "1")


def _cliente_tipo_documento(numero_doc: str) -> str:
    nd = (numero_doc or "").strip()
    if len(nd) == 11 and nd.isdigit():
        return "6"  # RUC
    return "1"  # DNI u otros (según SUNAT)


def construir_payload(documento: DocumentoVenta) -> dict[str, Any]:
    """
    Arma el JSON operacion=generar_comprobante a partir de documento_venta + líneas + cliente.
    `documento.subtotal` / `igv` / `total` deben estar alineados (p. ej. vía recalcular_totales).
    """
    if not documento.cliente_id:
        raise ValueError("El documento debe tener un cliente con documento y razón social.")

    cliente = documento.cliente
    doc_num = (cliente.documento or "").strip()
    if not doc_num:
        raise ValueError("El cliente debe tener número de documento (RUC/DNI).")

    denominacion = (cliente.razon_social or "").strip() or doc_num

    if documento.tipo not in (
        TipoDocumentoVenta.FACTURA,
        TipoDocumentoVenta.BOLETA,
    ):
        raise ValueError("Nubefact: solo se admite tipo FACTURA o BOLETA.")

    empresa_pk = getattr(documento, "empresa_id", None)
    if documento.tipo == TipoDocumentoVenta.FACTURA:
        tipo_comprobante = "1"
        serie = (documento.serie or "").strip() or "FFF1"
        formato_pdf = obtener_formato_pdf_nubefact(empresa_pk, documento.tipo)
    else:
        tipo_comprobante = "2"
        serie = (documento.serie or "").strip() or "BBB1"
        formato_pdf = obtener_formato_pdf_nubefact(empresa_pk, documento.tipo)

    numero = (documento.numero or "").strip() or str(documento.pk)

    lineas = list(
        documento.lineas.select_related("item", "item__unidad_medida").all()
    )
    if not lineas:
        raise ValueError("El documento no tiene líneas.")

    items: list[dict[str, Any]] = []
    for ln in lineas:
        it = ln.item
        codigo = (it.codigo or "").strip() or str(it.pk)
        desc = (it.nombre or "").strip() or codigo
        cant = ln.cantidad
        if cant <= 0:
            continue
        base = ln.subtotal
        ln_igv = (base * IGV_PCT).quantize(Decimal("0.01"))
        ln_total = base + ln_igv
        vu = (base / cant).quantize(Decimal("0.0001"))
        pu = (ln_total / cant).quantize(Decimal("0.0001"))
        items.append(
            {
                "unidad_de_medida": _unidad_nubefact(_item_unidad_codigo(it)),
                "codigo": str(codigo),
                "descripcion": str(desc),
                "cantidad": str(cant),
                "valor_unitario": _s_unit(vu),
                "precio_unitario": _s_unit(pu),
                "descuento": "",
                "subtotal": _s_money(base),
                "tipo_de_igv": "1",
                "igv": _s_money(ln_igv),
                "total": _s_money(ln_total),
                "anticipo_regularizacion": "false",
                "anticipo_documento_serie": "",
                "anticipo_documento_numero": "",
            }
        )

    if not items:
        raise ValueError("No hay líneas válidas con cantidad > 0.")

    fecha_emision = documento.fecha_emision.strftime("%d-%m-%Y")
    fv = getattr(documento, "fecha_vencimiento", None)
    fecha_venc_str = fv.strftime("%d-%m-%Y") if fv else ""
    moneda_cod = _nubefact_moneda_codigo(getattr(documento, "moneda", None) or MonedaDocumento.PEN)
    sunat_tx = _sunat_transaction_codigo(getattr(documento, "tipo_operacion", None) or "")
    medio_txt = ""
    if getattr(documento, "condicion_pago", "") == CondicionPagoDocumento.CONTADO:
        medio_txt = _medio_pago_etiqueta(getattr(documento, "medio_pago", "") or "")
    condiciones_txt = ""
    if getattr(documento, "condicion_pago", "") == CondicionPagoDocumento.CREDITO:
        condiciones_txt = "Crédito"
        if fecha_venc_str:
            condiciones_txt = f"Crédito — venc. {fecha_venc_str}"

    return {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": tipo_comprobante,
        "serie": serie,
        "numero": str(numero),
        "sunat_transaction": sunat_tx,
        "cliente_tipo_de_documento": _cliente_tipo_documento(doc_num),
        "cliente_numero_de_documento": doc_num,
        "cliente_denominacion": denominacion,
        "cliente_direccion": (getattr(cliente, "direccion", None) or "").strip(),
        "cliente_email": (cliente.email or "").strip(),
        "cliente_email_1": "",
        "cliente_email_2": "",
        "fecha_de_emision": fecha_emision,
        "fecha_de_vencimiento": fecha_venc_str,
        "moneda": moneda_cod,
        "tipo_de_cambio": "",
        "porcentaje_de_igv": "18.00",
        "descuento_global": "",
        "total_descuento": "",
        "total_anticipo": "",
        "total_gravada": _s_money(documento.subtotal),
        "total_inafecta": "",
        "total_exonerada": "",
        "total_igv": _s_money(documento.igv),
        "total_gratuita": "",
        "total_otros_cargos": "",
        "total": _s_money(documento.total),
        "percepcion_tipo": "",
        "percepcion_base_imponible": "",
        "total_percepcion": "",
        "total_incluido_percepcion": "",
        "detraccion": "false",
        "observaciones": ((getattr(documento, "observacion", None) or "").strip())[:500],
        "documento_que_se_modifica_tipo": "",
        "documento_que_se_modifica_serie": "",
        "documento_que_se_modifica_numero": "",
        "tipo_de_nota_de_credito": "",
        "tipo_de_nota_de_debito": "",
        "enviar_automaticamente_a_la_sunat": "true",
        "enviar_automaticamente_al_cliente": "false",
        "codigo_unico": "",
        "condiciones_de_pago": condiciones_txt,
        "medio_de_pago": medio_txt,
        "placa_vehiculo": "",
        "orden_compra_servicio": "",
        "tabla_personalizada_codigo": "",
        "formato_de_pdf": formato_pdf,
        "items": items,
    }


def extraer_sunat_desde_respuesta_nubefact(resp: dict[str, Any]) -> tuple[str, str]:
    """
    Devuelve (codigo, descripcion) desde el JSON de éxito de Nubefact.
    Busca en la raíz y en ``data`` si viene anidado.
    Claves habituales: sunat_responsecode, sunat_description (y variantes).
    """
    if not isinstance(resp, dict):
        return "", ""
    layers: list[dict[str, Any]] = [resp]
    inner = resp.get("data")
    if isinstance(inner, dict):
        layers.append(inner)

    code_raw = None
    for layer in layers:
        code_raw = layer.get("sunat_responsecode")
        if code_raw is not None and code_raw != "":
            break
        code_raw = layer.get("sunat_note")
        if code_raw is not None and code_raw != "":
            break
        code_raw = layer.get("sunat_codigo")
        if code_raw is not None and code_raw != "":
            break

    if isinstance(code_raw, bool):
        code = "1" if code_raw else "0"
    elif isinstance(code_raw, (int, float)):
        code = str(int(code_raw)) if float(code_raw) == int(code_raw) else str(code_raw)
    else:
        code = str(code_raw).strip() if code_raw is not None else ""
    code = code[:32]

    desc = ""
    for layer in layers:
        for key in (
            "sunat_description",
            "sunat_descripcion",
            "descripcion_sunat",
            "mensaje_sunat",
            "sunat_mensaje",
        ):
            v = layer.get(key)
            if v is not None and str(v).strip():
                desc = str(v).strip()
                break
        if desc:
            break
    desc = desc[:8000]
    return code, desc


def enviar_a_nubefact(api_url: str, token: str, data: dict[str, Any]) -> dict[str, Any]:
    """POST JSON. `api_url` típico: https://api.nubefact.com/api/v1/<uuid>"""
    url = api_url.rstrip("/")
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f'Token token="{token}"',
        },
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=90) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            logger.warning("Nubefact HTTP %s sin JSON", e.code)
            return {"errors": e.reason or str(e.code), "codigo": "HTTP"}
    except urllib.error.URLError as e:
        logger.warning("Nubefact URLError: %s", e.reason)
        return {"errors": str(e.reason), "codigo": "URL"}
    except json.JSONDecodeError as e:
        return {"errors": f"Respuesta no JSON: {e}", "codigo": "JSON"}
