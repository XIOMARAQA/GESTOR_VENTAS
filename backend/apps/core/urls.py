from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.core import views
from apps.core.views_consulta_reniec import ConsultarReniecDniView
from apps.core.views_consulta_ruc import ConsultarRucSunatView
from apps.core.views_plataforma import (
    PlataformaEmpresasExportView,
    PlataformaResumenView,
    PlataformaSuperusuarioDetalleView,
    PlataformaSuperusuariosView,
)

router = DefaultRouter()
router.register(r"empresas", views.EmpresaViewSet, basename="empresa")
router.register(r"sucursales", views.SucursalViewSet, basename="sucursal")
router.register(r"clientes", views.ClienteViewSet, basename="cliente")
router.register(r"proveedores", views.ProveedorViewSet, basename="proveedor")
router.register(r"vendedores", views.VendedorViewSet, basename="vendedor")
router.register(r"perfiles", views.PerfilUsuarioViewSet, basename="perfil")
router.register(
    r"notificaciones", views.NotificacionUsuarioViewSet, basename="notificacion"
)

urlpatterns = [
    path("consultar-ruc/", ConsultarRucSunatView.as_view(), name="consultar-ruc-sunat"),
    path(
        "consultar-reniec-dni/",
        ConsultarReniecDniView.as_view(),
        name="consultar-reniec-dni",
    ),
    path("plataforma/resumen/", PlataformaResumenView.as_view(), name="plataforma-resumen"),
    path(
        "plataforma/empresas-export.csv",
        PlataformaEmpresasExportView.as_view(),
        name="plataforma-empresas-export",
    ),
    path(
        "plataforma/superusuarios/",
        PlataformaSuperusuariosView.as_view(),
        name="plataforma-superusuarios",
    ),
    path(
        "plataforma/superusuarios/<int:pk>/",
        PlataformaSuperusuarioDetalleView.as_view(),
        name="plataforma-superusuario-detalle",
    ),
    path("", include(router.urls)),
]
