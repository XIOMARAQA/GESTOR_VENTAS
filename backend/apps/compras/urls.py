from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.compras import views

router = DefaultRouter()
router.register(r"ordenes", views.OrdenCompraViewSet, basename="orden-compra")
router.register(
    r"documentos", views.DocumentoCompraViewSet, basename="documento-compra"
)
router.register(r"gastos-recurrentes", views.GastoRecurrenteViewSet, basename="gasto-recurrente")

urlpatterns = [
    path("", include(router.urls)),
]
