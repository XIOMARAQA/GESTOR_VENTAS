from rest_framework import serializers

from apps.administracion.models import ConfiguracionSistema, Tarea


class ConfiguracionSistemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionSistema
        fields = "__all__"
        read_only_fields = ["creado_en", "actualizado_en"]


class TareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarea
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]
