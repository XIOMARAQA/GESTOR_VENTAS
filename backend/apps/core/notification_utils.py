"""Creación de notificaciones in-app (barra superior / usuarios de empresa)."""

from django.contrib.auth import get_user_model

from apps.core.models import Empresa, NotificacionUsuario, PerfilUsuario

User = get_user_model()

CAT_NUEVA = "nueva_empresa"
CAT_BIENVENIDA = "bienvenida"
CAT_RECHAZO = "rechazo"


def _es_ruc_persona_juridica(ruc: str) -> bool:
    return bool(ruc) and len(ruc) == 11 and ruc.startswith("20")


def notificar_superusuarios_nueva_empresa(empresa: Empresa) -> None:
    titulo = "Nueva solicitud de registro"
    partes = [
        f"La empresa «{empresa.razon_social}» (RUC {empresa.ruc}) solicita revisión y aprobación."
    ]
    if not _es_ruc_persona_juridica(empresa.ruc or ""):
        titular = " ".join(
            p
            for p in (
                (empresa.apellido_paterno or "").strip(),
                (empresa.apellido_materno or "").strip(),
                (empresa.nombres or "").strip(),
            )
            if p
        ).strip()
        if titular:
            partes.append(f"Titular (persona natural): {titular}.")
    tel = (empresa.telefono_contacto or "").strip()
    if tel:
        partes.append(f"Teléfono de contacto: {tel}.")
    mensaje = " ".join(partes)
    for u in User.objects.filter(is_superuser=True, is_active=True):
        NotificacionUsuario.objects.create(
            user=u,
            titulo=titulo,
            mensaje=mensaje,
            categoria=CAT_NUEVA,
        )


def notificar_bienvenida_empresa(empresa: Empresa) -> None:
    titulo = "¡Bienvenido a Gestor de Ventas!"
    for perfil in PerfilUsuario.objects.filter(empresa=empresa).select_related("user"):
        nombre = (perfil.nombres or perfil.user.first_name or "").strip()
        saludo = f"Hola, {nombre}" if nombre else "Hola"
        mensaje = (
            f"{saludo}. En representación de «{empresa.razon_social}», le damos la bienvenida: "
            "su registro fue aprobado y ya puede iniciar sesión con su RUC y sus credenciales. "
            "Gracias por habernos elegido."
        )
        NotificacionUsuario.objects.create(
            user=perfil.user,
            titulo=titulo,
            mensaje=mensaje,
            categoria=CAT_BIENVENIDA,
        )


def notificar_rechazo_empresa(empresa: Empresa) -> None:
    titulo = "Registro no aprobado"
    mensaje = (
        f"La solicitud asociada a «{empresa.razon_social}» no fue aprobada. "
        "La empresa quedó inactiva en la plataforma. Si cree que es un error, contacte a soporte."
    )
    for perfil in PerfilUsuario.objects.filter(empresa=empresa).select_related("user"):
        NotificacionUsuario.objects.create(
            user=perfil.user,
            titulo=titulo,
            mensaje=mensaje,
            categoria=CAT_RECHAZO,
        )


def dispatch_empresa_cambio_estado(
    empresa: Empresa, prev_aprobado: bool, prev_activo: bool
) -> None:
    if prev_aprobado is False and empresa.registro_aprobado is True:
        notificar_bienvenida_empresa(empresa)
    if (
        prev_activo is True
        and empresa.activo is False
        and prev_aprobado is False
        and empresa.registro_aprobado is False
    ):
        notificar_rechazo_empresa(empresa)
