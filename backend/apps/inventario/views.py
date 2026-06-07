import datetime as dt
from decimal import Decimal

from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.core.api_multitenancy import (
    EmpresaQuerysetMixin,
    EmpresaScopedViewSetMixin,
    empresa_scope_for_request,
)
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
    MovimientoStockLinea,
    Stock,
    TipoMovimientoStock,
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
from apps.inventario.categoria_excel import (
    build_categorias_template_xlsx,
    import_categorias_xlsx,
)
from apps.inventario.item_excel import build_items_template_xlsx, import_items_xlsx
from apps.inventario.marca_excel import build_marcas_template_xlsx, import_marcas_xlsx
from apps.inventario.sunat_tabla6 import TABLA6_UNIDADES
from apps.compras.models import DocumentoCompra
from apps.ventas.models import DocumentoVenta

_KARDEX_MAX_LINEAS = 10_000


def _movimiento_documento_context(movements):
    """Tipo SUNAT / interno, serie y número por documento de venta o compra referenciado."""
    ids_venta = [
        m.referencia_id
        for m in movements
        if (m.referencia_tipo or "").strip() == "DOCUMENTO_VENTA" and m.referencia_id
    ]
    ids_compra = [
        m.referencia_id
        for m in movements
        if (m.referencia_tipo or "").strip() == "DOCUMENTO_COMPRA" and m.referencia_id
    ]
    tipo_comp_venta = {}
    serie_venta = {}
    numero_venta = {}
    if ids_venta:
        for d in DocumentoVenta.objects.filter(pk__in=set(ids_venta)).only(
            "id", "tipo", "serie", "numero"
        ):
            tipo_comp_venta[d.pk] = d.get_tipo_display()
            serie_venta[d.pk] = (d.serie or "").strip()
            numero_venta[d.pk] = (d.numero or "").strip()
    tipo_comp_compra = {}
    serie_compra = {}
    numero_compra = {}
    if ids_compra:
        for d in DocumentoCompra.objects.filter(pk__in=set(ids_compra)).only(
            "id", "tipo", "serie", "numero"
        ):
            tipo_comp_compra[d.pk] = d.get_tipo_display()
            serie_compra[d.pk] = (d.serie or "").strip()
            numero_compra[d.pk] = (d.numero or "").strip()
    return {
        "tipo_comp_venta": tipo_comp_venta,
        "tipo_comp_compra": tipo_comp_compra,
        "serie_venta": serie_venta,
        "numero_venta": numero_venta,
        "serie_compra": serie_compra,
        "numero_compra": numero_compra,
    }


def _resolve_empresa_id_for_inventario_upload(request):
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

    @action(detail=False, methods=["get"], url_path="plantilla-excel")
    def plantilla_excel(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied()
        data = build_categorias_template_xlsx()
        resp = HttpResponse(
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        resp["Content-Disposition"] = (
            'attachment; filename="plantilla_categorias_producto.xlsx"'
        )
        return resp

    @action(detail=False, methods=["post"], url_path="importar-excel")
    def importar_excel(self, request):
        empresa_id = _resolve_empresa_id_for_inventario_upload(request)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Adjunte un archivo Excel (.xlsx)."})
        name = (upload.name or "").lower()
        if not name.endswith(".xlsx"):
            raise ValidationError({"file": "Solo se admite formato .xlsx"})
        try:
            body = upload.read()
            resumen = import_categorias_xlsx(body, empresa_id)
        except Exception as e:
            raise ValidationError({"file": f"No se pudo leer el archivo: {e}"}) from e
        return Response(resumen)


class MarcaViewSet(EmpresaScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Marca.objects.select_related("empresa")
    serializer_class = MarcaSerializer
    search_fields = ["nombre"]
    ordering = ["nombre"]

    @action(detail=False, methods=["get"], url_path="plantilla-excel")
    def plantilla_excel(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied()
        data = build_marcas_template_xlsx()
        resp = HttpResponse(
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        resp["Content-Disposition"] = 'attachment; filename="plantilla_marcas.xlsx"'
        return resp

    @action(detail=False, methods=["post"], url_path="importar-excel")
    def importar_excel(self, request):
        empresa_id = _resolve_empresa_id_for_inventario_upload(request)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Adjunte un archivo Excel (.xlsx)."})
        name = (upload.name or "").lower()
        if not name.endswith(".xlsx"):
            raise ValidationError({"file": "Solo se admite formato .xlsx"})
        try:
            body = upload.read()
            resumen = import_marcas_xlsx(body, empresa_id)
        except Exception as e:
            raise ValidationError({"file": f"No se pudo leer el archivo: {e}"}) from e
        return Response(resumen)


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

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            raw = self.request.query_params.get("empresa")
            if raw not in (None, ""):
                try:
                    qs = qs.filter(empresa_id=int(raw))
                except (TypeError, ValueError):
                    pass
        return qs

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
        empresa_id = _resolve_empresa_id_for_inventario_upload(request)
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
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            empresa_q = self.request.query_params.get("empresa")
            if empresa_q not in (None, ""):
                try:
                    qs = qs.filter(sucursal__empresa_id=int(empresa_q))
                except (TypeError, ValueError):
                    pass
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

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("item", "almacen")
            .order_by("almacen__nombre", "item__codigo", "item__nombre")
        )
        p = self.request.query_params
        codigo = (p.get("codigo") or "").strip()
        if codigo:
            qs = qs.filter(item__codigo__icontains=codigo)
        nombre = (p.get("nombre_producto") or p.get("nombre") or "").strip()
        if nombre:
            qs = qs.filter(item__nombre__icontains=nombre)
        almacen = p.get("almacen")
        if almacen not in (None, ""):
            try:
                qs = qs.filter(almacen_id=int(almacen))
            except (TypeError, ValueError):
                pass
        producto = p.get("producto") or p.get("item")
        if producto not in (None, ""):
            try:
                qs = qs.filter(item_id=int(producto))
            except (TypeError, ValueError):
                pass
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            empresa_q = p.get("empresa")
            if empresa_q not in (None, ""):
                try:
                    qs = qs.filter(item__empresa_id=int(empresa_q))
                except (TypeError, ValueError):
                    pass
        return qs


def _tipo_comprobante_movimiento(mov, ctx_doc):
    rt = (mov.referencia_tipo or "").strip()
    rid = mov.referencia_id
    if not rid:
        return ""
    if rt == "DOCUMENTO_VENTA":
        return ctx_doc["tipo_comp_venta"].get(rid, "")
    if rt == "DOCUMENTO_COMPRA":
        return ctx_doc["tipo_comp_compra"].get(rid, "")
    return ""


def _comprobante_serie_movimiento(mov, ctx_doc):
    rt = (mov.referencia_tipo or "").strip()
    rid = mov.referencia_id
    if not rid:
        return ""
    if rt == "DOCUMENTO_VENTA":
        return ctx_doc["serie_venta"].get(rid, "")
    if rt == "DOCUMENTO_COMPRA":
        return ctx_doc["serie_compra"].get(rid, "")
    return ""


def _comprobante_numero_movimiento(mov, ctx_doc):
    rt = (mov.referencia_tipo or "").strip()
    rid = mov.referencia_id
    if not rid:
        return ""
    if rt == "DOCUMENTO_VENTA":
        return ctx_doc["numero_venta"].get(rid, "")
    if rt == "DOCUMENTO_COMPRA":
        return ctx_doc["numero_compra"].get(rid, "")
    return ""


def _kardex_entradas_salidas(mov, cant):
    if mov.tipo == TipoMovimientoStock.INGRESO:
        return cant, Decimal("0")
    if mov.tipo == TipoMovimientoStock.SALIDA:
        return Decimal("0"), cant
    return Decimal("0"), Decimal("0")


def _kardex_saldo_neto_lineas(line_iter):
    total = Decimal("0")
    for ln in line_iter:
        e, s = _kardex_entradas_salidas(ln.movimiento, ln.cantidad)
        total += e - s
    return total


def _kardex_parse_mes(mes_raw):
    if mes_raw is None:
        return None
    s = str(mes_raw).strip()
    if not s:
        return None
    parts = s.split("-")
    if len(parts) != 2:
        raise ValidationError({"detail": "Use mes=YYYY-MM (por ejemplo 2026-04)."})
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError as exc:
        raise ValidationError({"detail": "mes debe ser numérico (YYYY-MM)."}) from exc
    if month < 1 or month > 12:
        raise ValidationError({"detail": "El mes debe estar entre 01 y 12."})
    return year, month


def _kardex_month_bounds(year, month):
    tz = timezone.get_current_timezone()
    start_local = dt.datetime(year, month, 1, 0, 0, 0)
    start = timezone.make_aware(start_local, tz)
    if month == 12:
        end_local = dt.datetime(year + 1, 1, 1, 0, 0, 0)
    else:
        end_local = dt.datetime(year, month + 1, 1, 0, 0, 0)
    end = timezone.make_aware(end_local, tz)
    return start, end


class MovimientoStockViewSet(EmpresaQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = MovimientoStock.objects.select_related(
        "empresa", "almacen", "usuario"
    ).prefetch_related(
        Prefetch(
            "lineas",
            queryset=MovimientoStockLinea.objects.select_related("item"),
        )
    )
    serializer_class = MovimientoStockSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by("-creado_en")
        p = self.request.query_params
        almacen = p.get("almacen")
        if almacen not in (None, ""):
            try:
                qs = qs.filter(almacen_id=int(almacen))
            except (TypeError, ValueError):
                pass
        producto = p.get("producto") or p.get("item")
        if producto not in (None, ""):
            try:
                qs = qs.filter(lineas__item_id=int(producto)).distinct()
            except (TypeError, ValueError):
                pass
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            empresa_q = p.get("empresa")
            if empresa_q not in (None, ""):
                try:
                    qs = qs.filter(empresa_id=int(empresa_q))
                except (TypeError, ValueError):
                    pass
        return qs

    @action(detail=False, methods=["get"], url_path="kardex")
    def kardex(self, request):
        """
        Kardex por **producto** y **almacén**: entradas, salidas y saldo acumulado.

        - Obligatorios: ``item`` (o ``producto``) y ``almacen``.
        - Opcional: ``mes=YYYY-MM`` — solo movimientos de ese mes; ``saldo_inicial`` es el
          existente al **inicio del mes** (cierre contable del mes anterior). ``saldo_cierre``
          es el saldo al **fin del período listado** (sin movimientos en el mes, coincide con
          el inicial; con movimientos, es el saldo tras el último del mes) y sirve como
          **apertura del siguiente corte** mensual.
        - La respuesta incluye una **primera fila** de apertura (``tipo``: ``SALDO_INICIAL``) con
          el saldo inicial; a continuación, movimientos del **más antiguo al más reciente**; en
          cada fila el ``saldo`` es el acumulado **tras** ese movimiento (o el inicial en la fila de apertura).
        """
        p = request.query_params
        item_raw = p.get("item") or p.get("producto")
        almacen_raw = p.get("almacen")
        mes_raw = p.get("mes")

        if item_raw in (None, "") or str(item_raw).strip() == "":
            raise ValidationError(
                {"detail": "Indique el producto (parámetro item o producto)."}
            )
        if almacen_raw in (None, "") or str(almacen_raw).strip() == "":
            raise ValidationError({"detail": "Indique el almacén."})
        try:
            item_id = int(item_raw)
            almacen_id = int(almacen_raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"detail": "Producto y almacén deben ser identificadores numéricos."}
            ) from exc

        mes_bounds = None
        mes_etiqueta = None
        if mes_raw not in (None, "") and str(mes_raw).strip():
            y, m = _kardex_parse_mes(mes_raw)
            mes_bounds = _kardex_month_bounds(y, m)
            mes_etiqueta = f"{y:04d}-{m:02d}"

        user = request.user
        scope = empresa_scope_for_request(request)
        if scope == -1:
            return Response(
                {
                    "count": 0,
                    "truncado": False,
                    "results": [],
                    "item": None,
                    "almacen": None,
                    "mes": None,
                    "saldo_inicial": Decimal("0"),
                    "saldo_cierre": Decimal("0"),
                }
            )

        item = (
            Item.objects.filter(pk=item_id)
            .only("id", "codigo", "nombre", "empresa_id")
            .first()
        )
        if item is None:
            raise ValidationError({"detail": "El producto indicado no existe."})
        alm = (
            Almacen.objects.filter(pk=almacen_id)
            .select_related("sucursal")
            .only("id", "nombre", "sucursal_id", "sucursal__empresa_id")
            .first()
        )
        if alm is None:
            raise ValidationError({"detail": "El almacén indicado no existe."})

        if item.empresa_id != alm.sucursal.empresa_id:
            raise ValidationError(
                {"detail": "El producto y el almacén deben pertenecer a la misma empresa."}
            )

        if scope is not None:
            if item.empresa_id != scope:
                raise PermissionDenied("El producto no pertenece a su empresa.")
            if alm.sucursal.empresa_id != scope:
                raise PermissionDenied("El almacén no pertenece a su empresa.")

        base = MovimientoStockLinea.objects.filter(
            item_id=item_id, movimiento__almacen_id=almacen_id
        ).select_related("item", "movimiento", "movimiento__almacen")
        if scope is not None:
            base = base.filter(movimiento__empresa_id=scope)
        if user.is_authenticated and user.is_superuser:
            empresa_q = p.get("empresa")
            if empresa_q not in (None, ""):
                try:
                    eid = int(empresa_q)
                    base = base.filter(movimiento__empresa_id=eid)
                    if item.empresa_id != eid:
                        raise ValidationError(
                            {
                                "detail": "El producto no coincide con la empresa seleccionada en la barra superior."
                            }
                        )
                except (TypeError, ValueError):
                    pass

        opening = Decimal("0")
        if mes_bounds is not None:
            start, _end = mes_bounds
            before_qs = base.filter(movimiento__creado_en__lt=start).order_by(
                "movimiento__creado_en", "movimiento_id", "id"
            )
            opening = _kardex_saldo_neto_lineas(before_qs)

        scoped = base
        if mes_bounds is not None:
            start, end = mes_bounds
            scoped = scoped.filter(
                movimiento__creado_en__gte=start,
                movimiento__creado_en__lt=end,
            )

        ordered = scoped.order_by("movimiento__creado_en", "movimiento_id", "id")
        line_list = list(ordered[: _KARDEX_MAX_LINEAS + 1])
        truncado = len(line_list) > _KARDEX_MAX_LINEAS
        if truncado:
            line_list = line_list[:_KARDEX_MAX_LINEAS]

        if mes_bounds is None and line_list:
            fl = line_list[0]
            t0, m0, l0 = fl.movimiento.creado_en, fl.movimiento_id, fl.id
            before0 = base.filter(
                Q(movimiento__creado_en__lt=t0)
                | Q(movimiento__creado_en=t0, movimiento_id__lt=m0)
                | Q(movimiento__creado_en=t0, movimiento_id=m0, id__lt=l0)
            ).order_by("movimiento__creado_en", "movimiento_id", "id")
            opening = _kardex_saldo_neto_lineas(before0)

        movements = {ln.movimiento for ln in line_list}
        ctx_doc = _movimiento_documento_context(movements)

        if mes_bounds is not None:
            apertura_en = mes_bounds[0]
        elif line_list:
            d0 = line_list[0].movimiento.creado_en.date()
            tz = timezone.get_current_timezone()
            apertura_en = timezone.make_aware(dt.datetime.combine(d0, dt.time.min), tz)
        else:
            apertura_en = None

        alm_nombre = (alm.nombre or "").strip()
        item_cod = (item.codigo or "").strip()
        item_nom = (item.nombre or "").strip()

        fila_apertura = {
            "linea_id": None,
            "movimiento_id": None,
            "tipo": "SALDO_INICIAL",
            "creado_en": apertura_en,
            "referencia_tipo": "",
            "referencia_id": None,
            "tipo_comprobante": "",
            "comprobante_serie": "",
            "comprobante_numero": "",
            "almacen_nombre": alm_nombre,
            "glosa": "Saldo inicial",
            "item_id": item.id,
            "item_codigo": item_cod,
            "item_nombre": item_nom,
            "entradas": Decimal("0"),
            "salidas": Decimal("0"),
            "saldo": opening,
        }

        saldo = opening
        results_mov = []
        for ln in line_list:
            mov = ln.movimiento
            entradas, salidas = _kardex_entradas_salidas(mov, ln.cantidad)
            saldo = saldo + entradas - salidas
            results_mov.append(
                {
                    "linea_id": ln.id,
                    "movimiento_id": mov.id,
                    "tipo": mov.tipo,
                    "creado_en": mov.creado_en,
                    "referencia_tipo": mov.referencia_tipo,
                    "referencia_id": mov.referencia_id,
                    "tipo_comprobante": _tipo_comprobante_movimiento(mov, ctx_doc),
                    "comprobante_serie": _comprobante_serie_movimiento(mov, ctx_doc),
                    "comprobante_numero": _comprobante_numero_movimiento(mov, ctx_doc),
                    "almacen_nombre": (mov.almacen.nombre or "").strip()
                    if getattr(mov, "almacen", None)
                    else "",
                    "glosa": (mov.glosa or "").strip(),
                    "item_id": ln.item_id,
                    "item_codigo": (ln.item.codigo or "").strip(),
                    "item_nombre": (ln.item.nombre or "").strip(),
                    "entradas": entradas,
                    "salidas": salidas,
                    "saldo": saldo,
                }
            )

        results = [fila_apertura, *results_mov]

        if line_list:
            saldo_cierre = saldo
        else:
            saldo_cierre = opening

        return Response(
            {
                "count": len(results),
                "truncado": truncado,
                "results": results,
                "item": {
                    "id": item.id,
                    "codigo": (item.codigo or "").strip(),
                    "nombre": (item.nombre or "").strip(),
                },
                "almacen": {"id": alm.id, "nombre": (alm.nombre or "").strip()},
                "mes": mes_etiqueta,
                "saldo_inicial": opening,
                "saldo_cierre": saldo_cierre,
            }
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        movements = list(page) if page is not None else list(queryset)

        ctx_doc = _movimiento_documento_context(movements)

        serializer = self.get_serializer(
            movements,
            many=True,
            context={**self.get_serializer_context(), **ctx_doc},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


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
