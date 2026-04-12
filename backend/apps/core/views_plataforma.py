"""APIs solo para superusuarios de plataforma (resumen, export, alta de superusuarios)."""

from __future__ import annotations

import csv
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Empresa

User = get_user_model()


class IsSuperuserPlatform(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class PlataformaResumenView(APIView):
    permission_classes = [IsSuperuserPlatform]

    def get(self, request):
        qs = Empresa.objects.all()
        total = qs.count()
        activas = qs.filter(activo=True).count()
        inactivas = qs.filter(activo=False).count()
        aprobadas = qs.filter(registro_aprobado=True).count()
        pendientes_aprobacion = qs.filter(
            activo=True, registro_aprobado=False
        ).count()
        activas_aprobadas = qs.filter(
            activo=True, registro_aprobado=True
        ).count()
        super_count = User.objects.filter(is_superuser=True, is_active=True).count()

        return Response(
            {
                "empresas_total": total,
                "empresas_activas": activas,
                "empresas_inactivas": inactivas,
                "empresas_aprobadas": aprobadas,
                "empresas_pendientes_aprobacion": pendientes_aprobacion,
                "empresas_activas_y_aprobadas": activas_aprobadas,
                "superusuarios_activos": super_count,
            }
        )


class PlataformaEmpresasExportView(APIView):
    """CSV de empresas activas y aprobadas (UTF-8 con BOM para Excel)."""

    permission_classes = [IsSuperuserPlatform]

    def get(self, request):
        qs = (
            Empresa.objects.filter(activo=True, registro_aprobado=True)
            .order_by("razon_social")
            .values(
                "id",
                "razon_social",
                "ruc",
                "apellido_paterno",
                "apellido_materno",
                "nombres",
                "telefono_contacto",
                "creado_en",
                "fecha_registro_aprobado",
            )
        )
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "id",
                "razon_social",
                "ruc",
                "apellido_paterno",
                "apellido_materno",
                "nombres",
                "telefono_contacto",
                "creado_en",
                "fecha_registro_aprobado",
            ]
        )
        for row in qs:
            w.writerow(
                [
                    row["id"],
                    row["razon_social"],
                    row["ruc"],
                    row["apellido_paterno"] or "",
                    row["apellido_materno"] or "",
                    row["nombres"] or "",
                    row["telefono_contacto"] or "",
                    row["creado_en"].isoformat() if row["creado_en"] else "",
                    row["fecha_registro_aprobado"].isoformat()
                    if row["fecha_registro_aprobado"]
                    else "",
                ]
            )
        data = "\ufeff" + buf.getvalue()
        resp = HttpResponse(data.encode("utf-8"), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="empresas_activas_aprobadas.csv"'
        return resp


def _apellidos_desde_last_name(last_name: str) -> tuple[str, str]:
    s = (last_name or "").strip()
    if not s:
        return "", ""
    parts = s.split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


class SuperusuarioPlataformaSerializer(serializers.ModelSerializer):
    """Listado: nombres y apellidos en columnas (provienen de first_name / last_name en auth_user)."""

    nombres = serializers.CharField(source="first_name", read_only=True)
    apellido_paterno = serializers.SerializerMethodField()
    apellido_materno = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "nombres",
            "apellido_paterno",
            "apellido_materno",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
        ]
        read_only_fields = fields

    def get_apellido_paterno(self, obj) -> str:
        return _apellidos_desde_last_name(getattr(obj, "last_name", "") or "")[0]

    def get_apellido_materno(self, obj) -> str:
        return _apellidos_desde_last_name(getattr(obj, "last_name", "") or "")[1]


class CrearSuperusuarioSerializer(serializers.Serializer):
    email = serializers.EmailField()
    nombres = serializers.CharField(max_length=100)
    apellido_paterno = serializers.CharField(max_length=80)
    apellido_materno = serializers.CharField(max_length=80)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_email(self, value):
        v = value.strip().lower()
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return v

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Las contraseñas no coinciden."}
            )
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        email = validated_data["email"].strip().lower()
        nom = validated_data["nombres"].strip()
        ap = validated_data["apellido_paterno"].strip()
        am = validated_data["apellido_materno"].strip()
        last = f"{ap} {am}".strip()
        return User.objects.create_superuser(
            username=email,
            email=email,
            password=validated_data["password"],
            first_name=nom[:150],
            last_name=last[:150],
        )


class ActualizarSuperusuarioSerializer(serializers.Serializer):
    """PATCH parcial: estado activo, nombres y/o contraseña."""

    nombres = serializers.CharField(max_length=100, required=False, allow_blank=True)
    apellido_paterno = serializers.CharField(max_length=80, required=False, allow_blank=True)
    apellido_materno = serializers.CharField(max_length=80, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_confirm = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        data = self.initial_data if isinstance(self.initial_data, dict) else {}
        name_touched = any(
            k in data and data[k] is not None and str(data[k]).strip() != ""
            for k in ("nombres", "apellido_paterno", "apellido_materno")
        )
        if name_touched or all(k in data for k in ("nombres", "apellido_paterno", "apellido_materno")):
            n = (data.get("nombres") or "").strip()
            ap = (data.get("apellido_paterno") or "").strip()
            am = (data.get("apellido_materno") or "").strip()
            if not (n and ap and am):
                raise serializers.ValidationError("Indique nombres y ambos apellidos.")
            attrs["nombres"] = n
            attrs["apellido_paterno"] = ap
            attrs["apellido_materno"] = am

        pw = (data.get("password") or "").strip()
        pwc = (data.get("password_confirm") or "").strip()
        if pw or pwc:
            if pw != pwc:
                raise serializers.ValidationError(
                    {"password_confirm": "Las contraseñas no coinciden."}
                )
            if pw:
                validate_password(pw)
                attrs["password"] = pw
        return attrs


class PlataformaSuperusuariosView(APIView):
    permission_classes = [IsSuperuserPlatform]

    def get(self, request):
        users = User.objects.filter(is_superuser=True).order_by("-date_joined")
        ser = SuperusuarioPlataformaSerializer(users, many=True)
        return Response({"results": ser.data})

    def post(self, request):
        ser = CrearSuperusuarioSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        out = SuperusuarioPlataformaSerializer(user)
        return Response(out.data, status=status.HTTP_201_CREATED)


class PlataformaSuperusuarioDetalleView(APIView):
    permission_classes = [IsSuperuserPlatform]

    def get_object(self, pk: int):
        return get_object_or_404(User, pk=pk, is_superuser=True)

    def patch(self, request, pk: int):
        user = self.get_object(pk)
        ser = ActualizarSuperusuarioSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        if v.get("is_active") is False:
            if request.user.pk == user.pk:
                return Response(
                    {"detail": "No puede inactivar su propia cuenta."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            otros_activos = (
                User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).exists()
            )
            if not otros_activos:
                return Response(
                    {"detail": "Debe quedar al menos un superusuario activo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if "is_active" in v:
            user.is_active = v["is_active"]
        if "nombres" in v:
            user.first_name = v["nombres"][:150]
        if "apellido_paterno" in v:
            user.last_name = (
                f"{v['apellido_paterno']} {v['apellido_materno']}".strip()[:150]
            )
        if v.get("password"):
            user.set_password(v["password"])
        user.save()

        return Response(SuperusuarioPlataformaSerializer(user).data)
