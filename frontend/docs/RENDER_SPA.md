# Vue Router en Render (recarga de `/panel`, `/login`, etc.)

Vue usa rutas del navegador (`createWebHistory`). Al **recargar** una URL como `/panel`, el servidor debe devolver `index.html`, no un 404.

## Opción A — Rewrite en Render (recomendado)

**GESTOR_VENTAS-frontend** → **Redirects/Rewrites** → añadir:

| Source | Destination | Action |
|--------|-------------|--------|
| `/*` | `/index.html` | **Rewrite** |

Luego **Manual Deploy**.

## Opción B — Automático en el build

El `vite.config.ts` copia `index.html` → `404.html` en `dist/`. Render sirve esa página en rutas inexistentes y Vue Router toma el control.

Tras cambiar esto, haz **deploy del front** de nuevo.
