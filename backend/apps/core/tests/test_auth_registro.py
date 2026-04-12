"""Verificación del registro: 400 = validación previa; contraseña hasheada en BD (no texto plano)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.core.models import Usuario

User = get_user_model()


@pytest.mark.django_db
def test_registro_201_guarda_hash_no_texto_plano():
    client = APIClient()
    plain = "Abcdef1!x"
    payload = {
        "ruc": "20123456789",
        "razon_social": "Empresa Test SAC",
        "apellido_paterno": "Perez",
        "apellido_materno": "Lopez",
        "nombres": "Juan",
        "email": "juan.registro.verify@example.com",
        "password": plain,
        "password_confirm": plain,
    }
    r = client.post("/api/v1/auth/registro/", payload, format="json")
    assert r.status_code == 201, r.content
    user = User.objects.get(username=payload["email"])
    assert user.password != plain
    assert user.password.startswith("pbkdf2_")
    row = Usuario.objects.get(email=payload["email"])
    assert row.password_hash == user.password


@pytest.mark.django_db
def test_registro_400_contrasena_sin_mayuscula_es_validacion_no_bd():
    """400 antes de escribir: el serializer rechaza la contraseña (no es fallo de columna password_hash)."""
    client = APIClient()
    r = client.post(
        "/api/v1/auth/registro/",
        {
            "ruc": "20987654321",
            "apellido_paterno": "Perez",
            "apellido_materno": "Lopez",
            "nombres": "Ana",
            "email": "ana.verify@example.com",
            "password": "abcdef1!x",
            "password_confirm": "abcdef1!x",
        },
        format="json",
    )
    assert r.status_code == 400
    assert "password" in r.data
    assert not User.objects.filter(username="ana.verify@example.com").exists()


@pytest.mark.django_db
def test_registro_400_ruc_duplicado():
    client = APIClient()
    base = {
        "ruc": "20555123456",
        "razon_social": "Dup Test SAC",
        "apellido_paterno": "A",
        "apellido_materno": "B",
        "nombres": "C",
        "password": "Zxcvb1!a",
        "password_confirm": "Zxcvb1!a",
    }
    r1 = client.post(
        "/api/v1/auth/registro/",
        {**base, "email": "uno@example.com"},
        format="json",
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/auth/registro/",
        {**base, "email": "dos@example.com"},
        format="json",
    )
    assert r2.status_code == 400
    assert "ruc" in r2.data


@pytest.mark.django_db
def test_registro_pj_201_sin_nombres_admin_marcador_en_tabla_usuario():
    """RUC 20…: solo razón social en pantalla; User/Usuario requieren texto — se usan marcadores."""
    client = APIClient()
    plain = "Abcdef1!z"
    payload = {
        "ruc": "20111222333",
        "razon_social": "Solo Razon SAC",
        "email": "pj.solo.razon@example.com",
        "password": plain,
        "password_confirm": plain,
    }
    r = client.post("/api/v1/auth/registro/", payload, format="json")
    assert r.status_code == 201, r.content
    emp = Empresa.objects.get(ruc=payload["ruc"])
    assert emp.razon_social == "Solo Razon SAC"
    assert emp.apellido_paterno == ""
    assert emp.nombres == ""
    row = Usuario.objects.get(email=payload["email"])
    assert row.nombre == "Administrador"
    assert row.apellido_paterno == "Registro"
    assert row.apellido_materno == "web"


@pytest.mark.django_db
def test_registro_pn_400_si_faltan_apellidos_o_nombres():
    client = APIClient()
    plain = "Abcdef1!w"
    r = client.post(
        "/api/v1/auth/registro/",
        {
            "ruc": "10765432101",
            "nombres": "",
            "apellido_paterno": "",
            "apellido_materno": "",
            "email": "pn.incompleto@example.com",
            "password": plain,
            "password_confirm": plain,
        },
        format="json",
    )
    assert r.status_code == 400
