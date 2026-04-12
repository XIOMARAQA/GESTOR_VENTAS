from decimal import Decimal

from rest_framework import serializers

from apps.ventas.models import (
    CondicionPagoDocumento,
    Cotizacion,
    CotizacionLinea,
    DocumentoVenta,
    DocumentoVentaLinea,
    EstadoDocumento,
    MedioPagoDocumento,
    MonedaDocumento,
    Pedido,
    PedidoLinea,
    TipoOperacionSunat,
)


class CotizacionLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CotizacionLinea
        fields = ["id", "item", "cantidad", "precio_unit", "subtotal"]
        read_only_fields = ["id"]


class CotizacionSerializer(serializers.ModelSerializer):
    lineas = CotizacionLineaSerializer(many=True, read_only=True)
    cliente_documento = serializers.SerializerMethodField()
    cliente_razon_social = serializers.SerializerMethodField()
    vendedor_nombre = serializers.SerializerMethodField()
    serie_numero = serializers.SerializerMethodField()
    documento_convertido_id = serializers.SerializerMethodField()
    puede_editar_eliminar = serializers.SerializerMethodField()

    class Meta:
        model = Cotizacion
        fields = [
            "id",
            "empresa",
            "sucursal",
            "cliente",
            "serie",
            "numero",
            "correlativo",
            "fecha",
            "estado",
            "subtotal",
            "igv",
            "total",
            "observacion",
            "moneda",
            "precio_incluye_igv",
            "condicion_pago",
            "fecha_vencimiento",
            "medio_pago",
            "tipo_operacion",
            "vendedor",
            "creado_en",
            "actualizado_en",
            "lineas",
            "cliente_documento",
            "cliente_razon_social",
            "vendedor_nombre",
            "serie_numero",
            "documento_convertido_id",
            "puede_editar_eliminar",
        ]
        read_only_fields = [
            "id",
            "creado_en",
            "actualizado_en",
            "subtotal",
            "igv",
            "total",
            "serie",
            "numero",
            "correlativo",
        ]

    def get_cliente_documento(self, obj):
        if obj.cliente_id and obj.cliente:
            return (obj.cliente.documento or "").strip() or None
        return None

    def get_cliente_razon_social(self, obj):
        if obj.cliente_id and obj.cliente:
            return (obj.cliente.razon_social or "").strip() or None
        return None

    def get_vendedor_nombre(self, obj):
        if obj.vendedor_id and obj.vendedor:
            return obj.vendedor.nombre_completo()
        return None

    def get_serie_numero(self, obj):
        if obj.serie and (obj.numero or obj.correlativo is not None):
            n = obj.numero or (str(obj.correlativo).zfill(4) if obj.correlativo else "")
            if n:
                return f"{obj.serie}-{n}"
        return ""

    def get_documento_convertido_id(self, obj):
        return (
            DocumentoVenta.objects.filter(cotizacion_origen_id=obj.pk)
            .values_list("id", flat=True)
            .first()
        )

    def get_puede_editar_eliminar(self, obj):
        """
        False si existe comprobante vinculado ya emitido (no BORRADOR).
        Así el front desactiva editar/eliminar y se evitan inconsistencias con SUNAT.
        """
        doc = (
            DocumentoVenta.objects.filter(cotizacion_origen_id=obj.pk)
            .only("estado")
            .first()
        )
        if doc is None:
            return True
        return doc.estado == EstadoDocumento.BORRADOR


class DocumentoVentaLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentoVentaLinea
        fields = ["id", "item", "cantidad", "precio_unit", "subtotal"]


class DocumentoVentaSerializer(serializers.ModelSerializer):
    lineas = DocumentoVentaLineaSerializer(many=True, read_only=True)
    cliente_razon_social = serializers.SerializerMethodField()
    cliente_documento = serializers.SerializerMethodField()
    vendedor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoVenta
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]

    def get_cliente_razon_social(self, obj):
        if obj.cliente_id and obj.cliente:
            return (obj.cliente.razon_social or "").strip() or None
        return None

    def get_cliente_documento(self, obj):
        if obj.cliente_id and obj.cliente:
            return (obj.cliente.documento or "").strip() or None
        return None

    def get_vendedor_nombre(self, obj):
        if obj.vendedor_id and obj.vendedor:
            return obj.vendedor.nombre_completo()
        return None


class DocumentoVentaLineaWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentoVentaLinea
        fields = ["item", "cantidad", "precio_unit", "subtotal"]


class PedidoLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoLinea
        fields = ["id", "item", "cantidad", "precio_unit"]
        read_only_fields = ["id"]


class PedidoSerializer(serializers.ModelSerializer):
    lineas = PedidoLineaSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class ComprobanteLineaBorradorSerializer(serializers.Serializer):
    """Línea según `documento_venta_linea`: item, cantidad, precio_unit (valor unitario sin IGV), subtotal calculado."""

    item_id = serializers.IntegerField(min_value=1)
    cantidad = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0.0001")
    )
    precio_unit = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0")
    )


class ComprobanteAltaBorradorSerializer(serializers.Serializer):
    """
    Alta de `documento_venta` en BORRADOR + líneas, alineado al esquema de negocio.
    Totales: subtotal/igv/total vía DocumentoVentaService.recalcular_totales.
    """

    empresa_id = serializers.IntegerField(required=False, min_value=1)
    sucursal_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    tipo = serializers.ChoiceField(choices=["FACTURA", "BOLETA"])
    serie = serializers.CharField(max_length=10, allow_blank=True, required=False, default="")
    fecha_emision = serializers.DateField()
    observacion = serializers.CharField(allow_blank=True, required=False, default="")
    cliente_documento = serializers.CharField(max_length=20)
    cliente_razon_social = serializers.CharField(max_length=255)
    cliente_email = serializers.EmailField(allow_blank=True, required=False, default="")
    cliente_direccion = serializers.CharField(allow_blank=True, required=False, default="")
    lineas = ComprobanteLineaBorradorSerializer(many=True)
    precio_incluye_igv = serializers.BooleanField(required=False, default=False)
    moneda = serializers.ChoiceField(choices=MonedaDocumento.choices, default=MonedaDocumento.PEN)
    condicion_pago = serializers.ChoiceField(
        choices=CondicionPagoDocumento.choices, default=CondicionPagoDocumento.CONTADO
    )
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True, default=None)
    medio_pago = serializers.CharField(max_length=24, required=False, allow_blank=True, default="")
    tipo_operacion = serializers.ChoiceField(
        choices=TipoOperacionSunat.choices, default=TipoOperacionSunat.VENTA_INTERNA
    )
    vendedor_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs):
        cond = attrs.get("condicion_pago") or CondicionPagoDocumento.CONTADO
        if cond == CondicionPagoDocumento.CREDITO:
            if not attrs.get("fecha_vencimiento"):
                raise serializers.ValidationError(
                    {"fecha_vencimiento": "Indique la fecha de vencimiento en venta a crédito."}
                )
            attrs["medio_pago"] = ""
        else:
            mp = (attrs.get("medio_pago") or "").strip()
            if not mp:
                raise serializers.ValidationError(
                    {"medio_pago": "Seleccione el medio de pago (venta al contado)."}
                )
            valid_mp = {c[0] for c in MedioPagoDocumento.choices}
            if mp not in valid_mp:
                raise serializers.ValidationError({"medio_pago": "Medio de pago no válido."})
            attrs["medio_pago"] = mp
            attrs["fecha_vencimiento"] = None
        return attrs

    def validate_lineas(self, value):
        if not value:
            raise serializers.ValidationError("Agregue al menos una línea de producto/servicio.")
        return value


class CotizacionAltaBorradorSerializer(serializers.Serializer):
    """Misma cabecera y líneas que un comprobante en borrador; sin tipo ni serie SUNAT (interno)."""

    empresa_id = serializers.IntegerField(required=False, min_value=1)
    sucursal_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    fecha_emision = serializers.DateField()
    observacion = serializers.CharField(allow_blank=True, required=False, default="")
    cliente_documento = serializers.CharField(max_length=20)
    cliente_razon_social = serializers.CharField(max_length=255)
    cliente_email = serializers.EmailField(allow_blank=True, required=False, default="")
    cliente_direccion = serializers.CharField(allow_blank=True, required=False, default="")
    lineas = ComprobanteLineaBorradorSerializer(many=True)
    precio_incluye_igv = serializers.BooleanField(required=False, default=False)
    moneda = serializers.ChoiceField(choices=MonedaDocumento.choices, default=MonedaDocumento.PEN)
    condicion_pago = serializers.ChoiceField(
        choices=CondicionPagoDocumento.choices, default=CondicionPagoDocumento.CONTADO
    )
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True, default=None)
    medio_pago = serializers.CharField(max_length=24, required=False, allow_blank=True, default="")
    tipo_operacion = serializers.ChoiceField(
        choices=TipoOperacionSunat.choices, default=TipoOperacionSunat.VENTA_INTERNA
    )
    vendedor_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs):
        cond = attrs.get("condicion_pago") or CondicionPagoDocumento.CONTADO
        if cond == CondicionPagoDocumento.CREDITO:
            if not attrs.get("fecha_vencimiento"):
                raise serializers.ValidationError(
                    {"fecha_vencimiento": "Indique la fecha de vencimiento en venta a crédito."}
                )
            attrs["medio_pago"] = ""
        else:
            mp = (attrs.get("medio_pago") or "").strip()
            if not mp:
                raise serializers.ValidationError(
                    {"medio_pago": "Seleccione el medio de pago (venta al contado)."}
                )
            valid_mp = {c[0] for c in MedioPagoDocumento.choices}
            if mp not in valid_mp:
                raise serializers.ValidationError({"medio_pago": "Medio de pago no válido."})
            attrs["medio_pago"] = mp
            attrs["fecha_vencimiento"] = None
        return attrs

    def validate_lineas(self, value):
        if not value:
            raise serializers.ValidationError("Agregue al menos una línea de producto/servicio.")
        return value


class CotizacionConvertirComprobanteSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=["FACTURA", "BOLETA"])
    serie = serializers.CharField(max_length=10)
    fecha_emision = serializers.DateField(required=False, allow_null=True)

    def validate_serie(self, v):
        s = (v or "").strip()
        if not s:
            raise serializers.ValidationError("Indique la serie del comprobante (SUNAT/Nubefact).")
        return s[:10]


class EmitirNubefactSerializer(serializers.Serializer):
    """Emisión vía Nubefact (documento en borrador).

    Por defecto usa `NUBEFACT_API_URL` y `NUBEFACT_TOKEN` del servidor.
    Opcionalmente se puede enviar `api_url` y `token` en el cuerpo (override).
    Con `entorno_prueba=true` y `NUBEFACT_PRUEBA_API_URL` configurada, usa esa URL.
    """

    documento_id = serializers.IntegerField(min_value=1)
    api_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="Opcional si están definidos NUBEFACT_API_URL / NUBEFACT_TOKEN en el servidor.",
    )
    token = serializers.CharField(
        max_length=512,
        allow_blank=True,
        required=False,
        default="",
        trim_whitespace=True,
    )
    entorno_prueba = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        from django.conf import settings as dj_settings

        prueba = attrs.get("entorno_prueba") or False
        url_in = (attrs.get("api_url") or "").strip()
        token_in = (attrs.get("token") or "").strip()

        prueba_url = (getattr(dj_settings, "NUBEFACT_PRUEBA_API_URL", "") or "").strip()
        default_url = (getattr(dj_settings, "NUBEFACT_API_URL", "") or "").strip()
        default_token = (getattr(dj_settings, "NUBEFACT_TOKEN", "") or "").strip()

        if prueba and prueba_url:
            attrs["api_url"] = prueba_url
            attrs["token"] = token_in or default_token
            if not attrs["token"]:
                raise serializers.ValidationError(
                    {"token": "Indique token o configure NUBEFACT_TOKEN en el servidor."}
                )
            return attrs

        if url_in and token_in:
            attrs["api_url"] = url_in
            attrs["token"] = token_in
            return attrs

        if default_url and default_token:
            attrs["api_url"] = default_url
            attrs["token"] = default_token
            return attrs

        raise serializers.ValidationError(
            {
                "detail": "Configure NUBEFACT_API_URL y NUBEFACT_TOKEN en el servidor "
                "(archivo .env), o envíe api_url y token en el cuerpo de la petición."
            }
        )
