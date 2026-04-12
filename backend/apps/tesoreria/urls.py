from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tesoreria import views

router = DefaultRouter()
router.register(r"bancos", views.CuentaBancariaViewSet, basename="cuenta-bancaria")
router.register(r"cajas", views.CajaViewSet, basename="caja")
router.register(r"cobranzas", views.CobranzaViewSet, basename="cobranza")
router.register(r"pagos-recibidos", views.PagoRecibidoViewSet, basename="pago-recibido")
router.register(r"cronograma", views.CronogramaPagoViewSet, basename="cronograma-pago")
router.register(
    r"pagos-proveedores",
    views.PagoRealizadoProveedorViewSet,
    basename="pago-proveedor",
)
router.register(
    r"conciliaciones", views.ConciliacionBancariaViewSet, basename="conciliacion"
)

urlpatterns = [
    path("", include(router.urls)),
]
