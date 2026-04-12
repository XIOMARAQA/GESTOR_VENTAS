import { createRouter, createWebHistory } from 'vue-router'

import { isLoggedIn, readHasTenantEmpresa, readIsSuperuser } from '@/auth/session'
import AppShell from '@/layouts/AppShell.vue'

function defaultAuthedPath(): string {
  if (readIsSuperuser() && !readHasTenantEmpresa()) return '/plataforma'
  return '/panel'
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: AppShell,
      meta: { requiresAuth: true },
      redirect: () => defaultAuthedPath(),
      children: [
        {
          path: 'plataforma',
          name: 'plataforma-home',
          meta: { superuserOnly: true },
          component: () => import('@/views/plataforma/PlataformaHomeView.vue'),
        },
        {
          path: 'plataforma/empresas/activas',
          name: 'plataforma-empresas-activas',
          meta: { superuserOnly: true },
          component: () => import('@/views/plataforma/PlataformaEmpresasView.vue'),
        },
        {
          path: 'plataforma/empresas/pendientes',
          name: 'plataforma-empresas-pendientes',
          meta: { superuserOnly: true },
          component: () => import('@/views/plataforma/PlataformaEmpresasView.vue'),
        },
        {
          path: 'plataforma/empresas/inactivas',
          name: 'plataforma-empresas-inactivas',
          meta: { superuserOnly: true },
          component: () => import('@/views/plataforma/PlataformaEmpresasView.vue'),
        },
        {
          path: 'plataforma/empresas',
          redirect: '/plataforma/empresas/activas',
        },
        {
          path: 'plataforma/equipo',
          name: 'plataforma-equipo',
          meta: { superuserOnly: true },
          component: () => import('@/views/plataforma/PlataformaEquipoView.vue'),
        },
        {
          path: 'panel',
          name: 'panel',
          component: () => import('@/views/panel/PanelDashboardView.vue'),
        },
        { path: 'maestros/productos', component: () => import('@/views/maestros/ProductosView.vue') },
        { path: 'maestros/clientes', component: () => import('@/views/maestros/ClientesView.vue') },
        { path: 'maestros/categorias', component: () => import('@/views/maestros/CategoriasView.vue') },
        { path: 'maestros/marcas', component: () => import('@/views/maestros/MarcasView.vue') },
        { path: 'maestros/unidades', component: () => import('@/views/maestros/UnidadesView.vue') },
        { path: 'maestros/proveedores', component: () => import('@/views/maestros/ProveedoresView.vue') },
        { path: 'maestros/vendedores', component: () => import('@/views/maestros/VendedoresView.vue') },
        {
          path: 'ventas/documentos',
          component: () => import('@/views/ventas/VentasDocumentosView.vue'),
        },
        {
          path: 'ventas/cotizaciones',
          component: () => import('@/views/ventas/VentasCotizacionesView.vue'),
        },
        {
          path: 'compras/documentos',
          component: () => import('@/views/compras/ComprasDocumentosView.vue'),
        },
        {
          path: 'tesoreria/cobranzas',
          component: () => import('@/views/tesoreria/TesoreriaCobranzasView.vue'),
        },
        { path: 'tesoreria/pagos', component: () => import('@/views/tesoreria/TesoreriaPagosView.vue') },
        {
          path: 'tesoreria/cuentas-por-pagar',
          component: () => import('@/views/tesoreria/TesoreriaCronogramaView.vue'),
        },
        {
          path: 'tesoreria/pagos-proveedores',
          component: () => import('@/views/tesoreria/TesoreriaPagosProveedoresView.vue'),
        },
        { path: 'tesoreria/cronograma', redirect: '/tesoreria/cuentas-por-pagar' },
        { path: 'inventario/almacenes', component: () => import('@/views/inventario/InvAlmacenesView.vue') },
        { path: 'inventario/stock', component: () => import('@/views/inventario/InvStockView.vue') },
        {
          path: 'inventario/movimientos',
          component: () => import('@/views/inventario/InvMovimientosView.vue'),
        },
        { path: 'admin/org', component: () => import('@/views/admin/OrgView.vue') },
        { path: 'admin/sistema', component: () => import('@/views/admin/SistemaView.vue') },
        { path: 'admin/tareas', component: () => import('@/views/admin/TareasView.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const logged = isLoggedIn()
  if (to.path === '/login' && logged) {
    return { path: defaultAuthedPath() }
  }
  const needsAuth = to.matched.some((record) => record.meta.requiresAuth)
  if (needsAuth && !logged) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  const superOnly = to.matched.some((record) => record.meta.superuserOnly)
  if (superOnly && !readIsSuperuser()) {
    return { path: '/panel' }
  }
  const isPlataformaRoute = to.path === '/plataforma' || to.path.startsWith('/plataforma/')
  if (logged && readIsSuperuser() && !readHasTenantEmpresa() && !isPlataformaRoute) {
    return { path: '/plataforma' }
  }
  return true
})

export default router
