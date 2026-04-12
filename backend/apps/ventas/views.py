from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api_multitenancy import EmpresaScopedViewSetMixin
from apps.core.models import Cliente, Empresa, Vendedor
from apps.inventario.models import Almacen, Item
from apps.inventario.services.stock_service import StockInsuficienteError

from apps.ventas.models import (
    Cotizacion,
    CotizacionLinea,
    DocumentoVenta,
    DocumentoVentaLinea,
    EstadoDocumento,
    Pedido,
    PedidoLinea,
)
from apps.ventas.serializers import (
    ComprobanteAltaBorradorSerializer,
    CotizacionAltaBorradorSerializer,
    CotizacionConvertirComprobanteSerializer,
    CotizacionLineaSerializer,
    CotizacionSerializer,
    DocumentoVentaLineaWriteSerializer,
    DocumentoVentaSerializer,
    PedidoLineaSerializer,
    PedidoSerializer,
)
from apps.ventas.comprobante_html import render_comprobante_venta_html
from apps.ventas.services.cotizacion_service import (
    CotizacionService,
    cotizacion_bloqueada_por_comprobante_emitido,
)
from apps.ventas.services.documento_venta_service import DocumentoVentaService


class CotizacionViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Cotizacion.objects.select_related(
        "empresa", "cliente", "sucursal", "vendedor"
    ).prefetch_related("lineas")
    serializer_class = CotizacionSerializer
    search_fields = ["serie", "numero", "cliente__documento", "cliente__razon_social"]
    ordering_fields = ["fecha", "total", "estado", "creado_en", "serie", "correlativo"]
    ordering = ["-fecha", "-creado_en"]

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        p = self.request.query_params
        doc = (p.get("cliente_documento") or "").strip()
        if doc:
            qs = qs.filter(cliente__documento__icontains=doc)
        rs = (p.get("cliente_razon_social") or "").strip()
        if rs:
            qs = qs.filter(cliente__razon_social__icontains=rs)
        fd = parse_date((p.get("fecha_desde") or "").strip())
        if fd:
            qs = qs.filter(fecha__gte=fd)
        fh = parse_date((p.get("fecha_hasta") or "").strip())
        if fh:
            qs = qs.filter(fecha__lte=fh)
        est = (p.get("estado") or "").strip()
        if est:
            qs = qs.filter(estado=est)
        sn = (p.get("serie_numero") or "").strip()
        if sn:
            q = Q(serie__icontains=sn) | Q(numero__icontains=sn)
            if sn.isdigit():
                q |= Q(pk=int(sn))
            qs = qs.filter(q)
        return qs

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /ventas/cotizaciones/alta-borrador/ para crear una cotización."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use los endpoints alta-borrador, emitir-cotizacion o convertir-comprobante."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        cot = self.get_object()
        if cotizacion_bloqueada_por_comprobante_emitido(cot):
            return Response(
                {
                    "detail": "No se puede modificar esta cotización: el comprobante vinculado ya fue emitido a SUNAT.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = CotizacionAltaBorradorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        eid = cot.empresa_id

        req_eid = data.get("empresa_id")
        if req_eid is not None and int(req_eid) != int(eid):
            return Response(
                {"detail": "No puede cambiar la empresa de la cotización."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        perfil = getattr(request.user, "perfil_gestor", None) if request.user.is_authenticated else None
        if (
            perfil is not None
            and perfil.empresa_id != eid
            and not request.user.is_superuser
        ):
            return Response(
                {"detail": "No puede editar cotizaciones de otra empresa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        doc_num = data["cliente_documento"].strip()
        razon = data["cliente_razon_social"].strip()
        if not doc_num or not razon:
            return Response(
                {"detail": "Documento y razón social del cliente son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = Cliente.objects.filter(empresa_id=eid, documento=doc_num).first()
        if cliente is None:
            cliente = Cliente.objects.create(
                empresa_id=eid,
                documento=doc_num,
                razon_social=razon,
                email=(data.get("cliente_email") or "").strip(),
                direccion=(data.get("cliente_direccion") or "").strip(),
            )
        else:
            cliente.razon_social = razon
            em = (data.get("cliente_email") or "").strip()
            if em:
                cliente.email = em
            cliente.direccion = (data.get("cliente_direccion") or "").strip()
            cliente.save(update_fields=["razon_social", "email", "direccion"])

        vendedor = None
        vid = data.get("vendedor_id")
        if vid is not None:
            vendedor = Vendedor.objects.filter(pk=vid, empresa_id=eid, activo=True).first()
            if vendedor is None:
                return Response(
                    {"detail": "El vendedor indicado no existe o está inactivo en esta empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        incluye = bool(data.get("precio_incluye_igv"))
        factor_igv = Decimal("1.18")

        CotizacionLinea.objects.filter(cotizacion=cot).delete()

        for ln in data["lineas"]:
            item = Item.objects.filter(pk=ln["item_id"], empresa_id=eid).first()
            if not item:
                return Response(
                    {"detail": f"El ítem {ln['item_id']} no existe en esta empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cant = ln["cantidad"]
            pu = ln["precio_unit"]
            if incluye:
                pu = (pu / factor_igv).quantize(Decimal("0.0001"))
            sub = (cant * pu).quantize(Decimal("0.01"))
            CotizacionLinea.objects.create(
                cotizacion=cot,
                item=item,
                cantidad=cant,
                precio_unit=pu,
                subtotal=sub,
            )

        cot.cliente = cliente
        cot.sucursal_id = data.get("sucursal_id")
        cot.fecha = data["fecha_emision"]
        cot.observacion = (data.get("observacion") or "").strip()
        cot.moneda = data.get("moneda") or "PEN"
        cot.precio_incluye_igv = incluye
        cot.condicion_pago = data["condicion_pago"]
        cot.fecha_vencimiento = data.get("fecha_vencimiento")
        cot.medio_pago = (data.get("medio_pago") or "").strip()
        cot.tipo_operacion = data.get("tipo_operacion") or "VENTA_INTERNA"
        cot.vendedor = vendedor
        cot.save()

        CotizacionService.recalcular_totales(cot)
        cot.refresh_from_db()
        return Response(CotizacionSerializer(cot).data)

    def destroy(self, request, *args, **kwargs):
        cot = self.get_object()
        if cotizacion_bloqueada_por_comprobante_emitido(cot):
            return Response(
                {
                    "detail": "No se puede eliminar: el comprobante vinculado ya fue emitido a SUNAT.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cot.estado not in (EstadoDocumento.BORRADOR, EstadoDocumento.EMITIDO):
            return Response(
                {"detail": "Solo se pueden eliminar cotizaciones en borrador o emitidas (internas)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="alta-borrador")
    @transaction.atomic
    def alta_borrador(self, request):
        """
        Crea cotización en BORRADOR + líneas (misma estructura que comprobante de venta).
        No asigna serie/correlativo hasta POST .../emitir-cotizacion/.
        """
        ser = CotizacionAltaBorradorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        eid = data.get("empresa_id")
        perfil = getattr(request.user, "perfil_gestor", None) if request.user.is_authenticated else None
        if eid is None:
            if perfil is not None:
                eid = perfil.empresa_id
            else:
                return Response(
                    {"detail": "Indique empresa_id o inicie sesión con un usuario con empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif (
            perfil is not None
            and perfil.empresa_id != eid
            and not request.user.is_superuser
        ):
            return Response(
                {"detail": "No puede crear cotizaciones para otra empresa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not Empresa.objects.filter(pk=eid).exists():
            return Response({"detail": "Empresa inválida."}, status=status.HTTP_400_BAD_REQUEST)

        doc_num = data["cliente_documento"].strip()
        razon = data["cliente_razon_social"].strip()
        if not doc_num:
            return Response(
                {"detail": "El número de documento del cliente es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not razon:
            return Response(
                {"detail": "La razón social del cliente es obligatoria."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = Cliente.objects.filter(empresa_id=eid, documento=doc_num).first()
        if cliente is None:
            cliente = Cliente.objects.create(
                empresa_id=eid,
                documento=doc_num,
                razon_social=razon,
                email=(data.get("cliente_email") or "").strip(),
                direccion=(data.get("cliente_direccion") or "").strip(),
            )
        else:
            cliente.razon_social = razon
            em = (data.get("cliente_email") or "").strip()
            if em:
                cliente.email = em
            cliente.direccion = (data.get("cliente_direccion") or "").strip()
            cliente.save(update_fields=["razon_social", "email", "direccion"])

        vendedor = None
        vid = data.get("vendedor_id")
        if vid is not None:
            vendedor = Vendedor.objects.filter(pk=vid, empresa_id=eid, activo=True).first()
            if vendedor is None:
                return Response(
                    {"detail": "El vendedor indicado no existe o está inactivo en esta empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        incluye = bool(data.get("precio_incluye_igv"))
        factor_igv = Decimal("1.18")

        cot = Cotizacion.objects.create(
            empresa_id=eid,
            sucursal_id=data.get("sucursal_id"),
            cliente=cliente,
            fecha=data["fecha_emision"],
            estado=EstadoDocumento.BORRADOR,
            serie="",
            numero="",
            correlativo=None,
            observacion=(data.get("observacion") or "").strip(),
            moneda=data.get("moneda") or "PEN",
            precio_incluye_igv=incluye,
            condicion_pago=data["condicion_pago"],
            fecha_vencimiento=data.get("fecha_vencimiento"),
            medio_pago=(data.get("medio_pago") or "").strip(),
            tipo_operacion=data.get("tipo_operacion") or "VENTA_INTERNA",
            vendedor=vendedor,
        )

        for ln in data["lineas"]:
            item = Item.objects.filter(pk=ln["item_id"], empresa_id=eid).first()
            if not item:
                return Response(
                    {"detail": f"El ítem {ln['item_id']} no existe en esta empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cant = ln["cantidad"]
            pu = ln["precio_unit"]
            if incluye:
                pu = (pu / factor_igv).quantize(Decimal("0.0001"))
            sub = (cant * pu).quantize(Decimal("0.01"))
            CotizacionLinea.objects.create(
                cotizacion=cot,
                item=item,
                cantidad=cant,
                precio_unit=pu,
                subtotal=sub,
            )

        CotizacionService.recalcular_totales(cot)
        cot.refresh_from_db()
        return Response(CotizacionSerializer(cot).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="emitir-cotizacion")
    @transaction.atomic
    def emitir_cotizacion(self, request, pk=None):
        """Asigna serie interna (p. ej. COT1) y correlativo 0001… Solo interno, sin Nubefact."""
        cot = self.get_object()
        try:
            CotizacionService.emitir_interna(cot)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cot.refresh_from_db()
        return Response(CotizacionSerializer(cot).data)

    @action(detail=True, methods=["post"], url_path="convertir-comprobante")
    @transaction.atomic
    def convertir_comprobante(self, request, pk=None):
        """
        Genera un `documento_venta` en BORRADOR (FACTURA o BOLETA) copiando cabecera y líneas.
        Aparece en el módulo de comprobantes; la emisión SUNAT/Nubefact es aparte.
        """
        cot = self.get_object()
        if cot.estado != EstadoDocumento.EMITIDO:
            return Response(
                {"detail": "Solo se puede convertir una cotización emitida (con número interno)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if DocumentoVenta.objects.filter(cotizacion_origen_id=cot.pk).exists():
            return Response(
                {"detail": "Esta cotización ya fue convertida en comprobante."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = CotizacionConvertirComprobanteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = ser.validated_data
        fecha_em = payload.get("fecha_emision") or cot.fecha

        doc = DocumentoVenta.objects.create(
            empresa_id=cot.empresa_id,
            sucursal_id=cot.sucursal_id,
            tipo=payload["tipo"],
            serie=payload["serie"],
            numero="",
            cliente_id=cot.cliente_id,
            fecha_emision=fecha_em,
            estado=EstadoDocumento.BORRADOR,
            observacion=cot.observacion or "",
            moneda=cot.moneda,
            precio_incluye_igv=cot.precio_incluye_igv,
            condicion_pago=cot.condicion_pago,
            fecha_vencimiento=cot.fecha_vencimiento,
            medio_pago=cot.medio_pago or "",
            tipo_operacion=cot.tipo_operacion,
            vendedor_id=cot.vendedor_id,
            cotizacion_origen=cot,
        )

        for ln in cot.lineas.select_related("item").all():
            DocumentoVentaLinea.objects.create(
                documento=doc,
                item_id=ln.item_id,
                cantidad=ln.cantidad,
                precio_unit=ln.precio_unit,
                subtotal=ln.subtotal,
            )

        DocumentoVentaService.recalcular_totales(doc)
        doc.refresh_from_db()
        return Response(DocumentoVentaSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="lineas")
    def agregar_linea(self, request, pk=None):
        cot = self.get_object()
        if cot.estado != EstadoDocumento.BORRADOR:
            return Response(
                {"detail": "Solo se pueden agregar líneas a cotizaciones en borrador."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = CotizacionLineaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(cotizacion=cot)
        CotizacionService.recalcular_totales(cot)
        cot.refresh_from_db()
        return Response(CotizacionSerializer(cot).data, status=status.HTTP_201_CREATED)


class DocumentoVentaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DocumentoVenta.objects.select_related(
        "empresa", "sucursal", "cliente", "vendedor"
    ).prefetch_related(
        Prefetch(
            "lineas",
            queryset=DocumentoVentaLinea.objects.select_related(
                "item", "item__unidad_medida"
            ).order_by("id"),
        )
    )
    serializer_class = DocumentoVentaSerializer
    search_fields = ["serie", "numero"]
    ordering_fields = ["fecha_emision", "tipo", "total", "creado_en", "estado"]
    ordering = ["-fecha_emision", "-creado_en"]

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        return self._filtros_comprobantes(qs)

    def _filtros_comprobantes(self, qs):
        p = self.request.query_params
        doc_pk = (p.get("documento") or "").strip()
        if doc_pk.isdigit():
            return qs.filter(pk=int(doc_pk))
        doc = (p.get("cliente_documento") or "").strip()
        if doc:
            qs = qs.filter(cliente__documento__icontains=doc)
        rs = (p.get("cliente_razon_social") or "").strip()
        if rs:
            qs = qs.filter(cliente__razon_social__icontains=rs)
        tipo = (p.get("tipo") or "").strip()
        if tipo and tipo.upper() != "TODOS":
            qs = qs.filter(tipo=tipo)
        serie = (p.get("serie") or "").strip()
        if serie:
            qs = qs.filter(serie__icontains=serie)
        numero = (p.get("numero") or "").strip()
        if numero:
            qs = qs.filter(numero__icontains=numero)
        fd = parse_date((p.get("fecha_emision_desde") or "").strip())
        if fd:
            qs = qs.filter(fecha_emision__gte=fd)
        fh = parse_date((p.get("fecha_emision_hasta") or "").strip())
        if fh:
            qs = qs.filter(fecha_emision__lte=fh)
        est = (p.get("estado") or "").strip()
        if est:
            qs = qs.filter(estado=est)
        return qs

    @action(detail=False, methods=["post"], url_path="alta-borrador")
    @transaction.atomic
    def alta_borrador(self, request):
        """
        Crea `documento_venta` (BORRADOR) + `documento_venta_linea` desde formulario tipo facturador.
        Cliente: `cliente` (documento, razon_social, email, direccion). Líneas: `item`, cantidad, precio_unit sin IGV.
        """
        ser = ComprobanteAltaBorradorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        eid = data.get("empresa_id")
        perfil = getattr(request.user, "perfil_gestor", None) if request.user.is_authenticated else None
        if eid is None:
            if perfil is not None:
                eid = perfil.empresa_id
            else:
                return Response(
                    {"detail": "Indique empresa_id o inicie sesión con un usuario con empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif (
            perfil is not None
            and perfil.empresa_id != eid
            and not request.user.is_superuser
        ):
            return Response(
                {"detail": "No puede crear comprobantes para otra empresa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not Empresa.objects.filter(pk=eid).exists():
            return Response({"detail": "Empresa inválida."}, status=status.HTTP_400_BAD_REQUEST)

        doc_num = data["cliente_documento"].strip()
        razon = data["cliente_razon_social"].strip()
        if not doc_num:
            return Response(
                {"detail": "El número de documento del cliente es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not razon:
            return Response(
                {"detail": "La razón social del cliente es obligatoria."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = Cliente.objects.filter(empresa_id=eid, documento=doc_num).first()
        if cliente is None:
            cliente = Cliente.objects.create(
                empresa_id=eid,
                documento=doc_num,
                razon_social=razon,
                email=(data.get("cliente_email") or "").strip(),
                direccion=(data.get("cliente_direccion") or "").strip(),
            )
        else:
            cliente.razon_social = razon
            em = (data.get("cliente_email") or "").strip()
            if em:
                cliente.email = em
            cliente.direccion = (data.get("cliente_direccion") or "").strip()
            cliente.save(update_fields=["razon_social", "email", "direccion"])

        vendedor = None
        vid = data.get("vendedor_id")
        if vid is not None:
            vendedor = Vendedor.objects.filter(pk=vid, empresa_id=eid, activo=True).first()
            if vendedor is None:
                return Response(
                    {"detail": "El vendedor indicado no existe o está inactivo en esta empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        incluye = bool(data.get("precio_incluye_igv"))
        factor_igv = Decimal("1.18")

        doc = DocumentoVenta.objects.create(
            empresa_id=eid,
            sucursal_id=data.get("sucursal_id"),
            tipo=data["tipo"],
            serie=(data.get("serie") or "").strip(),
            numero="",
            cliente=cliente,
            fecha_emision=data["fecha_emision"],
            estado=EstadoDocumento.BORRADOR,
            observacion=(data.get("observacion") or "").strip(),
            moneda=data.get("moneda") or "PEN",
            precio_incluye_igv=incluye,
            condicion_pago=data["condicion_pago"],
            fecha_vencimiento=data.get("fecha_vencimiento"),
            medio_pago=(data.get("medio_pago") or "").strip(),
            tipo_operacion=data.get("tipo_operacion") or "VENTA_INTERNA",
            vendedor=vendedor,
        )

        for ln in data["lineas"]:
            item = Item.objects.filter(pk=ln["item_id"], empresa_id=eid).first()
            if not item:
                return Response(
                    {"detail": f"El ítem {ln['item_id']} no existe en esta empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cant = ln["cantidad"]
            pu = ln["precio_unit"]
            if incluye:
                pu = (pu / factor_igv).quantize(Decimal("0.0001"))
            sub = (cant * pu).quantize(Decimal("0.01"))
            DocumentoVentaLinea.objects.create(
                documento=doc,
                item=item,
                cantidad=cant,
                precio_unit=pu,
                subtotal=sub,
            )

        DocumentoVentaService.recalcular_totales(doc)
        doc.refresh_from_db()
        return Response(
            DocumentoVentaSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="lineas")
    def agregar_linea(self, request, pk=None):
        doc = self.get_object()
        w = DocumentoVentaLineaWriteSerializer(data=request.data)
        w.is_valid(raise_exception=True)
        ln = DocumentoVentaLinea.objects.create(documento=doc, **w.validated_data)
        DocumentoVentaService.recalcular_totales(doc)
        return Response(
            DocumentoVentaSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="vista-comprobante")
    def vista_comprobante(self, request, pk=None):
        doc = self.get_object()
        body = render_comprobante_venta_html(request, doc)
        return HttpResponse(body, content_type="text/html; charset=utf-8")

    @action(detail=True, methods=["post"], url_path="emitir")
    def emitir(self, request, pk=None):
        doc = self.get_object()
        almacen_id = request.data.get("almacen_id")
        if not almacen_id:
            return Response(
                {"detail": "almacen_id es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        almacen = get_object_or_404(Almacen, pk=almacen_id)
        try:
            DocumentoVentaService.emitir(
                doc,
                almacen=almacen,
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except StockInsuficienteError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(DocumentoVentaSerializer(doc).data)


class PedidoViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Pedido.objects.select_related("empresa", "cliente").prefetch_related(
        "lineas"
    )
    serializer_class = PedidoSerializer

    @action(detail=True, methods=["post"], url_path="lineas")
    def agregar_linea(self, request, pk=None):
        pedido = self.get_object()
        data = request.data.copy()
        ser = PedidoLineaSerializer(data=data)
        ser.is_valid(raise_exception=True)
        PedidoLinea.objects.create(pedido=pedido, **ser.validated_data)
        return Response(PedidoSerializer(pedido).data, status=status.HTTP_201_CREATED)
