# Autenticación y usuarios (buenas prácticas)

## 1. No dupliques una tabla `usuario` con contraseña en texto plano

En PostgreSQL, **Django ya crea y mantiene** la tabla `auth_user` (o el modelo que definas en `AUTH_USER_MODEL`). Ahí se guarda la contraseña **hasheada** (PBKDF2 por defecto), nunca en claro.

Crear otra tabla `usuario` con `password_hash` manual suele ser **mala práctica** porque:

- Reimplementas hashing, recuperación de contraseña y bloqueos peor que el framework.
- Duplicas identidad entre `auth_user` y tu tabla.

## 2. Patrón recomendado en este proyecto

| Qué | Dónde |
|-----|--------|
| Login (usuario/contraseña, permisos de staff) | **`auth_user`** (`django.contrib.auth.models.User`) |
| A qué **empresa** y **sucursal** pertenece | **`PerfilUsuario`** (`apps.core.models.PerfilUsuario`) — `OneToOne` con `User` |

El **RUC** va en **`Empresa.ruc`**, no hace falta repetirlo en el usuario salvo que negocio lo exija en el formulario solo para **elegir la empresa** al iniciar sesión.

## 3. Cómo crear un usuario que pueda ingresar

### Opción A — Superusuario (admin web)

```bash
cd backend
python manage.py createsuperuser
```

Luego en el admin de Django puedes crear más usuarios y, si hace falta, filas de `PerfilUsuario` (o hazlo por shell).

### Opción B — Comando del proyecto (recomendado para equipos)

```bash
python manage.py crear_usuario_empresa --email tesoreria@empresa.com --password "UnaClaveSegura123" --empresa-ruc 20123456789 --username tesoreria
```

Crea el `User`, enlaza `PerfilUsuario` a la empresa cuyo RUC coincida (debe existir la empresa).

### Opción C — Shell de Django

```python
from django.contrib.auth import get_user_model
from apps.core.models import Empresa, PerfilUsuario

User = get_user_model()
empresa = Empresa.objects.get(ruc="20123456789")

u = User.objects.create_user(
    username="tesoreria",
    email="tesoreria@empresa.com",
    password="UnaClaveSegura123",  # Django hashea aquí; nunca guardes esto en otro sitio
)
PerfilUsuario.objects.create(user=u, empresa=empresa)
```

**Nunca** hagas `INSERT` SQL directo con contraseña en claro.

## 4. Registro multi-empresa (SaaS)

- **POST** `/api/v1/auth/registro/` — crea **empresa** (RUC único), **sucursal principal**, **usuario** y **perfil**. Si el RUC ya existe, el usuario debe **iniciar sesión**, no registrarse otra vez.
- **POST** `/api/v1/auth/login/` — body: `ruc`, `email`, `password`. Comprueba que el usuario pertenezca a la empresa con ese RUC.
- **POST** `/api/v1/auth/logout/` — con cabecera `Authorization: Token <key>` borra el token.

El frontend guarda el token y el `empresa_id` en `sessionStorage` y envía `Authorization` en cada petición.

## 5. Reglas útiles

- **Contraseñas:** en registro se exige además 1 minúscula, 1 mayúscula, 1 número y 1 carácter especial (además de `validate_password` de Django).
- **Email:** el `username` de Django es el correo en el flujo de registro; es único en toda la plataforma.
- **Varios usuarios en la misma empresa:** se pueden crear más filas en `PerfilUsuario` apuntando a la misma `Empresa` (por admin, comando o futuro “invitar usuario”).

## 6. Tablas en PostgreSQL (referencia)

Tras `migrate`, verás entre otras:

- `auth_user` — identidad y hash de contraseña
- `core_perfilusuario` — vínculo usuario ↔ empresa (y sucursal por defecto)

Tu script SQL con `usuario` + `password_hash` puede mapearse conceptualmente a `auth_user`; no hace falta crear esa tabla aparte si usas Django Auth.
