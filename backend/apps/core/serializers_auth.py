import re



from django.contrib.auth import get_user_model

from django.contrib.auth.password_validation import validate_password

from django.db import transaction

from rest_framework import serializers



from apps.core.models import Empresa, PerfilUsuario, Sucursal, Usuario
from apps.core.notification_utils import notificar_superusuarios_nueva_empresa



User = get_user_model()



RUC_RE = re.compile(r"^\d{11}$")


def es_ruc_persona_juridica(ruc: str) -> bool:
    """En Perú, RUC de persona jurídica suele iniciar en 20 (11 dígitos)."""
    return bool(ruc) and len(ruc) == 11 and ruc.startswith("20")


PASSWORD_RULES_MSG = (

    "La contraseña debe tener al menos 8 caracteres, 1 minúscula, 1 mayúscula, "

    "1 número y 1 carácter especial."

)


# Registro web PJ (RUC 20…): el front solo pide razón social; User/Usuario exigen nombre en BD.
REGISTRO_PJ_ADMIN_NOMBRES = "Administrador"
REGISTRO_PJ_ADMIN_APELLIDO_PATERNO = "Registro"
REGISTRO_PJ_ADMIN_APELLIDO_MATERNO = "web"





def password_cumple_politica(password: str) -> bool:

    if len(password) < 8:

        return False

    if not re.search(r"[a-z]", password):

        return False

    if not re.search(r"[A-Z]", password):

        return False

    if not re.search(r"\d", password):

        return False

    if not re.search(r"[^A-Za-z0-9]", password):

        return False

    return True





class RegistroEmpresaSerializer(serializers.Serializer):

    """Alta de empresa + primer usuario; queda pendiente de aprobación (sin acceso hasta activar)."""



    ruc = serializers.CharField(max_length=11, min_length=11)

    razon_social = serializers.CharField(

        max_length=255,

        required=False,

        allow_blank=True,

        help_text="Si se omite, se usa un texto por defecto hasta actualizar datos.",

    )

    apellido_paterno = serializers.CharField(

        max_length=50,

        required=False,

        allow_blank=True,

        default="",

    )

    apellido_materno = serializers.CharField(

        max_length=50,

        required=False,

        allow_blank=True,

        default="",

    )

    nombres = serializers.CharField(

        max_length=100,

        required=False,

        allow_blank=True,

        default="",

    )

    email = serializers.EmailField()

    password = serializers.CharField(write_only=True, min_length=8)

    password_confirm = serializers.CharField(write_only=True, min_length=8)

    telefono_contacto = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_ruc(self, value):

        v = value.strip()

        if not RUC_RE.match(v):

            raise serializers.ValidationError("El RUC debe tener exactamente 11 dígitos.")

        return v



    def validate_email(self, value):

        return value.strip().lower()



    def validate_password(self, value):

        if not password_cumple_politica(value):

            raise serializers.ValidationError(PASSWORD_RULES_MSG)

        validate_password(value)

        return value



    def validate(self, attrs):

        if attrs["password"] != attrs["password_confirm"]:

            raise serializers.ValidationError(

                {"password_confirm": "Las contraseñas no coinciden."}

            )

        ruc = attrs["ruc"]

        if Empresa.objects.filter(ruc=ruc).exists():

            raise serializers.ValidationError(

                {

                    "ruc": "Esta empresa ya está registrada. Use Iniciar sesión o contacte a su administrador."

                }

            )

        email = attrs["email"]

        if User.objects.filter(username=email).exists():

            raise serializers.ValidationError(

                {"email": "Ya existe una cuenta con este correo."}

            )

        if Usuario.objects.filter(email=email).exists():

            raise serializers.ValidationError(

                {"email": "Ya existe una cuenta con este correo."}

            )

        razon = (attrs.get("razon_social") or "").strip()

        if es_ruc_persona_juridica(ruc):

            if len(razon) < 2:

                raise serializers.ValidationError(

                    {

                        "razon_social": (

                            "Empresa (RUC que empieza en 20): escriba la razón social "

                            "o pulse «Consultar SUNAT» en el formulario."

                        )

                    }

                )

        else:

            n = (attrs.get("nombres") or "").strip()

            ap = (attrs.get("apellido_paterno") or "").strip()

            am = (attrs.get("apellido_materno") or "").strip()

            if not n or not ap or not am:

                raise serializers.ValidationError(

                    "Persona natural con RUC: complete apellido paterno, apellido materno y nombres."

                )

        return attrs



    @transaction.atomic

    def create(self, validated_data):

        validated_data.pop("password_confirm", None)

        ruc = validated_data["ruc"]

        n_in = (validated_data.get("nombres") or "").strip()

        ap_in = (validated_data.get("apellido_paterno") or "").strip()

        am_in = (validated_data.get("apellido_materno") or "").strip()

        tel = (validated_data.get("telefono_contacto") or "").strip()

        if es_ruc_persona_juridica(ruc):

            razon = (validated_data.get("razon_social") or "").strip()

            if not razon:

                razon = f"Empresa RUC {ruc}"

            if n_in and ap_in and am_in:

                n_adm, ap_adm, am_adm = n_in, ap_in, am_in

            else:

                n_adm = REGISTRO_PJ_ADMIN_NOMBRES

                ap_adm = REGISTRO_PJ_ADMIN_APELLIDO_PATERNO

                am_adm = REGISTRO_PJ_ADMIN_APELLIDO_MATERNO

            empresa = Empresa.objects.create(

                razon_social=razon,

                ruc=ruc,

                registro_aprobado=False,

                apellido_paterno="",

                apellido_materno="",

                nombres="",

                telefono_contacto=tel,

            )

        else:

            n_adm, ap_adm, am_adm = n_in, ap_in, am_in

            partes = [p for p in (n_adm, ap_adm, am_adm) if p]

            razon = " ".join(partes).strip() or f"Contribuyente RUC {ruc}"

            empresa = Empresa.objects.create(

                razon_social=razon,

                ruc=ruc,

                registro_aprobado=False,

                apellido_paterno=ap_adm,

                apellido_materno=am_adm,

                nombres=n_adm,

                telefono_contacto=tel,

            )

        sucursal = Sucursal.objects.create(

            empresa=empresa,

            nombre="Sucursal principal",

            activo=True,

        )



        email = validated_data["email"]

        user = User.objects.create_user(

            username=email,

            email=email,

            password=validated_data["password"],

            first_name=n_adm[:150],

            last_name=f"{ap_adm} {am_adm}"[:150],

        )

        PerfilUsuario.objects.create(

            user=user,

            empresa=empresa,

            sucursal_default=sucursal,

            nombres=n_adm,

            apellido_paterno=ap_adm,

            apellido_materno=am_adm,

        )

        Usuario.objects.create(

            empresa=empresa,

            ruc=ruc,

            apellido_paterno=ap_adm,

            apellido_materno=am_adm,

            nombre=n_adm,

            email=email,

            password_hash=user.password,

            activo=True,

        )

        notificar_superusuarios_nueva_empresa(empresa)

        return user





class LoginSerializer(serializers.Serializer):

    """RUC vacío = acceso plataforma (solo is_superuser). Con RUC = acceso tenant."""



    ruc = serializers.CharField(

        max_length=11,

        required=False,

        allow_blank=True,

        default="",

    )

    email = serializers.EmailField()

    password = serializers.CharField(write_only=True)



    def validate_email(self, value):

        return value.strip().lower()



    def validate(self, attrs):

        ruc = (attrs.get("ruc") or "").strip()

        attrs["ruc"] = ruc

        if ruc and not RUC_RE.match(ruc):

            raise serializers.ValidationError({"ruc": "El RUC debe tener exactamente 11 dígitos."})

        return attrs





class CambiarPasswordSerializer(serializers.Serializer):

    """Usuario autenticado: contraseña actual + nueva (misma política que el registro)."""



    password_actual = serializers.CharField(write_only=True)

    password = serializers.CharField(write_only=True, min_length=8)

    password_confirm = serializers.CharField(write_only=True, min_length=8)



    def validate_password(self, value):

        if not password_cumple_politica(value):

            raise serializers.ValidationError(PASSWORD_RULES_MSG)

        validate_password(value)

        return value



    def validate(self, attrs):

        if attrs["password"] != attrs["password_confirm"]:

            raise serializers.ValidationError(

                {"password_confirm": "Las contraseñas no coinciden."}

            )

        return attrs


