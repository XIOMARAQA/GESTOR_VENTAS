from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ventas import nubefact_views, views
from apps.ventas.reportes_views import VentasDashboardView

router = DefaultRouter()
router.register(r"cotizaciones", views.CotizacionViewSet, basename="cotizacion")
router.register(
    r"documentos", views.DocumentoVentaViewSet, basename="documento-venta"
)
router.register(r"pedidos", views.PedidoViewSet, basename="pedido")

urlpatterns = [
    path("reportes/dashboard/", VentasDashboardView.as_view(), name="ventas-dashboard"),
    path("nubefact/config/", nubefact_views.NubefactConfigView.as_view(), name="nubefact-config"),
    path("nubefact/emitir/", nubefact_views.EmitirNubefactView.as_view(), name="nubefact-emitir"),
    path("", include(router.urls)),
]
