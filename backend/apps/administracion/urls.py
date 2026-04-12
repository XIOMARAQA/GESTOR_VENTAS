from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.administracion import views

router = DefaultRouter()
router.register(
    r"configuracion", views.ConfiguracionSistemaViewSet, basename="configuracion"
)
router.register(r"tareas", views.TareaViewSet, basename="tarea")

urlpatterns = [
    path("", include(router.urls)),
]
