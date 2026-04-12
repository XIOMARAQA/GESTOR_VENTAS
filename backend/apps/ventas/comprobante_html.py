"""
HTML imprimible del comprobante de venta con el estilo guardado en
ConfiguracionSistema (clave nubefact_pdf_formatos), alineado con la vista previa
de Administración → Formato comprobante PDF.
"""

from __future__ import annotations

import html
from decimal import Decimal
from django.http import HttpRequest

from apps.administracion.models import ConfiguracionSistema
from apps.ventas.models import (
    CondicionPagoDocumento,
    DocumentoVenta,
    MedioPagoDocumento,
    MonedaDocumento,
    TipoDocumentoVenta,
)
from apps.ventas.services.nubefact_service import IGV_PCT, NUBEFACT_PDF_FORMATOS_CLAVE

DEFAULT_ESTILO: dict[str, str] = {
    "color_cabecera": "#1e40af",
    "color_lineas": "#93c5fd",
    "color_texto_cabecera": "#ffffff",
    "modelo": "a4_logo_izq",
    "fuente": "Arial",
}

MODELOS_VALIDOS = frozenset({"a4_logo_izq", "a4_logo_centro", "ticket"})
FUENTES_VALIDAS = frozenset(
    {"Arial", "Helvetica", "Times New Roman", "Georgia", "Verdana"}
)

TIPO_TITULO_FISCAL: dict[str, str] = {
    TipoDocumentoVenta.FACTURA: "FACTURA ELECTRÓNICA",
    TipoDocumentoVenta.BOLETA: "BOLETA DE VENTA ELECTRÓNICA",
    TipoDocumentoVenta.NOTA_VENTA: "NOTA DE VENTA",
    TipoDocumentoVenta.RESUMEN_BOLETAS: "RESUMEN DE BOLETAS",
    TipoDocumentoVenta.GUIA_REMISION: "GUÍA DE REMISIÓN ELECTRÓNICA",
    TipoDocumentoVenta.NOTA_CREDITO_CLIENTE: "NOTA DE CRÉDITO ELECTRÓNICA",
}

# CSS replicado desde FormatoComprobantePdfView.vue (preview-sheet … inv-legal)
CSS_COMPROBANTE = """
:root { box-sizing: border-box; }
*, *::before, *::after { box-sizing: inherit; }
body { margin: 0; background: #e2e8f0; padding: 0.75rem; }
.sheet {
  --cab: #1e40af;
  --lin: #93c5fd;
  --cab-txt: #ffffff;
  --pdf-font: Arial, "Helvetica Neue", Helvetica, sans-serif;
  margin: 0 auto;
  background: #fff;
  padding: 1.1rem 1.25rem 1.25rem;
  box-shadow: 0 4px 24px rgb(15 23 42 / 10%);
  font-family: var(--pdf-font);
  font-size: 0.72rem;
  color: #0f172a;
  max-width: 640px;
}
.sheet--ticket {
  max-width: 280px;
  font-size: 0.62rem;
  padding: 0.65rem 0.75rem;
}
.sheet--ticket .inv-table th,
.sheet--ticket .inv-table td {
  padding: 0.2rem 0.15rem;
  font-size: 0.55rem;
}
.sheet--ticket .inv-head {
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.sheet--ticket .inv-fiscal { width: 100%; margin-top: 0.5rem; }
.inv-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0.75rem 1rem;
  margin-bottom: 0.85rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--lin);
}
.sheet--center .inv-head {
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.sheet--center .inv-company { text-align: center; }
.sheet--left .inv-head {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: start;
}
@media (max-width: 520px) {
  .sheet--left .inv-head {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }
}
.inv-logo {
  max-height: 72px;
  max-width: 160px;
  object-fit: contain;
}
.sheet--ticket .inv-logo { max-height: 48px; max-width: 120px; }
.inv-company { flex: 1; min-width: 0; }
.inv-name {
  display: block;
  font-size: 0.95rem;
  margin-bottom: 0.25rem;
}
.sheet--ticket .inv-name { font-size: 0.75rem; }
.inv-meta {
  margin: 0;
  color: #475569;
  line-height: 1.4;
  font-size: 0.68rem;
}
.inv-fiscal {
  border: 1px solid var(--lin);
  padding: 0.45rem 0.55rem;
  text-align: center;
  min-width: 7.5rem;
}
.inv-fiscal__ruc { font-weight: 700; font-size: 0.7rem; }
.inv-fiscal__tipo {
  font-weight: 800;
  font-size: 0.62rem;
  margin: 0.2rem 0;
  color: #0f172a;
}
.inv-fiscal__num { font-weight: 700; font-size: 0.75rem; }
.inv-block { margin-bottom: 0.65rem; font-size: 0.68rem; }
.inv-row2 {
  display: grid;
  grid-template-columns: 5.5rem 1fr;
  gap: 0.35rem;
  margin-bottom: 0.25rem;
}
.inv-grid4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.75rem;
  margin-top: 0.4rem;
}
.k { color: #64748b; font-weight: 600; }
.inv-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0.65rem;
}
.inv-table th {
  background: var(--cab);
  color: var(--cab-txt);
  font-weight: 700;
  text-align: left;
  padding: 0.35rem 0.3rem;
  font-size: 0.62rem;
  border: 1px solid var(--cab);
}
.inv-table td {
  padding: 0.32rem 0.3rem;
  border-bottom: 1px solid var(--lin);
  vertical-align: top;
}
.td-desc { max-width: 8rem; }
.td-num { text-align: right; white-space: nowrap; }
.inv-totals {
  margin-left: auto;
  max-width: 14rem;
  font-size: 0.7rem;
}
.tot-line {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.2rem 0;
  border-bottom: 1px solid #e2e8f0;
}
.tot-line--strong {
  font-weight: 800;
  border-bottom: none;
  margin-top: 0.15rem;
}
.inv-legal {
  margin: 0.5rem 0 0;
  font-size: 0.58rem;
  color: #64748b;
  line-height: 1.35;
}
.inv-legal a { color: #0e7490; }
@media print {
  body { background: #fff; padding: 0; }
  .sheet { box-shadow: none; max-width: none; }
}
"""


def _font_stack(fuente: str) -> str:
    f = (fuente or "").strip()
    if f == "Times New Roman":
        return '"Times New Roman", Times, serif'
    if f == "Georgia":
        return 'Georgia, "Times New Roman", serif'
    if f == "Verdana":
        return "Verdana, Geneva, sans-serif"
    if f == "Helvetica":
        return "Helvetica, Arial, sans-serif"
    return 'Arial, "Helvetica Neue", Helvetica, sans-serif'


def _cargar_valor_config(empresa_id: int | None) -> dict[str, object]:
    if not empresa_id:
        return {}
    row = ConfiguracionSistema.objects.filter(
        empresa_id=int(empresa_id),
        clave=NUBEFACT_PDF_FORMATOS_CLAVE,
    ).first()
    if not row or not isinstance(row.valor, dict):
        return {}
    return row.valor


def estilo_comprobante_desde_config(empresa_id: int | None) -> dict[str, str]:
    """
    Colores, modelo y fuente como en FormatoComprobantePdfView; independiente del
    tamaño A4/ticket enviado a Nubefact (ese valor solo afecta al PDF del proveedor).
    """
    raw = _cargar_valor_config(empresa_id)
    out = {**DEFAULT_ESTILO}
    for k in ("color_cabecera", "color_lineas", "color_texto_cabecera"):
        v = raw.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    m = str(raw.get("modelo") or "").strip()
    if m in MODELOS_VALIDOS:
        out["modelo"] = m
    fn = str(raw.get("fuente") or "").strip()
    if fn in FUENTES_VALIDAS:
        out["fuente"] = fn
    return out


def _layout_class(modelo: str) -> str:
    if modelo == "a4_logo_centro":
        return "sheet--center"
    if modelo == "ticket":
        return "sheet--ticket"
    return "sheet--left"


def _fmt_money(d: Decimal) -> str:
    q = d.quantize(Decimal("0.01"))
    return f"{q:,.2f}"


def _fmt_qty(d: Decimal) -> str:
    q = d.quantize(Decimal("0.0001"))
    s = format(q, "f").rstrip("0").rstrip(".")
    return html.escape(s or "0")


def _fmt_unit(d: Decimal) -> str:
    q = d.quantize(Decimal("0.0001"))
    return f"{q:,.4f}"


def _fecha_es(doc: DocumentoVenta) -> str:
    return doc.fecha_emision.strftime("%d/%m/%Y")


def _serie_numero(doc: DocumentoVenta) -> str:
    s = (doc.serie or "").strip()
    n = (doc.numero or "").strip()
    if s and n:
        return f"{s}-{n}"
    return s or n or "—"


def _titulo_fiscal(doc: DocumentoVenta) -> str:
    return TIPO_TITULO_FISCAL.get(doc.tipo, doc.get_tipo_display().upper())


def _label_condicion(doc: DocumentoVenta) -> str:
    try:
        return str(CondicionPagoDocumento(doc.condicion_pago).label)
    except ValueError:
        return doc.condicion_pago or "—"


def _label_medio(doc: DocumentoVenta) -> str:
    mp = (doc.medio_pago or "").strip()
    if mp:
        try:
            return str(MedioPagoDocumento(mp).label)
        except ValueError:
            return mp
    if doc.condicion_pago == CondicionPagoDocumento.CREDITO:
        return "No indicado (venta a crédito)"
    return "—"


def _label_moneda(doc: DocumentoVenta) -> str:
    try:
        return str(MonedaDocumento(doc.moneda).label)
    except ValueError:
        return doc.moneda or "PEN"


def _meta_empresa(doc: DocumentoVenta) -> str:
    parts: list[str] = []
    if doc.sucursal_id and doc.sucursal:
        su = doc.sucursal
        line = (su.direccion or "").strip()
        if not line:
            line = (su.nombre or "").strip()
        if line:
            parts.append(line)
    tel = (doc.empresa.telefono_contacto or "").strip()
    if tel:
        parts.append(f"Telf.: {tel}")
    return " · ".join(parts) if parts else ""


def _logo_url(request: HttpRequest, doc: DocumentoVenta) -> str | None:
    emp = doc.empresa
    if not emp.logo_comprobante:
        return None
    url = emp.logo_comprobante.url
    if url.startswith("http"):
        return url
    return request.build_absolute_uri(url)


def _sunat_resumen(doc: DocumentoVenta) -> str:
    c = (doc.nubefact_sunat_codigo or "").strip()
    d = (doc.nubefact_sunat_descripcion or "").strip()
    if c and d:
        return f"Código SUNAT: {c} — {d}"
    if d:
        return d
    if c:
        return f"Código SUNAT: {c}"
    return ""


def render_comprobante_venta_html(request: HttpRequest, doc: DocumentoVenta) -> str:
    est = estilo_comprobante_desde_config(doc.empresa_id)
    layout = _layout_class(est["modelo"])
    cab = html.escape(est["color_cabecera"])
    lin = html.escape(est["color_lineas"])
    cab_txt = html.escape(est["color_texto_cabecera"])
    font = html.escape(_font_stack(est["fuente"]))

    rs = html.escape((doc.empresa.razon_social or "").strip() or "—")
    ruc_e = html.escape((doc.empresa.ruc or "").strip() or "—")
    meta = html.escape(_meta_empresa(doc))

    cli = doc.cliente
    if cli:
        cli_rs = html.escape((cli.razon_social or "").strip() or "—")
        cli_doc = html.escape((cli.documento or "").strip() or "—")
        cli_dir = html.escape((cli.direccion or "").strip() or "—")
    else:
        cli_rs = cli_doc = cli_dir = "—"

    logo_html = ""
    logo_u = _logo_url(request, doc)
    if logo_u:
        logo_html = f'<img src="{html.escape(logo_u, quote=True)}" class="inv-logo" alt="" />'

    line_rows: list[str] = []
    for i, ln in enumerate(doc.lineas.all(), start=1):
        it = ln.item
        um = it.unidad_medida
        und = (um.codigo_sunat or um.codigo or "NIU").strip() or "NIU"
        cod = (it.codigo or "").strip() or "—"
        desc = html.escape((it.nombre or "").strip() or "—")
        vu = ln.precio_unit
        pu = (vu * (Decimal("1") + IGV_PCT)).quantize(Decimal("0.0001"))
        line_rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td>{_fmt_qty(ln.cantidad)}</td>"
            f"<td>{html.escape(cod)}</td>"
            f'<td class="td-desc">{desc}</td>'
            f"<td>{html.escape(und)}</td>"
            f'<td class="td-num">{_fmt_unit(vu)}</td>'
            f'<td class="td-num">{_fmt_unit(pu)}</td>'
            '<td class="td-num">0.00</td>'
            f'<td class="td-num">{_fmt_money(ln.subtotal)}</td>'
            "</tr>"
        )

    tbody = "\n".join(line_rows) if line_rows else (
        '<tr><td colspan="9">Sin líneas</td></tr>'
    )

    sub = _fmt_money(doc.subtotal)
    igv = _fmt_money(doc.igv)
    tot = _fmt_money(doc.total)

    sunat = _sunat_resumen(doc)
    sunat_html = ""
    if sunat:
        sunat_html = f'<p class="inv-legal">{html.escape(sunat)}</p>'

    enlace = (doc.nubefact_enlace or "").strip()
    enlace_html = ""
    if enlace.startswith("http"):
        enlace_html = (
            f'<p class="inv-legal">PDF del proveedor electrónico: '
            f'<a href="{html.escape(enlace, quote=True)}" target="_blank" rel="noopener">abrir enlace</a></p>'
        )

    obs = (doc.observacion or "").strip()
    obs_html = ""
    if obs:
        obs_html = f'<p class="inv-legal"><strong>Obs.:</strong> {html.escape(obs)}</p>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(_serie_numero(doc))} — {html.escape(_titulo_fiscal(doc))}</title>
  <style>{CSS_COMPROBANTE}</style>
</head>
<body>
  <div class="sheet {layout}" style="--cab: {cab}; --lin: {lin}; --cab-txt: {cab_txt}; --pdf-font: {font};">
    <div class="inv-head">
      {logo_html}
      <div class="inv-company">
        <strong class="inv-name">{rs}</strong>
        <p class="inv-meta">{meta}</p>
      </div>
      <div class="inv-fiscal">
        <div class="inv-fiscal__ruc">RUC {ruc_e}</div>
        <div class="inv-fiscal__tipo">{html.escape(_titulo_fiscal(doc))}</div>
        <div class="inv-fiscal__num">{html.escape(_serie_numero(doc))}</div>
      </div>
    </div>

    <div class="inv-block">
      <div class="inv-row2">
        <span class="k">Señores:</span>
        <span class="v">{cli_rs}</span>
      </div>
      <div class="inv-row2">
        <span class="k">Dirección:</span>
        <span class="v">{cli_dir}</span>
      </div>
      <div class="inv-grid4">
        <div><span class="k">RUC:</span> {cli_doc}</div>
        <div><span class="k">Forma de pago:</span> {html.escape(_label_condicion(doc))}</div>
        <div><span class="k">Fecha emisión:</span> {_fecha_es(doc)}</div>
        <div><span class="k">Moneda:</span> {html.escape(_label_moneda(doc))}</div>
        <div><span class="k">Medio de pago:</span> {html.escape(_label_medio(doc))}</div>
        <div><span class="k">Estado:</span> {html.escape(doc.get_estado_display())}</div>
      </div>
    </div>

    <table class="inv-table">
      <thead>
        <tr>
          <th>Ítem</th>
          <th>Cant.</th>
          <th>Código</th>
          <th>Descripción</th>
          <th>Und.</th>
          <th>V.U.</th>
          <th>P.U.</th>
          <th>Dscto.</th>
          <th>Valor venta</th>
        </tr>
      </thead>
      <tbody>
        {tbody}
      </tbody>
    </table>

    <div class="inv-totals">
      <div class="tot-line"><span>Total venta gravada / valor venta</span><span>{sub}</span></div>
      <div class="tot-line"><span>Total IGV</span><span>{igv}</span></div>
      <div class="tot-line tot-line--strong"><span>Importe total de la venta</span><span>{tot}</span></div>
    </div>

    <p class="inv-legal">
      Representación impresa del comprobante · Estilo definido en Administración (formato comprobante PDF).
    </p>
    {sunat_html}
    {enlace_html}
    {obs_html}
  </div>
</body>
</html>
"""
