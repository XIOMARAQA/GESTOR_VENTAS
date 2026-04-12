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

const tipoOptions = [
  { value: '', label: 'Todos' },
  { value: 'FACTURA', label: 'Factura' },
  { value: 'BOLETA', label: 'Boleta' },
  { value: 'NOTA_VENTA', label: 'Nota de venta' },
  { value: 'NOTA_CREDITO_CLIENTE', label: 'N. crédito' },
  { value: 'GUIA_REMISION', label: 'Guía remisión' },
]

type CobranzaRow = {
  id: number
  documento_venta?: number
  documento_serie_numero?: string | null
  cliente_razon_social?: string | null
  condicion_pago_documento?: string | null
  monto_total?: string | number
  monto_pagado?: string | number
  monto_pendiente?: string | number
  fecha_vencimiento?: string | null
  estado?: string | null
}

const filtro = ref<'pendiente' | 'todos'>('pendiente')

const filters = reactive({
  cliente_documento: '',
  cliente_razon_social: '',
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

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const rows = ref<CobranzaRow[]>([])
const loading = ref(false)
const listError = ref('')
const selectedCobranzaIds = ref<number[]>([])

const modalOpen = ref(false)
const modalMetodo = ref('EFECTIVO')
const modalLines = ref<{ cobranzaId: number; comprobante: string; pendiente: string; monto: string }[]>([])
const modalError = ref('')
const modalSaving = ref(false)

const metodoOptions = [
  { value: 'EFECTIVO', label: 'Efectivo' },
  { value: 'TRANSFERENCIA', label: 'Transferencia' },
  { value: 'YAPE', label: 'Yape / Plin' },
  { value: 'POS', label: 'POS / Tarjeta' },
  { value: 'REGISTRO_MANUAL', label: 'Otro / manual' },
]

const documentosDesdeRuta = computed(() => idsFromDocumentosQuery())

const endpoint = computed(() => {
  void filterTick.value
  const params = new URLSearchParams()
  if (filtro.value === 'pendiente') params.set('pendiente', '1')
  params.set('page_size', '150')
  if (isSuperuser.value && empresaId.value) {
    params.set('empresa_id', String(empresaId.value))
  }
  const docIds = documentosDesdeRuta.value
  if (docIds.length) {
    params.set('documentos', docIds.join(','))
  }
  if (filters.cliente_documento.trim()) {
    params.set('cliente_documento', filters.cliente_documento.trim())
  }
  if (filters.cliente_razon_social.trim()) {
    params.set('cliente_razon_social', filters.cliente_razon_social.trim())
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
  return `/tesoreria/cobranzas/?${params}`
})

const filtroDescripcion = computed(() =>
  filtro.value === 'pendiente'
    ? 'Crédito y pagos parciales. El contado emitido figura como pagado y no entra aquí; use «Todos» si lo busca.'
    : 'Incluye contado (pagado) y crédito. Útil para comprobar que existió la cobranza tras emitir.',
)

const emptyCobranzasMsg = computed(() =>
  filtro.value === 'pendiente'
    ? 'Sin saldos abiertos. Si acaba de facturar al contado, cambie a «Todos». Si facturó a crédito, verifique la condición en comprobantes. Superusuario: confirme empresa en la barra superior.'
    : 'No hay cobranzas en el sistema para los filtros actuales. Tras emitir con Nubefact debería crearse el registro automáticamente.',
)

const hasBarFilters = computed(() => {
  return !!(
    filters.cliente_documento.trim() ||
    filters.cliente_razon_social.trim() ||
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
  filters.cliente_documento = ''
  filters.cliente_razon_social = ''
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
  void router.replace({ path: '/tesoreria/cobranzas', query: {} })
}

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

function numPendiente(row: CobranzaRow): number {
  const n = Number(row.monto_pendiente)
  return Number.isFinite(n) ? n : 0
}

const selectedRows = computed(() => {
  const set = new Set(selectedCobranzaIds.value)
  return rows.value.filter((r) => typeof r.id === 'number' && set.has(r.id))
})

const canRegistrarCobro = computed(() => {
  if (!selectedRows.value.length) return false
  return selectedRows.value.some((r) => numPendiente(r) > 0)
})

const pagosLink = computed(() => {
  const docs = selectedRows.value
    .map((r) => (typeof r.documento_venta === 'number' ? r.documento_venta : null))
    .filter((x): x is number => x != null)
  const unique = [...new Set(docs)]
  if (unique.length) {
    return { path: '/tesoreria/pagos', query: { documentos: unique.join(',') } } as const
  }
  return { path: '/tesoreria/pagos' } as const
})

const allPageSelected = computed({
  get() {
    const ids = rows.value.map((r) => r.id).filter((id): id is number => typeof id === 'number')
    return ids.length > 0 && ids.every((id) => selectedCobranzaIds.value.includes(id))
  },
  set(checked: boolean) {
    const ids = rows.value.map((r) => r.id).filter((id): id is number => typeof id === 'number')
    if (checked) {
      selectedCobranzaIds.value = [...new Set([...selectedCobranzaIds.value, ...ids])]
    } else {
      const drop = new Set(ids)
      selectedCobranzaIds.value = selectedCobranzaIds.value.filter((id) => !drop.has(id))
    }
  },
})

function toggleRow(id: number) {
  const cur = selectedCobranzaIds.value
  const i = cur.indexOf(id)
  if (i >= 0) selectedCobranzaIds.value = cur.filter((x) => x !== id)
  else selectedCobranzaIds.value = [...cur, id]
}

function rowChecked(id: number) {
  return selectedCobranzaIds.value.includes(id)
}

async function load() {
  loading.value = true
  listError.value = ''
  try {
    const { data } = await api.get<{ results?: CobranzaRow[] }>(endpoint.value)
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    listError.value = listLoadErrorMessage(e, 'cuentas por cobrar')
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(endpoint, () => {
  selectedCobranzaIds.value = []
  void load()
})

void load()

function openModalRegistrar() {
  if (!canRegistrarCobro.value) return
  modalError.value = ''
  modalMetodo.value = 'EFECTIVO'
  modalLines.value = selectedRows.value
    .filter((r) => numPendiente(r) > 0)
    .map((r) => ({
      cobranzaId: r.id,
      comprobante:
        typeof r.documento_serie_numero === 'string' && r.documento_serie_numero.trim()
          ? r.documento_serie_numero.trim()
          : `#${r.id}`,
      pendiente: formatMoney(r.monto_pendiente),
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
  return 'No se pudo registrar el cobro.'
}

async function submitModal() {
  modalError.value = ''
  const toPost: { id: number; monto: number }[] = []
  for (const line of modalLines.value) {
    const raw = line.monto.replace(',', '.').trim()
    const n = Number(raw)
    if (!Number.isFinite(n) || n <= 0) continue
    toPost.push({ id: line.cobranzaId, monto: n })
  }
  if (!toPost.length) {
    modalError.value = 'Indique al menos un monto mayor que cero.'
    return
  }
  modalSaving.value = true
  try {
    for (const { id, monto } of toPost) {
      await api.post(`/tesoreria/cobranzas/${id}/registrar-pago/`, {
        monto,
        metodo: modalMetodo.value,
      })
    }
    modalOpen.value = false
    selectedCobranzaIds.value = []
    await load()
  } catch (e) {
    modalError.value = registrarErrorMessage(e)
  } finally {
    modalSaving.value = false
  }
}
</script>

<template>
  <div class="cob-page">
    <header class="page-head">
      <div class="page-head__top">
        <div>
          <h1 class="page-title">Cuentas por cobrar</h1>
          <p class="page-lead">
            Seleccione una o varias filas para
            <strong>registrar un cobro</strong> (aparece en Pagos recibidos) o abrir el historial filtrado por esos
            comprobantes.
          </p>
        </div>
      </div>

      <div class="panel-card">
        <div class="panel-card__main">
          <label class="filtro-field">
            <span class="filtro-field__lab">Vista</span>
            <select v-model="filtro" class="filtro-field__sel" aria-describedby="filtro-help">
              <option value="pendiente">Pendientes y parciales</option>
              <option value="todos">Todos los registros</option>
            </select>
          </label>
          <p id="filtro-help" class="panel-hint">{{ filtroDescripcion }}</p>
        </div>
        <div class="panel-card__actions">
          <button
            type="button"
            class="action-pill action-pill--accent"
            :disabled="!canRegistrarCobro"
            title="Registra el pago aquí; se refleja en Pagos recibidos"
            @click="openModalRegistrar"
          >
            Registrar cobro
          </button>
          <RouterLink class="action-pill action-pill--primary" :to="pagosLink">Pagos recibidos</RouterLink>
          <RouterLink class="action-pill" to="/ventas/documentos">Comprobantes</RouterLink>
        </div>
      </div>
    </header>

    <p v-if="documentosDesdeRuta.length" class="route-banner">
      Filtrado por comprobante(s) desde un enlace ({{ documentosDesdeRuta.length }}).
      <button type="button" class="linkish" @click="clearRouteDocumentos">Quitar</button>
    </p>

    <section class="filters" aria-label="Filtros">
      <div class="filter-row filter-row--primary">
        <div class="filter-pair" aria-label="Cliente">
          <label class="filter-field filter-field--ruc">
            <span class="filter-label">RUC / doc.</span>
            <input
              v-model="filters.cliente_documento"
              type="text"
              class="filter-inp"
              placeholder="Documento del cliente"
              maxlength="20"
              autocomplete="off"
            />
          </label>
          <label class="filter-field filter-field--rs">
            <span class="filter-label">Razón social</span>
            <input
              v-model="filters.cliente_razon_social"
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
            placeholder="Observación del comprobante"
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

    <p v-if="selectedCobranzaIds.length" class="selection-bar">
      {{ selectedCobranzaIds.length }}
      {{ selectedCobranzaIds.length === 1 ? 'cobranza seleccionada' : 'cobranzas seleccionadas' }}.
    </p>

    <div class="table-wrap">
      <p v-if="loading" class="muted">Cargando…</p>
      <p v-else-if="listError" class="err">{{ listError }}</p>
      <template v-else>
        <table class="table">
          <thead>
            <tr>
              <th class="th-check">
                <input v-model="allPageSelected" type="checkbox" aria-label="Seleccionar todas en la página" />
              </th>
              <th>Comprobante</th>
              <th>Cliente</th>
              <th>Condición</th>
              <th class="num">Total</th>
              <th class="num">Cobrado</th>
              <th class="num">Por cobrar</th>
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
                  :aria-label="`Seleccionar cobranza ${row.id}`"
                  @change="toggleRow(row.id)"
                />
              </td>
              <td>{{ row.documento_serie_numero ?? '—' }}</td>
              <td>{{ row.cliente_razon_social?.trim() || '—' }}</td>
              <td>{{ row.condicion_pago_documento ?? '—' }}</td>
              <td class="num">{{ formatMoney(row.monto_total) }}</td>
              <td class="num">{{ formatMoney(row.monto_pagado) }}</td>
              <td class="num strong">{{ formatMoney(row.monto_pendiente) }}</td>
              <td>{{ formatDate(row.fecha_vencimiento) }}</td>
              <td>{{ row.estado ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!rows.length" class="muted empty-msg">{{ emptyCobranzasMsg }}</p>
      </template>
    </div>

    <Teleport to="body">
      <div v-if="modalOpen" class="modal-root" role="presentation" @click.self="closeModal">
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-registrar-title">
          <h2 id="modal-registrar-title" class="modal-title">Registrar cobro</h2>
          <p class="modal-lead">
            Los importes quedan registrados como
            <strong>pagos recibidos</strong> vinculados a cada cobranza. Puede abonos parciales; el saldo se actualiza al
            instante.
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
                  <th>Comprobante</th>
                  <th class="num">Pendiente</th>
                  <th class="num">Monto a registrar</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="line in modalLines" :key="line.cobranzaId">
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
              {{ modalSaving ? 'Guardando…' : 'Grabar cobro(s)' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.cob-page {
  width: 100%;
  max-width: 1200px;
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

.page-head {
  margin-bottom: 0.75rem;
}

.page-head__top {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
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
  max-width: 44rem;
  font-size: 0.9rem;
  line-height: 1.55;
  color: #475569;
}

.page-lead strong {
  color: #334155;
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
  padding: 0.55rem 0.7rem;
  border-radius: 8px;
  border: 1px solid #94a3b8;
  font-size: 0.88rem;
  font-weight: 500;
  color: #0f172a;
  background: #fff;
  max-width: 22rem;
}

.filtro-field__sel:focus {
  outline: none;
  border-color: #0d9488;
  box-shadow: 0 0 0 3px rgb(13 148 136 / 18%);
}

.panel-hint {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.5;
  color: #334155;
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

.th-check,
.td-check {
  width: 2.5rem;
  vertical-align: middle;
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

.strong {
  font-weight: 800;
  color: #0f172a;
}

tbody tr:hover {
  background: #f8fafc;
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
