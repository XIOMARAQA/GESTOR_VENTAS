"""
Configuración Django — Gestor de Ventas (capa de datos + API).
Usa PostgreSQL vía DATABASE_URL; si no existe, SQLite para desarrollo rápido.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
# Render expone RENDER_EXTERNAL_HOSTNAME (p. ej. gestor-ventas-backend.onrender.com).
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    "apps.core",
    "apps.inventario",
    "apps.ventas",
    "apps.compras",
    "apps.tesoreria",
    "apps.contabilidad",
    "apps.administracion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Esquema PostgreSQL dedicado (comparte BD con helpmed u otras apps en otros esquemas).
DB_SCHEMA = os.environ.get("DB_SCHEMA", "gestorVentas").strip() or "gestorVentas"

_database_url = (os.environ.get("DATABASE_URL") or "").strip()
_on_render = os.environ.get("RENDER", "").lower() in ("1", "true", "yes")
if not _database_url and (_on_render or not DEBUG):
    raise ImproperlyConfigured(
        "DATABASE_URL es obligatorio en producción (Render). "
        "En Render: Web Service → Environment → añada DATABASE_URL con la "
        "Internal Database URL de su PostgreSQL (o vincule la base al servicio web)."
    )
if _database_url:
    DATABASES = {"default": dj_database_url.config(default=_database_url, conn_max_age=600)}
    if DATABASES["default"].get("ENGINE") == "django.db.backends.postgresql":
        DATABASES["default"].setdefault("OPTIONS", {})
        # Identificador entre comillas: el esquema usa camelCase (gestorVentas).
        DATABASES["default"]["OPTIONS"]["options"] = (
            f'-c search_path="{DB_SCHEMA}",public'
        )
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS: frontend Vue (Vite default 5173)
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

_api_auth = os.environ.get("API_REQUIRE_AUTH", "false" if DEBUG else "true").lower()
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        (
            "rest_framework.permissions.IsAuthenticated"
            if _api_auth in ("1", "true", "yes")
            else "rest_framework.permissions.AllowAny"
        ),
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

# Nubefact: emisión desde el servidor (no exponer token en el frontend).
# Ej. https://api.nubefact.com/api/v1/<uuid-del-panel>
NUBEFACT_API_URL = os.environ.get("NUBEFACT_API_URL", "").strip()
NUBEFACT_TOKEN = os.environ.get("NUBEFACT_TOKEN", "").strip()

# URL completa de Nubefact para pruebas (opcional). Si la API recibe entorno_prueba=true,
# el backend usa esta URL en lugar de NUBEFACT_API_URL.
NUBEFACT_PRUEBA_API_URL = os.environ.get("NUBEFACT_PRUEBA_API_URL", "").strip()


def _nubefact_serie_env(name: str) -> str:
    """Serie desde .env únicamente (máx. 10 caracteres). Sin variable → cadena vacía."""
    raw = (os.environ.get(name, "") or "").strip()
    return raw[:10] if raw else ""


# Series para el formulario de comprobantes (solo .env; sin valor por defecto en código).
NUBEFACT_SERIE_FACTURA = _nubefact_serie_env("NUBEFACT_SERIE_FACTURA")
NUBEFACT_SERIE_BOLETA = _nubefact_serie_env("NUBEFACT_SERIE_BOLETA")
NUBEFACT_SERIE_NOTA_CREDITO_FACTURA = _nubefact_serie_env("NUBEFACT_SERIE_NOTA_CREDITO_FACTURA")
NUBEFACT_SERIE_NOTA_DEBITO_FACTURA = _nubefact_serie_env("NUBEFACT_SERIE_NOTA_DEBITO_FACTURA")
NUBEFACT_SERIE_NOTA_CREDITO_BOLETA = _nubefact_serie_env("NUBEFACT_SERIE_NOTA_CREDITO_BOLETA")
NUBEFACT_SERIE_NOTA_DEBITO_BOLETA = _nubefact_serie_env("NUBEFACT_SERIE_NOTA_DEBITO_BOLETA")

# Cotización interna (no se envía a Nubefact). Correlativo: {serie}-{0001}.
COTIZACION_SERIE_INTERNA = (os.environ.get("COTIZACION_SERIE_INTERNA", "COT1") or "COT1").strip()[:10]

# Consulta RUC SUNAT (Bearer). Token en panel del proveedor; no commitear.
# — apis.net.pe: https://apis.net.pe/ (suele ser token distinto de sk_…)
# — Decolecta: https://decolecta.com/ (tokens suelen empezar por sk_…)
APIS_NET_PE_TOKEN = os.environ.get("APIS_NET_PE_TOKEN", "").strip()
# Opcional: forzar URL (si no se define y el token empieza por sk_, se usa api.decolecta.com/v1).
SUNAT_RUC_API_BASE = os.environ.get("SUNAT_RUC_API_BASE", "").strip().rstrip("/")
SUNAT_RUC_API_PATH = os.environ.get("SUNAT_RUC_API_PATH", "").strip()
SUNAT_RUC_API_REFERER = os.environ.get("SUNAT_RUC_API_REFERER", "").strip()
# Igual que DecolectaAPIClient del gist (requests + Referer fijo).
SUNAT_RUC_DECOLECTA_REFERER = os.environ.get("SUNAT_RUC_DECOLECTA_REFERER", "python-decolecta").strip()
# Opcional: añade token en query además del Bearer.
_sunat_q = os.environ.get("SUNAT_RUC_TOKEN_IN_QUERY", "false").strip().lower()
SUNAT_RUC_TOKEN_IN_QUERY = _sunat_q in ("1", "true", "yes", "on")

SPECTACULAR_SETTINGS = {
    "TITLE": "Gestor de Ventas API",
    "VERSION": "1.0.0",
    "DESCRIPTION": "API modular: ventas, compras, tesorería, inventario, contabilidad.",
}
