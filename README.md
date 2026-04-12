# Gestor de Ventas

Monorepo con **backend** (Django 5 + Django REST Framework + PostgreSQL) y **frontend** (Vue 3 + Vite + TypeScript + Pinia + Vue Router).

## Requisitos

- Python 3.12+ (probado con 3.13)
- Node.js 20+ o 22+
- PostgreSQL (opcional en desarrollo: sin `DATABASE_URL` se usa SQLite)

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# Editar .env: DATABASE_URL=postgres://usuario:clave@localhost:5432/gestor_ventas
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

- API: `http://127.0.0.1:8000/api/v1/`
- Documentación OpenAPI: `http://127.0.0.1:8000/api/docs/`
- Panel admin: `http://127.0.0.1:8000/admin/` (crear superusuario con `createsuperuser`)

### Pruebas

```powershell
cd backend
.\.venv\Scripts\pytest --cov=apps --cov-report=term-missing
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Abre `http://127.0.0.1:5173`: la **primera pantalla es el login** (`/login`). Tras ingresar (demo: cualquier RUC/correo/clave), accedes al panel. El menú lateral es **colapsable por módulos** (`frontend/src/navigation/modules.ts`).

**Logo:** coloca tu imagen en `frontend/public/branding/logo.png` (ver `public/branding/README.txt`); si no existe, se usa `logo.svg`.

**Usuarios y login (backend):** no crees una tabla `usuario` manual en SQL; usa `auth_user` de Django y `PerfilUsuario`. Guía: `backend/docs/AUTENTICACION.md`. Comando: `python manage.py crear_usuario_empresa --help`.

## Documentación de arquitectura

Ver `backend/docs/ARQUITECTURA.md` (capas, módulos, flujos venta/compra/cobranza, validaciones).

## Módulos funcionales

1. Ventas e ingresos (POS, documentos, pedidos, cotizaciones, guías/NC)  
2. Compras y gastos  
3. Tesorería y cobranzas  
4. Inventario y almacén  
5. Restaurante  
6. Contabilidad y reportes  
7. Administración y mi cuenta  

Cada uno tiene rutas bajo `/api/v1/<modulo>/` y una vista introductoria en el frontend.
