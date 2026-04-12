from decimal import Decimal

from rest_framework import serializers

from apps.tesoreria.models import (
    Caja,
    Cobranza,
    ConciliacionBancaria,
    CronogramaPago,
    CuentaBancaria,
    EstadoCronogramaPago,
    PagoRealizadoProveedor,
    PagoRecibido,
)


class CuentaBancariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuentaBancaria
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class CajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caja
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class CobranzaSerializer(serializers.ModelSerializer):
    documento_serie_numero = serializers.SerializerMethodField()
    cliente_razon_social = serializers.SerializerMethodField()
    monto_pendiente = serializers.SerializerMethodField()
    condicion_pago_documento = serializers.SerializerMethodField()

    class Meta:
        model = Cobranza
        fields = [
            "id",
            "empresa",
            "documento_venta",
            "monto_total",
            "monto_pagado",
            "fecha_vencimiento",
            "estado",
            "creado_en",
            "actualizado_en",
            "documento_serie_numero",
            "cliente_razon_social",
            "monto_pendiente",
            "condicion_pago_documento",
        ]
        read_only_fields = fields

    def get_documento_serie_numero(self, obj):
        d = obj.documento_venta
        s = (d.serie or "").strip()
        n = (d.numero or "").strip()
        if s and n:
            return f"{s}-{n}"
        if s or n:
            return s or n
        return f"#{d.id}"

    def get_cliente_razon_social(self, obj):
        c = obj.documento_venta.cliente
        if c is None:
            return None
        return (c.razon_social or c.documento or "").strip() or None

    def get_monto_pendiente(self, obj):
        pendiente = obj.monto_total - obj.monto_pagado
        if pendiente < 0:
            pendiente = Decimal("0")
        return str(pendiente.quantize(Decimal("0.01")))

    def get_condicion_pago_documento(self, obj):
        return obj.documento_venta.condicion_pago


class PagoRecibidoSerializer(serializers.ModelSerializer):
    """Incluye datos del comprobante vía cobranza para listados legibles y enlaces en UI."""

    documento_venta_id = serializers.SerializerMethodField()
    documento_serie_numero = serializers.SerializerMethodField()
    cliente_razon_social = serializers.SerializerMethodField()
    tipo_documento = serializers.SerializerMethodField()

    class Meta:
        model = PagoRecibido
        fields = [
            "id",
            "empresa",
            "cobranza",
            "monto",
            "metodo",
            "cuenta_bancaria",
            "caja",
            "usuario",
            "creado_en",
            "actualizado_en",
            "documento_venta_id",
            "documento_serie_numero",
            "cliente_razon_social",
            "tipo_documento",
        ]
        read_only_fields = fields

    def get_documento_venta_id(self, obj):
        if obj.cobranza_id:
            return obj.cobranza.documento_venta_id
        return None

    def _doc_venta(self, obj):
        if not obj.cobranza_id:
            return None
        return obj.cobranza.documento_venta

    def get_documento_serie_numero(self, obj):
        d = self._doc_venta(obj)
        if d is None:
            return None
        s = (d.serie or "").strip()
        n = (d.numero or "").strip()
        if s and n:
            return f"{s}-{n}"
        if s or n:
            return s or n
        return f"#{d.id}"

    def get_cliente_razon_social(self, obj):
        d = self._doc_venta(obj)
        if d is None:
            return None
        c = d.cliente
        if c is None:
            return None
        return (c.razon_social or c.documento or "").strip() or None

    def get_tipo_documento(self, obj):
        d = self._doc_venta(obj)
        if d is None:
            return None
        return d.tipo


class CronogramaPagoSerializer(serializers.ModelSerializer):
    proveedor_razon_social = serializers.SerializerMethodField()
    proveedor_documento = serializers.SerializerMethodField()
    documento_compra_numero = serializers.SerializerMethodField()
    documento_compra_tipo = serializers.SerializerMethodField()
    monto_pendiente = serializers.SerializerMethodField()

    class Meta:
        model = CronogramaPago
        fields = [
            "id",
            "empresa",
            "proveedor",
            "proveedor_razon_social",
            "proveedor_documento",
            "documento_compra",
            "documento_compra_numero",
            "documento_compra_tipo",
            "descripcion",
            "monto",
            "monto_pendiente",
            "fecha_vencimiento",
            "estado",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = [
            "id",
            "creado_en",
            "actualizado_en",
            "proveedor_razon_social",
            "proveedor_documento",
            "documento_compra_numero",
            "documento_compra_tipo",
            "monto_pendiente",
        ]

    def _proveedor_resuelto(self, obj):
        p = obj.proveedor
        if p is None and obj.documento_compra_id and obj.documento_compra:
            p = obj.documento_compra.proveedor
        return p

    def get_proveedor_razon_social(self, obj):
        p = self._proveedor_resuelto(obj)
        if p is None:
            return None
        return (p.razon_social or "").strip() or None

    def get_proveedor_documento(self, obj):
        p = self._proveedor_resuelto(obj)
        if p is None:
            return None
        return (p.documento or "").strip() or None

    def get_documento_compra_numero(self, obj):
        dc = obj.documento_compra
        if dc is None:
            return None
        s = (dc.serie or "").strip()
        n = (dc.numero or "").strip()
        if s and n:
            return f"{s}-{n}"
        if s or n:
            return s or n
        return f"#{dc.id}"

    def get_documento_compra_tipo(self, obj):
        dc = obj.documento_compra
        if dc is None:
            return None
        return dc.tipo

    def get_monto_pendiente(self, obj):
        if obj.estado == EstadoCronogramaPago.PAGADO:
            return str(Decimal("0").quantize(Decimal("0.01")))
        return str(obj.monto.quantize(Decimal("0.01")))


class PagoRealizadoProveedorSerializer(serializers.ModelSerializer):
    documento_compra_id = serializers.SerializerMethodField()
    documento_compra_numero = serializers.SerializerMethodField()
    documento_compra_tipo = serializers.SerializerMethodField()
    proveedor_razon_social = serializers.SerializerMethodField()
    proveedor_documento = serializers.SerializerMethodField()

    class Meta:
        model = PagoRealizadoProveedor
        fields = [
            "id",
            "empresa",
            "cronograma_pago",
            "monto",
            "metodo",
            "usuario",
            "creado_en",
            "actualizado_en",
            "documento_compra_id",
            "documento_compra_numero",
            "documento_compra_tipo",
            "proveedor_razon_social",
            "proveedor_documento",
        ]
        read_only_fields = fields

    def _cron(self, obj):
        return obj.cronograma_pago

    def get_documento_compra_id(self, obj):
        c = self._cron(obj)
        if c is None or not c.documento_compra_id:
            return None
        return c.documento_compra_id

    def get_documento_compra_numero(self, obj):
        return CronogramaPagoSerializer().get_documento_compra_numero(self._cron(obj))

    def get_documento_compra_tipo(self, obj):
        return CronogramaPagoSerializer().get_documento_compra_tipo(self._cron(obj))

    def get_proveedor_razon_social(self, obj):
        return CronogramaPagoSerializer().get_proveedor_razon_social(self._cron(obj))

    def get_proveedor_documento(self, obj):
        return CronogramaPagoSerializer().get_proveedor_documento(self._cron(obj))


class ConciliacionBancariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConciliacionBancaria
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]
