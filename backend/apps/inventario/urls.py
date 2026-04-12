from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inventario import views

router = DefaultRouter()
router.register(r"categorias", views.CategoriaViewSet, basename="categoria")
router.register(r"marcas", views.MarcaViewSet, basename="marca")
router.register(
    r"unidades-medida", views.UnidadMedidaViewSet, basename="unidad-medida"
)
router.register(r"atributos", views.AtributoViewSet, basename="atributo")
router.register(r"items", views.ItemViewSet, basename="item")
router.register(
    r"items-atributos", views.ItemAtributoValorViewSet, basename="item-atributo"
)
router.register(r"almacenes", views.AlmacenViewSet, basename="almacen")
router.register(r"stock", views.StockViewSet, basename="stock")
router.register(r"movimientos", views.MovimientoStockViewSet, basename="movimiento-stock")
router.register(r"listas-precio", views.ListaPrecioViewSet, basename="lista-precio")
router.register(
    r"listas-precio-items", views.ListaPrecioItemViewSet, basename="lista-precio-item"
)

urlpatterns = [
    path("", include(router.urls)),
]
