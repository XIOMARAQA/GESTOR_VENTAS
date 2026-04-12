from decimal import Decimal

import pytest

from apps.core.models import Empresa, Sucursal
from apps.inventario.models import Almacen, Item, Stock
from apps.inventario.services.stock_service import StockInsuficienteError
from apps.tesoreria.models import Cobranza, EstadoCobranza
from apps.ventas.models import (
    Cliente,
    CondicionPagoDocumento,
    DocumentoVenta,
    DocumentoVentaLinea,
    EstadoDocumento,
    TipoDocumentoVenta,
)
from apps.ventas.services.documento_venta_service import DocumentoVentaService


@pytest.mark.django_db
class TestDocumentoVentaEmitir:
    def setup_method(self):
        self.empresa = Empresa.objects.create(razon_social="Test SAC", ruc="20123456789")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Principal"
        )
        self.almacen = Almacen.objects.create(sucursal=self.sucursal, nombre="Alm 1")
        self.item = Item.objects.create(
            empresa=self.empresa,
            codigo="SKU1",
            nombre="Producto 1",
            es_servicio=False,
        )
        Stock.objects.create(item=self.item, almacen=self.almacen, cantidad=Decimal("10"))

    def test_emitir_descuenta_stock_y_crea_cobranza(self):
        doc = DocumentoVenta.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            tipo=TipoDocumentoVenta.BOLETA,
            fecha_emision="2026-04-01",
            estado=EstadoDocumento.BORRADOR,
            subtotal=Decimal("100"),
            igv=Decimal("18"),
            total=Decimal("118"),
        )
        DocumentoVentaLinea.objects.create(
            documento=doc,
            item=self.item,
            cantidad=Decimal("2"),
            precio_unit=Decimal("50"),
            subtotal=Decimal("100"),
        )
        DocumentoVentaService.emitir(doc, almacen=self.almacen)
        doc.refresh_from_db()
        assert doc.estado == EstadoDocumento.EMITIDO
        assert doc.almacen_id == self.almacen.pk
        stock = Stock.objects.get(item=self.item, almacen=self.almacen)
        assert stock.cantidad == Decimal("8")
        cob = Cobranza.objects.get(documento_venta=doc)
        assert cob.estado == EstadoCobranza.PAGADO
        assert cob.monto_pagado == doc.total

    def test_emitir_credito_cobranza_pendiente(self):
        cli = Cliente.objects.create(
            empresa=self.empresa,
            documento="20111111119",
            razon_social="Cliente Crédito",
        )
        doc = DocumentoVenta.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            tipo=TipoDocumentoVenta.BOLETA,
            fecha_emision="2026-04-01",
            estado=EstadoDocumento.BORRADOR,
            cliente=cli,
            condicion_pago=CondicionPagoDocumento.CREDITO,
            fecha_vencimiento="2026-04-30",
            subtotal=Decimal("100"),
            igv=Decimal("18"),
            total=Decimal("118"),
        )
        DocumentoVentaLinea.objects.create(
            documento=doc,
            item=self.item,
            cantidad=Decimal("2"),
            precio_unit=Decimal("50"),
            subtotal=Decimal("100"),
        )
        DocumentoVentaService.emitir(doc, almacen=self.almacen)
        doc.refresh_from_db()
        cob = Cobranza.objects.get(documento_venta=doc)
        assert cob.estado == EstadoCobranza.PENDIENTE
        assert cob.monto_pagado == Decimal("0")
        assert cob.fecha_vencimiento == doc.fecha_vencimiento

    def test_emitir_sin_stock_falla(self):
        doc = DocumentoVenta.objects.create(
            empresa=self.empresa,
            tipo=TipoDocumentoVenta.BOLETA,
            fecha_emision="2026-04-01",
            estado=EstadoDocumento.BORRADOR,
            total=Decimal("100"),
        )
        DocumentoVentaLinea.objects.create(
            documento=doc,
            item=self.item,
            cantidad=Decimal("100"),
            precio_unit=Decimal("1"),
            subtotal=Decimal("100"),
        )
        with pytest.raises(StockInsuficienteError):
            DocumentoVentaService.emitir(doc, almacen=self.almacen)

    def test_emitir_nota_credito_cliente_suma_stock(self):
        doc = DocumentoVenta.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            tipo=TipoDocumentoVenta.NOTA_CREDITO_CLIENTE,
            fecha_emision="2026-04-01",
            estado=EstadoDocumento.BORRADOR,
            subtotal=Decimal("100"),
            igv=Decimal("18"),
            total=Decimal("118"),
        )
        DocumentoVentaLinea.objects.create(
            documento=doc,
            item=self.item,
            cantidad=Decimal("3"),
            precio_unit=Decimal("33.33"),
            subtotal=Decimal("100"),
        )
        DocumentoVentaService.emitir(doc, almacen=self.almacen)
        stock = Stock.objects.get(item=self.item, almacen=self.almacen)
        assert stock.cantidad == Decimal("13")
        assert not Cobranza.objects.filter(documento_venta=doc).exists()

    def test_emitir_guia_remision_no_mueve_stock(self):
        doc = DocumentoVenta.objects.create(
            empresa=self.empresa,
            tipo=TipoDocumentoVenta.GUIA_REMISION,
            fecha_emision="2026-04-01",
            estado=EstadoDocumento.BORRADOR,
            subtotal=Decimal("50"),
            igv=Decimal("9"),
            total=Decimal("59"),
        )
        DocumentoVentaLinea.objects.create(
            documento=doc,
            item=self.item,
            cantidad=Decimal("1"),
            precio_unit=Decimal("50"),
            subtotal=Decimal("50"),
        )
        DocumentoVentaService.emitir(doc, almacen=self.almacen)
        stock = Stock.objects.get(item=self.item, almacen=self.almacen)
        assert stock.cantidad == Decimal("10")
        assert Cobranza.objects.filter(documento_venta=doc).exists()
