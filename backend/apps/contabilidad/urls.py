from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.contabilidad import views

router = DefaultRouter()
router.register(r"plan-cuentas", views.PlanCuentaViewSet, basename="plan-cuenta")
router.register(r"asientos", views.AsientoContableViewSet, basename="asiento")
router.register(
    r"comunicaciones-baja", views.ComunicacionBajaViewSet, basename="comunicacion-baja"
)

urlpatterns = [
    path("", include(router.urls)),
]
