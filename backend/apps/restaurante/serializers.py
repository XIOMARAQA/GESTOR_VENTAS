from rest_framework import serializers

from apps.restaurante.models import Comanda, ComandaLinea


class ComandaLineaSerializer(serializers.ModelSerializer):
    item_nombre = serializers.CharField(source="item.nombre", read_only=True)

    class Meta:
        model = ComandaLinea
        fields = [
            "id",
            "comanda",
            "item",
            "item_nombre",
            "cantidad",
            "nota",
            "estado",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "comanda", "creado_en", "actualizado_en"]


class ComandaSerializer(serializers.ModelSerializer):
    lineas = ComandaLineaSerializer(many=True, read_only=True)

    class Meta:
        model = Comanda
        fields = "__all__"
        read_only_fields = ["id", "creado_en", "actualizado_en"]
