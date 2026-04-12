# Arquitectura técnica — Gestor de Ventas

## Capas

| Capa | Responsabilidad | Ubicación |
|------|-----------------|-----------|
| **Presentación** | HTTP, serialización JSON, OpenAPI | `apps/*/views.py`, `serializers.py`, `config/urls.py` |
| **Lógica de negocio** | Reglas, transacciones, orquestación entre módulos | `apps/*/services/` |
| **Datos** | Modelo relacional, integridad, migraciones | `apps/*/models.py` |

## Módulos Django (independientes)

Cada módulo es una `app` con modelos propios. Las dependencias cruzadas se limitan a **FK explícitas** y a **llamadas a servicios** en puntos definidos (p. ej. ventas → inventario + tesorería).

- `core`: empresa, sucursal, cliente, proveedor, perfil de usuario.
- `inventario`: ítems, categorías, atributos, almacenes, stock, movimientos, listas de precio.
- `ventas`: cotizaciones, documentos de venta, pedidos (POS / carga masiva vía `OrigenPedido`).
- `compras`: órdenes, documentos de compra (físico/electrónico), gastos recurrentes.
- `tesoreria`: bancos, cajas, cobranzas, pagos recibidos, cronograma, conciliaciones.
- `contabilidad`: plan de cuentas, asientos, comunicaciones de baja.
- `administracion`: configuración clave/valor JSON, tareas de usuario.

## Flujos principales

### Venta → inventario → tesorería

1. `DocumentoVenta` en `BORRADOR` con líneas (`DocumentoVentaLinea`).
2. **Emitir** (`DocumentoVentaService.emitir`): valida líneas y empresa del ítem.
3. Stock: factura, boleta y nota de venta → `StockService.aplicar_salida` (omite `Item.es_servicio`); nota de crédito cliente → `aplicar_ingreso` (devolución). Resumen de boletas y guía de remisión no mueven kardex en este flujo.
4. Estado pasa a `EMITIDO`.
5. `CobranzaService.crear_desde_documento`: crea registro de cobranza por el total.

### Compra → inventario

1. `DocumentoCompra` en borrador con líneas.
2. **Emitir** (`DocumentoCompraService.emitir`): factura de compra → `StockService.aplicar_ingreso`; nota de crédito proveedor → `aplicar_salida` (devolución al proveedor).

### Cobranza → pago

1. `POST .../cobranzas/{id}/registrar-pago/` con `monto`.
2. `CobranzaService.registrar_pago` valida que no exceda el pendiente y crea `PagoRecibido`.

## Validaciones destacadas

- Documentos emitidos: al menos una línea; cantidades &gt; 0; ítem de la misma empresa; almacén de la misma empresa que el documento.
- Stock: no saldo negativo en salidas (excepción `StockInsuficienteError`).
- Pagos: monto &gt; 0 y ≤ saldo pendiente de la cobranza.

## Pruebas y métricas

- **pytest** + **pytest-django** + **pytest-cov**: `pytest --cov=apps --cov-report=term-missing`
- Contrato de API: **drf-spectacular** en `/api/schema/` y **Swagger UI** en `/api/docs/`.

## Base de datos

- **PostgreSQL** en producción (`DATABASE_URL`).
- **SQLite** por defecto si no hay `DATABASE_URL` (solo desarrollo local).

## Integridad entre módulos

- Ventas no modifica tablas de tesorería directamente salvo vía `CobranzaService`.
- Movimientos de stock siempre pasan por `StockService` para mantener trazabilidad (`MovimientoStock` + líneas).

## Mapeo esquema SQL ↔ API ↔ Vue

El menú lateral del frontend se define en `frontend/src/navigation/modules.ts`: cada ítem tiene **ruta Vue**, **tabla lógica** (como en tu SQL) y consume el prefijo **`/api/v1/...`** indicado.

| Área | Tabla / origen (SQL de referencia) | Endpoint API |
|------|-----------------------------------|--------------|
| Maestros | `item` | `GET/POST …/inventario/items/` |
| Maestros | `cliente`, `proveedor` | `…/core/clientes/`, `…/core/proveedores/` |
| Maestros | `categoria`, `atributo` | `…/inventario/categorias/`, `…/inventario/atributos/` |
| Maestros | `item.unidad_medida` | Catálogo en UI (`/maestros/unidades`) |
| Ventas | `documento_venta` | `…/ventas/documentos/` + panel `…/ventas/reportes/dashboard/?empresa=&period=` |
| Ventas | `cotizacion`, `pedido` | `…/ventas/cotizaciones/`, `…/ventas/pedidos/` |
| Compras | `documento_compra`, `orden_compra`, `gasto_recurrente` | `…/compras/documentos/`, `ordenes/`, `gastos-recurrentes/` |
| Tesorería | `cobranza`, `pago_recibido`, etc. | `…/tesoreria/cobranzas/`, `pagos-recibidos/`, … |
| Inventario | `almacen`, `stock`, `movimiento_stock`, `lista_precio` | `…/inventario/almacenes/`, `stock/`, `movimientos/`, `listas-precio/` |
| Contabilidad | `plan_cuenta`, `asiento_contable`, `comunicacion_baja` | `…/contabilidad/plan-cuentas/`, `asientos/`, `comunicaciones-baja/` |
| Admin | `empresa`, `sucursal`, `configuracion_sistema`, `tarea` | `…/core/empresas/`, `sucursales/`, `…/administracion/configuracion/`, `tareas/` |

**Notas respecto al script SQL que compartiste:** Django usa `auth_user` (entero) para sesiones; tablas de negocio (`core_empresa`, `usuario`, etc.) usan `BigAutoField` (entero autoincremental en PostgreSQL). En `cobranza`, el ORM expone `monto_total` (equivalente lógico a pendiente + pagado en tu modelo). Los tipos enumerados en PostgreSQL en el script equivalen a `TextChoices` en Django.
