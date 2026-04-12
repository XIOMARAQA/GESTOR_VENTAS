from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.core.auth_urls")),
    path("core/", include("apps.core.urls")),
    path("inventario/", include("apps.inventario.urls")),
    path("ventas/", include("apps.ventas.urls")),
    path("compras/", include("apps.compras.urls")),
    path("tesoreria/", include("apps.tesoreria.urls")),
    path("restaurante/", include("apps.restaurante.urls")),
    path("contabilidad/", include("apps.contabilidad.urls")),
    path("administracion/", include("apps.administracion.urls")),
]
