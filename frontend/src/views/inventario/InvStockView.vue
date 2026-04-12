<script setup lang="ts">
import type { AxiosResponse } from 'axios'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type StockRow = {
  id: number
  item?: number
  item_codigo?: string
  item_nombre?: string
  almacen?: number
  almacen_nombre?: string
  cantidad?: string | number
}

type AlmOpt = { id: number; nombre: string }
type ItemOpt = { id: number; codigo?: string; nombre: string }
type StockPaginated = { results?: StockRow[]; next?: string | null }

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const rows = ref<StockRow[]>([])
const almacenes = ref<AlmOpt[]>([])
const items = ref<ItemOpt[]>([])
const loading = ref(true)
const exporting = ref(false)
const err = ref('')

const filtroCodigo = ref('')
const filtroNombreProducto = ref('')
const filtroAlmacenId = ref<number | ''>('')
const filtroProductoId = ref<number | ''>('')

let debounceTimer: ReturnType<typeof setTimeout> | null = null

const bloqueadoSinEmpresa = computed(() => isSuperuser.value && !empresaId.value)

function appendEmpresaParams(params: URLSearchParams) {
  if (isSuperuser.value && empresaId.value) {
    params.set('empresa', String(empresaId.value))
  }
}

function scheduleLoadStock() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debounceTimer = null
    void loadStock()
  }, 320)
}

function formatQty(v: unknown): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return n.toLocaleString('es-PE', { minimumFractionDigits: 0, maximumFractionDigits: 4 })
}

async function loadAlmacenes() {
  try {
    const params = new URLSearchParams()
    params.set('page_size', '500')
    params.set('ordering', 'nombre')
    params.set('activo', '1')
    appendEmpresaParams(params)
    const { data } = await api.get<{ results?: AlmOpt[] }>(`/inventario/almacenes/?${params}`)
    almacenes.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch {
    almacenes.value = []
  }
}

async function loadItems() {
  try {
    const params = new URLSearchParams()
    params.set('page_size', '500')
    params.set('ordering', 'codigo')
    appendEmpresaParams(params)
    const { data } = await api.get<{ results?: ItemOpt[] }>(`/inventario/items/?${params}`)
    items.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch {
    items.value = []
  }
}

async function loadStock() {
  loading.value = true
  err.value = ''
  try {
    const params = new URLSearchParams()
    params.set('page_size', '500')
    appendEmpresaParams(params)
    const c = filtroCodigo.value.trim()
    if (c) params.set('codigo', c)
    const n = filtroNombreProducto.value.trim()
    if (n) params.set('nombre_producto', n)
    if (filtroAlmacenId.value !== '') params.set('almacen', String(filtroAlmacenId.value))
    if (filtroProductoId.value !== '') params.set('producto', String(filtroProductoId.value))
    const { data } = await api.get<{ results?: StockRow[] }>(`/inventario/stock/?${params}`)
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'las existencias')
    rows.value = []
  } finally {
    loading.value = false
  }
}

function limpiarFiltros() {
  filtroCodigo.value = ''
  filtroNombreProducto.value = ''
  filtroAlmacenId.value = ''
  filtroProductoId.value = ''
  void loadStock()
}

function buildStockParamsForExport(): URLSearchParams {
  const params = new URLSearchParams()
  params.set('page_size', '5000')
  appendEmpresaParams(params)
  const c = filtroCodigo.value.trim()
  if (c) params.set('codigo', c)
  const n = filtroNombreProducto.value.trim()
  if (n) params.set('nombre_producto', n)
  if (filtroAlmacenId.value !== '') params.set('almacen', String(filtroAlmacenId.value))
  if (filtroProductoId.value !== '') params.set('producto', String(filtroProductoId.value))
  return params
}

function drfRelativePath(next: string): string {
  const u = new URL(next)
  const idx = u.pathname.indexOf('/api/v1/')
  if (idx >= 0) return u.pathname.slice(idx + '/api/v1'.length) + u.search
  return u.pathname + u.search
}

async function fetchAllStockForExport(): Promise<StockRow[]> {
  const acc: StockRow[] = []
  let path: string | null = `/inventario/stock/?${buildStockParamsForExport()}`
  while (path) {
    const res: AxiosResponse<StockRow[] | StockPaginated> = await api.get<
      StockRow[] | StockPaginated
    >(path)
    const data = res.data
    const chunk: StockRow[] = Array.isArray(data) ? data : (data.results ?? [])
    acc.push(...chunk)
    const nextUrl: string | null =
      !Array.isArray(data) && typeof data.next === 'string' && data.next ? data.next : null
    path = nextUrl ? drfRelativePath(nextUrl) : null
  }
  return acc
}

function escapeCsvCell(s: string): string {
  if (/[;"\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

async function descargarExcel() {
  if (bloqueadoSinEmpresa.value) return
  exporting.value = true
  err.value = ''
  try {
    const dataRows = await fetchAllStockForExport()
    const sep = ';'
    const headers = ['Código', 'Nombre del producto', 'Almacén', 'Cantidad']
    const lines = [headers.map(escapeCsvCell).join(sep)]
    for (const r of dataRows) {
      const cod = (r.item_codigo || '').trim()
      const nom = r.item_nombre || ''
      const alm = r.almacen_nombre || ''
      const qty = formatQty(r.cantidad)
      lines.push([cod, nom, alm, qty === '—' ? '' : qty].map(escapeCsvCell).join(sep))
    }
    const bom = '\uFEFF'
    const blob = new Blob([bom + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    const d = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    a.href = URL.createObjectURL(blob)
    a.download = `existencias_${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'la exportación')
  } finally {
    exporting.value = false
  }
}

function itemLabel(it: ItemOpt): string {
  const c = (it.codigo || '').trim()
  return c ? `${c} — ${it.nombre}` : it.nombre
}

onMounted(async () => {
  await ctx.ensureEmpresa()
  await Promise.all([loadAlmacenes(), loadItems()])
  await loadStock()
})

watch([filtroCodigo, filtroNombreProducto], () => scheduleLoadStock())
watch([filtroAlmacenId, filtroProductoId], () => void loadStock())
watch(empresaId, async () => {
  filtroProductoId.value = ''
  await Promise.all([loadAlmacenes(), loadItems(), loadStock()])
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title">Existencias</h1>
        <p class="lead">
          Consulte la cantidad disponible por <strong>producto</strong> y <strong>almacén</strong>. Los valores provienen
          de los movimientos de inventario registrados en el sistema.
        </p>
      </div>
      <div class="head-actions">
        <button type="button" class="btn-ref" :disabled="loading" @click="loadStock">
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="bloqueadoSinEmpresa" class="warn">
      Modo administrador global: elija una empresa en la barra superior para acotar almacenes, productos y existencias.
    </p>
    <p v-if="err" class="err">{{ err }}</p>

    <div class="filters">
      <label class="f">
        <span class="flab">Código producto</span>
        <input v-model="filtroCodigo" type="text" class="inp" placeholder="Contiene…" autocomplete="off" />
      </label>
      <label class="f">
        <span class="flab">Nombre producto</span>
        <input v-model="filtroNombreProducto" type="text" class="inp" placeholder="Contiene…" autocomplete="off" />
      </label>
      <label class="f">
        <span class="flab">Almacén</span>
        <select v-model="filtroAlmacenId" class="inp inp--select">
          <option value="">Todos</option>
          <option v-for="a in almacenes" :key="a.id" :value="a.id">{{ a.nombre }}</option>
        </select>
      </label>
      <label class="f">
        <span class="flab">Producto</span>
        <select
          v-model="filtroProductoId"
          class="inp inp--select inp--producto"
          :disabled="bloqueadoSinEmpresa"
          :title="bloqueadoSinEmpresa ? 'Seleccione empresa en la barra superior' : ''"
        >
          <option value="">Todos</option>
          <option v-for="it in items" :key="it.id" :value="it.id">{{ itemLabel(it) }}</option>
        </select>
      </label>
      <div class="filters-end">
        <button type="button" class="btn-clear" :disabled="loading || exporting" @click="limpiarFiltros">
          Limpiar filtros
        </button>
        <button
          type="button"
          class="btn-excel"
          :disabled="loading || exporting || bloqueadoSinEmpresa"
          title="Descargar listado (Excel / CSV)"
          aria-label="Descargar existencias en Excel"
          @click="descargarExcel"
        >
          <svg class="btn-excel__ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              fill="#217346"
              d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
            />
            <path stroke="#fff" stroke-width="1.2" stroke-linecap="round" d="M14 2v6h6M8 10h8M8 14h8M8 18h5" />
          </svg>
        </button>
        <p class="total">{{ rows.length }} registro(s)</p>
      </div>
    </div>

    <div class="card">
      <div v-if="loading" class="muted">Cargando…</div>
      <div v-else class="table-wrap">
        <template v-if="rows.length === 0">
          <div class="empty" role="status">
            <div class="empty__ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M20 7l-8 4-8-4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                />
              </svg>
            </div>
            <p class="empty__title">Sin existencias que mostrar</p>
            <p class="empty__text">
              No hay filas de stock para los criterios elegidos, o aún no se registran movimientos que generen saldo en
              almacén.
            </p>
          </div>
        </template>
        <table v-else class="t">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nombre del producto</th>
              <th>Almacén</th>
              <th class="th-num">Cantidad</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td class="td-code">{{ (r.item_codigo || '').trim() || '—' }}</td>
              <td class="td-name">{{ r.item_nombre || '—' }}</td>
              <td>{{ r.almacen_nombre || '—' }}</td>
              <td class="td-num">{{ formatQty(r.cantidad) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: 1200px;
  color: #0f172a;
}
.head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.title {
  margin: 0 0 0.35rem;
  font-size: 1.2rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.lead {
  margin: 0 0 0.85rem;
  font-size: 0.88rem;
  color: #475569;
  line-height: 1.5;
  max-width: 48rem;
}
.lead strong {
  color: #334155;
  font-weight: 600;
}
.head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: flex-start;
}
.btn-ref {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  font-family: inherit;
  color: #0f172a;
}
.btn-ref:hover:not(:disabled) {
  border-color: #0e7490;
  color: #0e7490;
}
.btn-ref:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.warn {
  font-size: 0.85rem;
  color: #9a3412;
  background: #ffedd5;
  border: 1px solid #fdba74;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  margin: 0 0 0.75rem;
}
.err {
  color: #991b1b;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.5;
  margin: 0 0 0.75rem;
  padding: 0.65rem 0.85rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 1rem;
}
.f {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.flab {
  font-size: 0.72rem;
  font-weight: 600;
  color: #64748b;
}
.inp {
  padding: 0.45rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.875rem;
  min-width: 10rem;
  color: #0f172a;
  background: #fff;
}
.inp--select {
  min-width: 12rem;
  cursor: pointer;
}
.inp--producto {
  min-width: 14rem;
  max-width: 22rem;
}
.btn-clear {
  padding: 0.45rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-weight: 600;
  font-size: 0.78rem;
  cursor: pointer;
  font-family: inherit;
  color: #475569;
}
.btn-clear:hover:not(:disabled) {
  border-color: #cbd5e1;
  color: #0f172a;
}
.filters-end {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.5rem;
  margin-left: auto;
}
.btn-excel {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border-radius: 8px;
  border: 1px solid #86efac;
  background: #f0fdf4;
  cursor: pointer;
  font-family: inherit;
}
.btn-excel:hover:not(:disabled) {
  background: #dcfce7;
  border-color: #22c55e;
}
.btn-excel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-excel__ico {
  width: 1.2rem;
  height: 1.2rem;
}
.total {
  margin: 0;
  font-size: 0.8rem;
  color: #64748b;
  margin-left: auto;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 0;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  border: 1px solid #e2e8f0;
  overflow: hidden;
}
.table-wrap {
  overflow-x: auto;
  min-height: 8rem;
}
.t {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}
.t th,
.t td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  color: #0f172a;
}
.t th {
  background: #f1f5f9;
  font-size: 0.8125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #334155;
}
.t td {
  font-weight: 500;
  font-size: 0.8125rem;
}
.th-num,
.td-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.td-name {
  font-weight: 600;
}
.td-code {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #475569;
}
.muted {
  padding: 1.5rem;
  color: #94a3b8;
  text-align: center;
}
.empty {
  padding: 2.25rem 1.5rem 2.5rem;
  text-align: center;
  max-width: 26rem;
  margin: 0 auto;
}
.empty__ico {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3.25rem;
  height: 3.25rem;
  border-radius: 14px;
  background: linear-gradient(135deg, #ecfdf5, #ccfbf1);
  color: #0f766e;
  margin-bottom: 1rem;
}
.empty__ico svg {
  width: 1.75rem;
  height: 1.75rem;
}
.empty__title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
}
.empty__text {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.55;
  color: #64748b;
}
</style>
