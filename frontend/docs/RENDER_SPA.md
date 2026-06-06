# Vue Router en Render (recarga de `/panel`, `/login`, etc.)

Vue usa rutas del navegador (`createWebHistory`). Al **recargar** una URL como `/panel`, el servidor debe devolver `index.html`, no un 404.

## Opción A — Rewrite en Render (recomendado)

**GESTOR_VENTAS-frontend** → **Redirects/Rewrites** → añadir:

| Source | Destination | Action |
|--------|-------------|--------|
| `/*` | `/index.html` | **Rewrite** |

Luego **Manual Deploy**.

## Opción B — Automático en el código (activo)

En **producción** el router usa `createWebHashHistory`: la URL pasa a ser `...onrender.com/#/panel`. Al recargar, el servidor solo pide `/` y no falla.

En **local** (`npm run dev`) sigue `createWebHistory` (sin `#`).

Tras cambiar esto, haz **deploy del front** de nuevo.
