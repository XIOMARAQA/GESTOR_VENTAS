from decimal import Decimal

from rest_framework import serializers

from apps.compras.models import (
    DocumentoCompra,
    DocumentoCompraLinea,
    GastoRecurrente,
    OrdenCompra,
    OrdenCompraLinea,
    TipoDocumentoCompra,
)
from apps.ventas.models import CondicionPagoDocumento


class OrdenCompraLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdenCompraLinea
        fields = ["id", "item", "cantidad", "precio_unit"]
        read_only_fields = ["id"]


class OrdenCompraSerializer(serializers.ModelSerializer):
    lineas = OrdenCompraLineaSerializer(many=True, read_only=True)

    class Meta:
        model = OrdenCompra
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class DocumentoCompraLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentoCompraLinea
        fields = ["id", "item", "cantidad", "precio_unit", "subtotal"]
        read_only_fields = ["id"]


class DocumentoCompraLineaEntradaSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(min_value=1)
    cantidad = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0.0001")
    )
    precio_unit = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0")
    )


class DocumentoCompraAltaBorradorSerializer(serializers.Serializer):
    """
    Alta interna de factura de compra (no SUNAT). Crea documento BORRADOR + líneas y recalcula total.
    """

    empresa_id = serializers.IntegerField(required=False, allow_null=True)
    proveedor_id = serializers.IntegerField(min_value=1)
    tipo = serializers.ChoiceField(
        choices=TipoDocumentoCompra.choices,
        default=TipoDocumentoCompra.FACTURA_COMPRA,
    )
    serie = serializers.CharField(max_length=10, allow_blank=True, required=False, default="")
    numero = serializers.CharField(max_length=20, allow_blank=True, required=False, default="")
    fecha = serializers.DateField()
    lineas = DocumentoCompraLineaEntradaSerializer(many=True)
    condicion_pago = serializers.ChoiceField(
        choices=CondicionPagoDocumento.choices,
        default=CondicionPagoDocumento.CONTADO,
    )
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)
    precio_incluye_igv = serializers.BooleanField(required=False, default=False)
    afecta_stock = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if attrs.get("condicion_pago") == CondicionPagoDocumento.CREDITO:
            if not attrs.get("fecha_vencimiento"):
                raise serializers.ValidationError(
                    {"fecha_vencimiento": "Obligatoria en compra a crédito (tesorería)."}
                )
        fv = attrs.get("fecha_vencimiento")
        fecha_doc = attrs.get("fecha")
        if fv and fecha_doc and fv < fecha_doc:
            raise serializers.ValidationError(
                {"fecha_vencimiento": "No puede ser anterior a la fecha del documento."}
            )
        return attrs


class DocumentoCompraSerializer(serializers.ModelSerializer):
    lineas = DocumentoCompraLineaSerializer(many=True, read_only=True)
    proveedor_razon_social = serializers.SerializerMethodField()
    serie_numero = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoCompra
        fields = [
            "id",
            "empresa",
            "tipo",
            "proveedor",
            "serie",
            "numero",
            "fecha",
            "estado",
            "subtotal",
            "igv",
            "total",
            "precio_incluye_igv",
            "afecta_stock",
            "condicion_pago",
            "fecha_vencimiento",
            "es_electronica",
            "hash_xml",
            "ruta_archivo",
            "creado_en",
            "actualizado_en",
            "lineas",
            "proveedor_razon_social",
            "serie_numero",
        ]
        read_only_fields = [
            "id",
            "creado_en",
            "actualizado_en",
            "subtotal",
            "igv",
            "total",
            "precio_incluye_igv",
            "afecta_stock",
            "lineas",
            "proveedor_razon_social",
            "serie_numero",
        ]

    def get_proveedor_razon_social(self, obj):
        if obj.proveedor_id and getattr(obj, "proveedor", None):
            return (obj.proveedor.razon_social or "").strip() or None
        return None

    def get_serie_numero(self, obj):
        s = (obj.serie or "").strip()
        n = (obj.numero or "").strip()
        if s and n:
            return f"{s}-{n}"
        if s:
            return s
        if n:
            return n
        return ""


class GastoRecurrenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GastoRecurrente
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]
