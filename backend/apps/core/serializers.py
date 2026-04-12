from rest_framework import serializers

from apps.core.models import (
    Cliente,
    Empresa,
    NotificacionUsuario,
    PerfilUsuario,
    Proveedor,
    Sucursal,
    Vendedor,
)


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = [
            "id",
            "razon_social",
            "ruc",
            "apellido_paterno",
            "apellido_materno",
            "nombres",
            "telefono_contacto",
            "activo",
            "registro_aprobado",
            "fecha_registro_aprobado",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en", "fecha_registro_aprobado"]


class SucursalSerializer(serializers.ModelSerializer):
    empresa_razon_social = serializers.CharField(source="empresa.razon_social", read_only=True)

    class Meta:
        model = Sucursal
        fields = [
            "id",
            "empresa",
            "empresa_razon_social",
            "nombre",
            "direccion",
            "activo",
        ]
        read_only_fields = ["id", "empresa_razon_social"]


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            "id",
            "empresa",
            "razon_social",
            "documento",
            "email",
            "direccion",
            "telefono",
            "activo",
        ]
        read_only_fields = ["id", "empresa"]


class VendedorSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = Vendedor
        fields = [
            "id",
            "empresa",
            "dni",
            "apellido_paterno",
            "apellido_materno",
            "nombres",
            "sucursal",
            "activo",
            "nombre_completo",
        ]
        read_only_fields = ["id", "empresa", "nombre_completo"]

    def get_nombre_completo(self, obj):
        return obj.nombre_completo()


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = [
            "id",
            "empresa",
            "razon_social",
            "documento",
            "activo",
        ]
        read_only_fields = ["id", "empresa"]


class NotificacionUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificacionUsuario
        fields = [
            "id",
            "titulo",
            "mensaje",
            "leida",
            "categoria",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = [
            "titulo",
            "mensaje",
            "categoria",
            "creado_en",
            "actualizado_en",
        ]


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            "id",
            "user",
            "username",
            "empresa",
            "sucursal_default",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en"]
