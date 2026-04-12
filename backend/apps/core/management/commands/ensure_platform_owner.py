"""
Asegura un superusuario de plataforma definido por variables de entorno.

Uso educativo / despliegue inicial: evita depender solo de createsuperuser interactivo.
La contraseña solo se usa al crear el usuario o si se pide actualizar; Django guarda el hash en BD.

Variables (en .env o entorno del servidor, no commitear secretos):
  PLATFORM_OWNER_EMAIL   — obligatoria para este comando (correo = username de login).
  PLATFORM_OWNER_PASSWORD — obligatoria si el usuario aún no existe; opcional si existe
                            (entonces actualiza la contraseña).
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Crea o actualiza el superusuario de plataforma según PLATFORM_OWNER_EMAIL "
        "y PLATFORM_OWNER_PASSWORD en el entorno. Login en Vue: RUC vacío + este correo."
    )

    def handle(self, *args, **options):
        raw_email = (os.environ.get("PLATFORM_OWNER_EMAIL") or "").strip()
        if not raw_email:
            raise CommandError(
                "Defina PLATFORM_OWNER_EMAIL en .env (o en el entorno) y vuelva a ejecutar.\n"
                "Ejemplo: PLATFORM_OWNER_EMAIL=admin@miempresa.com\n"
                "Alternativa: python manage.py createsuperuser"
            )

        email = raw_email.lower()
        password = (os.environ.get("PLATFORM_OWNER_PASSWORD") or "").strip()

        user = User.objects.filter(username=email).first()
        if user is None:
            user = User.objects.filter(email__iexact=email).first()

        if user is None:
            if not password:
                raise CommandError(
                    "El usuario no existe. Defina PLATFORM_OWNER_PASSWORD en .env para crearlo "
                    "(solo para el primer arranque; luego puede borrarla del archivo).\n"
                    "O use: python manage.py createsuperuser"
                )
            User.objects.create_superuser(
                username=email,
                email=email,
                password=password,
            )
            self.stdout.write(self.style.SUCCESS(f"Superusuario creado: {email}"))
            return

        updated = False
        if not user.is_superuser or not user.is_staff:
            user.is_superuser = True
            user.is_staff = True
            updated = True

        if user.email.lower() != email:
            user.email = email
            updated = True

        if password:
            user.set_password(password)
            updated = True

        if updated:
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superusuario actualizado: {email} (flags staff/superuser y/o contraseña)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Sin cambios: {email} ya es superusuario. "
                    "Defina PLATFORM_OWNER_PASSWORD si desea rotar la contraseña."
                )
            )
