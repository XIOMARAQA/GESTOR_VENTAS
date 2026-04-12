from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.restaurante import views

router = DefaultRouter()
router.register(r"comandas", views.ComandaViewSet, basename="comanda")
router.register(r"cocina", views.CocinaLineaViewSet, basename="cocina-linea")

urlpatterns = [
    path("", include(router.urls)),
]
