<script setup lang="ts">
import axios from 'axios'
import { storeToRefs } from 'pinia'
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage as listLoadErr } from '@/utils/listLoadErrorMessage'

const route = useRoute()
const router = useRouter()
const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

function idsFromDocumentosQuery(): number[] {
  const raw = route.query.documentos
  const s = typeof raw === 'string' ? raw : Array.isArray(raw) ? raw[0] : ''
  if (!s || typeof s !== 'string') return []
  return [
    ...new Set(
      s
        .split(',')
        .map((x) => parseInt(x.trim(), 10))
        .filter((n) => Number.isFinite(n) && n > 0),
    ),
  ]
}

const TIPO_CORTO: Record<string, string> = {
  FACTURA_COMPRA: 'FC',
  NOTA_CREDITO_PROVEEDOR: 'NC',
}

const tipoOptions = [
  { value: '', label: 'Todos' },
  { value: 'FACTURA_COMPRA', label: 'Factura de compra' },
  { value: 'NOTA_CREDITO_PROVEEDOR', label: 'N. crédito proveedor' },
]

type PagoRow = {
  id: number
  monto: string | number
  metodo: string
  creado_en: string
  cronograma_pago: number | null
  documento_compra_id: number | null
  documento_compra_numero?: string | null
  proveedor_razon_social?: string | null
  documento_compra_tipo?: string | null
}

const filters = reactive({
  proveedor_documento: '',
  proveedor_razon_social: '',
  tipo: '',
  serie: '',
  numero: '',
  fecha_documento_desde: '',
  fecha_documento_hasta: '',
  fecha_pago_desde: '',
  fecha_pago_hasta: '',
  metodo: '',
})

/** Fuerza recálculo del endpoint tras debounce de filtros. */
const filterTick = ref(0)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => ({ ...filters }),
  () => {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      filterTick.value += 1
    }, 320)
  },
  { deep: true },
)

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

const rows = ref<PagoRow[]>([])
const loading = ref(false)
const error = ref('')
const revertingId = ref<number | null>(null)

const moneyFmt = new Intl.NumberFormat('es-PE', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatMoney(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n) ? moneyFmt.format(n) : '—'
}

function formatDate(v: unknown): string {
  if (v == null || typeof v !== 'string') return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v)
  if (!m) return String(v)
  return `${m[3]}/${m[2]}/${m[1]}`
}

function labelTipoCorto(v: unknown): string {
  if (v == null || typeof v !== 'string') return '—'
  return TIPO_CORTO[v] ?? v.slice(0, 3).toUpperCase()
}

const documentosDesdeRuta = computed(() => idsFromDocumentosQuery())

const listEndpoint = computed(() => {
  void filterTick.value
  const params = new URLSearchParams()
  params.set('page_size', '150')
  if (isSuperuser.value && empresaId.value) {
    params.set('empresa_id', String(empresaId.value))
  }
  const docIds = documentosDesdeRuta.value
  if (docIds.length) {
    params.set('documentos', docIds.join(','))
  }
  if (filters.proveedor_documento.trim()) {
    params.set('proveedor_documento', filters.proveedor_documento.trim())
  }
  if (filters.proveedor_razon_social.trim()) {
    params.set('proveedor_razon_social', filters.proveedor_razon_social.trim())
  }
  if (filters.tipo.trim()) params.set('tipo', filters.tipo.trim())
  if (filters.serie.trim()) params.set('serie', filters.serie.trim())
  if (filters.numero.trim()) params.set('numero', filters.numero.trim())
  if (filters.fecha_documento_desde) params.set('fecha_documento_desde', filters.fecha_documento_desde)
  if (filters.fecha_documento_hasta) params.set('fecha_documento_hasta', filters.fecha_documento_hasta)
  if (filters.fecha_pago_desde) params.set('fecha_pago_desde', filters.fecha_pago_desde)
  if (filters.fecha_pago_hasta) params.set('fecha_pago_hasta', filters.fecha_pago_hasta)
  if (filters.metodo.trim()) params.set('metodo', filters.metodo.trim())
  return `/tesoreria/pagos-proveedores/?${params}`
})

async function loadPagos() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<{ results?: PagoRow[] }>(listEndpoint.value)
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    error.value = listLoadErr(e, 'los pagos realizados a proveedores')
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(listEndpoint, () => loadPagos(), { immediate: true })

function clearFilters() {
  filters.proveedor_documento = ''
  filters.proveedor_razon_social = ''
  filters.tipo = ''
  filters.serie = ''
  filters.numero = ''
  filters.fecha_documento_desde = ''
  filters.fecha_documento_hasta = ''
  filters.fecha_pago_desde = ''
  filters.fecha_pago_hasta = ''
  filters.metodo = ''
}

function clearRouteDocumentos() {
  void router.replace({ path: '/tesoreria/pagos-proveedores', query: {} })
}

const hasBarFilters = computed(() => {
  return !!(
    filters.proveedor_documento.trim() ||
    filters.proveedor_razon_social.trim() ||
    filters.tipo.trim() ||
    filters.serie.trim() ||
    filters.numero.trim() ||
    filters.fecha_documento_desde ||
    filters.fecha_documento_hasta ||
    filters.fecha_pago_desde ||
    filters.fecha_pago_hasta ||
    filters.metodo.trim()
  )
})

const emptyMsg =
  'Cuando registre un pago en Cuentas por pagar, el movimiento aparecerá aquí de inmediato. Si la tabla sigue vacía, aún no hay pagos registrados en el sistema para su empresa.'

const filteredEmptyMsg =
  'Ningún pago coincide con los filtros actuales. Amplíe el rango de fechas, quite criterios o use «Limpiar filtros».'

function apiErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e) && e.response?.data) {
    const d = e.response.data as Record<string, unknown>
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) return d.detail.map(String).join(' ')
  }
  return 'No se pudo completar la operación.'
}

async function revertirPago(row: PagoRow) {
  if (row.cronograma_pago == null) return
  const ok = window.confirm(
    '¿Revertir este pago? La obligación volverá a pendiente en Cuentas por pagar y este movimiento dejará de figurar aquí.',
  )
  if (!ok) return
  revertingId.value = row.id
  try {
    await api.post(`/tesoreria/pagos-proveedores/${row.id}/revertir/`)
    await loadPagos()
  } catch (e) {
    window.alert(apiErrorMessage(e))
  } finally {
    revertingId.value = null
  }
}

function canRevertir(row: PagoRow) {
  return row.cronograma_pago != null
}
</script>

<template>
  <div class="pagos-page">
    <header class="page-head">
      <div class="page-head__top">
        <div>
          <h1 class="page-title">Pagos realizados</h1>
          <p class="page-lead">
            Historial de abonos a proveedores registrados desde
            <strong>Cuentas por pagar</strong>. Filtre por comprobante, proveedor o fechas; si un pago fue un error, use
            <strong>Revertir</strong> en la fila para dejar la cuota otra vez en pendiente.
          </p>
        </div>
      </div>

      <div class="panel-inline">
        <span class="panel-inline__text">
          Registrar pagos:
          <RouterLink class="text-link" to="/tesoreria/cuentas-por-pagar">Cuentas por pagar</RouterLink>
          ·
          <RouterLink class="text-link" to="/compras/documentos">Facturas de proveedores</RouterLink>
        </span>
      </div>
    </header>

    <p v-if="documentosDesdeRuta.length" class="route-banner">
      Vista acotada por enlace ({{ documentosDesdeRuta.length }} documento(s) de compra).
      <button type="button" class="linkish" @click="clearRouteDocumentos">Quitar acotación</button>
    </p>

    <section class="filters" aria-label="Filtros de pagos">
      <div class="filter-row filter-row--primary">
        <div class="filter-pair" aria-label="Proveedor">
          <label class="filter-field filter-field--ruc">
            <span class="filter-label">RUC / doc.</span>
            <input
              v-model="filters.proveedor_documento"
              type="text"
              class="filter-inp"
              placeholder="Documento del proveedor"
              maxlength="20"
              autocomplete="off"
            />
          </label>
          <label class="filter-field filter-field--rs">
            <span class="filter-label">Razón social</span>
            <input
              v-model="filters.proveedor_razon_social"
              type="text"
              class="filter-inp"
              placeholder="Nombre o razón social"
              autocomplete="off"
            />
          </label>
        </div>
        <label class="filter-field filter-field--sm">
          <span class="filter-label">Tipo</span>
          <select v-model="filters.tipo" class="filter-inp filter-select">
            <option v-for="opt in tipoOptions" :key="opt.label" :value="opt.value">{{ opt.label }}</option>
          </select>
        </label>
        <label class="filter-field filter-field--xs">
          <span class="filter-label">Serie</span>
          <input v-model="filters.serie" type="text" class="filter-inp" placeholder="F001" maxlength="10" />
        </label>
        <label class="filter-field filter-field--xs">
          <span class="filter-label">Número</span>
          <input v-model="filters.numero" type="text" class="filter-inp" placeholder="N°" maxlength="20" />
        </label>
        <label class="filter-field filter-field--date">
          <span class="filter-label">Doc. desde</span>
          <input v-model="filters.fecha_documento_desde" type="date" class="filter-inp" />
        </label>
        <label class="filter-field filter-field--date">
          <span class="filter-label">Doc. hasta</span>
          <input v-model="filters.fecha_documento_hasta" type="date" class="filter-inp" />
        </label>
      </div>
      <div class="filter-row filter-row--secondary">
        <label class="filter-field filter-field--date">
          <span class="filter-label">Pago desde</span>
          <input v-model="filters.fecha_pago_desde" type="date" class="filter-inp" />
        </label>
        <label class="filter-field filter-field--date">
          <span class="filter-label">Pago hasta</span>
          <input v-model="filters.fecha_pago_hasta" type="date" class="filter-inp" />
        </label>
        <label class="filter-field filter-field--metodo">
          <span class="filter-label">Método</span>
          <input
            v-model="filters.metodo"
            type="text"
            class="filter-inp"
            placeholder="Ej. EFECTIVO"
            maxlength="30"
            autocomplete="off"
          />
        </label>
        <div class="filter-actions">
          <button type="button" class="btn-clear-filters" :disabled="!hasBarFilters" @click="clearFilters">
            Limpiar filtros
          </button>
        </div>
      </div>
    </section>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Tipo</th>
            <th>Doc. compra</th>
            <th>Proveedor</th>
            <th class="num">Monto</th>
            <th>Método</th>
            <th>Fecha pago</th>
            <th>Cuota</th>
            <th class="th-actions">Acciones</th>
          </tr>
        </thead>
        <tbody v-if="loading">
          <tr>
            <td colspan="8" class="td-state muted">Cargando…</td>
          </tr>
        </tbody>
        <tbody v-else-if="error">
          <tr>
            <td colspan="8" class="td-state err">{{ error }}</td>
          </tr>
        </tbody>
        <tbody v-else>
          <tr v-for="row in rows" :key="row.id">
            <td
              class="td-tipo"
              :title="row.documento_compra_tipo != null ? String(row.documento_compra_tipo) : undefined"
            >
              {{ labelTipoCorto(row.documento_compra_tipo) }}
            </td>
            <td>
              <RouterLink
                v-if="row.documento_compra_id != null"
                class="cell-link"
                :to="{ path: '/compras/documentos', query: { documento: String(row.documento_compra_id) } }"
              >
                {{ row.documento_compra_numero ?? `#${row.documento_compra_id}` }}
              </RouterLink>
              <span v-else class="muted-cell">Sin documento</span>
            </td>
            <td>{{ row.proveedor_razon_social?.trim() || '—' }}</td>
            <td class="num">{{ formatMoney(row.monto) }}</td>
            <td>{{ row.metodo || '—' }}</td>
            <td>{{ formatDate(row.creado_en) }}</td>
            <td class="td-cob">
              <span v-if="row.cronograma_pago != null" class="mono">{{ row.cronograma_pago }}</span>
              <span v-else class="muted-cell">—</span>
            </td>
            <td class="td-actions">
              <button
                type="button"
                class="btn-revert"
                :disabled="!canRevertir(row) || revertingId === row.id"
                :title="
                  canRevertir(row)
                    ? 'Quita este pago y deja la cuota pendiente otra vez'
                    : 'Sin cuota vinculada; no se puede revertir aquí'
                "
                @click="revertirPago(row)"
              >
                {{ revertingId === row.id ? '…' : 'Revertir' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!loading && !error && !rows.length" class="muted empty-msg">
        {{ hasBarFilters || documentosDesdeRuta.length ? filteredEmptyMsg : emptyMsg }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.pagos-page {
  width: 100%;
  max-width: 1200px;
}

.page-head {
  margin-bottom: 0.75rem;
}

.page-head__top {
  margin-bottom: 0.65rem;
  padding-bottom: 0.85rem;
  border-bottom: 3px solid #0d9488;
}

.page-title {
  margin: 0 0 0.4rem;
  font-size: 1.5rem;
  font-weight: 800;
  color: #020617;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.page-lead {
  margin: 0;
  max-width: 46rem;
  font-size: 0.9rem;
  line-height: 1.55;
  color: #475569;
}

.page-lead strong {
  color: #334155;
  font-weight: 700;
}

.panel-inline {
  padding: 0.5rem 0;
}

.panel-inline__text {
  font-size: 0.82rem;
  color: #64748b;
}

.text-link {
  color: #0f766e;
  font-weight: 600;
  text-decoration: none;
}

.text-link:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.route-banner {
  margin: 0 0 0.65rem;
  padding: 0.45rem 0.65rem;
  font-size: 0.8rem;
  color: #334155;
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.linkish {
  padding: 0;
  border: none;
  background: none;
  color: #0f766e;
  font-weight: 700;
  font-size: inherit;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  font-family: inherit;
}

.filters {
  background: #fff;
  border-radius: 12px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.85rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgb(15 23 42 / 6%);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.65rem 0.85rem;
}

.filter-row--primary {
  row-gap: 0.75rem;
}

.filter-row--secondary {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #f1f5f9;
}

.filter-pair {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.65rem;
  flex: 1 1 14rem;
  min-width: min(100%, 18rem);
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.filter-field--ruc {
  flex: 0 1 9rem;
  min-width: 7rem;
}

.filter-field--rs {
  flex: 1 1 12rem;
  min-width: 10rem;
}

.filter-field--sm {
  flex: 0 1 9.5rem;
}

.filter-field--xs {
  flex: 0 1 5.5rem;
}

.filter-field--date {
  flex: 0 1 9.5rem;
}

.filter-field--metodo {
  flex: 0 1 10rem;
  min-width: 8rem;
}

.filter-actions {
  display: flex;
  align-items: flex-end;
  flex: 1 1 auto;
  justify-content: flex-end;
}

.filter-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.filter-inp {
  width: 100%;
  padding: 0.45rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.85rem;
  background: #fff;
  color: #0f172a;
}

.filter-inp:focus {
  outline: none;
  border-color: #0d9488;
  box-shadow: 0 0 0 2px rgb(13 148 136 / 22%);
}

.filter-select {
  cursor: pointer;
}

.btn-clear-filters {
  padding: 0.45rem 0.85rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
}

.btn-clear-filters:hover:not(:disabled) {
  border-color: #94a3b8;
  color: #0f172a;
}

.btn-clear-filters:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.table-wrap {
  background: #fff;
  border-radius: 10px;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 10%);
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

th,
td {
  text-align: left;
  padding: 0.55rem 0.7rem;
  border-bottom: 1px solid #e2e8f0;
}

th {
  background: #f1f5f9;
  font-weight: 700;
  font-size: 0.8125rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #334155;
}

td {
  color: #0f172a;
  font-weight: 500;
  font-size: 0.8125rem;
}

th.num,
td.num {
  text-align: right;
}

.th-actions {
  width: 6.5rem;
  text-align: center;
}

.td-actions {
  text-align: center;
  vertical-align: middle;
}

.btn-revert {
  padding: 0.3rem 0.55rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: #991b1b;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  cursor: pointer;
  font-family: inherit;
}

.btn-revert:hover:not(:disabled) {
  background: #fee2e2;
  border-color: #f87171;
}

.btn-revert:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

tbody tr:hover {
  background: #f8fafc;
}

.td-tipo {
  font-weight: 800;
  color: #0f766e;
  width: 2.5rem;
}

.cell-link {
  color: #0f766e;
  font-weight: 700;
  text-decoration: none;
}

.cell-link:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.muted-cell {
  color: #94a3b8;
  font-size: 0.82rem;
}

.td-cob .mono {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #475569;
}

.muted {
  color: #475569;
}

.empty-msg {
  max-width: 42rem;
  line-height: 1.5;
  font-size: 0.84rem;
  color: #64748b;
  margin-top: 0.75rem;
}

.err {
  color: #b91c1c;
}

.td-state {
  padding: 1rem 0.85rem;
  text-align: left;
  font-size: 0.875rem;
  vertical-align: middle;
}

.td-state.err {
  color: #b91c1c;
  font-weight: 600;
  line-height: 1.5;
  max-width: 52rem;
}

</style>
