from decimal import Decimal

import pytest

from apps.compras.models import DocumentoCompra, DocumentoCompraLinea, TipoDocumentoCompra
from apps.compras.services.documento_compra_service import DocumentoCompraService
from apps.core.models import Empresa, Proveedor, Sucursal
from apps.inventario.models import Almacen, Item
from apps.tesoreria.models import CronogramaPago
from apps.ventas.models import CondicionPagoDocumento, EstadoDocumento


@pytest.mark.django_db
def test_emitir_compra_credito_crea_cronograma():
    empresa = Empresa.objects.create(razon_social="E", ruc="20987654321")
    suc = Sucursal.objects.create(empresa=empresa, nombre="S")
    alm = Almacen.objects.create(sucursal=suc, nombre="A1")
    prov = Proveedor.objects.create(empresa=empresa, razon_social="Prov SAC", documento="20100000000")
    item = Item.objects.create(empresa=empresa, codigo="X", nombre="It")
    doc = DocumentoCompra.objects.create(
        empresa=empresa,
        tipo=TipoDocumentoCompra.FACTURA_COMPRA,
        proveedor=prov,
        fecha="2026-04-01",
        estado=EstadoDocumento.BORRADOR,
        subtotal=Decimal("100"),
        igv=Decimal("18"),
        total=Decimal("118"),
        condicion_pago=CondicionPagoDocumento.CREDITO,
        fecha_vencimiento="2026-04-20",
    )
    DocumentoCompraLinea.objects.create(
        documento=doc,
        item=item,
        cantidad=Decimal("1"),
        precio_unit=Decimal("100"),
        subtotal=Decimal("100"),
    )
    DocumentoCompraService.emitir(doc, almacen=alm)
    doc.refresh_from_db()
    assert doc.estado == EstadoDocumento.EMITIDO
    assert CronogramaPago.objects.filter(documento_compra=doc).exists()
    cr = CronogramaPago.objects.get(documento_compra=doc)
    assert cr.estado == "PENDIENTE"
    assert cr.monto == doc.total == Decimal("118")


@pytest.mark.django_db
def test_emitir_compra_contado_sin_cronograma():
    empresa = Empresa.objects.create(razon_social="E2", ruc="20987654322")
    suc = Sucursal.objects.create(empresa=empresa, nombre="S")
    alm = Almacen.objects.create(sucursal=suc, nombre="A1")
    prov = Proveedor.objects.create(empresa=empresa, razon_social="P2", documento="20100000001")
    item = Item.objects.create(empresa=empresa, codigo="Y", nombre="It2")
    doc = DocumentoCompra.objects.create(
        empresa=empresa,
        tipo=TipoDocumentoCompra.FACTURA_COMPRA,
        proveedor=prov,
        fecha="2026-04-01",
        estado=EstadoDocumento.BORRADOR,
        subtotal=Decimal("50"),
        igv=Decimal("9"),
        total=Decimal("59"),
        condicion_pago=CondicionPagoDocumento.CONTADO,
    )
    DocumentoCompraLinea.objects.create(
        documento=doc,
        item=item,
        cantidad=Decimal("1"),
        precio_unit=Decimal("50"),
        subtotal=Decimal("50"),
    )
    DocumentoCompraService.emitir(doc, almacen=alm)
    assert not CronogramaPago.objects.filter(documento_compra=doc).exists()
