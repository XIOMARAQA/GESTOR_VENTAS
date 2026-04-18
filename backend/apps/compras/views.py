from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api_multitenancy import EmpresaScopedViewSetMixin
from apps.core.models import Empresa, Proveedor
from apps.compras.models import (
    DocumentoCompra,
    DocumentoCompraLinea,
    GastoRecurrente,
    OrdenCompra,
    OrdenCompraLinea,
)
from apps.compras.serializers import (
    DocumentoCompraAltaBorradorSerializer,
    DocumentoCompraLineaSerializer,
    DocumentoCompraSerializer,
    GastoRecurrenteSerializer,
    OrdenCompraLineaSerializer,
    OrdenCompraSerializer,
)
from apps.compras.services.documento_compra_service import DocumentoCompraService
from apps.inventario.models import Almacen, Item
from apps.inventario.services.stock_service import StockInsuficienteError
from apps.ventas.models import EstadoDocumento


class OrdenCompraViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = OrdenCompra.objects.select_related("empresa", "proveedor").prefetch_related(
        "lineas"
    )
    serializer_class = OrdenCompraSerializer

    @action(detail=True, methods=["post"], url_path="lineas")
    def agregar_linea(self, request, pk=None):
        orden = self.get_object()
        ser = OrdenCompraLineaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(orden=orden)
        return Response(OrdenCompraSerializer(orden).data, status=status.HTTP_201_CREATED)


class DocumentoCompraViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DocumentoCompra.objects.select_related(
        "empresa", "proveedor"
    ).prefetch_related("lineas")
    serializer_class = DocumentoCompraSerializer
    search_fields = ["serie", "numero", "proveedor__razon_social", "proveedor__documento"]
    ordering = ["-fecha", "-creado_en"]
    ordering_fields = ["fecha", "creado_en", "total", "estado"]

    def get_queryset(self):
        qs = super().get_queryset().exclude(estado=EstadoDocumento.ANULADO)
        doc_pk = (self.request.query_params.get("documento") or "").strip()
        if doc_pk.isdigit():
            qs = qs.filter(pk=int(doc_pk))
        est = (self.request.query_params.get("estado") or "").strip()
        if est:
            qs = qs.filter(estado=est)
        return qs

    @action(detail=False, methods=["post"], url_path="alta-borrador")
    @transaction.atomic
    def alta_borrador(self, request):
        """
        Crea documento de compra en BORRADOR + líneas. Registro interno (no SUNAT / Nubefact).
        """
        ser = DocumentoCompraAltaBorradorSerializer(data=request.data)
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
                {"detail": "No puede crear documentos de compra para otra empresa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not Empresa.objects.filter(pk=eid).exists():
            return Response({"detail": "Empresa inválida."}, status=status.HTTP_400_BAD_REQUEST)

        proveedor = Proveedor.objects.filter(pk=data["proveedor_id"], empresa_id=eid).first()
        if proveedor is None:
            return Response(
                {"detail": "El proveedor no existe en esta empresa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lineas_in = data["lineas"]
        if not lineas_in:
            return Response(
                {"detail": "Debe indicar al menos una línea."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        incluye = bool(data.get("precio_incluye_igv"))
        factor_igv = Decimal("1.18")

        doc = DocumentoCompra.objects.create(
            empresa_id=eid,
            tipo=data["tipo"],
            proveedor=proveedor,
            serie=(data.get("serie") or "").strip()[:10],
            numero=(data.get("numero") or "").strip()[:20],
            fecha=data["fecha"],
            condicion_pago=data["condicion_pago"],
            fecha_vencimiento=data.get("fecha_vencimiento"),
            es_electronica=False,
            precio_incluye_igv=incluye,
            afecta_stock=bool(data.get("afecta_stock", True)),
        )

        for ln in lineas_in:
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
            DocumentoCompraLinea.objects.create(
                documento=doc,
                item=item,
                cantidad=cant,
                precio_unit=pu,
                subtotal=sub,
            )

        DocumentoCompraService.recalcular_totales(doc)
        doc.refresh_from_db()
        return Response(
            DocumentoCompraSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="lineas")
    def agregar_linea(self, request, pk=None):
        doc = self.get_object()
        ser = DocumentoCompraLineaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        cant = vd["cantidad"]
        pu = vd["precio_unit"]
        if doc.precio_incluye_igv:
            pu = (pu / Decimal("1.18")).quantize(Decimal("0.0001"))
        sub = vd.get("subtotal")
        if sub is None:
            sub = (cant * pu).quantize(Decimal("0.01"))
        DocumentoCompraLinea.objects.create(
            documento=doc,
            item=vd["item"],
            cantidad=cant,
            precio_unit=pu,
            subtotal=sub,
        )
        DocumentoCompraService.recalcular_totales(doc)
        doc.refresh_from_db()
        return Response(DocumentoCompraSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="actualizar-borrador")
    @transaction.atomic
    def actualizar_borrador(self, request, pk=None):
        doc = self.get_object()
        if doc.estado != EstadoDocumento.BORRADOR:
            return Response(
                {"detail": "Solo se puede editar un documento en borrador."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = DocumentoCompraAltaBorradorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        proveedor = Proveedor.objects.filter(
            pk=data["proveedor_id"], empresa_id=doc.empresa_id
        ).first()
        if proveedor is None:
            return Response(
                {"detail": "El proveedor no existe en esta empresa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lineas_in = data["lineas"]
        if not lineas_in:
            return Response(
                {"detail": "Debe indicar al menos una línea."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        incluye = bool(data.get("precio_incluye_igv"))
        factor_igv = Decimal("1.18")

        doc.tipo = data["tipo"]
        doc.proveedor = proveedor
        doc.serie = (data.get("serie") or "").strip()[:10]
        doc.numero = (data.get("numero") or "").strip()[:20]
        doc.fecha = data["fecha"]
        doc.condicion_pago = data["condicion_pago"]
        doc.fecha_vencimiento = data.get("fecha_vencimiento")
        doc.precio_incluye_igv = incluye
        doc.afecta_stock = bool(data.get("afecta_stock", True))
        doc.save()

        DocumentoCompraLinea.objects.filter(documento=doc).delete()
        for ln in lineas_in:
            item = Item.objects.filter(pk=ln["item_id"], empresa_id=doc.empresa_id).first()
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
            DocumentoCompraLinea.objects.create(
                documento=doc,
                item=item,
                cantidad=cant,
                precio_unit=pu,
                subtotal=sub,
            )

        DocumentoCompraService.recalcular_totales(doc)
        doc.refresh_from_db()
        return Response(DocumentoCompraSerializer(doc).data)

    @action(detail=True, methods=["post"], url_path="anular")
    @transaction.atomic
    def anular(self, request, pk=None):
        doc = self.get_object()
        try:
            DocumentoCompraService.anular(
                doc,
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except StockInsuficienteError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        doc.refresh_from_db()
        return Response(DocumentoCompraSerializer(doc).data)

    @action(detail=True, methods=["post"], url_path="reabrir-borrador")
    @transaction.atomic
    def reabrir_borrador(self, request, pk=None):
        doc = self.get_object()
        try:
            DocumentoCompraService.reabrir_borrador_para_edicion(
                doc,
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except StockInsuficienteError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        doc.refresh_from_db()
        return Response(DocumentoCompraSerializer(doc).data)

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
            DocumentoCompraService.emitir(
                doc,
                almacen=almacen,
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except StockInsuficienteError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(DocumentoCompraSerializer(doc).data)


class GastoRecurrenteViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = GastoRecurrente.objects.select_related("empresa")
    serializer_class = GastoRecurrenteSerializer
