/**
 * Menú modular alineado al esquema de BD. `hint` se usa como tooltip (tabla / nota técnica).
 */
export type NavItem = {
  to: string
  label: string
  hint?: string
  /** Si true, solo activo en ruta exacta (p. ej. `/plataforma` vs `/plataforma/...`) */
  exact?: boolean
}

export type NavSection = {
  id: string
  label: string
  /** Solo visible si el usuario es superusuario de plataforma */
  superuserOnly?: boolean
  children: NavItem[]
}

export const navSections: NavSection[] = [
  {
    id: 'panel',
    label: 'Inicio',
    children: [
      {
        to: '/panel',
        label: 'Panel y métricas',
        hint: 'Agregados de documento_venta (emitidos)',
      },
    ],
  },
  {
    id: 'maestros',
    label: 'Datos maestros',
    children: [
      {
        to: '/maestros/productos',
        label: 'Productos y servicios',
        hint: 'inventario_item · plantilla/import Excel',
      },
      { to: '/maestros/clientes', label: 'Clientes', hint: 'cliente' },
      {
        to: '/maestros/categorias',
        label: 'Categorías de producto',
        hint: 'inventario_categoria → item.categoria_id, padre_id',
      },
      { to: '/maestros/marcas', label: 'Marcas', hint: 'inventario_marca → item.marca_id (opc.)' },
      {
        to: '/maestros/unidades',
        label: 'Unidades de medida',
        hint: 'inventario_unidadmedida → item.unidad_medida_id',
      },
      { to: '/maestros/proveedores', label: 'Proveedores', hint: 'proveedor' },
      { to: '/maestros/vendedores', label: 'Vendedores', hint: 'vendedor → comprobantes' },
    ],
  },
  {
    id: 'ventas',
    label: 'Ventas e ingresos',
    children: [
      { to: '/ventas/documentos', label: 'Comprobantes de venta', hint: 'documento_venta' },
      { to: '/ventas/cotizaciones', label: 'Cotizaciones', hint: 'cotizacion' },
    ],
  },
  {
    id: 'compras',
    label: 'Compras y gastos',
    children: [{ to: '/compras/documentos', label: 'Facturas de proveedores', hint: 'documento_compra' }],
  },
  {
    id: 'tesoreria',
    label: 'Tesorería',
    children: [
      { to: '/tesoreria/cobranzas', label: 'Cuentas por cobrar', hint: 'cobranza' },
      { to: '/tesoreria/pagos', label: 'Pagos recibidos', hint: 'pago_recibido' },
      { to: '/tesoreria/cuentas-por-pagar', label: 'Cuentas por pagar', hint: 'cronograma_pago' },
      { to: '/tesoreria/pagos-proveedores', label: 'Pagos realizados', hint: 'pago_realizado_proveedor' },
    ],
  },
  {
    id: 'inventario',
    label: 'Inventario y almacén',
    children: [
      { to: '/inventario/almacenes', label: 'Almacenes y ubicaciones', hint: 'almacen' },
      { to: '/inventario/stock', label: 'Existencias', hint: 'stock' },
      { to: '/inventario/movimientos', label: 'Kardex y movimientos', hint: 'movimiento_stock' },
    ],
  },
  {
    id: 'admin',
    label: 'Administración',
    children: [
      { to: '/admin/org', label: 'Empresa y sucursales', hint: 'empresa, sucursal' },
      {
        to: '/admin/formato-comprobante-pdf',
        label: 'Formato comprobante PDF',
        hint: 'nubefact_pdf_formatos',
      },
      { to: '/admin/cambiar-contrasena', label: 'Cambiar contraseña', hint: 'auth' },
    ],
  },
  {
    id: 'plataforma',
    label: 'Plataforma',
    superuserOnly: true,
    children: [
      {
        to: '/plataforma',
        label: 'Resumen y KPIs',
        hint: 'Totales de empresas y administradores globales',
        exact: true,
      },
      {
        to: '/plataforma/empresas/activas',
        label: 'Empresas activas',
        hint: 'Clientes aprobados; abrir su panel',
      },
      {
        to: '/plataforma/empresas/pendientes',
        label: 'Pendientes de aprobación',
        hint: 'Altas web por revisar',
      },
      {
        to: '/plataforma/empresas/inactivas',
        label: 'Suspendidas o inactivas',
        hint: 'Solo consulta',
      },
      {
        to: '/plataforma/equipo',
        label: 'Superusuarios plataforma',
        hint: 'Cuentas con acceso total a la plataforma',
      },
    ],
  },
]

/**
 * Menú cuando el superusuario aún no eligió una empresa: visión global (sin pantallas vacías).
 */
export const navPlataformaSuperuser: NavSection[] = [
  {
    id: 'plataforma-inicio',
    label: 'Vista general',
    children: [
      {
        to: '/plataforma',
        label: 'Resumen y KPIs',
        hint: 'Cifras globales: empresas, pendientes, equipo',
        exact: true,
      },
    ],
  },
  {
    id: 'plataforma-empresas',
    label: 'Empresas y clientes',
    children: [
      {
        to: '/plataforma/empresas/activas',
        label: 'Activas',
        hint: 'Abrir el sistema de cada cliente',
      },
      {
        to: '/plataforma/empresas/pendientes',
        label: 'Pendientes de aprobación',
        hint: 'Aprobar o rechazar registros',
      },
      {
        to: '/plataforma/empresas/inactivas',
        label: 'Suspendidas o inactivas',
        hint: 'Historial; sin operación',
      },
    ],
  },
  {
    id: 'plataforma-equipo',
    label: 'Equipo administrador',
    children: [
      {
        to: '/plataforma/equipo',
        label: 'Superusuarios plataforma',
        hint: 'Alta y mantenimiento de cuentas globales',
      },
    ],
  },
]
