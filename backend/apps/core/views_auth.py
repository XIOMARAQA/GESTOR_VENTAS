from django.contrib.auth import authenticate

from rest_framework import status

from rest_framework.authtoken.models import Token

from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework.response import Response

from rest_framework.views import APIView



from apps.core.models import PerfilUsuario

from apps.core.serializers_auth import LoginSerializer, RegistroEmpresaSerializer



REGISTRO_OK_MSG = (

    "Recibimos su solicitud de registro. El equipo de Gestor de Ventas se comunicará con ustedes "

    "para completar el alta y activar el acceso a la plataforma. Hasta entonces no podrá iniciar sesión."

)





class RegistroEmpresaView(APIView):

    """

    Registro público: crea empresa (pendiente de aprobación), sucursal, usuario y perfil.

    No devuelve token: el acceso queda bloqueado hasta que un superusuario apruebe la empresa.

    """



    permission_classes = [AllowAny]



    def post(self, request):

        ser = RegistroEmpresaSerializer(data=request.data)

        if not ser.is_valid():

            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ser.save()

        return Response(

            {

                "mensaje": REGISTRO_OK_MSG,

                "pendiente_aprobacion": True,

                "email": ser.validated_data["email"],

            },

            status=status.HTTP_201_CREATED,

        )





def _payload_tenant(user, perfil):

    token, _ = Token.objects.get_or_create(user=user)

    return {

        "token": token.key,

        "empresa_id": str(perfil.empresa_id),

        "empresa_razon_social": perfil.empresa.razon_social,

        "sucursal_id": str(perfil.sucursal_default_id)

        if perfil.sucursal_default_id

        else None,

        "email": user.email,

        "is_superuser": user.is_superuser,

    }





class LoginView(APIView):

    """

    - Sin RUC (vacío): solo superusuarios Django (acceso plataforma, todas las empresas).

    - Con RUC: usuario con perfil y empresa; exige registro aprobado salvo superusuario.

    """



    permission_classes = [AllowAny]



    def post(self, request):

        ser = LoginSerializer(data=request.data)

        if not ser.is_valid():

            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ruc = ser.validated_data["ruc"]

        email = ser.validated_data["email"]

        password = ser.validated_data["password"]



        user = authenticate(request, username=email, password=password)

        if user is None:

            return Response(

                {"detail": "Correo o contraseña incorrectos."},

                status=status.HTTP_401_UNAUTHORIZED,

            )



        if not ruc:

            if not user.is_superuser:

                return Response(

                    {

                        "detail": "Indique el RUC de su empresa (11 dígitos). "

                        "Las cuentas de administración de plataforma ingresan sin RUC."

                    },

                    status=status.HTTP_400_BAD_REQUEST,

                )

            token, _ = Token.objects.get_or_create(user=user)

            return Response(

                {

                    "token": token.key,

                    "empresa_id": "",

                    "empresa_razon_social": "Plataforma (todas las empresas)",

                    "sucursal_id": None,

                    "email": user.email,

                    "is_superuser": True,

                }

            )



        try:

            perfil = user.perfil_gestor

        except PerfilUsuario.DoesNotExist:

            if user.is_superuser:

                return Response(

                    {

                        "detail": "Para entrar con RUC necesita un perfil de empresa enlazado, "

                        "o deje el RUC vacío para modo plataforma."

                    },

                    status=status.HTTP_400_BAD_REQUEST,

                )

            return Response(

                {"detail": "Usuario sin empresa asignada. Contacte al administrador."},

                status=status.HTTP_403_FORBIDDEN,

            )



        if perfil.empresa.ruc != ruc:

            return Response(

                {"detail": "El RUC no corresponde a la empresa de esta cuenta."},

                status=status.HTTP_400_BAD_REQUEST,

            )

        if not perfil.empresa.activo:

            return Response(

                {"detail": "Empresa inactiva."},

                status=status.HTTP_403_FORBIDDEN,

            )

        if not user.is_superuser and not perfil.empresa.registro_aprobado:

            return Response(

                {

                    "detail": "Su solicitud de registro está pendiente de aprobación. "

                    "Gestor de Ventas se pondrá en contacto para activar su acceso."

                },

                status=status.HTTP_403_FORBIDDEN,

            )



        return Response(_payload_tenant(user, perfil))





class SessionView(APIView):
    """Correo y flags del usuario autenticado (p. ej. barra superior sin volver a iniciar sesión)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        mail = (u.email or "").strip() or u.get_username()
        return Response({"email": mail, "is_superuser": u.is_superuser})





class LogoutView(APIView):

    """Invalida el token actual (Authorization: Token ...)."""



    permission_classes = [IsAuthenticated]



    def post(self, request):

        if request.user.is_authenticated:

            Token.objects.filter(user=request.user).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


