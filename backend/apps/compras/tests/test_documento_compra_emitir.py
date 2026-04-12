from decimal import Decimal

import pytest

from apps.compras.models import DocumentoCompra, DocumentoCompraLinea, TipoDocumentoCompra
from apps.compras.services.documento_compra_service import DocumentoCompraService
from apps.core.models import Empresa, Proveedor, Sucursal
from apps.inventario.models import Almacen, Item, Stock, UnidadMedida
from apps.inventario.services.stock_service import StockInsuficienteError
from apps.tesoreria.models import CronogramaPago
from apps.ventas.models import CondicionPagoDocumento, EstadoDocumento


@pytest.mark.django_db
def test_emitir_compra_credito_crea_cronograma():
    empresa = Empresa.objects.create(razon_social="E", ruc="20987654321")
    suc = Sucursal.objects.create(empresa=empresa, nombre="S")
    alm = Almacen.objects.create(sucursal=suc, nombre="A1")
    prov = Proveedor.objects.create(empresa=empresa, razon_social="Prov SAC", documento="20100000000")
    um = UnidadMedida.objects.create(empresa=empresa, codigo="NIU", nombre="Unidad")
    item = Item.objects.create(empresa=empresa, codigo="X", nombre="It", unidad_medida=um)
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
    um = UnidadMedida.objects.create(empresa=empresa, codigo="NIU", nombre="Unidad")
    item = Item.objects.create(empresa=empresa, codigo="Y", nombre="It2", unidad_medida=um)
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


@pytest.mark.django_db
def test_emitir_nota_credito_proveedor_descuenta_stock():
    empresa = Empresa.objects.create(razon_social="E3", ruc="20987654323")
    suc = Sucursal.objects.create(empresa=empresa, nombre="S")
    alm = Almacen.objects.create(sucursal=suc, nombre="A1")
    prov = Proveedor.objects.create(empresa=empresa, razon_social="P3", documento="20100000002")
    um = UnidadMedida.objects.create(empresa=empresa, codigo="NIU", nombre="Unidad")
    item = Item.objects.create(empresa=empresa, codigo="Z", nombre="It3", unidad_medida=um)
    Stock.objects.create(item=item, almacen=alm, cantidad=Decimal("10"))
    doc = DocumentoCompra.objects.create(
        empresa=empresa,
        tipo=TipoDocumentoCompra.NOTA_CREDITO_PROVEEDOR,
        proveedor=prov,
        fecha="2026-04-01",
        estado=EstadoDocumento.BORRADOR,
        subtotal=Decimal("20"),
        igv=Decimal("3.6"),
        total=Decimal("23.6"),
    )
    DocumentoCompraLinea.objects.create(
        documento=doc,
        item=item,
        cantidad=Decimal("4"),
        precio_unit=Decimal("5"),
        subtotal=Decimal("20"),
    )
    DocumentoCompraService.emitir(doc, almacen=alm)
    assert Stock.objects.get(item=item, almacen=alm).cantidad == Decimal("6")
    assert not CronogramaPago.objects.filter(documento_compra=doc).exists()


@pytest.mark.django_db
def test_emitir_nota_credito_proveedor_sin_stock_falla():
    empresa = Empresa.objects.create(razon_social="E4", ruc="20987654324")
    suc = Sucursal.objects.create(empresa=empresa, nombre="S")
    alm = Almacen.objects.create(sucursal=suc, nombre="A1")
    prov = Proveedor.objects.create(empresa=empresa, razon_social="P4", documento="20100000003")
    um = UnidadMedida.objects.create(empresa=empresa, codigo="NIU", nombre="Unidad")
    item = Item.objects.create(empresa=empresa, codigo="W", nombre="It4", unidad_medida=um)
    Stock.objects.create(item=item, almacen=alm, cantidad=Decimal("1"))
    doc = DocumentoCompra.objects.create(
        empresa=empresa,
        tipo=TipoDocumentoCompra.NOTA_CREDITO_PROVEEDOR,
        proveedor=prov,
        fecha="2026-04-01",
        estado=EstadoDocumento.BORRADOR,
        total=Decimal("10"),
    )
    DocumentoCompraLinea.objects.create(
        documento=doc,
        item=item,
        cantidad=Decimal("5"),
        precio_unit=Decimal("2"),
        subtotal=Decimal("10"),
    )
    with pytest.raises(StockInsuficienteError):
        DocumentoCompraService.emitir(doc, almacen=alm)


@pytest.mark.django_db
def test_emitir_guia_compra_no_mueve_stock():
    empresa = Empresa.objects.create(razon_social="E5", ruc="20987654325")
    suc = Sucursal.objects.create(empresa=empresa, nombre="S")
    alm = Almacen.objects.create(sucursal=suc, nombre="A1")
    prov = Proveedor.objects.create(empresa=empresa, razon_social="P5", documento="20100000004")
    um = UnidadMedida.objects.create(empresa=empresa, codigo="NIU", nombre="Unidad")
    item = Item.objects.create(empresa=empresa, codigo="G", nombre="ItG", unidad_medida=um)
    Stock.objects.create(item=item, almacen=alm, cantidad=Decimal("3"))
    doc = DocumentoCompra.objects.create(
        empresa=empresa,
        tipo=TipoDocumentoCompra.GUIA_REMISION_COMPRA,
        proveedor=prov,
        fecha="2026-04-01",
        estado=EstadoDocumento.BORRADOR,
        subtotal=Decimal("10"),
        igv=Decimal("1.8"),
        total=Decimal("11.8"),
        condicion_pago=CondicionPagoDocumento.CONTADO,
    )
    DocumentoCompraLinea.objects.create(
        documento=doc,
        item=item,
        cantidad=Decimal("2"),
        precio_unit=Decimal("5"),
        subtotal=Decimal("10"),
    )
    DocumentoCompraService.emitir(doc, almacen=alm)
    assert Stock.objects.get(item=item, almacen=alm).cantidad == Decimal("3")


@pytest.mark.django_db
def test_emitir_boleta_compra_ingresa_stock():
    empresa = Empresa.objects.create(razon_social="E6", ruc="20987654326")
    suc = Sucursal.objects.create(empresa=empresa, nombre="S")
    alm = Almacen.objects.create(sucursal=suc, nombre="A1")
    prov = Proveedor.objects.create(empresa=empresa, razon_social="P6", documento="20100000005")
    um = UnidadMedida.objects.create(empresa=empresa, codigo="NIU", nombre="Unidad")
    item = Item.objects.create(empresa=empresa, codigo="B", nombre="ItB", unidad_medida=um)
    doc = DocumentoCompra.objects.create(
        empresa=empresa,
        tipo=TipoDocumentoCompra.BOLETA_COMPRA,
        proveedor=prov,
        fecha="2026-04-01",
        estado=EstadoDocumento.BORRADOR,
        subtotal=Decimal("20"),
        igv=Decimal("3.6"),
        total=Decimal("23.6"),
        condicion_pago=CondicionPagoDocumento.CONTADO,
    )
    DocumentoCompraLinea.objects.create(
        documento=doc,
        item=item,
        cantidad=Decimal("2"),
        precio_unit=Decimal("10"),
        subtotal=Decimal("20"),
    )
    DocumentoCompraService.emitir(doc, almacen=alm)
    assert Stock.objects.get(item=item, almacen=alm).cantidad == Decimal("2")
