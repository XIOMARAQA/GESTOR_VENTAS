from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.core.api_multitenancy import EmpresaQuerysetMixin, EmpresaScopedViewSetMixin
from apps.inventario.models import (
    Almacen,
    Atributo,
    Categoria,
    Item,
    ItemAtributoValor,
    ListaPrecio,
    ListaPrecioItem,
    Marca,
    MovimientoStock,
    Stock,
    UnidadMedida,
)
from apps.inventario.serializers import (
    AlmacenSerializer,
    AtributoSerializer,
    CategoriaSerializer,
    ItemAtributoValorSerializer,
    ItemSerializer,
    ListaPrecioItemSerializer,
    ListaPrecioSerializer,
    MarcaSerializer,
    MovimientoStockSerializer,
    StockSerializer,
    UnidadMedidaSerializer,
)
from apps.inventario.item_excel import build_items_template_xlsx, import_items_xlsx
from apps.inventario.sunat_tabla6 import TABLA6_UNIDADES


def _resolve_empresa_id_for_item_import(request):
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


class CategoriaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Categoria.objects.select_related("empresa", "padre")
    serializer_class = CategoriaSerializer
    search_fields = ["nombre"]
    ordering = ["nombre"]


class MarcaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Marca.objects.select_related("empresa")
    serializer_class = MarcaSerializer
    search_fields = ["nombre"]
    ordering = ["nombre"]


class UnidadMedidaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = UnidadMedida.objects.select_related("empresa")
    serializer_class = UnidadMedidaSerializer
    search_fields = ["codigo", "nombre", "codigo_sunat"]
    ordering = ["codigo", "nombre"]

    @action(detail=False, methods=["get"], url_path="catalogo-sunat")
    def catalogo_sunat(self, request):
        """SUNAT Tabla 6 — única fuente para UI y validación en servidor."""
        return Response(
            [{"codigo": c, "descripcion": d} for c, d in TABLA6_UNIDADES]
        )


class AtributoViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Atributo.objects.select_related("empresa")
    serializer_class = AtributoSerializer
    search_fields = ["nombre"]


class ItemViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Item.objects.select_related(
        "empresa", "categoria", "marca", "unidad_medida"
    )
    serializer_class = ItemSerializer
    search_fields = ["nombre", "codigo"]
    ordering = ["nombre"]

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            raw = self.request.data.get("empresa")
            if raw is not None and str(raw).strip() != "":
                serializer.save(empresa_id=int(raw))
                return
        super().perform_create(serializer)

    @action(
        detail=False,
        methods=["get"],
        url_path="plantilla-excel",
    )
    def plantilla_excel(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied()
        data = build_items_template_xlsx()
        resp = HttpResponse(
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        resp["Content-Disposition"] = (
            'attachment; filename="plantilla_productos_servicios.xlsx"'
        )
        return resp

    @action(
        detail=False,
        methods=["post"],
        url_path="importar-excel",
    )
    def importar_excel(self, request):
        empresa_id = _resolve_empresa_id_for_item_import(request)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Adjunte un archivo Excel (.xlsx)."})
        name = (upload.name or "").lower()
        if not name.endswith(".xlsx"):
            raise ValidationError({"file": "Solo se admite formato .xlsx"})
        try:
            body = upload.read()
            resumen = import_items_xlsx(body, empresa_id)
        except Exception as e:
            raise ValidationError(
                {"file": f"No se pudo leer el archivo: {e}"}
            ) from e
        return Response(resumen)


class ItemAtributoValorViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    queryset = ItemAtributoValor.objects.select_related("item", "atributo")
    serializer_class = ItemAtributoValorSerializer
    empresa_lookup = "item__empresa_id"

    def perform_create(self, serializer):
        self._assert_item_tenant(serializer.validated_data["item"])
        serializer.save()

    def perform_update(self, serializer):
        item = serializer.validated_data.get("item")
        if item is None and serializer.instance:
            item = serializer.instance.item
        self._assert_item_tenant(item)
        serializer.save()

    def _assert_item_tenant(self, item):
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied("Usuario sin empresa asignada.")
        if item is not None and item.empresa_id != perfil.empresa_id:
            raise PermissionDenied("El ítem no pertenece a su empresa.")


class AlmacenViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    queryset = Almacen.objects.select_related("sucursal", "sucursal__empresa")
    serializer_class = AlmacenSerializer
    search_fields = ["nombre"]
    empresa_lookup = "sucursal__empresa_id"

    def get_queryset(self):
        qs = super().get_queryset()
        raw = (self.request.query_params.get("activo") or "").strip().lower()
        if raw in ("1", "true", "yes", "si"):
            qs = qs.filter(activo=True)
        return qs

    def perform_create(self, serializer):
        self._assert_sucursal_tenant(serializer.validated_data.get("sucursal"))
        serializer.save()

    def perform_update(self, serializer):
        suc = serializer.validated_data.get("sucursal")
        if suc is not None:
            self._assert_sucursal_tenant(suc)
        serializer.save()

    def _assert_sucursal_tenant(self, sucursal):
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied("Usuario sin empresa asignada.")
        if sucursal is not None and sucursal.empresa_id != perfil.empresa_id:
            raise PermissionDenied("La sucursal no pertenece a su empresa.")


class StockViewSet(EmpresaQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Stock.objects.select_related("item", "almacen")
    serializer_class = StockSerializer
    empresa_lookup = "item__empresa_id"


class MovimientoStockViewSet(EmpresaQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = MovimientoStock.objects.select_related(
        "empresa", "almacen", "usuario"
    ).prefetch_related("lineas")
    serializer_class = MovimientoStockSerializer


class ListaPrecioViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ListaPrecio.objects.select_related("empresa")
    serializer_class = ListaPrecioSerializer


class ListaPrecioItemViewSet(EmpresaQuerysetMixin, viewsets.ModelViewSet):
    queryset = ListaPrecioItem.objects.select_related("lista", "item")
    serializer_class = ListaPrecioItemSerializer
    empresa_lookup = "lista__empresa_id"

    def perform_create(self, serializer):
        self._assert_lista_item_tenant(
            serializer.validated_data["lista"],
            serializer.validated_data["item"],
        )
        serializer.save()

    def perform_update(self, serializer):
        lista = serializer.validated_data.get("lista")
        item = serializer.validated_data.get("item")
        inst = serializer.instance
        if lista is None and inst:
            lista = inst.lista
        if item is None and inst:
            item = inst.item
        if lista is not None and item is not None:
            self._assert_lista_item_tenant(lista, item)
        serializer.save()

    def _assert_lista_item_tenant(self, lista, item):
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied("Usuario sin empresa asignada.")
        if lista.empresa_id != perfil.empresa_id or item.empresa_id != perfil.empresa_id:
            raise PermissionDenied("Lista o ítem no pertenecen a su empresa.")
