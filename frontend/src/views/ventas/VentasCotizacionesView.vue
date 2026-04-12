<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'

const router = useRouter()

type CotRow = Record<string, unknown> & { id?: number }

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
  { value: 'EXPORTACION', label: 'Exportación' },
] as const

function isoDate(d: Date) {
  return d.toISOString().slice(0, 10)
}

const hasta = new Date()
const desde = new Date()
desde.setDate(desde.getDate() - 90)

const filters = reactive({
  cliente_documento: '',
  cliente_razon_social: '',
  estado: '',
  fecha_desde: isoDate(desde),
  fecha_hasta: isoDate(hasta),
})

const rows = ref<CotRow[]>([])
const loading = ref(false)
const errorMsg = ref('')
const page = ref(1)
const totalCount = ref(0)
const hasNext = ref(false)
const hasPrev = ref(false)

const showModal = ref(false)
const editingId = ref<number | null>(null)
const catalogLoading = ref(false)
const formError = ref('')
const submitting = ref(false)

const modalTitulo = computed(() =>
  editingId.value != null ? 'Editar cotización' : 'Nueva cotización (borrador)',
)

const botonGuardarModal = computed(() =>
  editingId.value != null ? 'Guardar cambios' : 'Guardar borrador',
)

type ItemCat = { id: number; codigo?: string; nombre: string; unidad_medida_codigo?: string }
type ClienteCat = {
  id: number
  documento?: string
  razon_social?: string
  email?: string
  direccion?: string
  activo?: boolean
}
const itemCatalog = ref<ItemCat[]>([])
const clientesCatalog = ref<ClienteCat[]>([])
const vendedoresCatalog = ref<{ id: number; nombre_completo?: string; activo?: boolean }[]>([])

const consultDocLoading = ref(false)
const clienteConsultMsg = ref('')
const clienteConsultIsError = ref(false)
const docSuggestOpen = ref(false)
let docSuggestCloseTimer: ReturnType<typeof setTimeout> | null = null

const formCliente = reactive({
  tipo_doc: 'RUC' as 'RUC' | 'DNI',
  documento: '',
  razon_social: '',
  email: '',
  direccion: '',
})

const formCab = reactive({
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

type LineaForm = { item_id: number | ''; cantidad: string; precio_unit: string }
const lineasForm = ref<LineaForm[]>([{ item_id: '', cantidad: '1', precio_unit: '' }])

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

const ctx = useAppContextStore()

const showConvert = ref(false)
const convertRow = ref<CotRow | null>(null)
const convertTipo = ref<'BOLETA' | 'FACTURA'>('FACTURA')
const convertSerie = ref('')
const convertFecha = ref('')
const convertError = ref('')
const convertSubmitting = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function onFiltersChange() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debounceTimer = null
    page.value = 1
    load()
  }, 320)
}

watch(filters, onFiltersChange, { deep: true })

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const params = new URLSearchParams()
    if (filters.cliente_documento.trim()) params.set('cliente_documento', filters.cliente_documento.trim())
    if (filters.cliente_razon_social.trim())
      params.set('cliente_razon_social', filters.cliente_razon_social.trim())
    if (filters.estado.trim()) params.set('estado', filters.estado.trim())
    if (filters.fecha_desde) params.set('fecha_desde', filters.fecha_desde)
    if (filters.fecha_hasta) params.set('fecha_hasta', filters.fecha_hasta)
    params.set('page', String(page.value))

    const { data } = await api.get<{
      results?: CotRow[]
      count?: number
      next?: string | null
      previous?: string | null
    }>(`/ventas/cotizaciones/?${params.toString()}`)

    rows.value = Array.isArray(data) ? data : (data.results ?? [])
    totalCount.value = typeof data === 'object' && data && 'count' in data ? Number(data.count) : rows.value.length
    hasNext.value = !!(typeof data === 'object' && data && data.next)
    hasPrev.value = !!(typeof data === 'object' && data && data.previous)
  } catch {
    errorMsg.value = 'No se pudo cargar las cotizaciones.'
    rows.value = []
    totalCount.value = 0
    hasNext.value = false
    hasPrev.value = false
  } finally {
    loading.value = false
  }
}

onMounted(() => load())

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

function formatDate(v: unknown): string {
  if (typeof v !== 'string' || !v) return '—'
  return v.slice(0, 10).split('-').reverse().join('/')
}

function formatMoney(v: unknown): string {
  const n = typeof v === 'string' ? parseFloat(v) : typeof v === 'number' ? v : NaN
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function rowEstado(row: CotRow): string {
  const e = row.estado
  return typeof e === 'string' ? e : ''
}

function serieNumero(row: CotRow): string {
  const s = row.serie_numero
  if (typeof s === 'string' && s.trim()) return s
  const serie = typeof row.serie === 'string' ? row.serie : ''
  const num = typeof row.numero === 'string' ? row.numero : ''
  if (serie && num) return `${serie}-${num}`
  return '—'
}

function docConvertidoId(row: CotRow): number | null {
  const v = row.documento_convertido_id
  return typeof v === 'number' ? v : null
}

/** API: false si el comprobante vinculado ya fue emitido (SUNAT). */
function cotizacionPuedeEditarEliminar(row: CotRow): boolean {
  const v = row.puede_editar_eliminar
  if (v === false) return false
  return true
}

/** Hay borrador de venta vinculado aún sin enviar a Nubefact/SUNAT. */
function filaBorradorNubefactPendiente(row: CotRow): boolean {
  return docConvertidoId(row) != null && cotizacionPuedeEditarEliminar(row)
}

function puedeEditarRow(row: CotRow): boolean {
  return cotizacionPuedeEditarEliminar(row)
}

function puedeEliminarRow(row: CotRow): boolean {
  if (!cotizacionPuedeEditarEliminar(row)) return false
  const est = rowEstado(row)
  return est === 'BORRADOR' || est === 'EMITIDO'
}

function addLinea() {
  lineasForm.value = [...lineasForm.value, { item_id: '', cantidad: '1', precio_unit: '' }]
}

function removeLinea(idx: number) {
  lineasForm.value = lineasForm.value.filter((_, i) => i !== idx)
  if (!lineasForm.value.length) lineasForm.value = [{ item_id: '', cantidad: '1', precio_unit: '' }]
}

function itemLabel(it: ItemCat) {
  const c = (it.codigo || '').trim()
  return c ? `${c} — ${it.nombre}` : it.nombre
}

const factorIgv = 1.18
const simboloMonedaPreview = computed(() => (formCab.moneda === 'USD' ? 'US$' : 'S/'))

const totalGravada = computed(() => {
  let s = 0
  for (const ln of lineasForm.value) {
    if (ln.item_id === '') continue
    const c = Number(ln.cantidad)
    let p = Number(ln.precio_unit)
    if (!Number.isFinite(c) || c <= 0 || !Number.isFinite(p) || p < 0) continue
    if (formCab.precio_incluye_igv) p /= factorIgv
    s += c * p
  }
  return Math.round(s * 100) / 100
})

const totalIgvPreview = computed(() => Math.round(totalGravada.value * 0.18 * 100) / 100)
const totalDocPreview = computed(() => Math.round((totalGravada.value + totalIgvPreview.value) * 100) / 100)

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
          clienteConsultMsg.value = 'Razón social sugerida por SUNAT (revise antes de guardar).'
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
          clienteConsultMsg.value = 'Nombre sugerido por RENIEC (revise antes de guardar).'
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

async function openModal() {
  editingId.value = null
  formError.value = ''
  clienteConsultMsg.value = ''
  clienteConsultIsError.value = false
  docSuggestOpen.value = false
  showModal.value = true
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
  try {
    const [itemsRes, cliRes, vendRes] = await Promise.all([
      api.get<{ results?: ItemCat[] }>('/inventario/items/?page_size=500').catch(() => null),
      api.get<{ results?: ClienteCat[] }>('/core/clientes/?page_size=500&ordering=razon_social').catch(() => null),
      api.get<{ results?: { id: number; nombre_completo?: string; activo?: boolean }[] }>(
        '/core/vendedores/?page_size=500',
      ).catch(() => null),
    ])
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

function cerrarModal() {
  showModal.value = false
  editingId.value = null
}

type CotizacionDetalleLinea = { item: number; cantidad: unknown; precio_unit: unknown }

async function openEdit(row: CotRow) {
  const id = row.id
  if (typeof id !== 'number' || !puedeEditarRow(row)) return
  formError.value = ''
  clienteConsultMsg.value = ''
  clienteConsultIsError.value = false
  docSuggestOpen.value = false
  editingId.value = id
  showModal.value = true
  catalogLoading.value = true
  itemCatalog.value = []
  clientesCatalog.value = []
  vendedoresCatalog.value = []
  try {
    const [cotRes, itemsRes, cliRes, vendRes] = await Promise.all([
      api.get<Record<string, unknown>>(`/ventas/cotizaciones/${id}/`),
      api.get<{ results?: ItemCat[] }>('/inventario/items/?page_size=500').catch(() => null),
      api.get<{ results?: ClienteCat[] }>('/core/clientes/?page_size=500&ordering=razon_social').catch(() => null),
      api.get<{ results?: { id: number; nombre_completo?: string; activo?: boolean }[] }>(
        '/core/vendedores/?page_size=500',
      ).catch(() => null),
    ])
    const c = cotRes.data
    itemCatalog.value = itemsRes?.data?.results ?? []
    const cd = cliRes?.data
    clientesCatalog.value = Array.isArray(cd) ? cd : (cd?.results ?? [])
    const vd = vendRes?.data
    const rawV = Array.isArray(vd) ? vd : (vd?.results ?? [])
    vendedoresCatalog.value = rawV.filter((v) => v.activo !== false)

    const doc = typeof c.cliente_documento === 'string' ? c.cliente_documento.trim() : ''
    formCliente.documento = doc.slice(0, 20)
    const digits = formCliente.documento.replace(/\D/g, '')
    formCliente.tipo_doc = digits.length === 11 ? 'RUC' : digits.length === 8 ? 'DNI' : 'RUC'
    formCliente.razon_social =
      typeof c.cliente_razon_social === 'string' ? c.cliente_razon_social : ''
    formCliente.email = ''
    formCliente.direccion = ''

    const fe = c.fecha
    formCab.fecha_emision =
      typeof fe === 'string' && fe.length >= 10 ? fe.slice(0, 10) : isoDate(new Date())
    formCab.observacion = typeof c.observacion === 'string' ? c.observacion : ''
    formCab.precio_incluye_igv = !!c.precio_incluye_igv
    formCab.moneda = c.moneda === 'USD' ? 'USD' : 'PEN'
    formCab.condicion_pago = c.condicion_pago === 'CREDITO' ? 'CREDITO' : 'CONTADO'
    const fv = c.fecha_vencimiento
    formCab.fecha_vencimiento = typeof fv === 'string' && fv.length >= 10 ? fv.slice(0, 10) : ''
    formCab.medio_pago =
      typeof c.medio_pago === 'string' && c.medio_pago.trim()
        ? c.medio_pago.trim()
        : 'TRANSFERENCIA'
    formCab.tipo_operacion =
      typeof c.tipo_operacion === 'string' ? c.tipo_operacion : 'VENTA_INTERNA'
    const vid = c.vendedor
    formCab.vendedor_id = typeof vid === 'number' ? vid : ''

    const rawLineas = Array.isArray(c.lineas) ? (c.lineas as CotizacionDetalleLinea[]) : []
    if (rawLineas.length) {
      lineasForm.value = rawLineas.map((ln) => ({
        item_id: typeof ln.item === 'number' ? ln.item : '',
        cantidad: String(ln.cantidad ?? ''),
        precio_unit: String(ln.precio_unit ?? ''),
      }))
    } else {
      lineasForm.value = [{ item_id: '', cantidad: '1', precio_unit: '' }]
    }
  } catch {
    formError.value = 'No se pudo cargar la cotización.'
    cerrarModal()
  } finally {
    catalogLoading.value = false
  }
}

function validateForm(): string | null {
  const doc = formCliente.documento.trim()
  if (!doc) return 'Ingrese el documento del cliente.'
  if (formCliente.tipo_doc === 'RUC' && !/^\d{11}$/.test(doc)) return 'RUC debe tener 11 dígitos.'
  if (formCliente.tipo_doc === 'DNI' && !/^\d{8}$/.test(doc)) return 'DNI debe tener 8 dígitos.'
  if (!formCliente.razon_social.trim()) return 'Ingrese la razón social o nombre del cliente.'

  if (formCab.condicion_pago === 'CREDITO') {
    const fv = formCab.fecha_vencimiento.trim()
    if (!fv) return 'Indique la fecha de vencimiento (crédito).'
    if (formCab.fecha_emision && fv < formCab.fecha_emision)
      return 'La fecha de vencimiento no puede ser anterior a la fecha de emisión.'
  } else {
    const mp = (formCab.medio_pago || '').trim()
    if (!mp) return 'Seleccione el medio de pago (contado).'
    if (!mediosPagoOptions.some((o) => o.value === mp)) return 'Medio de pago no válido.'
  }

  const raw = lineasForm.value.filter((l) => l.item_id !== '')
  if (!raw.length) return 'Agregue al menos una línea con ítem.'
  const precioHint = formCab.precio_incluye_igv ? 'con IGV' : 'sin IGV'
  for (const ln of raw) {
    const c = Number(ln.cantidad)
    const p = Number(ln.precio_unit)
    if (!Number.isFinite(c) || c <= 0) return 'Revise las cantidades.'
    if (!Number.isFinite(p) || p < 0) return `Revise el valor unitario (${precioHint}).`
  }
  return null
}

async function guardarCotizacionBorrador() {
  const err = validateForm()
  if (err) {
    formError.value = err
    return
  }
  submitting.value = true
  formError.value = ''
  const raw = lineasForm.value.filter((l) => l.item_id !== '')
  const body: Record<string, unknown> = {
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
  if (formCab.vendedor_id !== '' && formCab.vendedor_id != null) body.vendedor_id = Number(formCab.vendedor_id)
  const emp = ctx.empresaId
  if (emp) body.empresa_id = Number(emp)

  try {
    if (editingId.value != null) {
      await api.patch(`/ventas/cotizaciones/${editingId.value}/`, body)
    } else {
      await api.post('/ventas/cotizaciones/alta-borrador/', body)
    }
    cerrarModal()
    load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as Record<string, unknown>
      formError.value =
        typeof d.detail === 'string'
          ? d.detail
          : Array.isArray(d.detail)
            ? d.detail.map(String).join(' ')
            : 'No se pudo guardar la cotización.'
    } else {
      formError.value = 'No se pudo guardar la cotización.'
    }
  } finally {
    submitting.value = false
  }
}

const actionBusyId = ref<number | null>(null)

async function emitirInterna(row: CotRow) {
  const id = row.id
  if (typeof id !== 'number') return
  actionBusyId.value = id
  errorMsg.value = ''
  try {
    await api.post(`/ventas/cotizaciones/${id}/emitir-cotizacion/`)
    await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as { detail?: string }
      errorMsg.value = typeof d.detail === 'string' ? d.detail : 'No se pudo emitir la cotización.'
    } else {
      errorMsg.value = 'No se pudo emitir la cotización.'
    }
  } finally {
    actionBusyId.value = null
  }
}

function nubefactEmitErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e) && e.response?.data) {
    const d = e.response.data as Record<string, unknown>
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) return d.detail.map(String).join(' ')
    if (d.errors != null) return typeof d.errors === 'string' ? d.errors : JSON.stringify(d.errors)
    return 'No se pudo emitir el comprobante con Nubefact.'
  }
  return 'Error de conexión o desconocido.'
}

async function emitirNubefactDesdeCotizacion(row: CotRow) {
  const cotId = row.id
  const docId = docConvertidoId(row)
  if (typeof cotId !== 'number' || typeof docId !== 'number') return
  actionBusyId.value = cotId
  errorMsg.value = ''
  try {
    await api.post('/ventas/nubefact/emitir/', { documento_id: docId })
    await load()
  } catch (e) {
    errorMsg.value = nubefactEmitErrorMessage(e)
  } finally {
    actionBusyId.value = null
  }
}

function abrirConvertir(row: CotRow, tipo: 'BOLETA' | 'FACTURA') {
  convertRow.value = row
  convertTipo.value = tipo
  convertSerie.value = ''
  convertFecha.value = typeof row.fecha === 'string' ? row.fecha.slice(0, 10) : isoDate(new Date())
  convertError.value = ''
  showConvert.value = true
}

function cerrarConvertir() {
  showConvert.value = false
  convertRow.value = null
}

async function confirmarConvertir() {
  const row = convertRow.value
  const id = row?.id
  if (typeof id !== 'number') return
  const serie = convertSerie.value.trim()
  if (!serie) {
    convertError.value = 'Indique la serie del comprobante (SUNAT).'
    return
  }
  convertSubmitting.value = true
  convertError.value = ''
  try {
    const { data } = await api.post<{ id?: number }>(`/ventas/cotizaciones/${id}/convertir-comprobante/`, {
      tipo: convertTipo.value,
      serie: serie.slice(0, 10),
      fecha_emision: convertFecha.value || null,
    })
    cerrarConvertir()
    const docId = data?.id
    if (typeof docId === 'number') {
      router.push({ path: '/ventas/documentos', query: { borrador: String(docId) } })
    } else {
      load()
    }
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as { detail?: string }
      convertError.value = typeof d.detail === 'string' ? d.detail : 'No se pudo crear el comprobante.'
    } else {
      convertError.value = 'No se pudo crear el comprobante.'
    }
  } finally {
    convertSubmitting.value = false
  }
}

async function eliminarCotizacion(row: CotRow) {
  const id = row.id
  if (typeof id !== 'number' || !puedeEliminarRow(row)) return
  if (!confirm('¿Eliminar esta cotización? Si tiene comprobante en borrador vinculado, quedará desvinculado.')) return
  actionBusyId.value = id
  errorMsg.value = ''
  try {
    await api.delete(`/ventas/cotizaciones/${id}/`)
    load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as { detail?: string }
      errorMsg.value = typeof d.detail === 'string' ? d.detail : 'No se pudo eliminar.'
    } else {
      errorMsg.value = 'No se pudo eliminar.'
    }
  } finally {
    actionBusyId.value = null
  }
}

const precioColumnLabel = computed(() =>
  formCab.precio_incluye_igv ? 'P. unitario (con IGV)' : 'P. unitario (sin IGV)',
)
</script>

<template>
  <div class="cot-page">
    <header class="toolbar">
      <div class="toolbar-left">
        <button type="button" class="btn-create" @click="openModal">
          <span class="plus" aria-hidden="true">+</span>
          Nueva cotización
        </button>
        <p class="hint">
          Documento interno (no Nubefact). Tras emitir obtiene correlativo tipo
          <strong>COT1-0001</strong>. Luego convierta a boleta o factura; el borrador aparece en
          <RouterLink class="link-doc" to="/ventas/documentos">Comprobantes de venta</RouterLink>.
        </p>
      </div>
      <div class="toolbar-right">
        <button type="button" class="icon-btn" title="Actualizar" @click="load">↻</button>
      </div>
    </header>

    <section class="filters">
      <div class="filter-row">
        <label class="filter-field">
          <span class="filter-label">Doc. cliente</span>
          <input v-model="filters.cliente_documento" type="text" class="filter-inp" maxlength="20" />
        </label>
        <label class="filter-field filter-field--grow">
          <span class="filter-label">Razón social</span>
          <input v-model="filters.cliente_razon_social" type="text" class="filter-inp" />
        </label>
        <label class="filter-field">
          <span class="filter-label">Estado</span>
          <select v-model="filters.estado" class="filter-inp">
            <option value="">Todos</option>
            <option value="BORRADOR">Borrador</option>
            <option value="EMITIDO">Emitido</option>
          </select>
        </label>
        <label class="filter-field">
          <span class="filter-label">Desde</span>
          <input v-model="filters.fecha_desde" type="date" class="filter-inp" />
        </label>
        <label class="filter-field">
          <span class="filter-label">Hasta</span>
          <input v-model="filters.fecha_hasta" type="date" class="filter-inp" />
        </label>
      </div>
    </section>

    <p v-if="errorMsg" class="err-banner">{{ errorMsg }}</p>

    <div class="table-head">
      <span class="total">Total registros: {{ totalCount }}</span>
    </div>

    <div class="table-card">
      <div v-if="loading" class="state muted">Cargando…</div>
      <template v-else>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Número interno</th>
                <th>Doc. cliente</th>
                <th>Cliente</th>
                <th>Moneda</th>
                <th class="num">Total</th>
                <th>Estado</th>
                <th>Comprobante</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in rows" :key="typeof row.id === 'number' ? row.id : idx">
                <td>{{ formatDate(row.fecha) }}</td>
                <td class="td-strong">{{ serieNumero(row) }}</td>
                <td>{{ row.cliente_documento ?? '—' }}</td>
                <td class="cell-clip">{{ row.cliente_razon_social ?? '—' }}</td>
                <td>{{ row.moneda ?? 'PEN' }}</td>
                <td class="num">{{ formatMoney(row.total) }}</td>
                <td>
                  <span class="pill" :class="rowEstado(row) === 'BORRADOR' ? 'pill--draft' : 'pill--ok'">{{
                    rowEstado(row) || '—'
                  }}</span>
                </td>
                <td>
                  <RouterLink
                    v-if="docConvertidoId(row)"
                    class="link-doc"
                    :to="{ path: '/ventas/documentos', query: { borrador: String(docConvertidoId(row)) } }"
                    title="Id interno del borrador en BD; el correlativo SUNAT aparece tras Emitir con Nubefact"
                    >Borrador #{{ docConvertidoId(row) }}</RouterLink
                  >
                  <span v-else class="muted">—</span>
                </td>
                <td class="td-actions">
                  <div class="action-icons" aria-label="Acciones sobre la cotización">
                    <button
                      type="button"
                      class="ico-act"
                      :disabled="!puedeEditarRow(row)"
                      title="Editar cotización"
                      aria-label="Editar"
                      @click="openEdit(row)"
                    >
                      <svg class="ico-act-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          stroke="currentColor"
                          stroke-width="1.75"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"
                        />
                        <path
                          stroke="currentColor"
                          stroke-width="1.75"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
                        />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="ico-act ico-act--danger"
                      :disabled="!puedeEliminarRow(row) || actionBusyId === row.id"
                      title="Eliminar cotización"
                      aria-label="Eliminar"
                      @click="eliminarCotizacion(row)"
                    >
                      <svg class="ico-act-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          stroke="currentColor"
                          stroke-width="1.75"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14zM10 11v6M14 11v6"
                        />
                      </svg>
                    </button>
                  </div>
                  <template v-if="rowEstado(row) === 'BORRADOR'">
                    <button
                      type="button"
                      class="btn-sm btn-sm--primary"
                      :disabled="actionBusyId === row.id || !cotizacionPuedeEditarEliminar(row)"
                      title="Asignar número interno COT1-0001…"
                      @click="emitirInterna(row)"
                    >
                      Emitir (interno)
                    </button>
                  </template>
                  <template v-else-if="rowEstado(row) === 'EMITIDO' && !docConvertidoId(row)">
                    <button type="button" class="btn-sm btn-sm--secondary" @click="abrirConvertir(row, 'BOLETA')">
                      → Boleta
                    </button>
                    <button type="button" class="btn-sm btn-sm--secondary" @click="abrirConvertir(row, 'FACTURA')">
                      → Factura
                    </button>
                  </template>
                  <template v-else-if="rowEstado(row) === 'EMITIDO' && filaBorradorNubefactPendiente(row)">
                    <button
                      type="button"
                      class="btn-sm btn-sm--nubefact"
                      :disabled="actionBusyId === row.id"
                      title="Envía el borrador vinculado a SUNAT (Nubefact): correlativo, estado y PDF"
                      @click="emitirNubefactDesdeCotizacion(row)"
                    >
                      {{ actionBusyId === row.id ? '…' : 'Emitir Nubefact' }}
                    </button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!rows.length" class="state empty">No hay datos</div>
        <div v-if="rows.length && (hasNext || hasPrev)" class="pager">
          <button type="button" class="btn-page" :disabled="!hasPrev" @click="goPrev">Anterior</button>
          <span class="page-num">Página {{ page }}</span>
          <button type="button" class="btn-page" :disabled="!hasNext" @click="goNext">Siguiente</button>
        </div>
      </template>
    </div>

    <Teleport to="body">
      <div v-if="showModal" class="modal-backdrop" @click.self="cerrarModal">
        <div class="modal-panel" role="dialog" aria-modal="true">
          <h2 class="modal-title">{{ modalTitulo }}</h2>
          <p class="modal-lead">
            <template v-if="editingId == null">
              Mismos datos que un comprobante de venta, sin serie SUNAT. Guarde el borrador y luego use
              <strong>Emitir (interno)</strong> en la tabla para asignar <strong>COT1-0001</strong>, etc.
            </template>
            <template v-else>
              Los cambios no afectan un comprobante ya emitido a SUNAT. Serie y número interno de la cotización no se
              modifican desde aquí.
            </template>
          </p>
          <div v-if="catalogLoading" class="muted">Cargando catálogos…</div>
          <template v-else>
            <section class="block">
              <h3 class="block-title">Cliente</h3>
              <div class="cliente-doc-grid">
                <label class="fld">
                  <span>Tipo doc.</span>
                  <select v-model="formCliente.tipo_doc" class="inp">
                    <option value="RUC">RUC</option>
                    <option value="DNI">DNI</option>
                  </select>
                </label>
                <div class="fld fld--doc">
                  <span>Número doc.</span>
                  <div
                    class="doc-num-row"
                    @focusin="onDocNumFocusIn"
                    @focusout="onDocNumFocusOut"
                  >
                    <div class="doc-num-input-wrap">
                      <input
                        v-model="formCliente.documento"
                        class="inp"
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
                <label class="fld fld--full">
                  <span>Razón social / nombre</span>
                  <input v-model="formCliente.razon_social" class="inp" placeholder="Según documento o consulta" />
                </label>
                <label class="fld">
                  <span>Email</span>
                  <input v-model="formCliente.email" class="inp" type="email" />
                </label>
                <label class="fld fld--full">
                  <span>Dirección</span>
                  <input v-model="formCliente.direccion" class="inp" />
                </label>
              </div>
            </section>
            <section class="block">
              <h3 class="block-title">Cabecera</h3>
              <div class="grid-2">
                <label class="fld">
                  <span>Fecha</span>
                  <input v-model="formCab.fecha_emision" type="date" class="inp" />
                </label>
                <label class="fld">
                  <span>Moneda</span>
                  <select v-model="formCab.moneda" class="inp">
                    <option value="PEN">PEN</option>
                    <option value="USD">USD</option>
                  </select>
                </label>
                <label class="fld">
                  <span>Condición</span>
                  <select v-model="formCab.condicion_pago" class="inp">
                    <option value="CONTADO">Contado</option>
                    <option value="CREDITO">Crédito</option>
                  </select>
                </label>
                <label v-if="formCab.condicion_pago === 'CREDITO'" class="fld">
                  <span>Vencimiento</span>
                  <input v-model="formCab.fecha_vencimiento" type="date" class="inp" />
                </label>
                <label v-else class="fld">
                  <span>Medio pago</span>
                  <select v-model="formCab.medio_pago" class="inp">
                    <option v-for="o in mediosPagoOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
                  </select>
                </label>
                <label class="fld">
                  <span>Operación</span>
                  <select v-model="formCab.tipo_operacion" class="inp">
                    <option v-for="o in tiposOperacionOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
                  </select>
                </label>
                <label class="fld fld--full">
                  <span>Vendedor</span>
                  <select v-model="formCab.vendedor_id" class="inp">
                    <option value="">—</option>
                    <option v-for="v in vendedoresCatalog" :key="v.id" :value="v.id">{{ v.nombre_completo ?? v.id }}</option>
                  </select>
                </label>
                <label class="fld fld--full chk">
                  <input v-model="formCab.precio_incluye_igv" type="checkbox" />
                  Precio unitario incluye IGV
                </label>
                <label class="fld fld--full">
                  <span>Observación</span>
                  <input v-model="formCab.observacion" class="inp" />
                </label>
              </div>
            </section>
            <section class="block">
              <h3 class="block-title">Líneas</h3>
              <table class="lines">
                <thead>
                  <tr>
                    <th>Ítem</th>
                    <th>UM</th>
                    <th>Cant.</th>
                    <th>{{ precioColumnLabel }}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(ln, idx) in lineasForm" :key="idx">
                    <td>
                      <select v-model="ln.item_id" class="inp inp--sm">
                        <option value="" disabled>Seleccionar…</option>
                        <option v-for="it in itemCatalog" :key="it.id" :value="it.id">{{ itemLabel(it) }}</option>
                      </select>
                    </td>
                    <td class="muted">{{ itemCatalog.find((x) => x.id === ln.item_id)?.unidad_medida_codigo || '—' }}</td>
                    <td><input v-model="ln.cantidad" class="inp inp--sm" /></td>
                    <td><input v-model="ln.precio_unit" class="inp inp--sm" /></td>
                    <td>
                      <button type="button" class="btn-x" @click="removeLinea(idx)">✕</button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <button type="button" class="btn-add" @click="addLinea">+ Línea</button>
              <div class="totals">
                <span>Gravado {{ simboloMonedaPreview }} {{ totalGravada.toFixed(2) }}</span>
                <span>IGV {{ simboloMonedaPreview }} {{ totalIgvPreview.toFixed(2) }}</span>
                <strong>Total {{ simboloMonedaPreview }} {{ totalDocPreview.toFixed(2) }}</strong>
              </div>
            </section>
          </template>
          <p v-if="formError" class="form-err">{{ formError }}</p>
          <div class="modal-foot">
            <button type="button" class="btn-ghost" :disabled="submitting" @click="cerrarModal">Cerrar</button>
            <button type="button" class="btn-primary" :disabled="submitting || catalogLoading" @click="guardarCotizacionBorrador">
              {{ submitting ? '…' : botonGuardarModal }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showConvert" class="modal-backdrop" @click.self="cerrarConvertir">
        <div class="modal-panel modal-panel--sm" role="dialog" aria-modal="true">
          <h2 class="modal-title">Convertir a {{ convertTipo === 'BOLETA' ? 'boleta' : 'factura' }}</h2>
          <p class="modal-lead">
            Se creará un <strong>borrador</strong> de comprobante con los mismos datos y líneas. Luego lo enviamos al listado
            de comprobantes para que pueda <strong>emitir con Nubefact</strong> (SUNAT) en el siguiente paso; hasta entonces no
            hay correlativo ni PDF.
          </p>
          <label class="fld">
            <span>Serie SUNAT</span>
            <input v-model="convertSerie" class="inp" maxlength="10" placeholder="Ej. F001 / B001" />
          </label>
          <label class="fld">
            <span>Fecha emisión comprobante</span>
            <input v-model="convertFecha" type="date" class="inp" />
          </label>
          <p v-if="convertError" class="form-err">{{ convertError }}</p>
          <div class="modal-foot">
            <button type="button" class="btn-ghost" :disabled="convertSubmitting" @click="cerrarConvertir">Cancelar</button>
            <button type="button" class="btn-primary" :disabled="convertSubmitting" @click="confirmarConvertir">
              {{ convertSubmitting ? '…' : 'Crear borrador' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.cot-page {
  width: 100%;
  max-width: 100%;
  /* El shell usa .brand-bg con color claro; sin esto el texto heredado no contrasta con tarjetas blancas. */
  color: #0f172a;
}

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.toolbar-left {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.hint {
  margin: 0;
  font-size: 0.8rem;
  color: #64748b;
  max-width: 42rem;
  line-height: 1.45;
}

.link-doc {
  color: #0284c7;
  font-weight: 600;
  text-decoration: none;
}

.link-doc:hover {
  text-decoration: underline;
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
  cursor: pointer;
  width: fit-content;
}

.icon-btn {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  font-size: 1.1rem;
}

.filters {
  background: #fff;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  align-items: flex-end;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 8rem;
}

.filter-field--grow {
  flex: 1;
  min-width: 12rem;
}

.filter-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
}

.filter-inp {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.45rem 0.55rem;
  font-size: 0.88rem;
}

.err-banner {
  background: #fef2f2;
  color: #b91c1c;
  padding: 0.65rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.88rem;
}

.table-head {
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
  color: #64748b;
}

.table-card {
  position: relative;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  min-height: 8rem;
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
  padding: 0.55rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}

.data-table tbody td {
  color: #0f172a;
  font-weight: 500;
  font-size: 0.8rem;
}

.data-table tbody tr:hover {
  background: #f8fafc;
}

.data-table th {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #475569;
  font-weight: 700;
  background: #f8fafc;
}

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.td-strong {
  font-weight: 700;
  color: #0f172a;
}

.cell-clip {
  max-width: 11rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.td-actions {
  white-space: normal;
  vertical-align: top;
}

.action-icons {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.35rem;
}

.ico-act {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #0284c7;
  cursor: pointer;
  transition:
    background 0.15s ease,
    opacity 0.15s ease;
}

.ico-act:hover:not(:disabled) {
  background: #e0f2fe;
  border-color: #0284c7;
}

.ico-act:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.ico-act--danger {
  color: #b91c1c;
}

.ico-act--danger:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #fecaca;
}

.ico-act-svg {
  width: 1.05rem;
  height: 1.05rem;
}

.btn-sm {
  font-size: 0.72rem;
  padding: 0.25rem 0.45rem;
  margin-right: 0.35rem;
  margin-bottom: 0.2rem;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  font-weight: 600;
}

.btn-sm--primary {
  background: #0284c7;
  border-color: #0284c7;
  color: #fff;
}

.btn-sm--nubefact {
  background: linear-gradient(135deg, #059669, #047857);
  border-color: #047857;
  color: #fff;
}

.btn-sm--nubefact:hover:not(:disabled) {
  filter: brightness(1.06);
}

.btn-sm--nubefact:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-sm--secondary {
  background: #f1f5f9;
}

.btn-sm--ghost {
  color: #64748b;
}

.pill {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
}

.pill--draft {
  background: #fef3c7;
  color: #92400e;
}

.pill--ok {
  background: #dcfce7;
  color: #166534;
}

.muted {
  color: #64748b;
  font-weight: 500;
}

.state {
  padding: 2rem;
  text-align: center;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 1rem;
}

.btn-page {
  padding: 0.35rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 2rem 1rem;
  overflow-y: auto;
}

.modal-panel {
  background: #fff;
  border-radius: 14px;
  max-width: 52rem;
  width: 100%;
  padding: 1.25rem 1.5rem 1.5rem;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.2);
}

.modal-panel--sm {
  max-width: 24rem;
}

.modal-title {
  margin: 0 0 0.35rem;
  font-size: 1.15rem;
}

.modal-lead {
  margin: 0 0 1rem;
  font-size: 0.85rem;
  color: #64748b;
  line-height: 1.45;
}

.block {
  margin-bottom: 1.1rem;
}

.block-title {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem 1rem;
}

.fld {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: #475569;
}

.fld--full {
  grid-column: 1 / -1;
}

.cliente-doc-grid {
  display: grid;
  grid-template-columns: minmax(7rem, 9rem) 1fr;
  gap: 0.65rem 1rem;
  align-items: start;
}

@media (max-width: 640px) {
  .cliente-doc-grid {
    grid-template-columns: 1fr;
  }
}

.fld--doc {
  grid-column: 2;
  min-width: 0;
}

@media (max-width: 640px) {
  .fld--doc {
    grid-column: 1 / -1;
  }
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

.fld.chk {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.inp {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.45rem 0.55rem;
  font-size: 0.88rem;
}

.inp--sm {
  font-size: 0.82rem;
  padding: 0.35rem 0.45rem;
}

.lines {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  margin-bottom: 0.5rem;
}

.lines th,
.lines td {
  padding: 0.35rem 0.25rem;
  border-bottom: 1px solid #f1f5f9;
}

.btn-x {
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
}

.btn-add {
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}

.totals {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  font-size: 0.85rem;
  color: #475569;
}

.form-err {
  color: #b91c1c;
  font-size: 0.85rem;
  margin: 0.5rem 0 0;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #f1f5f9;
}

.btn-ghost {
  padding: 0.5rem 1rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
}

.btn-primary {
  padding: 0.5rem 1.1rem;
  border-radius: 8px;
  border: none;
  background: #0284c7;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}
</style>
