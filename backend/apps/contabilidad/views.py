from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api_multitenancy import EmpresaScopedViewSetMixin
from apps.contabilidad.models import AsientoContable, AsientoLinea, ComunicacionBaja, PlanCuenta
from apps.contabilidad.serializers import (
    AsientoContableSerializer,
    AsientoLineaSerializer,
    ComunicacionBajaSerializer,
    PlanCuentaSerializer,
)


class PlanCuentaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PlanCuenta.objects.select_related("empresa")
    serializer_class = PlanCuentaSerializer
    search_fields = ["codigo", "nombre"]


class AsientoContableViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = AsientoContable.objects.select_related("empresa").prefetch_related(
        "lineas"
    )
    serializer_class = AsientoContableSerializer

    @action(detail=True, methods=["post"], url_path="lineas")
    def agregar_linea(self, request, pk=None):
        asiento = self.get_object()
        ser = AsientoLineaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        AsientoLinea.objects.create(asiento=asiento, **ser.validated_data)
        return Response(AsientoContableSerializer(asiento).data, status=status.HTTP_201_CREATED)


class ComunicacionBajaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ComunicacionBaja.objects.select_related("empresa")
    serializer_class = ComunicacionBajaSerializer
