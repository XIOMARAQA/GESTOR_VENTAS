from rest_framework import serializers

from apps.inventario.models import (
    Almacen,
    Atributo,
    Categoria,
    Item,
    Marca,
    ItemAtributoValor,
    ListaPrecio,
    ListaPrecioItem,
    MovimientoStock,
    MovimientoStockLinea,
    Stock,
    UnidadMedida,
)
from apps.inventario.sunat_tabla6 import CODIGOS_SUNAT_TABLA6


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en", "empresa"]

    def validate_padre(self, value):
        inst = self.instance
        if inst is not None and value is not None and value.pk == inst.pk:
            raise serializers.ValidationError(
                "La categoría no puede ser padre de sí misma."
            )
        return value


class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en", "empresa"]


class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = "__all__"
        # La empresa la fija el servidor (tenant); el cliente no debe enviarla en POST/PATCH.
        read_only_fields = ["id", "creado_en", "actualizado_en", "empresa"]

    def validate_codigo_sunat(self, value):
        v = (value or "").strip().upper()
        if not v:
            return ""
        if v not in CODIGOS_SUNAT_TABLA6:
            raise serializers.ValidationError(
                "Debe ser un código válido de la Tabla 6 SUNAT (unidad de medida)."
            )
        return v


class AtributoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Atributo
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class ItemSerializer(serializers.ModelSerializer):
    unidad_medida_codigo = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en", "empresa"]
        extra_kwargs = {"unidad_medida": {"required": False}}

    def get_unidad_medida_codigo(self, obj):
        um = getattr(obj, "unidad_medida", None)
        return um.codigo if um is not None else ""

    def create(self, validated_data):
        if validated_data.get("unidad_medida") is None:
            emp_id = validated_data.get("empresa_id")
            if emp_id is None:
                emp = validated_data.get("empresa")
                emp_id = getattr(emp, "pk", None) if emp is not None else None
            if emp_id is not None:
                um, _ = UnidadMedida.objects.get_or_create(
                    empresa_id=emp_id,
                    codigo="UND",
                    defaults={
                        "nombre": "Unidad",
                        "codigo_sunat": "",
                        "activo": True,
                    },
                )
                validated_data["unidad_medida"] = um
        return super().create(validated_data)


class ItemAtributoValorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemAtributoValor
        fields = "__all__"


class AlmacenSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)

    class Meta:
        model = Almacen
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "nombre",
            "direccion",
            "es_principal",
            "activo",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en", "sucursal_nombre"]


class StockSerializer(serializers.ModelSerializer):
    item_codigo = serializers.CharField(source="item.codigo", read_only=True)
    item_nombre = serializers.CharField(source="item.nombre", read_only=True)
    almacen_nombre = serializers.CharField(source="almacen.nombre", read_only=True)

    class Meta:
        model = Stock
        fields = [
            "id",
            "item",
            "item_codigo",
            "item_nombre",
            "almacen",
            "almacen_nombre",
            "cantidad",
        ]


class MovimientoStockLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoStockLinea
        fields = ["id", "item", "cantidad"]


class MovimientoStockSerializer(serializers.ModelSerializer):
    lineas = MovimientoStockLineaSerializer(many=True, read_only=True)
    almacen_nombre = serializers.SerializerMethodField()
    tipo_comprobante = serializers.SerializerMethodField()
    producto_nombre = serializers.SerializerMethodField()
    comprobante_serie = serializers.SerializerMethodField()
    comprobante_numero = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoStock
        fields = [
            "id",
            "empresa",
            "almacen",
            "tipo",
            "referencia_tipo",
            "referencia_id",
            "glosa",
            "usuario",
            "creado_en",
            "actualizado_en",
            "lineas",
            "almacen_nombre",
            "producto_nombre",
            "tipo_comprobante",
            "comprobante_serie",
            "comprobante_numero",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en"]

    def get_almacen_nombre(self, obj):
        if getattr(obj, "almacen", None) is not None:
            return (obj.almacen.nombre or "").strip()
        return ""

    def get_producto_nombre(self, obj):
        nombres = []
        seen = set()
        for ln in obj.lineas.all():
            nom = ""
            if getattr(ln, "item", None) is not None:
                nom = (ln.item.nombre or "").strip()
            if nom and nom not in seen:
                seen.add(nom)
                nombres.append(nom)
        if not nombres:
            return ""
        if len(nombres) <= 2:
            return ", ".join(nombres)
        return ", ".join(nombres[:2]) + f" (+{len(nombres) - 2})"

    def get_tipo_comprobante(self, obj):
        rt = (obj.referencia_tipo or "").strip()
        rid = obj.referencia_id
        if not rid:
            return ""
        ctx = self.context
        if rt == "DOCUMENTO_VENTA":
            m = ctx.get("tipo_comp_venta")
            if isinstance(m, dict) and rid in m:
                return m[rid]
            from apps.ventas.models import DocumentoVenta

            doc = DocumentoVenta.objects.filter(pk=rid).only("tipo").first()
            return doc.get_tipo_display() if doc else ""
        if rt == "DOCUMENTO_COMPRA":
            m = ctx.get("tipo_comp_compra")
            if isinstance(m, dict) and rid in m:
                return m[rid]
            from apps.compras.models import DocumentoCompra

            doc = DocumentoCompra.objects.filter(pk=rid).only("tipo").first()
            return doc.get_tipo_display() if doc else ""
        return ""

    def get_comprobante_serie(self, obj):
        rt = (obj.referencia_tipo or "").strip()
        rid = obj.referencia_id
        if not rid:
            return ""
        ctx = self.context
        if rt == "DOCUMENTO_VENTA":
            m = ctx.get("serie_venta")
            if isinstance(m, dict) and rid in m:
                return m[rid]
            from apps.ventas.models import DocumentoVenta

            doc = DocumentoVenta.objects.filter(pk=rid).only("serie").first()
            return (doc.serie or "").strip() if doc else ""
        if rt == "DOCUMENTO_COMPRA":
            m = ctx.get("serie_compra")
            if isinstance(m, dict) and rid in m:
                return m[rid]
            from apps.compras.models import DocumentoCompra

            doc = DocumentoCompra.objects.filter(pk=rid).only("serie").first()
            return (doc.serie or "").strip() if doc else ""
        return ""

    def get_comprobante_numero(self, obj):
        rt = (obj.referencia_tipo or "").strip()
        rid = obj.referencia_id
        if not rid:
            return ""
        ctx = self.context
        if rt == "DOCUMENTO_VENTA":
            m = ctx.get("numero_venta")
            if isinstance(m, dict) and rid in m:
                return m[rid]
            from apps.ventas.models import DocumentoVenta

            doc = DocumentoVenta.objects.filter(pk=rid).only("numero").first()
            return (doc.numero or "").strip() if doc else ""
        if rt == "DOCUMENTO_COMPRA":
            m = ctx.get("numero_compra")
            if isinstance(m, dict) and rid in m:
                return m[rid]
            from apps.compras.models import DocumentoCompra

            doc = DocumentoCompra.objects.filter(pk=rid).only("numero").first()
            return (doc.numero or "").strip() if doc else ""
        return ""


class ListaPrecioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListaPrecio
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class ListaPrecioItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListaPrecioItem
        fields = "__all__"
