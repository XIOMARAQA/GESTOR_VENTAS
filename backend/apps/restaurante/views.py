from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.restaurante.models import Comanda, ComandaLinea, EstadoComandaLinea
from apps.restaurante.serializers import ComandaLineaSerializer, ComandaSerializer


class ComandaViewSet(viewsets.ModelViewSet):
    queryset = Comanda.objects.select_related("sucursal").prefetch_related("lineas")
    serializer_class = ComandaSerializer

    @action(detail=True, methods=["post"], url_path="lineas")
    def agregar_linea(self, request, pk=None):
        comanda = self.get_object()
        data = request.data.copy()
        ser = ComandaLineaSerializer(data=data)
        ser.is_valid(raise_exception=True)
        ser.save(comanda=comanda)
        return Response(ComandaSerializer(comanda).data, status=status.HTTP_201_CREATED)


class CocinaLineaViewSet(viewsets.ReadOnlyModelViewSet):
    """Monitor de cocina: líneas pendientes o en preparación."""

    serializer_class = ComandaLineaSerializer

    def get_queryset(self):
        qs = ComandaLinea.objects.select_related("comanda", "item", "comanda__sucursal")
        sucursal = self.request.query_params.get("sucursal")
        if sucursal:
            qs = qs.filter(comanda__sucursal_id=sucursal)
        return qs.filter(
            estado__in=[
                EstadoComandaLinea.PENDIENTE,
                EstadoComandaLinea.EN_PREPARACION,
            ]
        ).order_by("creado_en")

    @action(detail=True, methods=["post"], url_path="cambiar-estado")
    def cambiar_estado(self, request, pk=None):
        linea = self.get_object()
        nuevo = request.data.get("estado")
        if nuevo not in EstadoComandaLinea.values:
            return Response(
                {"detail": "estado no válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        linea.estado = nuevo
        linea.save(update_fields=["estado", "actualizado_en"])
        return Response(ComandaLineaSerializer(linea).data)
