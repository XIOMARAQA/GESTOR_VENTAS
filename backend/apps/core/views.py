from django.http import HttpResponse
from django.utils import timezone

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.api_multitenancy import EmpresaScopedViewSetMixin, filter_queryset_by_empresa
from apps.core.cliente_excel import build_clientes_template_xlsx, import_clientes_xlsx
from apps.core.proveedor_excel import build_proveedores_template_xlsx, import_proveedores_xlsx
from apps.core.models import (
    Cliente,
    Empresa,
    NotificacionUsuario,
    PerfilUsuario,
    Proveedor,
    Sucursal,
    Vendedor,
)
from apps.core.notification_utils import dispatch_empresa_cambio_estado
from apps.core.serializers import (
    ClienteSerializer,
    EmpresaSerializer,
    NotificacionUsuarioSerializer,
    PerfilUsuarioSerializer,
    ProveedorSerializer,
    SucursalSerializer,
    VendedorSerializer,
)


def _resolve_empresa_id_for_core_upload(request):
    user = request.user
    if not user.is_authenticated:
        raise PermissionDenied("Debe iniciar sesión.")
    if user.is_superuser:
        raw = request.query_params.get("empresa")
        if raw is None and hasattr(request, "data"):
            raw = request.data.get("empresa")
        if raw is None or str(raw).strip() == "":
            raise ValidationError(
                {
                    "empresa": "Como administrador global, indique la empresa (campo empresa o ?empresa=id)."
                }
            )
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ValidationError({"empresa": "Identificador de empresa inválido."}) from None
    perfil = getattr(user, "perfil_gestor", None)
    if perfil is None:
        raise PermissionDenied(
            "Usuario sin empresa asignada. Contacte al administrador de la plataforma."
        )
    return int(perfil.empresa_id)


class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    search_fields = ["razon_social", "ruc"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs
        if user.is_superuser:
            return qs
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            return qs.none()
        return qs.filter(pk=perfil.empresa_id)

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            serializer.save()
            return
        if not user.is_superuser:
            raise PermissionDenied(
                "Solo el superusuario de la plataforma puede registrar nuevas empresas."
            )
        serializer.save(registro_aprobado=True)

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            serializer.validated_data.pop("registro_aprobado", None)
        if not user.is_authenticated or user.is_superuser:
            serializer.save()
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied("Sin perfil de empresa.")
        if serializer.instance.pk != perfil.empresa_id:
            raise PermissionDenied("No puede modificar otra empresa.")
        serializer.save()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        prev_aprobado = instance.registro_aprobado
        prev_activo = instance.activo
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        empresa = serializer.instance
        if request.user.is_authenticated and request.user.is_superuser:
            if (
                prev_aprobado is False
                and empresa.registro_aprobado is True
                and empresa.fecha_registro_aprobado is None
            ):
                empresa.fecha_registro_aprobado = timezone.now()
                empresa.save(update_fields=["fecha_registro_aprobado"])
            dispatch_empresa_cambio_estado(empresa, prev_aprobado, prev_activo)
        return Response(serializer.data)


class NotificacionUsuarioViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificacionUsuarioSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return NotificacionUsuario.objects.filter(user=self.request.user).order_by("-creado_en")

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        n = self.get_queryset().filter(leida=False).count()
        return Response({"no_leidas": n})

    @action(detail=False, methods=["post"])
    def marcar_todas_leidas(self, request):
        updated = self.get_queryset().filter(leida=False).update(leida=True)
        return Response({"actualizadas": updated})


class SucursalViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Sucursal.objects.select_related("empresa")
    serializer_class = SucursalSerializer
    search_fields = ["nombre"]


class ClienteViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Cliente.objects.select_related("empresa")
    serializer_class = ClienteSerializer
    search_fields = ["razon_social", "documento", "email", "telefono"]
    ordering = ["razon_social"]

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            raw = self.request.data.get("empresa")
            if raw is not None and str(raw).strip() != "":
                serializer.save(empresa_id=int(raw))
                return
        super().perform_create(serializer)

    @action(detail=False, methods=["get"], url_path="plantilla-excel")
    def plantilla_excel(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied()
        data = build_clientes_template_xlsx()
        resp = HttpResponse(
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        resp["Content-Disposition"] = 'attachment; filename="plantilla_clientes.xlsx"'
        return resp

    @action(detail=False, methods=["post"], url_path="importar-excel")
    def importar_excel(self, request):
        empresa_id = _resolve_empresa_id_for_core_upload(request)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Adjunte un archivo Excel (.xlsx)."})
        name = (upload.name or "").lower()
        if not name.endswith(".xlsx"):
            raise ValidationError({"file": "Solo se admite formato .xlsx"})
        try:
            body = upload.read()
            resumen = import_clientes_xlsx(body, empresa_id)
        except Exception as e:
            raise ValidationError({"file": f"No se pudo leer el archivo: {e}"}) from e
        return Response(resumen)


class VendedorViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Vendedor.objects.select_related("empresa", "sucursal")
    serializer_class = VendedorSerializer
    search_fields = ["dni", "nombres", "apellido_paterno", "apellido_materno"]
    ordering = ["apellido_paterno", "apellido_materno", "nombres"]

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            raw = self.request.data.get("empresa")
            if raw is not None and str(raw).strip() != "":
                serializer.save(empresa_id=int(raw))
                return
        super().perform_create(serializer)


class ProveedorViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Proveedor.objects.select_related("empresa")
    serializer_class = ProveedorSerializer
    search_fields = ["razon_social", "documento"]
    ordering = ["razon_social"]

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            raw = self.request.data.get("empresa")
            if raw is not None and str(raw).strip() != "":
                serializer.save(empresa_id=int(raw))
                return
        super().perform_create(serializer)

    @action(detail=False, methods=["get"], url_path="plantilla-excel")
    def plantilla_excel(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied()
        data = build_proveedores_template_xlsx()
        resp = HttpResponse(
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        resp["Content-Disposition"] = 'attachment; filename="plantilla_proveedores.xlsx"'
        return resp

    @action(detail=False, methods=["post"], url_path="importar-excel")
    def importar_excel(self, request):
        empresa_id = _resolve_empresa_id_for_core_upload(request)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Adjunte un archivo Excel (.xlsx)."})
        name = (upload.name or "").lower()
        if not name.endswith(".xlsx"):
            raise ValidationError({"file": "Solo se admite formato .xlsx"})
        try:
            body = upload.read()
            resumen = import_proveedores_xlsx(body, empresa_id)
        except Exception as e:
            raise ValidationError({"file": f"No se pudo leer el archivo: {e}"}) from e
        return Response(resumen)


class PerfilUsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PerfilUsuario.objects.select_related("user", "empresa", "sucursal_default")
    serializer_class = PerfilUsuarioSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_empresa(qs, self.request, "empresa_id")
