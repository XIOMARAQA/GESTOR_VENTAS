"""
Crea un usuario Django (auth_user) con contraseña hasheada y un PerfilUsuario
vinculado a la empresa indicada por RUC.

Buenas prácticas: usar create_user / set_password, nunca almacenar contraseña en claro en tablas propias.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Empresa, PerfilUsuario

User = get_user_model()


class Command(BaseCommand):
    help = "Crea usuario de login y lo asocia a una empresa existente (por RUC)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Nombre de usuario único (puede ser el email).")
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument(
            "--empresa-ruc",
            required=True,
            dest="ruc",
            help="RUC de la empresa (debe existir en la tabla empresa).",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Marca como staff y superuser (solo administración).",
        )

    def handle(self, *args, **options):
        ruc = options["ruc"].strip()
        try:
            empresa = Empresa.objects.get(ruc=ruc, activo=True)
        except Empresa.DoesNotExist as exc:
            raise CommandError(
                f'No hay empresa activa con RUC "{ruc}". Crea primero la empresa (admin o API).'
            ) from exc

        username = options["username"].strip()
        email = options["email"].strip()

        if User.objects.filter(username=username).exists():
            raise CommandError(f'Ya existe un usuario con username "{username}".')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=options["password"],
        )
        if options["superuser"]:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])

        PerfilUsuario.objects.create(user=user, empresa=empresa)

        self.stdout.write(
            self.style.SUCCESS(
                f'Usuario "{username}" creado y asociado a empresa "{empresa.razon_social}" (RUC {ruc}).'
            )
        )
