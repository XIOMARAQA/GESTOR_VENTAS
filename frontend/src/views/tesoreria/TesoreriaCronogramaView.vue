<script setup lang="ts">
import axios from 'axios'
import { storeToRefs } from 'pinia'
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

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

type CronogramaRow = {
  id: number
  documento_compra: number | null
  documento_compra_numero?: string | null
  documento_compra_tipo?: string | null
  proveedor_documento?: string | null
  proveedor_razon_social?: string | null
  descripcion?: string | null
  monto: string | number
  monto_pendiente?: string | number | null
  fecha_vencimiento: string | null
  estado: string
}

const vistaFiltro = ref<'pendiente' | 'todos'>('pendiente')

const filters = reactive({
  proveedor_documento: '',
  proveedor_razon_social: '',
  tipo: '',
  serie: '',
  numero: '',
  fecha_documento_desde: '',
  fecha_documento_hasta: '',
  fecha_vencimiento_desde: '',
  fecha_vencimiento_hasta: '',
  descripcion: '',
})

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

const rows = ref<CronogramaRow[]>([])
const loading = ref(false)
const error = ref('')
const selectedCronogramaIds = ref<number[]>([])

const modalOpen = ref(false)
const modalMetodo = ref('EFECTIVO')
const modalLines = ref<{ cronogramaId: number; comprobante: string; pendiente: string; monto: string }[]>([])
const modalError = ref('')
const modalSaving = ref(false)

const metodoOptions = [
  { value: 'EFECTIVO', label: 'Efectivo' },
  { value: 'TRANSFERENCIA', label: 'Transferencia' },
  { value: 'YAPE', label: 'Yape / Plin' },
  { value: 'POS', label: 'POS / Tarjeta' },
  { value: 'REGISTRO_MANUAL', label: 'Otro / manual' },
]

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

function estadoLabel(est: string): string {
  if (est === 'PAGADO') return 'Pagado'
  if (est === 'PENDIENTE') return 'Pendiente'
  return est || '—'
}

const documentosDesdeRuta = computed(() => idsFromDocumentosQuery())

const listEndpoint = computed(() => {
  void filterTick.value
  const params = new URLSearchParams()
  params.set('page_size', '150')
  if (isSuperuser.value && empresaId.value) {
    params.set('empresa_id', String(empresaId.value))
  }
  if (vistaFiltro.value === 'pendiente') {
    params.set('pendiente', '1')
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
  if (filters.fecha_vencimiento_desde) {
    params.set('fecha_vencimiento_desde', filters.fecha_vencimiento_desde)
  }
  if (filters.fecha_vencimiento_hasta) {
    params.set('fecha_vencimiento_hasta', filters.fecha_vencimiento_hasta)
  }
  if (filters.descripcion.trim()) params.set('descripcion', filters.descripcion.trim())
  return `/tesoreria/cronograma/?${params}`
})

async function loadRows() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<{ results?: CronogramaRow[] }>(listEndpoint.value)
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    error.value = listLoadErrorMessage(e, 'cuentas por pagar')
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(listEndpoint, () => {
  selectedCronogramaIds.value = []
  void loadRows()
})
void loadRows()

const filtroVistaHelp = computed(() =>
  vistaFiltro.value === 'pendiente'
    ? 'Solo obligaciones abiertas. El contado no genera filas aquí.'
    : 'Incluye cuotas ya marcadas como pagadas.',
)

const hasBarFilters = computed(() => {
  return !!(
    filters.proveedor_documento.trim() ||
    filters.proveedor_razon_social.trim() ||
    filters.tipo.trim() ||
    filters.serie.trim() ||
    filters.numero.trim() ||
    filters.fecha_documento_desde ||
    filters.fecha_documento_hasta ||
    filters.fecha_vencimiento_desde ||
    filters.fecha_vencimiento_hasta ||
    filters.descripcion.trim()
  )
})

function clearFilters() {
  filters.proveedor_documento = ''
  filters.proveedor_razon_social = ''
  filters.tipo = ''
  filters.serie = ''
  filters.numero = ''
  filters.fecha_documento_desde = ''
  filters.fecha_documento_hasta = ''
  filters.fecha_vencimiento_desde = ''
  filters.fecha_vencimiento_hasta = ''
  filters.descripcion = ''
}

function clearRouteDocumentos() {
  void router.replace({ path: '/tesoreria/cuentas-por-pagar', query: {} })
}

const emptyMsg =
  'Sin obligaciones a proveedor con los filtros actuales. Las compras al crédito registradas al ingresar stock generan cuotas aquí.'

function numPendiente(row: CronogramaRow): number {
  const n = Number(row.monto_pendiente)
  if (Number.isFinite(n) && n >= 0) return n
  if (row.estado === 'PAGADO') return 0
  const m = Number(row.monto)
  return Number.isFinite(m) ? m : 0
}

const selectedRows = computed(() => {
  const set = new Set(selectedCronogramaIds.value)
  return rows.value.filter((r) => typeof r.id === 'number' && set.has(r.id))
})

const canRegistrarPago = computed(() => {
  if (!selectedRows.value.length) return false
  return selectedRows.value.some((r) => r.estado === 'PENDIENTE' && numPendiente(r) > 0)
})

const pagosRealizadosLink = computed(() => {
  const docs = selectedRows.value
    .map((r) => (typeof r.documento_compra === 'number' ? r.documento_compra : null))
    .filter((x): x is number => x != null)
  const unique = [...new Set(docs)]
  if (unique.length) {
    return { path: '/tesoreria/pagos-proveedores', query: { documentos: unique.join(',') } } as const
  }
  return { path: '/tesoreria/pagos-proveedores' } as const
})

const allPageSelected = computed({
  get() {
    const ids = rows.value.map((r) => r.id).filter((id): id is number => typeof id === 'number')
    return ids.length > 0 && ids.every((id) => selectedCronogramaIds.value.includes(id))
  },
  set(checked: boolean) {
    const ids = rows.value.map((r) => r.id).filter((id): id is number => typeof id === 'number')
    if (checked) {
      selectedCronogramaIds.value = [...new Set([...selectedCronogramaIds.value, ...ids])]
    } else {
      const drop = new Set(ids)
      selectedCronogramaIds.value = selectedCronogramaIds.value.filter((id) => !drop.has(id))
    }
  },
})

function toggleRow(id: number) {
  const cur = selectedCronogramaIds.value
  const i = cur.indexOf(id)
  if (i >= 0) selectedCronogramaIds.value = cur.filter((x) => x !== id)
  else selectedCronogramaIds.value = [...cur, id]
}

function rowChecked(id: number) {
  return selectedCronogramaIds.value.includes(id)
}

function openModalRegistrar() {
  if (!canRegistrarPago.value) return
  modalError.value = ''
  modalMetodo.value = 'EFECTIVO'
  modalLines.value = selectedRows.value
    .filter((r) => r.estado === 'PENDIENTE' && numPendiente(r) > 0)
    .map((r) => ({
      cronogramaId: r.id,
      comprobante:
        typeof r.documento_compra_numero === 'string' && r.documento_compra_numero.trim()
          ? r.documento_compra_numero.trim()
          : `#${r.id}`,
      pendiente: formatMoney(r.monto_pendiente ?? r.monto),
      monto: String(numPendiente(r)),
    }))
  if (!modalLines.value.length) return
  modalOpen.value = true
}

function closeModal() {
  if (modalSaving.value) return
  modalOpen.value = false
}

function registrarErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e) && e.response?.data) {
    const d = e.response.data as Record<string, unknown>
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) return d.detail.map(String).join(' ')
  }
  return 'No se pudo registrar el pago.'
}

async function submitModal() {
  modalError.value = ''
  const toPost: { id: number; monto: number }[] = []
  for (const line of modalLines.value) {
    const raw = line.monto.replace(',', '.').trim()
    const n = Number(raw)
    if (!Number.isFinite(n) || n <= 0) continue
    toPost.push({ id: line.cronogramaId, monto: n })
  }
  if (!toPost.length) {
    modalError.value = 'Indique al menos un monto mayor que cero.'
    return
  }
  modalSaving.value = true
  try {
    for (const { id, monto } of toPost) {
      await api.post(`/tesoreria/cronograma/${id}/marcar-pagado/`, {
        monto,
        metodo: modalMetodo.value,
      })
    }
    modalOpen.value = false
    selectedCronogramaIds.value = []
    await loadRows()
  } catch (e) {
    modalError.value = registrarErrorMessage(e)
  } finally {
    modalSaving.value = false
  }
}

function clipText(s: string, max: number) {
  const t = s.trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}
</script>

<template>
  <div class="cron-page">
    <header class="page-head">
      <div class="page-head__top">
        <div>
          <h1 class="page-title">Cuentas por pagar</h1>
          <p class="page-lead">
            Seleccione una o varias cuotas para
            <strong>registrar un pago</strong> (aparece en Pagos realizados). Para deshacer un abono, use
            <strong>Revertir</strong> en Pagos realizados.
          </p>
        </div>
      </div>

      <div class="panel-card">
        <div class="panel-card__main">
          <label class="filtro-field">
            <span class="filtro-field__lab">Vista</span>
            <select v-model="vistaFiltro" class="filtro-field__sel" aria-describedby="vista-help">
              <option value="pendiente">Solo pendientes</option>
              <option value="todos">Todos</option>
            </select>
          </label>
          <p id="vista-help" class="panel-hint">{{ filtroVistaHelp }}</p>
        </div>
        <div class="panel-card__actions">
          <button
            type="button"
            class="action-pill action-pill--accent"
            :disabled="!canRegistrarPago"
            title="Registra el pago aquí; se refleja en Pagos realizados"
            @click="openModalRegistrar"
          >
            Registrar pago
          </button>
          <RouterLink class="action-pill action-pill--primary" :to="pagosRealizadosLink">Pagos realizados</RouterLink>
          <RouterLink class="action-pill" to="/compras/documentos">Facturas de proveedores</RouterLink>
        </div>
      </div>
    </header>

    <p v-if="documentosDesdeRuta.length" class="route-banner">
      Filtrado por documento(s) de compra desde un enlace ({{ documentosDesdeRuta.length }}).
      <button type="button" class="linkish" @click="clearRouteDocumentos">Quitar</button>
    </p>

    <section class="filters" aria-label="Filtros">
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
          <span class="filter-label">Tipo doc.</span>
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
          <span class="filter-label">F. documento desde</span>
          <input v-model="filters.fecha_documento_desde" type="date" class="filter-inp" />
        </label>
        <label class="filter-field filter-field--date">
          <span class="filter-label">F. documento hasta</span>
          <input v-model="filters.fecha_documento_hasta" type="date" class="filter-inp" />
        </label>
      </div>
      <div class="filter-row filter-row--secondary">
        <label class="filter-field filter-field--date">
          <span class="filter-label">Venc. desde</span>
          <input v-model="filters.fecha_vencimiento_desde" type="date" class="filter-inp" />
        </label>
        <label class="filter-field filter-field--date">
          <span class="filter-label">Venc. hasta</span>
          <input v-model="filters.fecha_vencimiento_hasta" type="date" class="filter-inp" />
        </label>
        <label class="filter-field filter-field--desc">
          <span class="filter-label">Descripción</span>
          <input
            v-model="filters.descripcion"
            type="text"
            class="filter-inp"
            placeholder="Texto en la cuota"
            maxlength="120"
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

    <p v-if="selectedCronogramaIds.length" class="selection-bar">
      {{ selectedCronogramaIds.length }}
      {{ selectedCronogramaIds.length === 1 ? 'fila seleccionada' : 'filas seleccionadas' }}.
    </p>

    <div class="table-wrap">
      <p v-if="loading" class="muted">Cargando…</p>
      <p v-else-if="error" class="err">{{ error }}</p>
      <template v-else>
        <table class="table">
          <thead>
            <tr>
              <th class="th-check">
                <input v-model="allPageSelected" type="checkbox" aria-label="Seleccionar todas en la página" />
              </th>
              <th>Tipo</th>
              <th>Doc. compra</th>
              <th>Doc. proveedor</th>
              <th>Proveedor</th>
              <th>Descripción</th>
              <th class="num">Monto</th>
              <th class="num">Pendiente</th>
              <th>Vencimiento</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td class="td-check">
                <input
                  type="checkbox"
                  :checked="rowChecked(row.id)"
                  :aria-label="`Seleccionar cuota ${row.id}`"
                  @change="toggleRow(row.id)"
                />
              </td>
              <td
                class="td-tipo"
                :title="row.documento_compra_tipo != null ? String(row.documento_compra_tipo) : undefined"
              >
                {{ labelTipoCorto(row.documento_compra_tipo) }}
              </td>
              <td>
                <RouterLink
                  v-if="row.documento_compra != null"
                  class="cell-link"
                  :to="{ path: '/compras/documentos', query: { documento: String(row.documento_compra) } }"
                >
                  {{ row.documento_compra_numero ?? `#${row.documento_compra}` }}
                </RouterLink>
                <span v-else class="muted-cell">—</span>
              </td>
              <td class="td-compact">{{ row.proveedor_documento?.trim() || '—' }}</td>
              <td>{{ row.proveedor_razon_social?.trim() || '—' }}</td>
              <td class="cell-desc" :title="row.descripcion?.trim() || undefined">
                {{ row.descripcion?.trim() ? clipText(row.descripcion, 48) : '—' }}
              </td>
              <td class="num">{{ formatMoney(row.monto) }}</td>
              <td class="num strong">{{ formatMoney(row.monto_pendiente ?? (row.estado === 'PAGADO' ? 0 : row.monto)) }}</td>
              <td>{{ formatDate(row.fecha_vencimiento) }}</td>
              <td>
                <span class="pill" :class="row.estado === 'PAGADO' ? 'pill--ok' : 'pill--pend'">{{
                  estadoLabel(row.estado)
                }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!rows.length" class="muted empty-msg">{{ emptyMsg }}</p>
      </template>
    </div>

    <Teleport to="body">
      <div v-if="modalOpen" class="modal-root" role="presentation" @click.self="closeModal">
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-pago-prov-title">
          <h2 id="modal-pago-prov-title" class="modal-title">Registrar pago</h2>
          <p class="modal-lead">
            Los importes quedan en
            <strong>Pagos realizados</strong> vinculados a cada cuota. Si necesita deshacer, revierta desde allí.
          </p>

          <label class="modal-field">
            <span class="modal-field__lab">Medio de pago</span>
            <select v-model="modalMetodo" class="modal-field__sel">
              <option v-for="o in metodoOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>

          <div class="modal-table-wrap">
            <table class="modal-table">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th class="num">Pendiente</th>
                  <th class="num">Monto a registrar</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="line in modalLines" :key="line.cronogramaId">
                  <td>{{ line.comprobante }}</td>
                  <td class="num muted-td">{{ line.pendiente }}</td>
                  <td class="num">
                    <input
                      v-model="line.monto"
                      type="text"
                      class="modal-inp"
                      inputmode="decimal"
                      autocomplete="off"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <p v-if="modalError" class="modal-err">{{ modalError }}</p>

          <div class="modal-actions">
            <button type="button" class="btn-ghost" :disabled="modalSaving" @click="closeModal">Cancelar</button>
            <button type="button" class="btn-primary" :disabled="modalSaving" @click="submitModal">
              {{ modalSaving ? 'Guardando…' : 'Grabar pago(s)' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.cron-page {
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

.selection-bar {
  margin: 0 0 0.65rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: #0f766e;
}

.panel-card {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  justify-content: space-between;
  gap: 1rem 1.5rem;
  padding: 1rem 1.15rem;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgb(15 23 42 / 7%);
}

.panel-card__main {
  flex: 1 1 16rem;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.panel-card__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  align-self: center;
}

.action-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  text-decoration: none;
  color: #475569;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  transition:
    background 0.15s,
    border-color 0.15s,
    color 0.15s;
  cursor: pointer;
  font-family: inherit;
}

.action-pill:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #94a3b8;
  color: #0f172a;
}

.action-pill:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.action-pill--accent {
  color: #0f766e;
  border-color: #5eead4;
  background: #ecfdf5;
}

.action-pill--accent:hover:not(:disabled) {
  background: #d1fae5;
  border-color: #2dd4bf;
  color: #115e59;
}

.action-pill--primary {
  color: #fff;
  background: linear-gradient(135deg, #0d9488, #0f766e);
  border-color: transparent;
}

.action-pill--primary:hover:not(:disabled) {
  filter: brightness(1.06);
  color: #fff;
}

.filtro-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.filtro-field__lab {
  font-size: 0.7rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #334155;
}

.filtro-field__sel {
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  border: 1px solid #94a3b8;
  font-size: 0.88rem;
  max-width: 18rem;
  background: #fff;
}

.filtro-field__sel:focus {
  outline: none;
  border-color: #0d9488;
  box-shadow: 0 0 0 3px rgb(13 148 136 / 18%);
}

.panel-hint {
  margin: 0.5rem 0 0;
  font-size: 0.78rem;
  line-height: 1.45;
  color: #64748b;
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

.filter-field--desc {
  flex: 1 1 12rem;
  min-width: 10rem;
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

.th-check,
.td-check {
  width: 2.5rem;
  vertical-align: middle;
}

.strong {
  font-weight: 800;
  color: #0f172a;
}

tbody tr:hover {
  background: #f8fafc;
}

.td-tipo {
  font-weight: 800;
  color: #0f766e;
  width: 2.5rem;
}

.td-compact {
  font-size: 0.82rem;
  color: #475569;
}

.cell-desc {
  max-width: 14rem;
  font-size: 0.82rem;
  color: #475569;
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

.pill {
  display: inline-block;
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
}

.pill--pend {
  background: #fef3c7;
  color: #92400e;
}

.pill--ok {
  background: #d1fae5;
  color: #065f46;
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
  color: #991b1b;
  font-weight: 600;
  line-height: 1.5;
  padding: 0.65rem 0.85rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.modal-root {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgb(15 23 42 / 45%);
}

.modal-card {
  width: 100%;
  max-width: 32rem;
  max-height: min(90vh, 640px);
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  padding: 1.25rem 1.35rem;
  box-shadow: 0 20px 50px rgb(15 23 42 / 25%);
}

.modal-title {
  margin: 0 0 0.35rem;
  font-size: 1.15rem;
  font-weight: 800;
  color: #020617;
}

.modal-lead {
  margin: 0 0 1rem;
  font-size: 0.82rem;
  line-height: 1.5;
  color: #475569;
}

.modal-lead strong {
  color: #334155;
}

.modal-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.modal-field__lab {
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.modal-field__sel {
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  border: 1px solid #94a3b8;
  font-size: 0.88rem;
}

.modal-table-wrap {
  overflow-x: auto;
  margin-bottom: 0.75rem;
}

.modal-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.modal-table th,
.modal-table td {
  padding: 0.45rem 0.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-table th {
  text-align: left;
  font-weight: 700;
  color: #475569;
  font-size: 0.72rem;
  text-transform: uppercase;
}

.modal-table th.num,
.modal-table td.num {
  text-align: right;
}

.muted-td {
  color: #64748b;
}

.modal-inp {
  width: 100%;
  max-width: 8rem;
  margin-left: auto;
  display: block;
  padding: 0.35rem 0.45rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.85rem;
}

.modal-err {
  margin: 0 0 0.75rem;
  font-size: 0.82rem;
  color: #b91c1c;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
}

.btn-ghost {
  padding: 0.5rem 1rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  font-family: inherit;
}

.btn-ghost:hover:not(:disabled) {
  background: #f8fafc;
}

.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  padding: 0.5rem 1rem;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #0d9488, #0f766e);
  font-size: 0.85rem;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  font-family: inherit;
}

.btn-primary:hover:not(:disabled) {
  filter: brightness(1.06);
}

.btn-primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
