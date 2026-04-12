from rest_framework import serializers

from apps.contabilidad.models import AsientoContable, AsientoLinea, ComunicacionBaja, PlanCuenta


class PlanCuentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanCuenta
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class AsientoLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AsientoLinea
        fields = ["id", "cuenta", "debe", "haber"]
        read_only_fields = ["id"]


class AsientoContableSerializer(serializers.ModelSerializer):
    lineas = AsientoLineaSerializer(many=True, read_only=True)

    class Meta:
        model = AsientoContable
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class ComunicacionBajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComunicacionBaja
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]
