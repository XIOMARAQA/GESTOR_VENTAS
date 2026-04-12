<script setup lang="ts">
import type { AxiosResponse } from 'axios'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type MovRow = {
  id: number
  tipo?: string
  creado_en?: string
  referencia_tipo?: string
  tipo_comprobante?: string
  almacen_nombre?: string
  glosa?: string
}

type MovPaginated = { results?: MovRow[]; next?: string | null; count?: number }

const REF_TIPO_LABELS: Record<string, string> = {
  DOCUMENTO_VENTA: 'Documento de venta',
  DOCUMENTO_COMPRA: 'Documento de compra',
}

const TIPO_MOV_LABELS: Record<string, string> = {
  INGRESO: 'Ingreso',
  SALIDA: 'Salida',
  AJUSTE: 'Ajuste',
  TRANSFERENCIA: 'Transferencia',
}

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const rows = ref<MovRow[]>([])
const loading = ref(true)
const exporting = ref(false)
const err = ref('')
const page = ref(1)
const totalCount = ref(0)
const hasNext = ref(false)
const hasPrev = ref(false)

const bloqueadoSinEmpresa = computed(() => isSuperuser.value && !empresaId.value)

function appendEmpresaParams(params: URLSearchParams) {
  if (isSuperuser.value && empresaId.value) {
    params.set('empresa', String(empresaId.value))
  }
}

function labelRefTipo(code: unknown): string {
  if (code == null || typeof code !== 'string' || !code.trim()) return '—'
  return REF_TIPO_LABELS[code] ?? code
}

function labelTipoMov(t: unknown): string {
  if (t == null || typeof t !== 'string') return '—'
  return TIPO_MOV_LABELS[t] ?? t
}

function formatFechaHora(iso: unknown): string {
  if (iso == null || typeof iso !== 'string') return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yyyy = d.getFullYear()
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${dd}/${mm}/${yyyy} ${hh}:${min}`
}

function tipoMovClass(t: unknown): string {
  if (t === 'SALIDA') return 'tipo-mov tipo-mov--salida'
  if (t === 'INGRESO') return 'tipo-mov tipo-mov--ingreso'
  return 'tipo-mov'
}

function drfRelativePath(next: string): string {
  const u = new URL(next)
  const idx = u.pathname.indexOf('/api/v1/')
  if (idx >= 0) return u.pathname.slice(idx + '/api/v1'.length) + u.search
  return u.pathname + u.search
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const params = new URLSearchParams()
    params.set('page', String(page.value))
    params.set('page_size', '50')
    appendEmpresaParams(params)
    const { data } = await api.get<MovRow[] | MovPaginated>(`/inventario/movimientos/?${params}`)
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
    const paginated = !Array.isArray(data) ? data : null
    totalCount.value =
      paginated && typeof paginated.count === 'number' ? paginated.count : rows.value.length
    hasNext.value = !!(paginated && paginated.next)
    hasPrev.value = page.value > 1
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'los movimientos de inventario')
    rows.value = []
    totalCount.value = 0
    hasNext.value = false
    hasPrev.value = false
  } finally {
    loading.value = false
  }
}

function goNext() {
  if (hasNext.value) {
    page.value += 1
    void load()
  }
}

function goPrev() {
  if (hasPrev.value && page.value > 1) {
    page.value -= 1
    void load()
  }
}

watch(empresaId, () => {
  page.value = 1
  void load()
})

onMounted(() => {
  void load()
})

function escapeCsvCell(s: string): string {
  if (/[;"\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function buildMovParamsForExport(): URLSearchParams {
  const params = new URLSearchParams()
  params.set('page_size', '500')
  appendEmpresaParams(params)
  return params
}

async function fetchAllMovimientosForExport(): Promise<MovRow[]> {
  const acc: MovRow[] = []
  let path: string | null = `/inventario/movimientos/?${buildMovParamsForExport()}`
  while (path) {
    const res: AxiosResponse<MovRow[] | MovPaginated> = await api.get<MovRow[] | MovPaginated>(path)
    const data = res.data
    const chunk: MovRow[] = Array.isArray(data) ? data : (data.results ?? [])
    acc.push(...chunk)
    const nextUrl: string | null =
      !Array.isArray(data) && typeof data.next === 'string' && data.next ? data.next : null
    path = nextUrl ? drfRelativePath(nextUrl) : null
  }
  return acc
}

async function descargarExcel() {
  if (bloqueadoSinEmpresa.value) return
  exporting.value = true
  err.value = ''
  try {
    const dataRows = await fetchAllMovimientosForExport()
    const sep = ';'
    const headers = [
      'Tipo',
      'Fecha',
      'Origen ref.',
      'Tipo comprobante',
      'Almacén',
      'Glosa',
    ]
    const lines = [headers.map(escapeCsvCell).join(sep)]
    for (const r of dataRows) {
      const fechaIso = r.creado_en ? formatFechaHora(r.creado_en) : ''
      lines.push(
        [
          labelTipoMov(r.tipo),
          fechaIso,
          labelRefTipo(r.referencia_tipo),
          (r.tipo_comprobante || '').trim() || '—',
          (r.almacen_nombre || '').trim() || '—',
          (r.glosa || '').trim(),
        ]
          .map((x) => escapeCsvCell(String(x)))
          .join(sep),
      )
    }
    const bom = '\uFEFF'
    const blob = new Blob([bom + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    const d = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    a.href = URL.createObjectURL(blob)
    a.download = `movimientos_inventario_${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'la exportación')
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="page">
    <header class="head">
      <div class="head-text">
        <h1 class="title">Movimientos de inventario</h1>
        <p class="lead">
          Historial de <strong>entradas y salidas</strong> de stock por almacén. Cada fila corresponde a un movimiento
          registrado en el sistema (por ejemplo, al emitir una factura o al registrar una compra). Use el listado para
          auditar el kardex y cruzar con comprobantes de venta o compra.
        </p>
      </div>
      <div class="head-actions">
        <button
          type="button"
          class="btn-excel"
          :disabled="loading || exporting || bloqueadoSinEmpresa"
          title="Descargar listado (Excel / CSV)"
          aria-label="Exportar movimientos a Excel"
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
        <button type="button" class="btn-ref" :disabled="loading" @click="load">
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="bloqueadoSinEmpresa" class="warn">
      Modo administrador global: elija una empresa en la barra superior para ver movimientos de inventario acotados a
      esa empresa.
    </p>
    <p v-if="err" class="err">{{ err }}</p>

    <div class="meta-row">
      <span class="count">{{ totalCount }} movimiento(s)</span>
    </div>

    <div class="card">
      <div v-if="loading" class="muted">Cargando…</div>
      <div v-else class="table-wrap">
        <table class="t">
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Fecha</th>
              <th>Origen</th>
              <th>Tipo de comprobante</th>
              <th>Almacén</th>
              <th>Glosa</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td>
                <span :class="tipoMovClass(r.tipo)">{{ labelTipoMov(r.tipo) }}</span>
              </td>
              <td class="td-fecha">{{ formatFechaHora(r.creado_en) }}</td>
              <td>{{ labelRefTipo(r.referencia_tipo) }}</td>
              <td>{{ (r.tipo_comprobante || '').trim() || '—' }}</td>
              <td>{{ (r.almacen_nombre || '').trim() || '—' }}</td>
              <td class="td-glosa">{{ (r.glosa || '').trim() || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!rows.length" class="empty">No hay movimientos para mostrar en esta página.</p>
      </div>
      <div v-if="!loading && rows.length && (hasNext || hasPrev)" class="pager">
        <button type="button" class="btn-page" :disabled="!hasPrev" @click="goPrev">Anterior</button>
        <span class="page-num">Página {{ page }}</span>
        <button type="button" class="btn-page" :disabled="!hasNext" @click="goNext">Siguiente</button>
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

.head-text {
  min-width: 0;
  flex: 1;
}

.title {
  margin: 0 0 0.35rem;
  font-size: 1.2rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.lead {
  margin: 0;
  font-size: 0.88rem;
  color: #475569;
  line-height: 1.55;
  max-width: 46rem;
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
  margin: 0 0 0.75rem;
  padding: 0.65rem 0.85rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.meta-row {
  display: flex;
  align-items: center;
  margin-bottom: 0.65rem;
}

.count {
  font-size: 0.8rem;
  color: #64748b;
  font-weight: 600;
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
  min-height: 6rem;
}

.t {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.t th,
.t td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

.t th {
  background: linear-gradient(180deg, #f8fafc, #f1f5f9);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #475569;
}

.t tbody tr:hover {
  background: #f8fafc;
}

.tipo-mov {
  font-weight: 700;
  font-size: 0.8rem;
  letter-spacing: 0.02em;
}

.tipo-mov--salida {
  color: #b91c1c;
}

.tipo-mov--ingreso {
  color: #15803d;
}

.td-fecha {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: #334155;
}

.td-glosa {
  color: #64748b;
  font-size: 0.78rem;
  line-height: 1.4;
  max-width: 22rem;
}

.muted {
  padding: 1.25rem;
  color: #94a3b8;
}

.empty {
  margin: 0;
  padding: 1.5rem 1rem 1.75rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.86rem;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid #e2e8f0;
  background: #fafafa;
}

.btn-page {
  padding: 0.35rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  color: #334155;
}

.btn-page:hover:not(:disabled) {
  border-color: #94a3b8;
}

.btn-page:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.page-num {
  font-size: 0.8rem;
  color: #64748b;
}
</style>
