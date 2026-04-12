from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.core.api_multitenancy import EmpresaQuerysetMixin, EmpresaScopedViewSetMixin
from apps.tesoreria.models import (
    Caja,
    Cobranza,
    ConciliacionBancaria,
    CronogramaPago,
    CuentaBancaria,
    EstadoCobranza,
    EstadoCronogramaPago,
    PagoRealizadoProveedor,
    PagoRecibido,
)
from apps.tesoreria.serializers import (
    CajaSerializer,
    CobranzaSerializer,
    ConciliacionBancariaSerializer,
    CronogramaPagoSerializer,
    CuentaBancariaSerializer,
    PagoRealizadoProveedorSerializer,
    PagoRecibidoSerializer,
)
from apps.tesoreria.services.cobranza_service import CobranzaService
from apps.tesoreria.services.proveedor_pago_service import ProveedorPagoService


class CobranzaPagination(PageNumberPagination):
    """Lista de cobranzas: más filas por página y límite ampliable desde el cliente."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class CuentaBancariaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CuentaBancaria.objects.select_related("empresa")
    serializer_class = CuentaBancariaSerializer


class CajaViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    queryset = Caja.objects.select_related("sucursal", "sucursal__empresa")
    serializer_class = CajaSerializer
    empresa_lookup = "sucursal__empresa_id"

    def perform_create(self, serializer):
        self._assert_sucursal_tenant(serializer.validated_data.get("sucursal"))
        serializer.save()

    def perform_update(self, serializer):
        suc = serializer.validated_data.get("sucursal")
        if suc is not None:
            self._assert_sucursal_tenant(suc)
        serializer.save()

    def _assert_sucursal_tenant(self, sucursal):
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied("Usuario sin empresa asignada.")
        if sucursal is not None and sucursal.empresa_id != perfil.empresa_id:
            raise PermissionDenied("La sucursal no pertenece a su empresa.")


class CobranzaViewSet(EmpresaQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Cobranza.objects.select_related(
        "empresa", "documento_venta", "documento_venta__cliente"
    )
    serializer_class = CobranzaSerializer
    pagination_class = CobranzaPagination

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and getattr(user, "is_superuser", False):
            raw_e = (self.request.query_params.get("empresa_id") or "").strip()
            if raw_e.isdigit():
                qs = qs.filter(empresa_id=int(raw_e))
        raw_pend = (self.request.query_params.get("pendiente") or "").strip().lower()
        if raw_pend in ("1", "true", "yes", "si"):
            qs = qs.filter(
                estado__in=[EstadoCobranza.PENDIENTE, EstadoCobranza.PAGADO_PARCIAL]
            )
        else:
            est = (self.request.query_params.get("estado") or "").strip()
            if est:
                qs = qs.filter(estado=est)

        raw_docs = (self.request.query_params.get("documentos") or "").strip()
        if raw_docs:
            ids = [int(x) for x in raw_docs.split(",") if x.strip().isdigit()]
            if ids:
                qs = qs.filter(documento_venta_id__in=ids)

        p = self.request.query_params
        cd = (p.get("cliente_documento") or "").strip()
        if cd:
            qs = qs.filter(documento_venta__cliente__documento__icontains=cd)
        crs = (p.get("cliente_razon_social") or "").strip()
        if crs:
            qs = qs.filter(documento_venta__cliente__razon_social__icontains=crs)
        tipo = (p.get("tipo") or "").strip()
        if tipo:
            qs = qs.filter(documento_venta__tipo=tipo)
        serie = (p.get("serie") or "").strip()
        if serie:
            qs = qs.filter(documento_venta__serie__icontains=serie)
        numero = (p.get("numero") or "").strip()
        if numero:
            qs = qs.filter(documento_venta__numero__icontains=numero)
        fd = parse_date((p.get("fecha_documento_desde") or "").strip())
        if fd:
            qs = qs.filter(documento_venta__fecha_emision__gte=fd)
        fh = parse_date((p.get("fecha_documento_hasta") or "").strip())
        if fh:
            qs = qs.filter(documento_venta__fecha_emision__lte=fh)
        fv_d = parse_date((p.get("fecha_vencimiento_desde") or "").strip())
        if fv_d:
            qs = qs.filter(fecha_vencimiento__gte=fv_d)
        fv_h = parse_date((p.get("fecha_vencimiento_hasta") or "").strip())
        if fv_h:
            qs = qs.filter(fecha_vencimiento__lte=fv_h)
        desc = (p.get("descripcion") or "").strip()
        if desc:
            qs = qs.filter(documento_venta__observacion__icontains=desc)
        return qs

    @action(detail=True, methods=["post"], url_path="registrar-pago")
    def registrar_pago(self, request, pk=None):
        cobranza = self.get_object()
        monto = request.data.get("monto")
        if monto is None:
            return Response(
                {"detail": "monto es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from decimal import Decimal

            monto_dec = Decimal(str(monto))
            raw_metodo = request.data.get("metodo")
            metodo_str = (
                str(raw_metodo).strip()
                if raw_metodo is not None and str(raw_metodo).strip()
                else None
            )
            CobranzaService.registrar_pago(
                cobranza,
                monto_dec,
                usuario=request.user if request.user.is_authenticated else None,
                metodo=metodo_str,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cobranza.refresh_from_db()
        return Response(CobranzaSerializer(cobranza).data)


class PagoRecibidoViewSet(EmpresaQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PagoRecibido.objects.select_related(
        "empresa",
        "cobranza",
        "cobranza__documento_venta",
        "cobranza__documento_venta__cliente",
        "cuenta_bancaria",
        "caja",
        "usuario",
    )
    serializer_class = PagoRecibidoSerializer
    pagination_class = CobranzaPagination

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and getattr(user, "is_superuser", False):
            raw_e = (self.request.query_params.get("empresa_id") or "").strip()
            if raw_e.isdigit():
                qs = qs.filter(empresa_id=int(raw_e))
        raw_docs = (self.request.query_params.get("documentos") or "").strip()
        if raw_docs:
            ids = [int(x) for x in raw_docs.split(",") if x.strip().isdigit()]
            if ids:
                qs = qs.filter(cobranza__documento_venta_id__in=ids)

        p = self.request.query_params
        doc_cli = (p.get("cliente_documento") or "").strip()
        if doc_cli:
            qs = qs.filter(
                cobranza__documento_venta__cliente__documento__icontains=doc_cli
            )
        rs = (p.get("cliente_razon_social") or "").strip()
        if rs:
            qs = qs.filter(
                cobranza__documento_venta__cliente__razon_social__icontains=rs
            )
        tipo = (p.get("tipo") or "").strip()
        if tipo and tipo.upper() != "TODOS":
            qs = qs.filter(cobranza__documento_venta__tipo=tipo)
        serie = (p.get("serie") or "").strip()
        if serie:
            qs = qs.filter(cobranza__documento_venta__serie__icontains=serie)
        numero = (p.get("numero") or "").strip()
        if numero:
            qs = qs.filter(cobranza__documento_venta__numero__icontains=numero)
        fd = parse_date((p.get("fecha_emision_desde") or "").strip())
        if fd:
            qs = qs.filter(cobranza__documento_venta__fecha_emision__gte=fd)
        fh = parse_date((p.get("fecha_emision_hasta") or "").strip())
        if fh:
            qs = qs.filter(cobranza__documento_venta__fecha_emision__lte=fh)
        fp_d = parse_date((p.get("fecha_pago_desde") or "").strip())
        if fp_d:
            qs = qs.filter(creado_en__date__gte=fp_d)
        fp_h = parse_date((p.get("fecha_pago_hasta") or "").strip())
        if fp_h:
            qs = qs.filter(creado_en__date__lte=fp_h)
        met = (p.get("metodo") or "").strip()
        if met:
            qs = qs.filter(metodo__icontains=met)
        return qs

    @action(detail=True, methods=["post"], url_path="revertir")
    def revertir(self, request, pk=None):
        pago = self.get_object()
        try:
            CobranzaService.revertir_pago(pago)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PagoRealizadoProveedorViewSet(EmpresaQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PagoRealizadoProveedor.objects.select_related(
        "empresa",
        "usuario",
        "cronograma_pago",
        "cronograma_pago__documento_compra",
        "cronograma_pago__documento_compra__proveedor",
        "cronograma_pago__proveedor",
    )
    serializer_class = PagoRealizadoProveedorSerializer
    pagination_class = CobranzaPagination

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and getattr(user, "is_superuser", False):
            raw_e = (self.request.query_params.get("empresa_id") or "").strip()
            if raw_e.isdigit():
                qs = qs.filter(empresa_id=int(raw_e))
        raw_docs = (self.request.query_params.get("documentos") or "").strip()
        if raw_docs:
            ids = [int(x) for x in raw_docs.split(",") if x.strip().isdigit()]
            if ids:
                qs = qs.filter(cronograma_pago__documento_compra_id__in=ids)

        p = self.request.query_params
        pd = (p.get("proveedor_documento") or "").strip()
        if pd:
            qs = qs.filter(
                Q(cronograma_pago__proveedor__documento__icontains=pd)
                | Q(
                    cronograma_pago__documento_compra__proveedor__documento__icontains=pd
                )
            )
        pr = (p.get("proveedor_razon_social") or "").strip()
        if pr:
            qs = qs.filter(
                Q(cronograma_pago__proveedor__razon_social__icontains=pr)
                | Q(
                    cronograma_pago__documento_compra__proveedor__razon_social__icontains=pr
                )
            )
        tipo = (p.get("tipo") or "").strip()
        if tipo:
            qs = qs.filter(cronograma_pago__documento_compra__tipo=tipo)
        serie = (p.get("serie") or "").strip()
        if serie:
            qs = qs.filter(cronograma_pago__documento_compra__serie__icontains=serie)
        numero = (p.get("numero") or "").strip()
        if numero:
            qs = qs.filter(cronograma_pago__documento_compra__numero__icontains=numero)
        fd = parse_date((p.get("fecha_documento_desde") or "").strip())
        if fd:
            qs = qs.filter(cronograma_pago__documento_compra__fecha__gte=fd)
        fh = parse_date((p.get("fecha_documento_hasta") or "").strip())
        if fh:
            qs = qs.filter(cronograma_pago__documento_compra__fecha__lte=fh)
        fp_d = parse_date((p.get("fecha_pago_desde") or "").strip())
        if fp_d:
            qs = qs.filter(creado_en__date__gte=fp_d)
        fp_h = parse_date((p.get("fecha_pago_hasta") or "").strip())
        if fp_h:
            qs = qs.filter(creado_en__date__lte=fp_h)
        met = (p.get("metodo") or "").strip()
        if met:
            qs = qs.filter(metodo__icontains=met)
        return qs

    @action(detail=True, methods=["post"], url_path="revertir")
    def revertir(self, request, pk=None):
        pago = self.get_object()
        try:
            ProveedorPagoService.revertir_pago(pago)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CronogramaPagoViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CronogramaPago.objects.select_related(
        "empresa", "proveedor", "documento_compra", "documento_compra__proveedor"
    )
    serializer_class = CronogramaPagoSerializer
    pagination_class = CobranzaPagination

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and getattr(user, "is_superuser", False):
            raw_e = (self.request.query_params.get("empresa_id") or "").strip()
            if raw_e.isdigit():
                qs = qs.filter(empresa_id=int(raw_e))

        raw_pend = (self.request.query_params.get("pendiente") or "").strip().lower()
        if raw_pend in ("1", "true", "yes", "si"):
            qs = qs.filter(estado=EstadoCronogramaPago.PENDIENTE)
        else:
            est = (self.request.query_params.get("estado") or "").strip()
            if est:
                qs = qs.filter(estado=est)

        raw_docs = (self.request.query_params.get("documentos") or "").strip()
        if raw_docs:
            ids = [int(x) for x in raw_docs.split(",") if x.strip().isdigit()]
            if ids:
                qs = qs.filter(documento_compra_id__in=ids)

        p = self.request.query_params
        pd = (p.get("proveedor_documento") or "").strip()
        if pd:
            qs = qs.filter(
                Q(proveedor__documento__icontains=pd)
                | Q(documento_compra__proveedor__documento__icontains=pd)
            )
        pr = (p.get("proveedor_razon_social") or "").strip()
        if pr:
            qs = qs.filter(
                Q(proveedor__razon_social__icontains=pr)
                | Q(documento_compra__proveedor__razon_social__icontains=pr)
            )
        tipo = (p.get("tipo") or "").strip()
        if tipo:
            qs = qs.filter(documento_compra__tipo=tipo)
        serie = (p.get("serie") or "").strip()
        if serie:
            qs = qs.filter(documento_compra__serie__icontains=serie)
        numero = (p.get("numero") or "").strip()
        if numero:
            qs = qs.filter(documento_compra__numero__icontains=numero)
        fd = parse_date((p.get("fecha_documento_desde") or "").strip())
        if fd:
            qs = qs.filter(documento_compra__fecha__gte=fd)
        fh = parse_date((p.get("fecha_documento_hasta") or "").strip())
        if fh:
            qs = qs.filter(documento_compra__fecha__lte=fh)
        fv_d = parse_date((p.get("fecha_vencimiento_desde") or "").strip())
        if fv_d:
            qs = qs.filter(fecha_vencimiento__gte=fv_d)
        fv_h = parse_date((p.get("fecha_vencimiento_hasta") or "").strip())
        if fv_h:
            qs = qs.filter(fecha_vencimiento__lte=fv_h)
        desc = (p.get("descripcion") or "").strip()
        if desc:
            qs = qs.filter(descripcion__icontains=desc)
        return qs

    @action(detail=True, methods=["post"], url_path="marcar-pagado")
    def marcar_pagado(self, request, pk=None):
        cuota = self.get_object()
        try:
            from decimal import Decimal

            monto = request.data.get("monto")
            if monto is None:
                monto_dec = cuota.monto
            else:
                monto_dec = Decimal(str(monto))
            raw_metodo = request.data.get("metodo")
            metodo_str = (
                str(raw_metodo).strip()
                if raw_metodo is not None and str(raw_metodo).strip()
                else None
            )
            ProveedorPagoService.registrar_pago_cronograma(
                cuota,
                monto_dec,
                usuario=request.user if request.user.is_authenticated else None,
                metodo=metodo_str,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cuota.refresh_from_db()
        return Response(CronogramaPagoSerializer(cuota).data)

    @action(detail=True, methods=["post"], url_path="revertir")
    def revertir(self, request, pk=None):
        cuota = self.get_object()
        try:
            ProveedorPagoService.revertir_obligacion_pagada(cuota)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cuota.refresh_from_db()
        return Response(CronogramaPagoSerializer(cuota).data)

    @action(detail=False, methods=["post"], url_path="registrar-por-documento")
    def registrar_por_documento(self, request):
        doc_id = request.data.get("documento_compra_id")
        if doc_id is None:
            return Response(
                {"detail": "documento_compra_id es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            doc_id_int = int(doc_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "documento_compra_id inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cuota = (
            self.get_queryset()
            .filter(
                documento_compra_id=doc_id_int,
                estado=EstadoCronogramaPago.PENDIENTE,
            )
            .first()
        )
        if cuota is None:
            return Response(
                {"detail": "No hay obligación pendiente para ese documento."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from decimal import Decimal

            monto = request.data.get("monto")
            if monto is None:
                monto_dec = cuota.monto
            else:
                monto_dec = Decimal(str(monto))
            raw_metodo = request.data.get("metodo")
            metodo_str = (
                str(raw_metodo).strip()
                if raw_metodo is not None and str(raw_metodo).strip()
                else None
            )
            ProveedorPagoService.registrar_pago_cronograma(
                cuota,
                monto_dec,
                usuario=request.user if request.user.is_authenticated else None,
                metodo=metodo_str,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cuota.refresh_from_db()
        return Response(CronogramaPagoSerializer(cuota).data)


class ConciliacionBancariaViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    queryset = ConciliacionBancaria.objects.select_related("cuenta")
    serializer_class = ConciliacionBancariaSerializer
    empresa_lookup = "cuenta__empresa_id"

    def perform_create(self, serializer):
        self._assert_cuenta_tenant(serializer.validated_data.get("cuenta"))
        serializer.save()

    def perform_update(self, serializer):
        cuenta = serializer.validated_data.get("cuenta")
        if cuenta is None and serializer.instance:
            cuenta = serializer.instance.cuenta
        self._assert_cuenta_tenant(cuenta)
        serializer.save()

    def _assert_cuenta_tenant(self, cuenta):
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied("Usuario sin empresa asignada.")
        if cuenta is not None and cuenta.empresa_id != perfil.empresa_id:
            raise PermissionDenied("La cuenta no pertenece a su empresa.")
