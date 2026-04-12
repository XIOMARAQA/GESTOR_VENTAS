<script setup lang="ts">
import axios from 'axios'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'

type DocRow = Record<string, unknown> & { id?: number }

const TIPO_LABELS: Record<string, string> = {
  FACTURA: 'Factura',
  BOLETA: 'Boleta',
  NOTA_VENTA: 'Nota de venta',
  RESUMEN_BOLETAS: 'Resumen boletas',
  GUIA_REMISION: 'Guía remisión',
  NOTA_CREDITO_CLIENTE: 'N. crédito',
}

/** Una letra / código corto por fila (estilo listados tipo Nubefact). */
const TIPO_CORTO: Record<string, string> = {
  FACTURA: 'F',
  BOLETA: 'B',
  NOTA_VENTA: 'NV',
  RESUMEN_BOLETAS: 'RB',
  GUIA_REMISION: 'GR',
  NOTA_CREDITO_CLIENTE: 'NC',
}

const tipoOptions = [
  { value: '', label: 'Todos' },
  { value: 'FACTURA', label: 'Factura' },
  { value: 'BOLETA', label: 'Boleta' },
  { value: 'NOTA_VENTA', label: 'Nota de venta' },
  { value: 'RESUMEN_BOLETAS', label: 'Resumen de boletas' },
  { value: 'GUIA_REMISION', label: 'Guía de remisión' },
  { value: 'NOTA_CREDITO_CLIENTE', label: 'Nota de crédito' },
]

const mediosPagoOptions = [
  { value: 'EFECTIVO', label: 'Efectivo' },
  { value: 'DEPOSITO_CUENTA', label: 'Depósito en cuenta' },
  { value: 'TRANSFERENCIA', label: 'Transferencia bancaria' },
  { value: 'TARJETA_DEBITO', label: 'Tarjeta de débito' },
  { value: 'OTROS', label: 'Otros medios de pago' },
  { value: 'TARJETA_CREDITO', label: 'Tarjeta de crédito' },
  { value: 'YAPE', label: 'Yape' },
  { value: 'PLIN', label: 'Plin' },
] as const

const tiposOperacionOptions = [
  { value: 'VENTA_INTERNA', label: 'Venta interna' },
  { value: 'ANTICIPO', label: 'Anticipo' },
  { value: 'REGULARIZACION_ANTICIPO', label: 'Regularización de anticipo' },
  { value: 'EXPORTACION', label: 'Exportación' },
  { value: 'NO_DOMICILIADOS', label: 'No domiciliados' },
  { value: 'VENTA_ITINERANTE', label: 'Venta itinerante' },
] as const

/** Claves de series; valores solo desde GET /ventas/nubefact/config/ (NUBEFACT_SERIE_* en .env del servidor). */
type SeriesNubefactCfg = {
  FACTURA: string
  BOLETA: string
  NOTA_CREDITO_FACTURA: string
  NOTA_DEBITO_FACTURA: string
  NOTA_CREDITO_BOLETA: string
  NOTA_DEBITO_BOLETA: string
}

const EMPTY_SERIES_NUBEFACT: SeriesNubefactCfg = {
  FACTURA: '',
  BOLETA: '',
  NOTA_CREDITO_FACTURA: '',
  NOTA_DEBITO_FACTURA: '',
  NOTA_CREDITO_BOLETA: '',
  NOTA_DEBITO_BOLETA: '',
}

const seriesNubefact = ref<SeriesNubefactCfg>({ ...EMPTY_SERIES_NUBEFACT })

function mergeSeriesDesdeApi(raw: Record<string, unknown> | undefined) {
  if (!raw || typeof raw !== 'object') return
  const keys = Object.keys(EMPTY_SERIES_NUBEFACT) as (keyof SeriesNubefactCfg)[]
  for (const k of keys) {
    if (!Object.prototype.hasOwnProperty.call(raw, k)) continue
    const v = raw[k]
    if (typeof v === 'string') {
      seriesNubefact.value[k] = v.trim().slice(0, 10)
    } else if (v != null) {
      seriesNubefact.value[k] = String(v).trim().slice(0, 10)
    } else {
      seriesNubefact.value[k] = ''
    }
  }
}

const tituloAyudaSeries = computed(() => {
  const s = seriesNubefact.value
  const hasAny = Object.values(s).some((x) => (x || '').trim())
  if (!hasAny) {
    return 'Defina NUBEFACT_SERIE_* en el .env del backend o escriba la serie aquí.'
  }
  return `Factura ${s.FACTURA || '—'}; NC/ND factura ${s.NOTA_CREDITO_FACTURA || '—'} / ${s.NOTA_DEBITO_FACTURA || '—'}. Boleta ${s.BOLETA || '—'}; NC/ND boleta ${s.NOTA_CREDITO_BOLETA || '—'} / ${s.NOTA_DEBITO_BOLETA || '—'}. (Desde .env del servidor.)`
})

function isoDate(d: Date) {
  return d.toISOString().slice(0, 10)
}

const hasta = new Date()
const desde = new Date()
desde.setDate(desde.getDate() - 30)

const filters = reactive({
  cliente_documento: '',
  cliente_razon_social: '',
  tipo: '',
  serie: '',
  numero: '',
  fecha_emision_desde: isoDate(desde),
  fecha_emision_hasta: isoDate(hasta),
})

const rows = ref<DocRow[]>([])
const totalCount = ref(0)
const loading = ref(false)
const errorMsg = ref('')
const page = ref(1)
const hasNext = ref(false)
const hasPrev = ref(false)

const selected = ref<Set<number>>(new Set())

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

function labelTipo(v: unknown): string {
  if (v == null || typeof v !== 'string') return '—'
  return TIPO_LABELS[v] ?? v
}

function labelTipoCorto(v: unknown): string {
  if (v == null || typeof v !== 'string') return '—'
  return TIPO_CORTO[v] ?? v.slice(0, 3).toUpperCase()
}

function clienteReceptor(row: DocRow): string {
  const rs = row.cliente_razon_social
  const doc = row.cliente_documento
  const s = typeof rs === 'string' && rs.trim() ? rs.trim() : ''
  if (s) return s
  const d = typeof doc === 'string' && doc.trim() ? doc.trim() : ''
  return d || '—'
}

function serieNum(row: DocRow): string {
  const s = row.serie != null ? String(row.serie).trim() : ''
  const n = row.numero != null ? String(row.numero).trim() : ''
  if (s && n) return `${s}-${n}`
  return s || n || '—'
}

function sunatCodigo(row: DocRow): string {
  const v = row.nubefact_sunat_codigo
  return v != null ? String(v).trim() : ''
}

function sunatDescripcion(row: DocRow): string {
  const v = row.nubefact_sunat_descripcion
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

function sunatEstadoTexto(row: DocRow): string {
  const c = sunatCodigo(row)
  const d = sunatDescripcion(row)
  if (!c && !d) return ''
  if (c === '0') return 'ACEPTADO'
  if (c) return `Cód. ${c}`
  return 'SUNAT'
}

function sunatPillClass(row: DocRow): string {
  const c = sunatCodigo(row)
  if (c === '0') return 'sunat-pill sunat-pill--ok'
  if (c) return 'sunat-pill sunat-pill--warn'
  if (sunatDescripcion(row)) return 'sunat-pill sunat-pill--muted'
  return 'sunat-pill sunat-pill--empty'
}

const sunatFloatOpen = ref(false)
const sunatFloatTitulo = ref('')
const sunatFloatMensaje = ref('')
const sunatFloatCodigo = ref('')

function openSunatFloat(row: DocRow) {
  const msg = sunatDescripcion(row)
  if (!msg) return
  const tipo = labelTipo(row.tipo)
  const sn = serieNum(row)
  sunatFloatTitulo.value = sn !== '—' ? `${tipo}: ${sn}` : tipo
  sunatFloatMensaje.value = msg
  sunatFloatCodigo.value = sunatCodigo(row) || ''
  sunatFloatOpen.value = true
}

function closeSunatFloat() {
  sunatFloatOpen.value = false
}

function onSunatFloatKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && sunatFloatOpen.value) closeSunatFloat()
}

watch(sunatFloatOpen, (open) => {
  if (open) document.addEventListener('keydown', onSunatFloatKeydown)
  else document.removeEventListener('keydown', onSunatFloatKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onSunatFloatKeydown)
})

const allPageSelected = computed({
  get() {
    const ids = rows.value.map((r) => r.id).filter((id): id is number => typeof id === 'number')
    return ids.length > 0 && ids.every((id) => selected.value.has(id))
  },
  set(checked: boolean) {
    if (checked) {
      for (const r of rows.value) {
        if (typeof r.id === 'number') selected.value.add(r.id)
      }
    } else {
      for (const r of rows.value) {
        if (typeof r.id === 'number') selected.value.delete(r.id)
      }
    }
    selected.value = new Set(selected.value)
  },
})

function toggleRow(id: number) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function rowChecked(id: number) {
  return selected.value.has(id)
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function onFiltersChange() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debounceTimer = null
    page.value = 1
    load()
  }, 320)
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const params = new URLSearchParams()
    if (filters.cliente_documento.trim())
      params.set('cliente_documento', filters.cliente_documento.trim())
    if (filters.cliente_razon_social.trim())
      params.set('cliente_razon_social', filters.cliente_razon_social.trim())
    if (filters.tipo.trim()) params.set('tipo', filters.tipo.trim())
    if (filters.serie.trim()) params.set('serie', filters.serie.trim())
    if (filters.numero.trim()) params.set('numero', filters.numero.trim())
    if (filters.fecha_emision_desde) params.set('fecha_emision_desde', filters.fecha_emision_desde)
    if (filters.fecha_emision_hasta) params.set('fecha_emision_hasta', filters.fecha_emision_hasta)
    params.set('page', String(page.value))

    const docFocus = route.query.documento
    const dfs = typeof docFocus === 'string' ? docFocus : Array.isArray(docFocus) ? docFocus[0] : ''
    if (dfs && /^\d+$/.test(String(dfs))) params.set('documento', String(dfs))

    const { data } = await api.get<{
      results?: DocRow[]
      count?: number
      next?: string | null
      previous?: string | null
    }>(`/ventas/documentos/?${params.toString()}`)

    rows.value = Array.isArray(data) ? data : (data.results ?? [])
    totalCount.value = typeof data === 'object' && data && 'count' in data ? Number(data.count) : rows.value.length
    hasNext.value = !!(typeof data === 'object' && data && data.next)
    hasPrev.value = !!(typeof data === 'object' && data && data.previous)
  } catch {
    errorMsg.value = 'No se pudo cargar los comprobantes.'
    rows.value = []
    totalCount.value = 0
    hasNext.value = false
    hasPrev.value = false
  } finally {
    loading.value = false
  }
  applyDocumentoQuerySelection()
}

function applyDocumentoQuerySelection() {
  const raw = route.query.documento
  const s = typeof raw === 'string' ? raw : Array.isArray(raw) ? raw[0] : ''
  const id = parseInt(String(s), 10)
  if (!Number.isFinite(id) || id <= 0) return
  const found = rows.value.some((r) => r.id === id)
  if (found) {
    selected.value = new Set([id])
    void nextTick(() => {
      const el = document.querySelector(`[data-doc-id="${id}"]`)
      el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }
}

watch(filters, onFiltersChange, { deep: true })

const route = useRoute()
const router = useRouter()

/** Id de borrador recién creado desde cotización (?borrador=) para ofrecer emisión Nubefact al instante. */
const borradorQueryId = ref<number | null>(null)
const borradorBannerErr = ref('')
const borradorEmitLoading = ref(false)

function syncBorradorFromRoute() {
  const raw = route.query.borrador
  const s = typeof raw === 'string' ? raw : Array.isArray(raw) ? raw[0] : ''
  const n = parseInt(String(s), 10)
  borradorQueryId.value = Number.isFinite(n) && n > 0 ? n : null
  borradorBannerErr.value = ''
}

watch(
  () => route.query.borrador,
  () => {
    syncBorradorFromRoute()
  },
)

watch(
  () => route.query.documento,
  () => {
    page.value = 1
    void load()
  },
)

onMounted(() => {
  syncBorradorFromRoute()
  load()
})

function nubefactEmitErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e) && e.response?.data) {
    const d = e.response.data as Record<string, unknown>
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) return d.detail.map(String).join(' ')
    if (d.errors != null) return typeof d.errors === 'string' ? d.errors : JSON.stringify(d.errors)
    return 'Error al emitir el comprobante (pudo haberse creado el borrador; revíselo en la lista).'
  }
  return 'Error de conexión o desconocido.'
}

function cerrarBannerBorrador() {
  borradorBannerErr.value = ''
  router.replace({ path: '/ventas/documentos' })
}

async function emitirBorradorDesdeBanner() {
  const id = borradorQueryId.value
  if (typeof id !== 'number') return
  borradorEmitLoading.value = true
  borradorBannerErr.value = ''
  try {
    await api.post('/ventas/nubefact/emitir/', { documento_id: id })
    router.replace({ path: '/ventas/documentos' })
    borradorQueryId.value = null
    await load()
  } catch (e) {
    borradorBannerErr.value = nubefactEmitErrorMessage(e)
  } finally {
    borradorEmitLoading.value = false
  }
}

function goNext() {
  if (hasNext.value) {
    page.value += 1
    load()
  }
}

function goPrev() {
  if (hasPrev.value && page.value > 1) {
    page.value -= 1
    load()
  }
}

function refresh() {
  load()
}

const ctx = useAppContextStore()

type ItemCat = {
  id: number
  codigo?: string
  nombre: string
  unidad_medida_codigo?: string
}

type ClienteCat = {
  id: number
  documento?: string
  razon_social?: string
  email?: string
  direccion?: string
  activo?: boolean
}

type LineaForm = {
  item_id: number | ''
  cantidad: string
  precio_unit: string
}

const showComprobanteModal = ref(false)
const catalogLoading = ref(false)
const itemCatalog = ref<ItemCat[]>([])
const clientesCatalog = ref<ClienteCat[]>([])
const vendedoresCatalog = ref<{ id: number; nombre_completo?: string }[]>([])
const nubSubmitting = ref(false)
const nubError = ref('')
const clienteConsultMsg = ref('')
const clienteConsultIsError = ref(false)
const consultDocLoading = ref(false)
const docSuggestOpen = ref(false)
let docSuggestCloseTimer: ReturnType<typeof setTimeout> | null = null

const formCab = reactive({
  tipo: 'FACTURA' as 'FACTURA' | 'BOLETA',
  serie: '',
  fecha_emision: isoDate(new Date()),
  observacion: '',
  precio_incluye_igv: false,
  moneda: 'PEN' as 'PEN' | 'USD',
  condicion_pago: 'CONTADO' as 'CONTADO' | 'CREDITO',
  fecha_vencimiento: '',
  medio_pago: 'TRANSFERENCIA',
  tipo_operacion: 'VENTA_INTERNA',
  vendedor_id: '' as number | '',
})

const formCliente = reactive({
  tipo_doc: 'RUC' as 'RUC' | 'DNI',
  documento: '',
  razon_social: '',
  email: '',
  direccion: '',
})

watch(
  () => formCab.tipo,
  (t) => {
    if (t === 'FACTURA') formCab.serie = seriesNubefact.value.FACTURA
    else if (t === 'BOLETA') formCab.serie = seriesNubefact.value.BOLETA
  },
)

const clientesMatches = computed(() => {
  const t = formCliente.documento.trim()
  if (!t) return []
  const td = t.replace(/\D/g, '')
  const tLower = t.toLowerCase()
  return clientesCatalog.value
    .filter((c) => c.activo !== false)
    .filter((c) => {
      const doc = (c.documento || '').trim()
      if (!doc) return false
      const dd = doc.replace(/\D/g, '')
      if (doc.toLowerCase().startsWith(tLower)) return true
      if (td.length > 0 && dd.startsWith(td)) return true
      return false
    })
    .slice(0, 10)
})

const puedeConsultarPadron = computed(() => {
  const n = formCliente.documento.replace(/\D/g, '')
  if (formCliente.tipo_doc === 'RUC') return /^\d{11}$/.test(n)
  return /^\d{8}$/.test(n)
})

const lineasForm = ref<LineaForm[]>([{ item_id: '', cantidad: '1', precio_unit: '' }])

const IGV_RATE = 0.18

function subtotalLineaSinIgv(ln: LineaForm): number {
  if (ln.item_id === '') return 0
  const c = Number(ln.cantidad)
  const p = Number(ln.precio_unit)
  if (!Number.isFinite(c) || !Number.isFinite(p) || c <= 0 || p < 0) return 0
  const unitBase = formCab.precio_incluye_igv ? p / (1 + IGV_RATE) : p
  return Math.round(c * unitBase * 100) / 100
}

const totalGravada = computed(() => {
  let s = 0
  for (const ln of lineasForm.value) {
    s += subtotalLineaSinIgv(ln)
  }
  return Math.round(s * 100) / 100
})

const precioColumnLabel = computed(() =>
  formCab.precio_incluye_igv ? 'Valor unit. (con IGV)' : 'Valor unit. (sin IGV)',
)

const totalIgvPreview = computed(() => Math.round(totalGravada.value * IGV_RATE * 100) / 100)
const totalDocPreview = computed(() => Math.round((totalGravada.value + totalIgvPreview.value) * 100) / 100)

const simboloMonedaPreview = computed(() => (formCab.moneda === 'USD' ? '$' : 'S/'))

function addLinea() {
  lineasForm.value.push({ item_id: '', cantidad: '1', precio_unit: '' })
}

function removeLinea(i: number) {
  if (lineasForm.value.length > 1) lineasForm.value.splice(i, 1)
}

function itemLabel(it: ItemCat) {
  const c = (it.codigo || '').trim()
  return c ? `${c} — ${it.nombre}` : it.nombre
}

function pickClienteCatalogo(c: ClienteCat) {
  formCliente.documento = (c.documento || '').trim().slice(0, 20)
  formCliente.razon_social = (c.razon_social || '').trim().slice(0, 255)
  formCliente.email = (c.email || '').trim().slice(0, 254)
  formCliente.direccion = (c.direccion || '').trim()
  const digits = formCliente.documento.replace(/\D/g, '')
  if (digits.length === 11) formCliente.tipo_doc = 'RUC'
  else if (digits.length === 8) formCliente.tipo_doc = 'DNI'
  docSuggestOpen.value = false
  clienteConsultMsg.value = ''
  clienteConsultIsError.value = false
}

function onDocNumFocusIn() {
  if (docSuggestCloseTimer) {
    clearTimeout(docSuggestCloseTimer)
    docSuggestCloseTimer = null
  }
  docSuggestOpen.value = true
}

function onDocNumFocusOut() {
  docSuggestCloseTimer = setTimeout(() => {
    docSuggestOpen.value = false
    docSuggestCloseTimer = null
  }, 220)
}

async function consultarPadronCliente() {
  clienteConsultMsg.value = ''
  clienteConsultIsError.value = false
  const n = formCliente.documento.replace(/\D/g, '')
  if (formCliente.tipo_doc === 'RUC') {
    if (!/^\d{11}$/.test(n)) {
      clienteConsultMsg.value = 'Para SUNAT ingrese 11 dígitos de RUC.'
      clienteConsultIsError.value = true
      return
    }
  } else if (!/^\d{8}$/.test(n)) {
    clienteConsultMsg.value = 'Para RENIEC ingrese 8 dígitos de DNI.'
    clienteConsultIsError.value = true
    return
  }

  consultDocLoading.value = true
  try {
    if (formCliente.tipo_doc === 'RUC') {
      const { data } = await api.get<{
        ok?: boolean
        nombre_padron?: string
        razon_social?: string
        detail?: string
      }>('/core/consultar-ruc/', { params: { numero: n } })
      if (data.ok) {
        const pad = (data.nombre_padron || data.razon_social || '').trim()
        if (pad) {
          formCliente.razon_social = pad.slice(0, 255)
          clienteConsultMsg.value = 'Razón social sugerida por SUNAT (revise antes de emitir).'
          clienteConsultIsError.value = false
        } else {
          clienteConsultMsg.value = 'SUNAT no devolvió nombre para este RUC.'
          clienteConsultIsError.value = true
        }
      } else {
        clienteConsultMsg.value =
          typeof data.detail === 'string' && data.detail.trim()
            ? data.detail
            : 'No se pudo consultar el RUC.'
        clienteConsultIsError.value = true
      }
    } else {
      const { data } = await api.get<{
        ok?: boolean
        razon_social?: string
        nombre_completo?: string
        detail?: string
      }>('/core/consultar-reniec-dni/', { params: { numero: n } })
      if (data.ok) {
        const nom = (data.razon_social || data.nombre_completo || '').trim()
        if (nom) {
          formCliente.razon_social = nom.slice(0, 255)
          clienteConsultMsg.value = 'Nombre sugerido por RENIEC (revise antes de emitir).'
          clienteConsultIsError.value = false
        } else {
          clienteConsultMsg.value = 'No se recibió nombre para este DNI.'
          clienteConsultIsError.value = true
        }
      } else {
        clienteConsultMsg.value =
          typeof data.detail === 'string' && data.detail.trim()
            ? data.detail
            : 'No se pudo consultar el DNI.'
        clienteConsultIsError.value = true
      }
    }
  } catch (e) {
    clienteConsultIsError.value = true
    if (axios.isAxiosError(e) && e.response?.data && typeof e.response.data === 'object') {
      const d = e.response.data as { detail?: string }
      clienteConsultMsg.value =
        typeof d.detail === 'string' ? d.detail : 'Error al consultar el padrón.'
    } else {
      clienteConsultMsg.value = 'Error de conexión al consultar el padrón.'
    }
  } finally {
    consultDocLoading.value = false
  }
}

async function openComprobanteModal() {
  nubError.value = ''
  clienteConsultMsg.value = ''
  clienteConsultIsError.value = false
  docSuggestOpen.value = false
  showComprobanteModal.value = true
  formCab.fecha_emision = isoDate(new Date())
  formCab.observacion = ''
  formCab.precio_incluye_igv = false
  formCab.moneda = 'PEN'
  formCab.condicion_pago = 'CONTADO'
  formCab.fecha_vencimiento = ''
  formCab.medio_pago = 'TRANSFERENCIA'
  formCab.tipo_operacion = 'VENTA_INTERNA'
  formCab.vendedor_id = ''
  formCliente.tipo_doc = 'RUC'
  formCliente.documento = ''
  formCliente.razon_social = ''
  formCliente.email = ''
  formCliente.direccion = ''
  lineasForm.value = [{ item_id: '', cantidad: '1', precio_unit: '' }]

  catalogLoading.value = true
  itemCatalog.value = []
  clientesCatalog.value = []
  vendedoresCatalog.value = []
  seriesNubefact.value = { ...EMPTY_SERIES_NUBEFACT }
  try {
    const [itemsRes, cliRes, vendRes, nubCfgRes] = await Promise.all([
      api.get<{ results?: ItemCat[] }>('/inventario/items/?page_size=500').catch(() => null),
      api
        .get<{ results?: ClienteCat[] }>('/core/clientes/?page_size=500&ordering=razon_social')
        .catch(() => null),
      api.get<{ results?: { id: number; nombre_completo?: string; activo?: boolean }[] }>('/core/vendedores/?page_size=500').catch(() => null),
      api
        .get<{ series?: Record<string, unknown> }>('/ventas/nubefact/config/')
        .catch(() => null),
    ])
    mergeSeriesDesdeApi(nubCfgRes?.data?.series)
    formCab.tipo = 'FACTURA'
    formCab.serie = seriesNubefact.value.FACTURA
    itemCatalog.value = itemsRes?.data?.results ?? []
    const cd = cliRes?.data
    clientesCatalog.value = Array.isArray(cd) ? cd : (cd?.results ?? [])
    const vd = vendRes?.data
    const rawV = Array.isArray(vd) ? vd : (vd?.results ?? [])
    vendedoresCatalog.value = rawV.filter((v) => v.activo !== false)
  } finally {
    catalogLoading.value = false
  }
}

function cerrarComprobanteModal() {
  showComprobanteModal.value = false
}

function validateComprobanteForm(): string | null {
  const doc = formCliente.documento.trim()
  if (!doc) return 'Ingrese el número de documento del cliente.'
  if (formCliente.tipo_doc === 'RUC' && !/^\d{11}$/.test(doc))
    return 'RUC debe tener 11 dígitos numéricos.'
  if (formCliente.tipo_doc === 'DNI' && !/^\d{8}$/.test(doc)) return 'DNI debe tener 8 dígitos.'
  if (!formCliente.razon_social.trim()) return 'Ingrese la razón social o nombre del cliente.'

  if (!formCab.serie.trim()) return 'Indique la serie del comprobante (defínala en .env o escríbala).'

  if (formCab.condicion_pago === 'CREDITO') {
    const fv = formCab.fecha_vencimiento.trim()
    if (!fv) return 'En venta a crédito indique la fecha de vencimiento.'
    if (formCab.fecha_emision && fv < formCab.fecha_emision)
      return 'La fecha de vencimiento no puede ser anterior a la fecha de emisión.'
  } else {
    const mp = (formCab.medio_pago || '').trim()
    if (!mp) return 'Seleccione el medio de pago (venta al contado).'
    if (!mediosPagoOptions.some((o) => o.value === mp)) return 'Medio de pago no válido.'
  }

  const raw = lineasForm.value.filter((l) => l.item_id !== '')
  if (!raw.length) return 'Agregue al menos una línea con producto/servicio (ítem).'
  const precioHint = formCab.precio_incluye_igv ? 'con IGV' : 'sin IGV'
  for (const ln of raw) {
    const c = Number(ln.cantidad)
    const p = Number(ln.precio_unit)
    if (!Number.isFinite(c) || c <= 0) return 'Revise las cantidades de las líneas.'
    if (!Number.isFinite(p) || p < 0) return `Revise el valor unitario (${precioHint}) de las líneas.`
  }
  return null
}

async function postAltaBorrador(): Promise<number> {
  const raw = lineasForm.value.filter((l) => l.item_id !== '')
  const body: Record<string, unknown> = {
    tipo: formCab.tipo,
    serie: formCab.serie.trim(),
    fecha_emision: formCab.fecha_emision,
    observacion: formCab.observacion.trim(),
    cliente_documento: formCliente.documento.trim(),
    cliente_razon_social: formCliente.razon_social.trim(),
    cliente_email: formCliente.email.trim(),
    cliente_direccion: formCliente.direccion.trim(),
    lineas: raw.map((l) => ({
      item_id: Number(l.item_id),
      cantidad: String(l.cantidad),
      precio_unit: String(l.precio_unit),
    })),
    precio_incluye_igv: formCab.precio_incluye_igv,
    moneda: formCab.moneda,
    condicion_pago: formCab.condicion_pago,
    tipo_operacion: formCab.tipo_operacion,
  }
  if (formCab.condicion_pago === 'CREDITO') {
    body.fecha_vencimiento = formCab.fecha_vencimiento.trim() || null
    body.medio_pago = ''
  } else {
    body.medio_pago = formCab.medio_pago
    body.fecha_vencimiento = null
  }
  if (formCab.vendedor_id !== '' && formCab.vendedor_id != null) {
    body.vendedor_id = Number(formCab.vendedor_id)
  }
  const emp = ctx.empresaId
  if (emp) body.empresa_id = Number(emp)

  const { data } = await api.post<{ id?: number }>('/ventas/documentos/alta-borrador/', body)
  const id = data.id
  if (typeof id !== 'number') throw new Error('Respuesta sin id de documento.')
  return id
}

async function soloGuardarBorrador() {
  const err = validateComprobanteForm()
  if (err) {
    nubError.value = err
    return
  }
  nubSubmitting.value = true
  nubError.value = ''
  try {
    await postAltaBorrador()
    cerrarComprobanteModal()
    load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as Record<string, unknown>
      nubError.value =
        typeof d.detail === 'string'
          ? d.detail
          : Array.isArray(d.detail)
            ? d.detail.map(String).join(' ')
            : 'No se pudo guardar el borrador.'
    } else {
      nubError.value = 'No se pudo guardar el borrador.'
    }
  } finally {
    nubSubmitting.value = false
  }
}

async function emitirComprobante() {
  const err = validateComprobanteForm()
  if (err) {
    nubError.value = err
    return
  }
  nubSubmitting.value = true
  nubError.value = ''
  try {
    const docId = await postAltaBorrador()
    await api.post('/ventas/nubefact/emitir/', { documento_id: docId })
    cerrarComprobanteModal()
    load()
  } catch (e) {
    nubError.value = nubefactEmitErrorMessage(e)
  } finally {
    nubSubmitting.value = false
  }
}

function pdfLink(row: DocRow): string | null {
  const u = row.nubefact_enlace
  return typeof u === 'string' && u.startsWith('http') ? u : null
}
</script>

<template>
  <div class="doc-page">
    <header class="toolbar">
      <div class="toolbar-left">
        <button type="button" class="btn-create" @click="openComprobanteModal">
          <span class="plus" aria-hidden="true">+</span>
          Crear comprobante
        </button>
      </div>
      <div class="toolbar-right">
        <button type="button" class="icon-btn" title="Actualizar" @click="refresh">↻</button>
      </div>
    </header>

    <div v-if="borradorQueryId" class="borrador-banner" role="status">
      <div class="borrador-banner__body">
        <p class="borrador-banner__title">Borrador listo (desde cotización)</p>
        <p class="borrador-banner__desc">
          El valor <strong>#{{ borradorQueryId }}</strong> es el id interno en base de datos, no el número SUNAT. Pulse
          <strong>Emitir con Nubefact</strong> para obtener correlativo, estado SUNAT y PDF, igual que al crear un comprobante
          y emitirlo desde el formulario.
        </p>
        <p v-if="borradorBannerErr" class="borrador-banner__err">{{ borradorBannerErr }}</p>
        <div class="borrador-banner__actions">
          <button
            type="button"
            class="btn-create btn-create--compact"
            :disabled="borradorEmitLoading"
            @click="emitirBorradorDesdeBanner"
          >
            {{ borradorEmitLoading ? 'Emitiendo…' : 'Emitir con Nubefact' }}
          </button>
          <button type="button" class="borrador-banner__dismiss" :disabled="borradorEmitLoading" @click="cerrarBannerBorrador">
            Cerrar aviso
          </button>
        </div>
      </div>
    </div>

    <section class="filters">
      <div class="filter-row filter-row--primary">
        <div class="filter-pair" aria-label="Cliente (documento y razón social)">
          <label class="filter-field filter-field--ruc">
            <span class="filter-label">RUC</span>
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
          <span class="filter-label">Emisión desde</span>
          <input v-model="filters.fecha_emision_desde" type="date" class="filter-inp" />
        </label>
        <label class="filter-field filter-field--date">
          <span class="filter-label">Hasta</span>
          <input v-model="filters.fecha_emision_hasta" type="date" class="filter-inp" />
        </label>
      </div>
    </section>

    <p v-if="errorMsg" class="err-banner">{{ errorMsg }}</p>

    <div class="table-head">
      <span class="total">Total registros: {{ totalCount }}</span>
      <div class="bulk-actions">
        <button type="button" class="btn-ghost" disabled title="Próximamente">Nota de crédito</button>
        <button type="button" class="btn-ghost" disabled title="Próximamente">Nota de débito</button>
        <button type="button" class="btn-ghost" disabled title="Próximamente">Anular</button>
      </div>
    </div>

    <div class="table-card">
      <div v-if="loading" class="state muted">Cargando…</div>
      <template v-else>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th class="th-check">
                  <input v-model="allPageSelected" type="checkbox" aria-label="Seleccionar página" />
                </th>
                <th>F. emisión</th>
                <th>Tipo</th>
                <th>Serie-Núm</th>
                <th>Cliente receptor</th>
                <th>Moneda</th>
                <th class="num">Subtotal</th>
                <th class="num">IGV</th>
                <th class="num">Total</th>
                <th>Estado SUNAT</th>
                <th class="th-sunat-info" title="Clic en el icono de la fila para ver el mensaje SUNAT">ℹ</th>
                <th>PDF</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, idx) in rows"
                :key="typeof row.id === 'number' ? row.id : idx"
                :data-doc-id="typeof row.id === 'number' ? row.id : undefined"
              >
                <td class="td-check">
                  <input
                    v-if="typeof row.id === 'number'"
                    type="checkbox"
                    :checked="rowChecked(row.id)"
                    @change="toggleRow(row.id)"
                  />
                </td>
                <td class="td-compact">{{ formatDate(row.fecha_emision) }}</td>
                <td class="td-tipo-corto" :title="labelTipo(row.tipo)">{{ labelTipoCorto(row.tipo) }}</td>
                <td class="td-compact">{{ serieNum(row) }}</td>
                <td class="cell-receptor">{{ clienteReceptor(row) }}</td>
                <td class="td-compact">{{ row.moneda ?? 'PEN' }}</td>
                <td class="num td-monto">{{ formatMoney(row.subtotal) }}</td>
                <td class="num td-monto">{{ formatMoney(row.igv) }}</td>
                <td class="num strong">{{ formatMoney(row.total) }}</td>
                <td class="cell-sunat-estado">
                  <span
                    v-if="sunatCodigo(row) || sunatDescripcion(row)"
                    :class="sunatPillClass(row)"
                    :title="sunatCodigo(row) ? `Código: ${sunatCodigo(row)}` : undefined"
                  >
                    {{ sunatEstadoTexto(row) }}
                  </span>
                  <span v-else class="muted-cell">—</span>
                </td>
                <td class="cell-sunat-info">
                  <button
                    v-if="sunatDescripcion(row)"
                    type="button"
                    class="btn-sunat-info"
                    aria-label="Ver mensaje SUNAT"
                    @click.stop="openSunatFloat(row)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" class="ico-sunat-info">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.75" />
                      <path
                        stroke="currentColor"
                        stroke-width="1.75"
                        stroke-linecap="round"
                        d="M12 16v-5M12 8h.01"
                      />
                    </svg>
                  </button>
                  <span v-else class="muted-cell">—</span>
                </td>
                <td>
                  <a
                    v-if="pdfLink(row)"
                    :href="pdfLink(row)!"
                    class="link-pdf"
                    target="_blank"
                    rel="noopener noreferrer"
                    >Ver</a
                  >
                  <span v-else class="muted-cell">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!rows.length" class="state empty">
          <span class="empty-icon" aria-hidden="true">📄</span>
          <p>No hay datos</p>
        </div>
        <div v-if="rows.length && (hasNext || hasPrev)" class="pager">
          <button type="button" class="btn-page" :disabled="!hasPrev" @click="goPrev">Anterior</button>
          <span class="page-num">Página {{ page }}</span>
          <button type="button" class="btn-page" :disabled="!hasNext" @click="goNext">Siguiente</button>
        </div>
      </template>
    </div>

    <Teleport to="body">
      <Transition name="sunat-float">
        <div v-if="sunatFloatOpen" class="sunat-float-layer">
          <button
            type="button"
            class="sunat-float-backdrop"
            tabindex="-1"
            aria-label="Cerrar mensaje SUNAT"
            @click="closeSunatFloat"
          />
          <aside
            class="sunat-float-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="sunat-float-heading"
            @click.stop
          >
            <div class="sunat-float-panel__head">
              <h3 id="sunat-float-heading" class="sunat-float-panel__title">{{ sunatFloatTitulo }}</h3>
              <button type="button" class="sunat-float-close" aria-label="Cerrar" @click="closeSunatFloat">
                ×
              </button>
            </div>
            <p v-if="sunatFloatCodigo" class="sunat-float-codigo">Código SUNAT: {{ sunatFloatCodigo }}</p>
            <p class="sunat-float-msg">{{ sunatFloatMensaje }}</p>
          </aside>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <div v-if="showComprobanteModal" class="modal-backdrop" @click.self="cerrarComprobanteModal">
        <div class="modal-nube modal-nube--wide" role="dialog" aria-modal="true" aria-labelledby="cmp-title">
          <h2 id="cmp-title" class="modal-title">Nuevo comprobante de venta</h2>
          <p class="modal-lead">
            Complete los datos del comprobante, el cliente y las líneas. Si el precio unitario
            <strong>ya incluye IGV</strong>, márchelo en la casilla: el sistema lo pasará a valor sin impuesto antes de
            guardar (tasa 18%). Los totales de la parte inferior son una vista previa; confirme antes de emitir.
          </p>

          <div class="form-grid-top">
            <section class="form-card" aria-labelledby="cab-h">
              <h3 id="cab-h" class="form-card-title">Datos del comprobante</h3>
              <div class="form-row-2">
                <label class="modal-field">
                  <span class="modal-lab">Tipo</span>
                  <select v-model="formCab.tipo" class="modal-inp">
                    <option value="FACTURA">Factura</option>
                    <option value="BOLETA">Boleta</option>
                  </select>
                </label>
                <label class="modal-field">
                  <span class="modal-lab">Serie</span>
                  <input
                    v-model="formCab.serie"
                    class="modal-inp"
                    maxlength="10"
                    :placeholder="
                      (formCab.tipo === 'BOLETA' ? seriesNubefact.BOLETA : seriesNubefact.FACTURA) ||
                      'Serie'
                    "
                    :title="tituloAyudaSeries"
                  />
                </label>
              </div>
              <div class="form-row-2">
                <label class="modal-field">
                  <span class="modal-lab">Fecha emisión</span>
                  <input v-model="formCab.fecha_emision" type="date" class="modal-inp" />
                </label>
                <label class="modal-field">
                  <span class="modal-lab">Moneda</span>
                  <select v-model="formCab.moneda" class="modal-inp">
                    <option value="PEN">PEN (S/)</option>
                    <option value="USD">USD ($)</option>
                  </select>
                </label>
              </div>
              <label class="modal-field modal-field--check">
                <input v-model="formCab.precio_incluye_igv" type="checkbox" class="modal-check" />
                <span class="modal-check-label">El precio unitario incluye IGV</span>
              </label>
              <div class="form-row-2">
                <label class="modal-field">
                  <span class="modal-lab">Condición</span>
                  <select v-model="formCab.condicion_pago" class="modal-inp">
                    <option value="CONTADO">Contado</option>
                    <option value="CREDITO">Crédito</option>
                  </select>
                </label>
                <label v-if="formCab.condicion_pago === 'CONTADO'" class="modal-field">
                  <span class="modal-lab">Medio de pago</span>
                  <select v-model="formCab.medio_pago" class="modal-inp">
                    <option v-for="opt in mediosPagoOptions" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
                <label v-else class="modal-field">
                  <span class="modal-lab">Fecha vencimiento</span>
                  <input v-model="formCab.fecha_vencimiento" type="date" class="modal-inp" />
                </label>
              </div>
              <div class="form-row-2">
                <label class="modal-field">
                  <span class="modal-lab">Operación</span>
                  <select v-model="formCab.tipo_operacion" class="modal-inp">
                    <option v-for="opt in tiposOperacionOptions" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
                <label class="modal-field">
                  <span class="modal-lab">Vendedor</span>
                  <select v-model="formCab.vendedor_id" class="modal-inp">
                    <option value="">— Opcional —</option>
                    <option v-for="v in vendedoresCatalog" :key="v.id" :value="v.id">
                      {{ v.nombre_completo?.trim() || `ID ${v.id}` }}
                    </option>
                  </select>
                </label>
              </div>
              <label class="modal-field">
                <span class="modal-lab">Observación</span>
                <textarea
                  v-model="formCab.observacion"
                  class="modal-textarea"
                  rows="2"
                  placeholder="Notas internas / referencia"
                />
              </label>
            </section>

            <section class="form-card" aria-labelledby="cli-h">
              <h3 id="cli-h" class="form-card-title">Cliente receptor</h3>
              <div class="cliente-doc-grid">
                <label class="modal-field">
                  <span class="modal-lab">Tipo doc.</span>
                  <select v-model="formCliente.tipo_doc" class="modal-inp">
                    <option value="RUC">RUC</option>
                    <option value="DNI">DNI</option>
                  </select>
                </label>
                <div class="modal-field modal-field--doc">
                  <span class="modal-lab">Número doc.</span>
                  <div
                    class="doc-num-row"
                    @focusin="onDocNumFocusIn"
                    @focusout="onDocNumFocusOut"
                  >
                    <div class="doc-num-input-wrap">
                      <input
                        v-model="formCliente.documento"
                        class="modal-inp"
                        maxlength="20"
                        autocomplete="off"
                        :placeholder="formCliente.tipo_doc === 'RUC' ? '20123456789' : '12345678'"
                        @input="docSuggestOpen = true"
                      />
                      <ul
                        v-if="docSuggestOpen && clientesMatches.length"
                        class="doc-suggest"
                        role="listbox"
                        aria-label="Clientes que coinciden"
                      >
                        <li
                          v-for="c in clientesMatches"
                          :key="c.id"
                          role="option"
                          class="doc-suggest__item"
                          @mousedown.prevent="pickClienteCatalogo(c)"
                        >
                          <span class="doc-suggest__doc">{{ c.documento?.trim() || '—' }}</span>
                          <span class="doc-suggest__rs">{{ c.razon_social?.trim() || '—' }}</span>
                        </li>
                      </ul>
                    </div>
                    <button
                      type="button"
                      class="btn-consult-padron"
                      :disabled="!puedeConsultarPadron || consultDocLoading"
                      :title="
                        formCliente.tipo_doc === 'RUC'
                          ? 'Consultar razón social en SUNAT (11 dígitos)'
                          : 'Consultar nombre en RENIEC (8 dígitos)'
                      "
                      @click="consultarPadronCliente"
                    >
                      {{
                        consultDocLoading
                          ? '…'
                          : formCliente.tipo_doc === 'RUC'
                            ? 'Consultar SUNAT'
                            : 'Consultar RENIEC'
                      }}
                    </button>
                  </div>
                  <p
                    v-if="clienteConsultMsg"
                    class="doc-num-feedback"
                    :class="{ 'doc-num-feedback--err': clienteConsultIsError }"
                  >
                    {{ clienteConsultMsg }}
                  </p>
                </div>
              </div>
              <label class="modal-field">
                <span class="modal-lab">Razón social / nombres</span>
                <input
                  v-model="formCliente.razon_social"
                  class="modal-inp"
                  placeholder="Según documento"
                />
              </label>
              <label class="modal-field">
                <span class="modal-lab">Correo</span>
                <input v-model="formCliente.email" type="email" class="modal-inp" placeholder="opcional" />
              </label>
              <label class="modal-field">
                <span class="modal-lab">Dirección</span>
                <input v-model="formCliente.direccion" class="modal-inp" placeholder="opcional" />
              </label>
            </section>
          </div>

          <section class="form-card form-card--lines" aria-labelledby="lin-h">
            <div class="lines-head">
              <h3 id="lin-h" class="form-card-title">Productos / servicios</h3>
              <span class="catalog-hint">{{ catalogLoading ? 'Cargando ítems…' : `${itemCatalog.length} ítems` }}</span>
            </div>
            <div class="lines-table-wrap">
              <table class="lines-table">
                <thead>
                  <tr>
                    <th>Ítem (catálogo)</th>
                    <th>UM</th>
                    <th>Cantidad</th>
                    <th>{{ precioColumnLabel }}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(ln, idx) in lineasForm" :key="idx">
                    <td>
                      <select v-model="ln.item_id" class="modal-inp modal-inp--compact">
                        <option value="" disabled>Seleccionar…</option>
                        <option v-for="it in itemCatalog" :key="it.id" :value="it.id">{{ itemLabel(it) }}</option>
                      </select>
                    </td>
                    <td class="um-cell">
                      {{
                        itemCatalog.find((x) => x.id === ln.item_id)?.unidad_medida_codigo?.trim() ||
                        '—'
                      }}
                    </td>
                    <td><input v-model="ln.cantidad" class="modal-inp modal-inp--num" type="text" inputmode="decimal" /></td>
                    <td>
                      <input v-model="ln.precio_unit" class="modal-inp modal-inp--num" type="text" inputmode="decimal" />
                    </td>
                    <td>
                      <button type="button" class="btn-icon-del" title="Quitar" @click="removeLinea(idx)">✕</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button type="button" class="btn-add-line" @click="addLinea">+ Agregar línea</button>

            <div class="totals-preview">
              <div>
                <span class="tot-label">T. gravado</span>
                <span class="tot-val">{{ simboloMonedaPreview }} {{ totalGravada.toFixed(2) }}</span>
              </div>
              <div>
                <span class="tot-label">IGV 18%</span>
                <span class="tot-val">{{ simboloMonedaPreview }} {{ totalIgvPreview.toFixed(2) }}</span>
              </div>
              <div class="tot-row-total">
                <span class="tot-label">Total</span>
                <span class="tot-val tot-grand">{{ simboloMonedaPreview }} {{ totalDocPreview.toFixed(2) }}</span>
              </div>
            </div>
          </section>

          <p v-if="nubError" class="modal-err">{{ nubError }}</p>

          <div class="modal-actions modal-actions--split">
            <button type="button" class="btn-modal-close" :disabled="nubSubmitting" @click="cerrarComprobanteModal">
              Cerrar
            </button>
            <div class="modal-actions-right">
              <button
                type="button"
                class="btn-modal-secondary"
                :disabled="nubSubmitting"
                @click="soloGuardarBorrador"
              >
                {{ nubSubmitting ? '…' : 'Solo guardar borrador' }}
              </button>
              <button
                type="button"
                class="btn-modal-primary"
                :disabled="nubSubmitting"
                @click="emitirComprobante"
              >
                {{ nubSubmitting ? 'Procesando…' : 'Emitir comprobante' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.doc-page {
  width: 100%;
  max-width: 100%;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.toolbar-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
}

.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 1.1rem;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #0ea5e9, #0284c7);
  color: #fff;
  font-weight: 700;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  text-decoration: none;
  box-shadow: 0 4px 14px rgba(14, 165, 233, 0.35);
  cursor: pointer;
  font: inherit;
}

.btn-create:hover {
  filter: brightness(1.06);
  text-decoration: none;
}

.plus {
  font-size: 1.25rem;
  line-height: 1;
  font-weight: 300;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.icon-btn {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #475569;
  font-size: 1.1rem;
  cursor: pointer;
  line-height: 1;
}

.icon-btn:hover {
  background: #f8fafc;
  border-color: #94a3b8;
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
  border-color: #0ea5e9;
  box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.2);
}

.filter-select {
  cursor: pointer;
}

.err-banner {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.85rem;
}

.borrador-banner {
  margin: 0 0 0.85rem;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  border: 1px solid #bae6fd;
  background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
  color: #0c4a6e;
  font-size: 0.82rem;
  line-height: 1.45;
}

.borrador-banner__title {
  margin: 0 0 0.35rem;
  font-weight: 700;
  font-size: 0.88rem;
  color: #075985;
}

.borrador-banner__desc {
  margin: 0;
}

.borrador-banner__err {
  margin: 0.45rem 0 0;
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.8rem;
}

.borrador-banner__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  margin-top: 0.65rem;
}

.btn-create--compact {
  padding: 0.38rem 0.85rem;
  font-size: 0.76rem;
  letter-spacing: 0.03em;
  box-shadow: 0 2px 10px rgba(14, 165, 233, 0.28);
}

.borrador-banner__dismiss {
  padding: 0.35rem 0.65rem;
  border-radius: 8px;
  border: 1px solid #7dd3fc;
  background: #fff;
  color: #0369a1;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
}

.borrador-banner__dismiss:hover:not(:disabled) {
  background: #f0f9ff;
}

.borrador-banner__dismiss:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.table-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.total {
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
}

.bulk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.btn-ghost {
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: not-allowed;
  opacity: 0.75;
}

.table-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  min-height: 12rem;
  position: relative;
}

.table-scroll {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.data-table th,
.data-table td {
  padding: 0.42rem 0.5rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: middle;
}

.data-table tbody td {
  color: #0f172a;
  font-weight: 500;
  font-size: 0.8rem;
}

.data-table tbody td .muted-cell {
  font-weight: 400;
}

.data-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 700;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.th-check,
.td-check {
  width: 2.5rem;
  text-align: center;
}

.data-table tbody tr:hover {
  background: #f8fafc;
}

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.strong {
  font-weight: 700;
  color: #0f172a;
}

.td-compact,
.td-tipo-corto {
  white-space: nowrap;
}

.td-tipo-corto {
  text-align: center;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.td-monto {
  font-weight: 600;
  color: #0f172a;
}

.cell-receptor {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.th-sunat-info {
  width: 2.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.85rem;
}

.cell-sunat-estado {
  white-space: nowrap;
}

.cell-sunat-info {
  text-align: center;
  vertical-align: middle;
}

.btn-sunat-info {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.85rem;
  height: 1.85rem;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: #0284c7;
  color: #fff;
  cursor: pointer;
  vertical-align: middle;
}

.btn-sunat-info:hover {
  background: #0369a1;
}

.ico-sunat-info {
  width: 1.05rem;
  height: 1.05rem;
}

.sunat-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.sunat-pill--ok {
  background: #dcfce7;
  color: #166534;
}

.sunat-pill--warn {
  background: #ffedd5;
  color: #9a3412;
}

.sunat-pill--muted {
  background: #e2e8f0;
  color: #475569;
}

.sunat-pill--empty {
  background: #f1f5f9;
  color: #64748b;
}

.sunat-float-enter-active,
.sunat-float-leave-active {
  transition: opacity 0.2s ease;
}

.sunat-float-enter-active .sunat-float-panel,
.sunat-float-leave-active .sunat-float-panel {
  transition: transform 0.22s ease, opacity 0.2s ease;
}

.sunat-float-enter-from,
.sunat-float-leave-to {
  opacity: 0;
}

.sunat-float-enter-from .sunat-float-panel,
.sunat-float-leave-to .sunat-float-panel {
  opacity: 0;
  transform: translateY(-0.5rem) scale(0.98);
}

.sunat-float-layer {
  position: fixed;
  inset: 0;
  z-index: 75;
  pointer-events: none;
}

.sunat-float-backdrop {
  position: absolute;
  inset: 0;
  pointer-events: auto;
  border: none;
  padding: 0;
  margin: 0;
  background: rgba(15, 23, 42, 0.14);
  cursor: pointer;
}

.sunat-float-panel {
  position: absolute;
  top: max(1rem, env(safe-area-inset-top, 0px));
  right: max(1rem, env(safe-area-inset-right, 0px));
  width: min(22rem, calc(100vw - 2rem));
  max-height: min(70vh, 24rem);
  overflow: auto;
  pointer-events: auto;
  background: #fff;
  border-radius: 12px;
  box-shadow:
    0 16px 48px rgba(15, 23, 42, 0.2),
    0 0 0 1px rgba(148, 163, 184, 0.35);
  padding: 0.95rem 1.05rem 1.1rem;
}

.sunat-float-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
  padding-bottom: 0.6rem;
  border-bottom: 1px solid #e2e8f0;
}

.sunat-float-panel__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.35;
}

.sunat-float-close {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  margin: -0.25rem -0.35rem 0 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
}

.sunat-float-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.sunat-float-codigo {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.sunat-float-msg {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}

.state {
  padding: 2.5rem 1rem;
  text-align: center;
}

.state.muted {
  color: #94a3b8;
}

.state.empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  color: #94a3b8;
}

.state.empty p {
  margin: 0.35rem 0 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.empty-icon {
  font-size: 2.5rem;
  opacity: 0.45;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.75rem;
  border-top: 1px solid #e2e8f0;
}

.btn-page {
  padding: 0.35rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  color: #334155;
  cursor: pointer;
}

.btn-page:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.page-num {
  font-size: 0.82rem;
  color: #64748b;
}

.link-pdf {
  font-size: 0.78rem;
  font-weight: 700;
  color: #0284c7;
}

.muted-cell {
  color: #64748b;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.modal-nube {
  width: 100%;
  max-width: 26rem;
  max-height: min(90vh, 36rem);
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  padding: 1.35rem 1.4rem;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.25);
}

.modal-title {
  margin: 0 0 0.35rem;
  font-size: 1.15rem;
  color: #0f172a;
}

.modal-lead {
  margin: 0 0 1rem;
  font-size: 0.82rem;
  color: #64748b;
  line-height: 1.45;
}

.modal-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.85rem;
}

.modal-lab {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.modal-inp {
  width: 100%;
  padding: 0.5rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.85rem;
}

.modal-inp:focus {
  outline: none;
  border-color: #0ea5e9;
  box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.2);
}

.modal-hint {
  font-size: 0.72rem;
  color: #94a3b8;
}

.modal-check {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  font-size: 0.82rem;
  color: #334155;
  margin-bottom: 0.75rem;
  cursor: pointer;
}

.modal-check input {
  margin-top: 0.2rem;
}

.modal-err {
  margin: 0 0 0.5rem;
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.82rem;
}

.modal-ok {
  margin: 0 0 0.5rem;
  color: #047857;
  font-size: 0.82rem;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.btn-modal-primary {
  flex: 1;
  min-width: 8rem;
  padding: 0.55rem 1rem;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #0ea5e9, #0284c7);
  color: #fff;
  font-weight: 700;
  font-size: 0.82rem;
  cursor: pointer;
}

.btn-modal-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-modal-close {
  padding: 0.55rem 1rem;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
}

.btn-modal-close:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.modal-nube--wide {
  max-width: min(52rem, 100%);
  max-height: min(92vh, 48rem);
}

.form-grid-top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
  margin-bottom: 0.85rem;
}

@media (max-width: 52rem) {
  .form-grid-top {
    grid-template-columns: 1fr;
  }
}

.form-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0.85rem 1rem;
  background: #f8fafc;
}

.form-card--lines {
  margin-bottom: 0.85rem;
  background: #fff;
}

.form-card-title {
  margin: 0 0 0.65rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: #334155;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem;
}

@media (max-width: 36rem) {
  .form-row-2 {
    grid-template-columns: 1fr;
  }
}

.cliente-doc-grid {
  display: grid;
  grid-template-columns: minmax(5.5rem, 7.5rem) 1fr;
  gap: 0.65rem 0.85rem;
  align-items: start;
  margin-bottom: 0.65rem;
}

@media (max-width: 36rem) {
  .cliente-doc-grid {
    grid-template-columns: 1fr;
  }
}

.modal-field--doc {
  margin-bottom: 0;
  min-width: 0;
}

.doc-num-row {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.doc-num-input-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
}

.doc-suggest {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 3px);
  margin: 0;
  padding: 0.2rem 0;
  list-style: none;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 12px 28px rgb(15 23 42 / 14%);
  max-height: 11.5rem;
  overflow-y: auto;
  z-index: 10;
}

.doc-suggest__item {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  padding: 0.45rem 0.6rem;
  cursor: pointer;
  font-size: 0.78rem;
  border-bottom: 1px solid #f1f5f9;
}

.doc-suggest__item:last-child {
  border-bottom: none;
}

.doc-suggest__item:hover {
  background: #e0f2fe;
}

.doc-suggest__doc {
  font-weight: 700;
  color: #0f172a;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
}

.doc-suggest__rs {
  color: #475569;
  line-height: 1.25;
}

.btn-consult-padron {
  flex-shrink: 0;
  align-self: stretch;
  padding: 0.45rem 0.65rem;
  border-radius: 8px;
  border: 1px solid #0284c7;
  background: #f0f9ff;
  color: #0369a1;
  font-weight: 700;
  font-size: 0.68rem;
  line-height: 1.25;
  cursor: pointer;
  max-width: 6.4rem;
  text-align: center;
}

.btn-consult-padron:hover:not(:disabled) {
  background: #e0f2fe;
}

.btn-consult-padron:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.doc-num-feedback {
  margin: 0.35rem 0 0;
  font-size: 0.72rem;
  color: #047857;
  line-height: 1.35;
}

.doc-num-feedback--err {
  color: #b91c1c;
}

.form-card .modal-field {
  margin-bottom: 0.65rem;
}

.form-card .modal-field:last-child {
  margin-bottom: 0;
}

.modal-field--check {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  user-select: none;
}

.modal-check {
  width: 1rem;
  height: 1rem;
  accent-color: #0284c7;
  flex-shrink: 0;
}

.modal-check-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: #334155;
}

.modal-textarea {
  width: 100%;
  padding: 0.5rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.85rem;
  font-family: inherit;
  resize: vertical;
  min-height: 3rem;
}

.modal-textarea:focus {
  outline: none;
  border-color: #0ea5e9;
  box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.2);
}

.lines-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.catalog-hint {
  font-size: 0.72rem;
  color: #94a3b8;
}

.lines-table-wrap {
  overflow-x: auto;
  margin: 0.5rem 0 0.5rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.lines-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.lines-table th,
.lines-table td {
  padding: 0.45rem 0.5rem;
  border-bottom: 1px solid #e2e8f0;
  vertical-align: middle;
}

.lines-table th {
  background: #f8fafc;
  text-align: left;
  font-weight: 700;
  color: #475569;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.lines-table tbody tr:last-child td {
  border-bottom: none;
}

.um-cell {
  color: #64748b;
  white-space: nowrap;
  max-width: 5rem;
  overflow: hidden;
  text-overflow: ellipsis;
}

.modal-inp--compact {
  min-width: 12rem;
}

.modal-inp--num {
  max-width: 7rem;
  font-variant-numeric: tabular-nums;
}

.btn-icon-del {
  padding: 0.25rem 0.45rem;
  border: none;
  border-radius: 6px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.85rem;
  cursor: pointer;
  line-height: 1;
}

.btn-icon-del:hover {
  background: #fee2e2;
}

.btn-add-line {
  margin-top: 0.25rem;
  padding: 0.4rem 0.75rem;
  border-radius: 8px;
  border: 1px dashed #94a3b8;
  background: #fff;
  color: #475569;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
}

.btn-add-line:hover {
  border-color: #0ea5e9;
  color: #0284c7;
}

.totals-preview {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-width: 16rem;
  margin-left: auto;
}

.totals-preview > div {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
}

.tot-label {
  font-size: 0.78rem;
  color: #64748b;
}

.tot-val {
  font-size: 0.88rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
}

.tot-row-total {
  padding-top: 0.35rem;
  margin-top: 0.2rem;
  border-top: 1px solid #e2e8f0;
}

.tot-grand {
  font-size: 1.05rem;
  font-weight: 800;
  color: #0284c7;
}

.modal-actions--split {
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
}

.modal-actions-right {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn-modal-secondary {
  padding: 0.55rem 1rem;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
}

.btn-modal-secondary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
