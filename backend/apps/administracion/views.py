from rest_framework import viewsets

from apps.administracion.models import ConfiguracionSistema, Tarea
from apps.core.api_multitenancy import EmpresaScopedViewSetMixin
from apps.administracion.serializers import ConfiguracionSistemaSerializer, TareaSerializer


class ConfiguracionSistemaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ConfiguracionSistema.objects.select_related("empresa")
    serializer_class = ConfiguracionSistemaSerializer


class TareaViewSet(viewsets.ModelViewSet):
    queryset = Tarea.objects.select_related("usuario")
    serializer_class = TareaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            return qs.filter(usuario=self.request.user)
        return qs.none()
