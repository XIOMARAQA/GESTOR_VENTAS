<script setup lang="ts">
import axios from 'axios'
import ExcelJS from 'exceljs'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'

type DocRow = Record<string, unknown> & { id?: number }

type ItemCat = { id: number; codigo?: string; nombre: string }
type ProvCat = { id: number; razon_social?: string; documento?: string; activo?: boolean }
type AlmCat = { id: number; nombre?: string; sucursal?: number }

type LineaForm = { item_id: number | ''; cantidad: string; precio_unit: string }

/**
 * Tipos de documento de compra: mismas etiquetas que en comprobantes de venta
 * (`TipoDocumentoVenta`), con códigos internos propios de compras en backend.
 */
const tipoComprobanteCompraOptions = [
  { value: 'FACTURA_COMPRA', label: 'Factura' },
  { value: 'BOLETA_COMPRA', label: 'Boleta' },
  { value: 'NOTA_COMPRA', label: 'Nota de venta' },
  { value: 'RESUMEN_COMPRAS', label: 'Resumen de boletas' },
  { value: 'GUIA_REMISION_COMPRA', label: 'Guía de remisión' },
  { value: 'NOTA_CREDITO_PROVEEDOR', label: 'Nota de crédito (proveedor)' },
] as const

type TipoComprobanteCompraCab = (typeof tipoComprobanteCompraOptions)[number]['value']

function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const route = useRoute()
const ctx = useAppContextStore()

function detailFromAxios(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e) && e.response?.data) {
    const d = e.response.data as Record<string, unknown>
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) return d.detail.map(String).join(' ')
  }
  return fallback
}

const loading = ref(false)
const errorMsg = ref('')
const rows = ref<DocRow[]>([])
const page = ref(1)
const totalCount = ref(0)
const hasNext = ref(false)
const hasPrev = ref(false)

const filters = reactive({
  search: '',
  estado: '' as '' | 'BORRADOR' | 'EMITIDO',
})

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
  selectedCompraIds.value = []
  try {
    const params = new URLSearchParams()
    params.set('page', String(page.value))
    if (filters.search.trim()) params.set('search', filters.search.trim())
    if (filters.estado) params.set('estado', filters.estado)
    const docFocus = route.query.documento
    const dfs = typeof docFocus === 'string' ? docFocus : Array.isArray(docFocus) ? docFocus[0] : ''
    if (dfs && /^\d+$/.test(String(dfs))) params.set('documento', String(dfs))
    const { data } = await api.get<{
      results?: DocRow[]
      count?: number
      next?: string | null
      previous?: string | null
    }>(`/compras/documentos/?${params.toString()}`)
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
    totalCount.value =
      typeof data === 'object' && data && 'count' in data ? Number(data.count) : rows.value.length
    hasNext.value = !!(typeof data === 'object' && data && data.next)
    hasPrev.value = !!(typeof data === 'object' && data && data.previous)
  } catch {
    errorMsg.value = 'No se pudo cargar las facturas de compra.'
    rows.value = []
    totalCount.value = 0
    hasNext.value = false
    hasPrev.value = false
  } finally {
    loading.value = false
  }
  applyDocumentoQueryScroll()
}

function applyDocumentoQueryScroll() {
  const raw = route.query.documento
  const s = typeof raw === 'string' ? raw : Array.isArray(raw) ? raw[0] : ''
  const id = parseInt(String(s), 10)
  if (!Number.isFinite(id) || id <= 0) return
  const found = rows.value.some((r) => r.id === id)
  if (found) {
    void nextTick(() => {
      const el = document.querySelector(`[data-doc-compra-id="${id}"]`)
      el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }
}

watch(
  () => route.query.documento,
  () => {
    page.value = 1
    void load()
  },
)

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

function refresh() {
  load()
}

const TIPOS_COMPRA_IMPORT = new Set<string>([
  'FACTURA_COMPRA',
  'BOLETA_COMPRA',
  'NOTA_COMPRA',
  'RESUMEN_COMPRAS',
  'GUIA_REMISION_COMPRA',
  'NOTA_CREDITO_PROVEEDOR',
])

const PLANTILLA_COMPRAS_HEADERS = [
  'grupo_doc',
  'ruc_proveedor',
  'tipo',
  'serie',
  'numero',
  'fecha',
  'condicion_pago',
  'fecha_vencimiento',
  'precios_con_igv',
  'codigo_item',
  'cantidad',
  'precio_unit',
  'afecta_stock',
] as const

type CompraImportLine = {
  rowExcel: number
  grupo: string
  ruc: string
  tipo: string
  serie: string
  numero: string
  fecha: string
  condicion: string
  fechaVenc: string
  precioIncluyeIgv: boolean
  codigoItem: string
  cantidad: string
  precioUnit: string
  afectaStock: boolean
}

const importComprasInputRef = ref<HTMLInputElement | null>(null)
const importComprasBusy = ref(false)
const bulkImportMsg = ref('')
const bulkImportOk = ref(true)

const canUseComprasExcel = computed(() => {
  if (!ctx.isSuperuser) return true
  return !!(ctx.empresaId && String(ctx.empresaId).trim())
})

function cellToString(v: unknown): string {
  if (v == null || v === '') return ''
  if (typeof v === 'number' && Number.isFinite(v)) {
    return Number.isInteger(v) ? String(v) : String(v)
  }
  return String(v).trim()
}

function cellToFechaIso(v: unknown): string | null {
  if (v == null || v === '') return null
  if (v instanceof Date) {
    if (Number.isNaN(v.getTime())) return null
    return isoDate(v)
  }
  if (typeof v === 'number' && Number.isFinite(v)) {
    const utc = Math.round((v - 25569) * 86400 * 1000)
    const d = new Date(utc)
    if (!Number.isNaN(d.getTime())) return isoDate(d)
  }
  const s = String(v).trim()
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10)
  const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (m?.[1] && m[2] && m[3]) {
    const dd = m[1].padStart(2, '0')
    const mm = m[2].padStart(2, '0')
    return `${m[3]}-${mm}-${dd}`
  }
  return null
}

function ynToBool(s: string): boolean {
  const u = s.trim().toUpperCase()
  return u === 'S' || u === 'SI' || u === 'Y' || u === '1' || u === 'TRUE'
}

function proveedorIdPorRuc(ruc: string, catalog: ProvCat[]): number | null {
  const d = ruc.replace(/\D/g, '')
  if (!d) return null
  const p = catalog.find((x) => (x.documento || '').replace(/\D/g, '') === d)
  return typeof p?.id === 'number' ? p.id : null
}

function itemIdPorCodigo(cod: string, catalog: ItemCat[]): number | null {
  const c = cod.trim().toUpperCase()
  if (!c) return null
  const it = catalog.find((x) => (x.codigo || '').trim().toUpperCase() === c)
  return typeof it?.id === 'number' ? it.id : null
}

function cabKeyLine(l: CompraImportLine): string {
  return [
    l.ruc.toUpperCase(),
    l.tipo.toUpperCase(),
    l.serie.trim(),
    l.numero.trim(),
    l.fecha,
    l.condicion.toUpperCase(),
    l.fechaVenc,
    l.precioIncluyeIgv ? '1' : '0',
    l.afectaStock ? '1' : '0',
  ].join('|')
}

async function descargarPlantillaComprasExcel() {
  const wb = new ExcelJS.Workbook()
  const ws = wb.addWorksheet('Compras', { views: [{ state: 'frozen', ySplit: 1 }] })
  const headers = [...PLANTILLA_COMPRAS_HEADERS]
  const hdr = ws.addRow(headers)
  hdr.height = 30
  const headBorder = {
    top: { style: 'thin' as const, color: { argb: 'FF0d5c56' } },
    left: { style: 'thin' as const, color: { argb: 'FF0d5c56' } },
    bottom: { style: 'thin' as const, color: { argb: 'FF0d5c56' } },
    right: { style: 'thin' as const, color: { argb: 'FF0d5c56' } },
  }
  hdr.eachCell((cell) => {
    cell.font = { bold: true, size: 11, color: { argb: 'FFFFFFFF' } }
    cell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF0f766e' },
    }
    cell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true }
    cell.border = headBorder
  })

  const hair = {
    top: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
    left: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
    bottom: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
    right: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
  }

  const ejemplo1 = [
    1,
    '20123456789',
    'FACTURA_COMPRA',
    'F002',
    '1',
    new Date(2026, 3, 1),
    'CONTADO',
    '',
    'N',
    'PROD-01',
    2,
    10,
    'S',
  ]
  const ejemplo2 = [
    1,
    '20123456789',
    'FACTURA_COMPRA',
    'F002',
    '1',
    new Date(2026, 3, 1),
    'CONTADO',
    '',
    'N',
    'PROD-02',
    1,
    15.5,
    'S',
  ]
  const ejemplo3 = [
    2,
    '20123456789',
    'FACTURA_COMPRA',
    'F002',
    '2',
    new Date(2026, 3, 2),
    'CREDITO',
    new Date(2026, 4, 2),
    'S',
    'PROD-01',
    3,
    20,
    'S',
  ]
  ws.addRow(ejemplo1)
  ws.addRow(ejemplo2)
  ws.addRow(ejemplo3)

  const colWidths = [11, 16, 18, 10, 10, 12, 14, 14, 14, 14, 10, 12, 12]
  colWidths.forEach((w, i) => {
    ws.getColumn(i + 1).width = w
  })

  const nCols = headers.length
  for (let r = 2; r <= 4; r++) {
    for (let c = 1; c <= nCols; c++) {
      const cell = ws.getCell(r, c)
      cell.border = hair
      if (c === 1) {
        cell.numFmt = '0'
        cell.alignment = { horizontal: 'center', vertical: 'middle' }
      } else if (c === 2) {
        cell.numFmt = '@'
        cell.alignment = { horizontal: 'left', vertical: 'middle' }
      } else if (c === 6 || c === 8) {
        if (cell.value instanceof Date) cell.numFmt = 'yyyy-mm-dd'
        cell.alignment = { horizontal: 'center', vertical: 'middle' }
      } else if (c === 11 || c === 12) {
        if (typeof cell.value === 'number') cell.numFmt = '#,##0.####'
        cell.alignment = { horizontal: 'right', vertical: 'middle' }
      } else {
        cell.alignment = { vertical: 'middle', horizontal: 'left' }
      }
    }
  }

  const inst = wb.addWorksheet('Instrucciones')
  const lines = [
    'Uso de la plantilla',
    '',
    '• No cambie los nombres de la fila 1 en la hoja «Compras»: la importación exige exactamente esos encabezados.',
    '• Borre las filas 2–4 de ejemplo y escriba sus datos a partir de la fila 2 (la primera fila de datos debe quedar en la fila 2).',
    '• Cada fila = una línea de detalle (un producto).',
    '• Varias filas con el mismo grupo_doc = un solo comprobante con varias líneas.',
    '• Cambie grupo_doc para el siguiente comprobante.',
    '• ruc_proveedor: debe existir en Proveedores (maestro).',
    '• codigo_item: código del producto en Inventario.',
    '• tipo: FACTURA_COMPRA, BOLETA_COMPRA, etc. (vacío = FACTURA_COMPRA).',
    '• condicion_pago: CONTADO o CREDITO. Si CREDITO, fecha_vencimiento obligatoria.',
    '• precios_con_igv: S o N.',
    '• afecta_stock: S = al registrar mueve inventario y kardex; N = documento contable sin movimiento de stock.',
    '• La importación crea borradores; registre el ingreso a stock desde la lista (si afecta_stock es S).',
  ]
  lines.forEach((line, idx) => {
    const c = inst.getCell(idx + 1, 1)
    c.value = line
    if (idx === 0) c.font = { bold: true, size: 13 }
  })
  inst.getColumn(1).width = 88

  const buf = await wb.xlsx.writeBuffer()
  const blob = new Blob([buf], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'plantilla_facturas_proveedor.xlsx'
  a.click()
  URL.revokeObjectURL(a.href)
}

function parseComprasSheet(sheet: ExcelJS.Worksheet): { lines: CompraImportLine[]; errors: string[] } {
  const errors: string[] = []
  const lines: CompraImportLine[] = []
  const h1 = sheet.getRow(1)
  const got: string[] = []
  h1.eachCell({ includeEmpty: true }, (cell, colNumber) => {
    got[colNumber - 1] = cellToString(cell.value).toLowerCase()
  })
  for (let i = 0; i < PLANTILLA_COMPRAS_HEADERS.length; i++) {
    const exp = PLANTILLA_COMPRAS_HEADERS[i]
    const g = (got[i] || '').trim()
    if (g !== exp) {
      errors.push(
        `La fila 1 debe tener las columnas de la plantilla (columna ${i + 1}: se esperaba "${exp}", se leyó "${g || '(vacío)'}"). Descargue la plantilla oficial.`,
      )
      return { lines: [], errors }
    }
  }

  const maxRow = sheet.rowCount || 0
  for (let r = 2; r <= maxRow; r++) {
    const g0 = cellToString(sheet.getCell(r, 1).value)
    if (!g0) continue
    const ruc = cellToString(sheet.getCell(r, 2).value)
    let tipo = cellToString(sheet.getCell(r, 3).value).toUpperCase()
    if (!tipo) tipo = 'FACTURA_COMPRA'
    const serie = cellToString(sheet.getCell(r, 4).value)
    const numero = cellToString(sheet.getCell(r, 5).value)
    const fechaRaw = sheet.getCell(r, 6).value
    const fecha = cellToFechaIso(fechaRaw)
    const condicion = cellToString(sheet.getCell(r, 7).value).toUpperCase()
    const fvRaw = sheet.getCell(r, 8).value
    const fechaVenc = cellToFechaIso(fvRaw) || ''
    const precioIncluyeIgv = ynToBool(cellToString(sheet.getCell(r, 9).value))
    const codigoItem = cellToString(sheet.getCell(r, 10).value)
    const cantidad = cellToString(sheet.getCell(r, 11).value)
    const precioUnit = cellToString(sheet.getCell(r, 12).value)
    const afectaStockRaw = cellToString(sheet.getCell(r, 13).value)
    const afectaStock = afectaStockRaw === '' ? true : ynToBool(afectaStockRaw)

    const rowMsgs: string[] = []
    if (!ruc) rowMsgs.push(`Fila ${r}: falta ruc_proveedor.`)
    if (!TIPOS_COMPRA_IMPORT.has(tipo)) rowMsgs.push(`Fila ${r}: tipo inválido (${tipo}).`)
    if (!fecha) rowMsgs.push(`Fila ${r}: fecha inválida o vacía.`)
    if (condicion !== 'CONTADO' && condicion !== 'CREDITO')
      rowMsgs.push(`Fila ${r}: condicion_pago debe ser CONTADO o CREDITO.`)
    if (condicion === 'CREDITO' && !fechaVenc) rowMsgs.push(`Fila ${r}: en CREDITO indique fecha_vencimiento.`)
    if (!codigoItem) rowMsgs.push(`Fila ${r}: falta codigo_item.`)
    const cQty = Number(String(cantidad).replace(',', '.'))
    const cPu = Number(String(precioUnit).replace(',', '.'))
    if (!Number.isFinite(cQty) || cQty <= 0) rowMsgs.push(`Fila ${r}: cantidad inválida.`)
    if (!Number.isFinite(cPu) || cPu < 0) rowMsgs.push(`Fila ${r}: precio_unit inválido.`)
    if (afectaStockRaw !== '' && !/^(S|N|SI|NO|Y|1|0|TRUE|FALSE)$/i.test(afectaStockRaw.trim()))
      rowMsgs.push(`Fila ${r}: afecta_stock debe ser S o N (vacío = S).`)
    if (rowMsgs.length) {
      errors.push(...rowMsgs)
      continue
    }

    lines.push({
      rowExcel: r,
      grupo: g0,
      ruc,
      tipo,
      serie,
      numero,
      fecha: fecha || '',
      condicion,
      fechaVenc,
      precioIncluyeIgv,
      codigoItem,
      cantidad: String(cantidad).replace(',', '.'),
      precioUnit: String(precioUnit).replace(',', '.'),
      afectaStock,
    })
  }

  return { lines, errors }
}

function clickImportComprasExcel() {
  bulkImportMsg.value = ''
  if (!canUseComprasExcel.value) {
    errorMsg.value = 'Seleccione una empresa en la barra superior para importar (modo administrador).'
    return
  }
  importComprasInputRef.value?.click()
}

async function onImportComprasExcelFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!canUseComprasExcel.value) {
    errorMsg.value = 'Seleccione una empresa en la barra superior para importar (modo administrador).'
    return
  }

  importComprasBusy.value = true
  bulkImportMsg.value = ''
  errorMsg.value = ''
  try {
    const wb = new ExcelJS.Workbook()
    const ab = await file.arrayBuffer()
    await wb.xlsx.load(ab)
    const sheet = wb.worksheets[0]
    if (!sheet) {
      errorMsg.value = 'El archivo no tiene hojas de cálculo.'
      return
    }

    const { lines, errors } = parseComprasSheet(sheet)
    if (errors.length) {
      errorMsg.value = errors.slice(0, 8).join(' ') + (errors.length > 8 ? ' …' : '')
      return
    }
    if (!lines.length) {
      errorMsg.value = 'No hay filas de datos (desde la fila 2).'
      return
    }

    const [provRes, itemsRes] = await Promise.all([
      api.get<{ results?: ProvCat[] }>('/core/proveedores/?page_size=500&ordering=razon_social'),
      api.get<{ results?: ItemCat[] }>('/inventario/items/?page_size=500'),
    ])
    const proveedores = provRes.data?.results ?? []
    const items = itemsRes.data?.results ?? []

    const byGrupo = new Map<string, CompraImportLine[]>()
    for (const ln of lines) {
      const k = ln.grupo.trim()
      if (!byGrupo.has(k)) byGrupo.set(k, [])
      byGrupo.get(k)!.push(ln)
    }

    const fail: string[] = []
    let ok = 0
    for (const [, groupLines] of byGrupo) {
      if (!groupLines.length) continue
      const first = groupLines[0]!
      const k0 = cabKeyLine(first)
      for (const ln of groupLines.slice(1)) {
        if (cabKeyLine(ln) !== k0) {
          fail.push(
            `Grupo "${first.grupo}": las filas ${groupLines.map((x) => x.rowExcel).join(', ')} deben repetir los mismos datos de cabecera (RUC, tipo, serie, número, fecha, pago, vencimiento, precios_con_igv).`,
          )
          break
        }
      }
    }
    if (fail.length) {
      errorMsg.value = fail[0] ?? 'Error de agrupación.'
      return
    }

    for (const [, groupLines] of byGrupo) {
      if (!groupLines.length) continue
      const first = groupLines[0]!
      const pid = proveedorIdPorRuc(first.ruc, proveedores)
      if (pid == null) {
        fail.push(`Grupo "${first.grupo}": no hay proveedor con documento "${first.ruc}".`)
        continue
      }
      const lineasPayload: { item_id: number; cantidad: string; precio_unit: string }[] = []
      let groupItemError: string | null = null
      for (const ln of groupLines) {
        const iid = itemIdPorCodigo(ln.codigoItem, items)
        if (iid == null) {
          groupItemError = `Fila ${ln.rowExcel}: código de ítem "${ln.codigoItem}" no encontrado.`
          break
        }
        lineasPayload.push({
          item_id: iid,
          cantidad: ln.cantidad,
          precio_unit: ln.precioUnit,
        })
      }
      if (groupItemError) {
        fail.push(groupItemError)
        continue
      }

      const body: Record<string, unknown> = {
        proveedor_id: pid,
        tipo: first.tipo,
        serie: first.serie.trim().slice(0, 10),
        numero: first.numero.trim().slice(0, 20),
        fecha: first.fecha,
        lineas: lineasPayload,
        condicion_pago: first.condicion,
        fecha_vencimiento: first.condicion === 'CREDITO' ? first.fechaVenc : null,
        precio_incluye_igv: first.precioIncluyeIgv,
        afecta_stock: first.afectaStock,
      }
      const emp = ctx.empresaId
      if (emp) body.empresa_id = Number(emp)

      try {
        await api.post('/compras/documentos/alta-borrador/', body)
        ok += 1
      } catch (e) {
        fail.push(
          `Grupo "${first.grupo}" (${first.serie}-${first.numero}): ${detailFromAxios(e, 'Error al crear borrador.')}`,
        )
      }
    }

    if (fail.length && ok === 0) {
      errorMsg.value = fail.slice(0, 5).join(' ') + (fail.length > 5 ? ' …' : '')
      bulkImportMsg.value = ''
      return
    }
    bulkImportOk.value = fail.length === 0
    bulkImportMsg.value =
      `Importación terminada: ${ok} comprobante(s) en borrador.` +
      (fail.length ? ` Errores (${fail.length}): ${fail.slice(0, 3).join(' ')}${fail.length > 3 ? ' …' : ''}` : '')
    await load()
  } catch {
    errorMsg.value = 'No se pudo leer el archivo Excel.'
  } finally {
    importComprasBusy.value = false
  }
}

function formatDate(v: unknown): string {
  if (typeof v !== 'string' || !v) return '—'
  return v.slice(0, 10).split('-').reverse().join('/')
}

function formatDateTimeShort(v: unknown): string {
  if (typeof v !== 'string' || !v) return '—'
  const d = v.slice(0, 10).split('-').reverse().join('/')
  const t = v.slice(11, 16)
  return t ? `${d} ${t}` : d
}

function formatMoney(v: unknown): string {
  const n = typeof v === 'string' ? parseFloat(v) : typeof v === 'number' ? v : NaN
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function numeroCompra(row: DocRow): string {
  const sn = row.serie_numero
  if (typeof sn === 'string' && sn.trim()) return sn.trim()
  const s = typeof row.serie === 'string' ? row.serie.trim() : ''
  const n = typeof row.numero === 'string' ? row.numero.trim() : ''
  if (s && n) return `${s}-${n}`
  if (s || n) return s || n
  return 'S/N'
}

function rowEstado(row: DocRow): string {
  const e = row.estado
  return typeof e === 'string' ? e : ''
}

function condicionPagoLabel(row: DocRow): string {
  const c = row.condicion_pago
  if (c === 'CREDITO') return 'Crédito'
  if (c === 'CONTADO') return 'Contado'
  return typeof c === 'string' ? c : '—'
}

function rowAfectaStock(row: DocRow): boolean {
  const v = row.afecta_stock
  if (v === false || v === 'false' || v === 0) return false
  return true
}

function labelStockKardex(row: DocRow): string {
  return rowAfectaStock(row) ? 'Kardex sí' : 'Kardex no'
}

function puedeVerPagosProveedor(row: DocRow): boolean {
  if (typeof row.id !== 'number') return false
  if (rowEstado(row) !== 'EMITIDO') return false
  return row.condicion_pago === 'CREDITO'
}

function pagosProveedorTo(row: DocRow) {
  return {
    path: '/tesoreria/cuentas-por-pagar',
    query: { documentos: String(row.id) },
  } as const
}

const selectedCompraIds = ref<number[]>([])

const modalPagoOpen = ref(false)
const modalPagoMetodo = ref('EFECTIVO')
const modalPagoLines = ref<{ documentoId: number; label: string; totalFmt: string; monto: string }[]>([])
const modalPagoError = ref('')
const modalPagoSaving = ref(false)

const metodoPagoOptions = [
  { value: 'EFECTIVO', label: 'Efectivo' },
  { value: 'TRANSFERENCIA', label: 'Transferencia' },
  { value: 'YAPE', label: 'Yape / Plin' },
  { value: 'POS', label: 'POS / Tarjeta' },
  { value: 'REGISTRO_MANUAL', label: 'Otro / manual' },
]

const payableRowsOnPage = computed(() => rows.value.filter((r) => puedeVerPagosProveedor(r)))

const allComprasPageSelected = computed({
  get() {
    const ids = payableRowsOnPage.value
      .map((r) => r.id)
      .filter((id): id is number => typeof id === 'number')
    return ids.length > 0 && ids.every((id) => selectedCompraIds.value.includes(id))
  },
  set(checked: boolean) {
    const ids = payableRowsOnPage.value
      .map((r) => r.id)
      .filter((id): id is number => typeof id === 'number')
    if (checked) {
      selectedCompraIds.value = [...new Set([...selectedCompraIds.value, ...ids])]
    } else {
      const drop = new Set(ids)
      selectedCompraIds.value = selectedCompraIds.value.filter((id) => !drop.has(id))
    }
  },
})

function toggleCompraRow(id: number) {
  const cur = selectedCompraIds.value
  const i = cur.indexOf(id)
  if (i >= 0) selectedCompraIds.value = cur.filter((x) => x !== id)
  else selectedCompraIds.value = [...cur, id]
}

function rowCompraChecked(id: number) {
  return selectedCompraIds.value.includes(id)
}

const selectedCompraRows = computed(() => {
  const set = new Set(selectedCompraIds.value)
  return rows.value.filter((r) => typeof r.id === 'number' && set.has(r.id))
})

const canRegistrarPagoCompras = computed(() => {
  if (!selectedCompraRows.value.length) return false
  return selectedCompraRows.value.every((r) => puedeVerPagosProveedor(r))
})

const pagosRealizadosComprasLink = computed(() => {
  const ids = selectedCompraRows.value
    .map((r) => r.id)
    .filter((id): id is number => typeof id === 'number')
  const unique = [...new Set(ids)]
  if (unique.length) {
    return { path: '/tesoreria/pagos-proveedores', query: { documentos: unique.join(',') } } as const
  }
  return { path: '/tesoreria/pagos-proveedores' } as const
})

function montoDefaultDoc(row: DocRow): string {
  const n = Number(row.total)
  if (Number.isFinite(n) && n > 0) return String(n)
  return ''
}

function openModalRegistrarPagoCompras() {
  if (!canRegistrarPagoCompras.value) return
  modalPagoError.value = ''
  modalPagoMetodo.value = 'EFECTIVO'
  modalPagoLines.value = selectedCompraRows.value.map((r) => ({
    documentoId: r.id as number,
    label: numeroCompra(r),
    totalFmt: formatMoney(r.total),
    monto: montoDefaultDoc(r),
  }))
  if (!modalPagoLines.value.length) return
  modalPagoOpen.value = true
}

function closeModalPagoCompras() {
  if (modalPagoSaving.value) return
  modalPagoOpen.value = false
}

function modalPagoErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e) && e.response?.data) {
    const d = e.response.data as Record<string, unknown>
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) return d.detail.map(String).join(' ')
  }
  return 'No se pudo registrar el pago.'
}

async function submitModalPagoCompras() {
  modalPagoError.value = ''
  const toPost: { documento_compra_id: number; monto: number }[] = []
  for (const line of modalPagoLines.value) {
    const raw = line.monto.replace(',', '.').trim()
    const n = Number(raw)
    if (!Number.isFinite(n) || n <= 0) continue
    toPost.push({ documento_compra_id: line.documentoId, monto: n })
  }
  if (!toPost.length) {
    modalPagoError.value = 'Indique al menos un monto mayor que cero.'
    return
  }
  modalPagoSaving.value = true
  try {
    for (const { documento_compra_id, monto } of toPost) {
      await api.post('/tesoreria/cronograma/registrar-por-documento/', {
        documento_compra_id,
        monto,
        metodo: modalPagoMetodo.value,
      })
    }
    modalPagoOpen.value = false
    selectedCompraIds.value = []
    await load()
  } catch (e) {
    modalPagoError.value = modalPagoErrorMessage(e)
  } finally {
    modalPagoSaving.value = false
  }
}

/** Si no es null, el modal edita este borrador (PATCH actualizar-borrador). */
const editingDocId = ref<number | null>(null)

const showModal = ref(false)
const catalogLoading = ref(false)
const submitError = ref('')
const submitting = ref(false)
const proveedoresCatalog = ref<ProvCat[]>([])
const itemCatalog = ref<ItemCat[]>([])
const almacenesCatalog = ref<AlmCat[]>([])

const formCab = reactive({
  proveedor_id: '' as number | '',
  tipo: 'FACTURA_COMPRA' as TipoComprobanteCompraCab,
  serie: '',
  numero: '',
  fecha: isoDate(new Date()),
  condicion_pago: 'CONTADO' as 'CONTADO' | 'CREDITO',
  fecha_vencimiento: '',
  precio_incluye_igv: false,
  /** Si es false, al emitir no se crean movimientos de inventario (no aparece en kardex). */
  afecta_stock: true,
})

/** Captura / alta rápida de proveedor (misma idea que cliente en ventas). */
const formProveedor = reactive({
  tipo_doc: 'RUC' as 'RUC' | 'DNI',
  documento: '',
  razon_social: '',
})

const provSuggestOpen = ref(false)
let provSuggestCloseTimer: ReturnType<typeof setTimeout> | null = null
const consultProvLoading = ref(false)
const proveedorConsultMsg = ref('')
const proveedorConsultIsError = ref(false)
const crearProvLoading = ref(false)

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

const totalIgvPreview = computed(() => Math.round(totalGravada.value * IGV_RATE * 100) / 100)
const totalDocPreview = computed(() => Math.round((totalGravada.value + totalIgvPreview.value) * 100) / 100)

const precioUnitHint = computed(() =>
  formCab.precio_incluye_igv ? 'Valor unitario (con IGV)' : 'Valor unitario (sin IGV)',
)

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

const proveedoresMatches = computed(() => {
  const t = formProveedor.documento.trim()
  if (!t) return []
  const td = t.replace(/\D/g, '')
  const tLower = t.toLowerCase()
  return proveedoresCatalog.value
    .filter((p) => p.activo !== false)
    .filter((p) => {
      const doc = (p.documento || '').trim()
      if (!doc) return false
      const dd = doc.replace(/\D/g, '')
      if (doc.toLowerCase().startsWith(tLower)) return true
      if (td.length > 0 && dd.startsWith(td)) return true
      return false
    })
    .slice(0, 10)
})

const puedeConsultarPadronProv = computed(() => {
  const n = formProveedor.documento.replace(/\D/g, '')
  if (formProveedor.tipo_doc === 'RUC') return /^\d{11}$/.test(n)
  return /^\d{8}$/.test(n)
})

const compraEsCredito = computed(() => formCab.condicion_pago === 'CREDITO')

function onProvDocFocusIn() {
  if (provSuggestCloseTimer) {
    clearTimeout(provSuggestCloseTimer)
    provSuggestCloseTimer = null
  }
  provSuggestOpen.value = true
}

function onProvDocFocusOut() {
  provSuggestCloseTimer = setTimeout(() => {
    provSuggestOpen.value = false
    provSuggestCloseTimer = null
  }, 220)
}

function pickProveedorCatalogo(p: ProvCat) {
  formCab.proveedor_id = p.id
  formProveedor.documento = (p.documento || '').trim().slice(0, 20)
  formProveedor.razon_social = (p.razon_social || '').trim().slice(0, 255)
  const digits = formProveedor.documento.replace(/\D/g, '')
  if (digits.length === 11) formProveedor.tipo_doc = 'RUC'
  else if (digits.length === 8) formProveedor.tipo_doc = 'DNI'
  provSuggestOpen.value = false
  proveedorConsultMsg.value = ''
  proveedorConsultIsError.value = false
}

async function consultarPadronProveedor() {
  proveedorConsultMsg.value = ''
  proveedorConsultIsError.value = false
  const n = formProveedor.documento.replace(/\D/g, '')
  if (formProveedor.tipo_doc === 'RUC') {
    if (!/^\d{11}$/.test(n)) {
      proveedorConsultMsg.value = 'Para SUNAT ingrese 11 dígitos de RUC.'
      proveedorConsultIsError.value = true
      return
    }
  } else if (!/^\d{8}$/.test(n)) {
    proveedorConsultMsg.value = 'Para RENIEC ingrese 8 dígitos de DNI.'
    proveedorConsultIsError.value = true
    return
  }

  consultProvLoading.value = true
  try {
    if (formProveedor.tipo_doc === 'RUC') {
      const { data } = await api.get<{
        ok?: boolean
        nombre_padron?: string
        razon_social?: string
        detail?: string
      }>('/core/consultar-ruc/', { params: { numero: n } })
      if (data.ok) {
        const pad = (data.nombre_padron || data.razon_social || '').trim()
        if (pad) {
          formProveedor.razon_social = pad.slice(0, 255)
          proveedorConsultMsg.value = 'Razón social sugerida por SUNAT (revise antes de guardar).'
          proveedorConsultIsError.value = false
        } else {
          proveedorConsultMsg.value = 'SUNAT no devolvió nombre para este RUC.'
          proveedorConsultIsError.value = true
        }
      } else {
        proveedorConsultMsg.value =
          typeof data.detail === 'string' && data.detail.trim()
            ? data.detail
            : 'No se pudo consultar el RUC.'
        proveedorConsultIsError.value = true
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
          formProveedor.razon_social = nom.slice(0, 255)
          proveedorConsultMsg.value = 'Nombre sugerido por RENIEC (revise antes de guardar).'
          proveedorConsultIsError.value = false
        } else {
          proveedorConsultMsg.value = 'No se recibió nombre para este DNI.'
          proveedorConsultIsError.value = true
        }
      } else {
        proveedorConsultMsg.value =
          typeof data.detail === 'string' && data.detail.trim()
            ? data.detail
            : 'No se pudo consultar el DNI.'
        proveedorConsultIsError.value = true
      }
    }
  } catch (e) {
    proveedorConsultIsError.value = true
    proveedorConsultMsg.value = detailFromAxios(e, 'Error al consultar el padrón.')
  } finally {
    consultProvLoading.value = false
  }
}

async function crearProveedorDesdeForm() {
  proveedorConsultMsg.value = ''
  proveedorConsultIsError.value = false
  const rs = formProveedor.razon_social.trim()
  if (!rs) {
    proveedorConsultIsError.value = true
    proveedorConsultMsg.value = 'Ingrese la razón social o nombre del proveedor.'
    return
  }
  const doc = formProveedor.documento.trim().slice(0, 20)
  const dDigits = doc.replace(/\D/g, '')
  if (dDigits.length > 0) {
    const existing = proveedoresCatalog.value.find(
      (p) => (p.documento || '').replace(/\D/g, '') === dDigits,
    )
    if (existing) {
      pickProveedorCatalogo(existing)
      proveedorConsultIsError.value = false
      proveedorConsultMsg.value = 'Ya estaba en el maestro; datos cargados para esta factura.'
      return
    }
  }

  crearProvLoading.value = true
  try {
    const body: Record<string, unknown> = {
      razon_social: rs.slice(0, 255),
      documento: doc,
      email: '',
      telefono: '',
      direccion: '',
      activo: true,
    }
    if (ctx.isSuperuser && ctx.empresaId) {
      body.empresa = Number(ctx.empresaId)
    }
    const { data } = await api.post<{ id?: number; razon_social?: string; documento?: string }>(
      '/core/proveedores/',
      body,
    )
    const newId = data.id
    if (typeof newId !== 'number') throw new Error('Respuesta sin id')
    const nuevo: ProvCat = {
      id: newId,
      razon_social: data.razon_social || rs,
      documento: (data.documento ?? doc) || undefined,
      activo: true,
    }
    proveedoresCatalog.value = [...proveedoresCatalog.value, nuevo].sort((a, b) =>
      (a.razon_social || '').localeCompare(b.razon_social || '', 'es'),
    )
    formCab.proveedor_id = newId
    proveedorConsultIsError.value = false
    proveedorConsultMsg.value = 'Proveedor creado y seleccionado para esta factura.'
  } catch (e) {
    proveedorConsultIsError.value = true
    proveedorConsultMsg.value = detailFromAxios(e, 'No se pudo crear el proveedor.')
  } finally {
    crearProvLoading.value = false
  }
}

async function openNuevaFactura() {
  editingDocId.value = null
  submitError.value = ''
  showModal.value = true
  formCab.proveedor_id = ''
  formCab.tipo = 'FACTURA_COMPRA'
  formCab.serie = ''
  formCab.numero = ''
  formCab.fecha = isoDate(new Date())
  formCab.condicion_pago = 'CONTADO'
  formCab.fecha_vencimiento = ''
  formCab.precio_incluye_igv = false
  formCab.afecta_stock = true
  formProveedor.tipo_doc = 'RUC'
  formProveedor.documento = ''
  formProveedor.razon_social = ''
  proveedorConsultMsg.value = ''
  proveedorConsultIsError.value = false
  lineasForm.value = [{ item_id: '', cantidad: '1', precio_unit: '' }]

  catalogLoading.value = true
  proveedoresCatalog.value = []
  itemCatalog.value = []
  almacenesCatalog.value = []
  try {
    const [provRes, itemsRes, almRes] = await Promise.all([
      api.get<{ results?: ProvCat[] }>('/core/proveedores/?page_size=500&ordering=razon_social').catch(() => null),
      api.get<{ results?: ItemCat[] }>('/inventario/items/?page_size=500').catch(() => null),
      api.get<{ results?: AlmCat[] }>('/inventario/almacenes/?page_size=100&activo=1').catch(() => null),
    ])
    proveedoresCatalog.value = provRes?.data?.results ?? []
    itemCatalog.value = itemsRes?.data?.results ?? []
    almacenesCatalog.value = almRes?.data?.results ?? []
  } finally {
    catalogLoading.value = false
  }
}

function cerrarModal() {
  showModal.value = false
  editingDocId.value = null
}

function validateForm(): string | null {
  if (formCab.proveedor_id === '' || formCab.proveedor_id == null) return 'Seleccione un proveedor.'
  const raw = lineasForm.value.filter((l) => l.item_id !== '')
  if (!raw.length) return 'Agregue al menos una línea con producto.'
  for (const ln of raw) {
    const c = Number(ln.cantidad)
    const p = Number(ln.precio_unit)
    if (!Number.isFinite(c) || c <= 0) return 'Revise las cantidades.'
    if (!Number.isFinite(p) || p < 0)
      return `Revise el valor unitario de las líneas (${formCab.precio_incluye_igv ? 'con IGV' : 'sin IGV'}).`
  }
  if (formCab.condicion_pago === 'CREDITO') {
    const fv = formCab.fecha_vencimiento.trim()
    if (!fv) return 'En compra a crédito indique la fecha de vencimiento del pago (tesorería).'
    if (formCab.fecha && fv < formCab.fecha)
      return 'La fecha de vencimiento no puede ser anterior a la fecha del documento.'
  }
  return null
}

function buildAltaBorradorBody(): Record<string, unknown> {
  const raw = lineasForm.value.filter((l) => l.item_id !== '')
  const body: Record<string, unknown> = {
    proveedor_id: Number(formCab.proveedor_id),
    tipo: formCab.tipo,
    serie: formCab.serie.trim().slice(0, 10),
    numero: formCab.numero.trim().slice(0, 20),
    fecha: formCab.fecha,
    lineas: raw.map((l) => ({
      item_id: Number(l.item_id),
      cantidad: String(l.cantidad),
      precio_unit: String(l.precio_unit),
    })),
    condicion_pago: formCab.condicion_pago,
    fecha_vencimiento:
      formCab.condicion_pago === 'CREDITO' ? formCab.fecha_vencimiento.trim() || null : null,
    precio_incluye_igv: formCab.precio_incluye_igv,
    afecta_stock: formCab.afecta_stock,
  }
  const emp = ctx.empresaId
  if (emp) body.empresa_id = Number(emp)
  return body
}

async function postAltaBorrador(): Promise<number> {
  const body = buildAltaBorradorBody()
  const { data } = await api.post<{ id?: number }>('/compras/documentos/alta-borrador/', body)
  const id = data.id
  if (typeof id !== 'number') throw new Error('Respuesta sin id de documento.')
  return id
}

function precioUnitUiDesdeLineaApi(precioUnit: unknown, precioIncluyeIgv: boolean): string {
  const n = typeof precioUnit === 'string' ? parseFloat(precioUnit) : Number(precioUnit)
  if (!Number.isFinite(n) || n < 0) return ''
  const shown = precioIncluyeIgv ? n * (1 + IGV_RATE) : n
  const r = Math.round(shown * 10000) / 10000
  return String(r)
}

async function openEditarBorradorPorId(id: number) {
  submitError.value = ''
  editingDocId.value = id
  showModal.value = true
  catalogLoading.value = true
  try {
    const [docRes, provRes, itemsRes, almRes] = await Promise.all([
      api.get<{
        proveedor?: number
        tipo?: string
        serie?: string
        numero?: string
        fecha?: string
        condicion_pago?: string
        fecha_vencimiento?: string | null
        precio_incluye_igv?: boolean
        afecta_stock?: boolean
        lineas?: { item?: number; cantidad?: string; precio_unit?: string }[]
      }>(`/compras/documentos/${id}/`),
      api.get<{ results?: ProvCat[] }>('/core/proveedores/?page_size=500&ordering=razon_social').catch(() => null),
      api.get<{ results?: ItemCat[] }>('/inventario/items/?page_size=500').catch(() => null),
      api.get<{ results?: AlmCat[] }>('/inventario/almacenes/?page_size=100&activo=1').catch(() => null),
    ])
    const d = docRes.data
    proveedoresCatalog.value = provRes?.data?.results ?? []
    itemCatalog.value = itemsRes?.data?.results ?? []
    almacenesCatalog.value = almRes?.data?.results ?? []

    const pid = d.proveedor
    formCab.proveedor_id = typeof pid === 'number' ? pid : ''
    formCab.tipo = (d.tipo as TipoComprobanteCompraCab) || 'FACTURA_COMPRA'
    formCab.serie = typeof d.serie === 'string' ? d.serie : ''
    formCab.numero = typeof d.numero === 'string' ? d.numero : ''
    formCab.fecha = typeof d.fecha === 'string' ? d.fecha.slice(0, 10) : isoDate(new Date())
    formCab.condicion_pago = d.condicion_pago === 'CREDITO' ? 'CREDITO' : 'CONTADO'
    formCab.fecha_vencimiento =
      typeof d.fecha_vencimiento === 'string' ? d.fecha_vencimiento.slice(0, 10) : ''
    formCab.precio_incluye_igv = !!d.precio_incluye_igv
    formCab.afecta_stock = d.afecta_stock !== false

    const prov = proveedoresCatalog.value.find((p) => p.id === pid)
    if (prov) {
      pickProveedorCatalogo(prov)
    } else {
      formProveedor.documento = ''
      formProveedor.razon_social = ''
    }

    const incl = !!d.precio_incluye_igv
    const lns = Array.isArray(d.lineas) ? d.lineas : []
    lineasForm.value =
      lns.length > 0
        ? lns.map((ln) => ({
            item_id: typeof ln.item === 'number' ? ln.item : '',
            cantidad: ln.cantidad != null ? String(ln.cantidad) : '1',
            precio_unit: precioUnitUiDesdeLineaApi(ln.precio_unit, incl),
          }))
        : [{ item_id: '', cantidad: '1', precio_unit: '' }]
  } catch (e) {
    submitError.value = detailFromAxios(e, 'No se pudo cargar el borrador.')
    editingDocId.value = null
    showModal.value = false
  } finally {
    catalogLoading.value = false
  }
}

async function openEditarBorrador(row: DocRow) {
  const id = row.id
  if (typeof id !== 'number' || rowEstado(row) !== 'BORRADOR') return
  await openEditarBorradorPorId(id)
}

const showReabrirModal = ref(false)
const reabrirRow = ref<DocRow | null>(null)
const reabrirSubmitting = ref(false)
const reabrirError = ref('')

const reabrirResumenReversion = computed(() => {
  const r = reabrirRow.value
  if (!r) return [] as string[]
  const out: string[] = []
  if (rowAfectaStock(r)) out.push('Se revertirá el movimiento de inventario (kardex).')
  if (r.condicion_pago === 'CREDITO') out.push('Se revertirán los pagos a proveedor registrados en tesorería.')
  return out
})

function abrirModalReabrirParaEditar(row: DocRow) {
  const id = row.id
  if (typeof id !== 'number' || rowEstado(row) !== 'EMITIDO') return
  reabrirRow.value = row
  reabrirError.value = ''
  showReabrirModal.value = true
}

function cerrarModalReabrirParaEditar() {
  if (reabrirSubmitting.value) return
  showReabrirModal.value = false
  reabrirRow.value = null
  reabrirError.value = ''
}

async function confirmarReabrirParaEditar() {
  const row = reabrirRow.value
  const id = row?.id
  if (typeof id !== 'number') return
  actionBusyId.value = id
  reabrirSubmitting.value = true
  reabrirError.value = ''
  try {
    await api.post(`/compras/documentos/${id}/reabrir-borrador/`)
    showReabrirModal.value = false
    reabrirRow.value = null
    await load()
    await openEditarBorradorPorId(id)
  } catch (e) {
    reabrirError.value = detailFromAxios(e, 'No se pudo reabrir el documento para edición.')
  } finally {
    reabrirSubmitting.value = false
    actionBusyId.value = null
  }
}

async function guardarBorrador() {
  const err = validateForm()
  if (err) {
    submitError.value = err
    return
  }
  submitting.value = true
  submitError.value = ''
  try {
    const eid = editingDocId.value
    const body = buildAltaBorradorBody()
    if (eid != null) {
      await api.patch(`/compras/documentos/${eid}/actualizar-borrador/`, body)
    } else {
      await api.post('/compras/documentos/alta-borrador/', body)
    }
    cerrarModal()
    await load()
  } catch (e) {
    submitError.value = detailFromAxios(e, 'No se pudo guardar el borrador.')
  } finally {
    submitting.value = false
  }
}

async function guardarEIngresarStock() {
  const err = validateForm()
  if (err) {
    submitError.value = err
    return
  }
  if (formAlmacenId.value === '' || formAlmacenId.value == null) {
    submitError.value = almacenesCatalog.value.length
      ? 'Seleccione el almacén de ingreso para registrar el stock.'
      : 'No hay almacenes registrados. Vaya a Inventario → Almacenes y ubicaciones, cree uno y vuelva a intentar.'
    return
  }
  submitting.value = true
  submitError.value = ''
  try {
    const eid = editingDocId.value
    let docId: number
    if (eid != null) {
      await api.patch(`/compras/documentos/${eid}/actualizar-borrador/`, buildAltaBorradorBody())
      docId = eid
    } else {
      docId = await postAltaBorrador()
    }
    await api.post(`/compras/documentos/${docId}/emitir/`, {
      almacen_id: Number(formAlmacenId.value),
    })
    cerrarModal()
    await load()
  } catch (e) {
    submitError.value = detailFromAxios(
      e,
      'No se pudo registrar la compra (pudo haberse creado el borrador; revíselo en la lista).',
    )
  } finally {
    submitting.value = false
  }
}

/** Almacén elegido en el modal de nueva factura (solo para “Registrar e ingresar stock”). */
const formAlmacenId = ref<number | ''>('')

const showEmitModal = ref(false)
const emitRow = ref<DocRow | null>(null)

const emitModalAfectaStock = computed(() => {
  const r = emitRow.value
  if (!r) return true
  return rowAfectaStock(r)
})
const emitAlmacenId = ref<number | ''>('')
const emitSubmitting = ref(false)
const emitError = ref('')

function abrirEmitir(row: DocRow) {
  if (rowEstado(row) !== 'BORRADOR') return
  emitRow.value = row
  emitAlmacenId.value = ''
  emitError.value = ''
  showEmitModal.value = true
  if (!almacenesCatalog.value.length) {
    api
      .get<{ results?: AlmCat[] }>('/inventario/almacenes/?page_size=100&activo=1')
      .then((r) => {
        almacenesCatalog.value = r.data?.results ?? []
      })
      .catch(() => {})
  }
}

function cerrarEmitModal() {
  showEmitModal.value = false
  emitRow.value = null
}

async function confirmarEmitir() {
  const row = emitRow.value
  const id = row?.id
  if (typeof id !== 'number') return
  if (emitAlmacenId.value === '' || emitAlmacenId.value == null) {
    emitError.value = 'Seleccione almacén.'
    return
  }
  emitSubmitting.value = true
  emitError.value = ''
  try {
    await api.post(`/compras/documentos/${id}/emitir/`, {
      almacen_id: Number(emitAlmacenId.value),
    })
    cerrarEmitModal()
    await load()
  } catch (e) {
    emitError.value = detailFromAxios(e, 'No se pudo registrar el ingreso a inventario.')
  } finally {
    emitSubmitting.value = false
  }
}

const actionBusyId = ref<number | null>(null)

async function anularDocumentoCompra(row: DocRow) {
  const id = row.id
  if (typeof id !== 'number') return
  const st = rowEstado(row)
  if (st === 'BORRADOR') {
    if (!confirm('¿Anular este borrador? Dejará de mostrarse en el listado.')) return
  } else if (st === 'EMITIDO') {
    if (
      !confirm(
        '¿Anular este documento registrado? Se revertirá el movimiento de inventario (si aplica) y solo es posible si no hay pagos en tesorería.',
      )
    )
      return
  } else {
    return
  }
  actionBusyId.value = id
  errorMsg.value = ''
  try {
    await api.post(`/compras/documentos/${id}/anular/`, {})
    await load()
  } catch (e) {
    errorMsg.value = detailFromAxios(e, 'No se pudo anular el documento.')
  } finally {
    actionBusyId.value = null
  }
}

const modalFacturaTitulo = computed(() =>
  editingDocId.value != null ? 'Editar factura de proveedor (borrador)' : 'Nueva factura de proveedor',
)
</script>

<template>
  <div class="cmp-page">
    <header class="toolbar">
      <div class="toolbar-left">
        <div class="head-text">
          <h1 class="title">Facturas de proveedores</h1>
          <p class="lead">
            Registre compras a sus proveedores como documento <strong>interno</strong> (no se declara a SUNAT). Al
            <strong>registrar el ingreso</strong> se actualiza el inventario (kardex), salvo que marque
            <strong>sin movimiento de inventario</strong> en el documento. Compras a <strong>crédito</strong> generan un
            pendiente en Tesorería → Cuentas por pagar; al <strong>contado</strong> no.
          </p>
        </div>
        <div class="toolbar-actions-row">
          <button type="button" class="btn-create" @click="openNuevaFactura">
            <span class="plus" aria-hidden="true">+</span>
            Nueva factura de proveedor
          </button>
          <button type="button" class="btn-tool-secondary" @click="descargarPlantillaComprasExcel">
            Descargar plantilla
          </button>
          <button
            type="button"
            class="btn-tool-secondary"
            :disabled="importComprasBusy || !canUseComprasExcel"
            :title="
              !canUseComprasExcel
                ? 'Seleccione empresa en la barra superior (administrador).'
                : 'Subir Excel con la misma estructura que la plantilla (hoja Compras).'
            "
            @click="clickImportComprasExcel"
          >
            {{ importComprasBusy ? 'Importando…' : 'Importar Excel' }}
          </button>
          <button type="button" class="btn-tool-ghost" :disabled="loading" @click="refresh">Actualizar</button>
          <input
            ref="importComprasInputRef"
            type="file"
            class="sr-only"
            accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
            @change="onImportComprasExcelFile"
          />
        </div>
      </div>
    </header>

    <section class="filters">
      <label class="filter-field filter-grow">
        <span class="filter-label">Buscar proveedor o documento</span>
        <input
          v-model="filters.search"
          type="search"
          class="filter-inp"
          placeholder="Razón social, RUC, serie o número"
          autocomplete="off"
        />
      </label>
      <label class="filter-field filter-sm">
        <span class="filter-label">Estado</span>
        <select v-model="filters.estado" class="filter-inp filter-select">
          <option value="">Todos</option>
          <option value="BORRADOR">Borrador</option>
          <option value="EMITIDO">Registrado (stock)</option>
        </select>
      </label>
    </section>

    <p v-if="errorMsg" class="err-banner">{{ errorMsg }}</p>
    <p v-if="bulkImportMsg" class="import-notice" :class="bulkImportOk ? 'import-notice--ok' : 'import-notice--warn'">
      {{ bulkImportMsg }}
    </p>

    <div class="compras-pay-panel">
      <p class="compras-pay-panel__hint">
        Compras a crédito emitidas: seleccione filas para registrar el pago (igual que en Cuentas por pagar) o abrir el
        historial en Pagos realizados.
      </p>
      <div class="compras-pay-panel__actions">
        <button
          type="button"
          class="cmp-pay-pill cmp-pay-pill--accent"
          :disabled="!canRegistrarPagoCompras"
          title="Abre el registro de pago por documento"
          @click="openModalRegistrarPagoCompras"
        >
          Registrar pago
        </button>
        <RouterLink class="cmp-pay-pill cmp-pay-pill--primary" :to="pagosRealizadosComprasLink">
          Pagos realizados
        </RouterLink>
        <RouterLink class="cmp-pay-pill" to="/tesoreria/cuentas-por-pagar">Cuentas por pagar</RouterLink>
      </div>
    </div>

    <p v-if="selectedCompraIds.length" class="selection-bar">
      {{ selectedCompraIds.length }}
      {{ selectedCompraIds.length === 1 ? 'documento seleccionado' : 'documentos seleccionados' }}.
    </p>

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
                <th class="th-check">
                  <input
                    v-model="allComprasPageSelected"
                    type="checkbox"
                    aria-label="Seleccionar todas las compras a crédito en la página"
                  />
                </th>
                <th>Número</th>
                <th>Proveedor</th>
                <th>F. documento</th>
                <th>Creación</th>
                <th class="num">Total</th>
                <th>Pago</th>
                <th>Venc.</th>
                <th>Estado</th>
                <th>Inventario</th>
                <th>Origen</th>
                <th class="td-gestion">Gestión</th>
                <th class="td-actions">Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, idx) in rows"
                :key="typeof row.id === 'number' ? row.id : idx"
                :data-doc-compra-id="typeof row.id === 'number' ? row.id : undefined"
              >
                <td class="td-check">
                  <input
                    v-if="puedeVerPagosProveedor(row) && typeof row.id === 'number'"
                    type="checkbox"
                    :checked="rowCompraChecked(row.id)"
                    :aria-label="`Seleccionar documento ${numeroCompra(row)}`"
                    @change="toggleCompraRow(row.id)"
                  />
                </td>
                <td class="td-strong">{{ numeroCompra(row) }}</td>
                <td class="cell-clip">{{ row.proveedor_razon_social ?? '—' }}</td>
                <td>{{ formatDate(row.fecha) }}</td>
                <td class="muted-sm">{{ formatDateTimeShort(row.creado_en) }}</td>
                <td class="num">{{ formatMoney(row.total) }}</td>
                <td>{{ condicionPagoLabel(row) }}</td>
                <td class="muted-sm">{{ formatDate(row.fecha_vencimiento) }}</td>
                <td>
                  <span
                    class="pill"
                    :class="rowEstado(row) === 'BORRADOR' ? 'pill--draft' : 'pill--ok'"
                    >{{ rowEstado(row) === 'BORRADOR' ? 'Borrador' : 'Registrado' }}</span
                  >
                </td>
                <td>
                  <span
                    class="pill"
                    :class="rowAfectaStock(row) ? 'pill--ok' : 'pill--muted'"
                    :title="
                      rowAfectaStock(row)
                        ? 'Al registrar se generan movimientos de stock (kardex).'
                        : 'Al registrar no se mueve inventario; no aparece en kardex.'
                    "
                    >{{ labelStockKardex(row) }}</span
                  >
                </td>
                <td><span class="pill pill--muted">Interno</span></td>
                <td class="td-gestion">
                  <div class="cmp-gestion-icons" role="group" :aria-label="`Gestión documento ${numeroCompra(row)}`">
                    <button
                      v-if="rowEstado(row) === 'BORRADOR'"
                      type="button"
                      class="cmp-icon-btn cmp-icon-btn--edit"
                      title="Editar borrador"
                      :disabled="actionBusyId === row.id"
                      @click="openEditarBorrador(row)"
                    >
                      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          stroke="currentColor"
                          stroke-width="1.75"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"
                        />
                      </svg>
                    </button>
                    <button
                      v-if="rowEstado(row) === 'EMITIDO'"
                      type="button"
                      class="cmp-icon-btn cmp-icon-btn--edit"
                      title="Reabrir a borrador: revierte stock y/o pagos a proveedor, luego edita"
                      :disabled="actionBusyId === row.id"
                      @click="abrirModalReabrirParaEditar(row)"
                    >
                      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          stroke="currentColor"
                          stroke-width="1.75"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"
                        />
                      </svg>
                    </button>
                    <button
                      v-if="rowEstado(row) === 'BORRADOR' || rowEstado(row) === 'EMITIDO'"
                      type="button"
                      class="cmp-icon-btn cmp-icon-btn--del"
                      title="Anular documento (lógico)"
                      :disabled="actionBusyId === row.id"
                      @click="anularDocumentoCompra(row)"
                    >
                      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          stroke="currentColor"
                          stroke-width="1.75"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                        />
                      </svg>
                    </button>
                    <span
                      v-if="rowEstado(row) !== 'BORRADOR' && rowEstado(row) !== 'EMITIDO'"
                      class="muted-sm"
                      >—</span
                    >
                  </div>
                </td>
                <td class="td-actions">
                  <template v-if="rowEstado(row) === 'BORRADOR'">
                    <button
                      type="button"
                      class="btn-row btn-row--primary"
                      :disabled="actionBusyId === row.id"
                      @click="abrirEmitir(row)"
                    >
                      Ingresar stock
                    </button>
                  </template>
                  <RouterLink
                    v-else-if="puedeVerPagosProveedor(row)"
                    class="btn-row btn-row--cronograma"
                    title="Abrir Cuentas por pagar filtrado por este documento"
                    :to="pagosProveedorTo(row)"
                  >
                    Cuentas por pagar
                  </RouterLink>
                  <span v-else class="muted-sm">—</span>
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
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="cmp-modal-title">
          <h2 id="cmp-modal-title" class="modal-title">{{ modalFacturaTitulo }}</h2>
          <p class="modal-lead">
            Documento <strong>solo interno</strong> (no Nubefact ni SUNAT). Factura gravada con IGV 18%: indique si el
            precio unitario <strong>incluye IGV</strong> o no (igual que en ventas); el sistema calcula base, IGV y total.
          </p>
          <div v-if="catalogLoading" class="muted">Cargando catálogos…</div>
          <template v-else>
            <section class="block">
              <div class="prov-registro">
                <h4 class="prov-registro__title">Buscar o registrar proveedor</h4>
                <div class="prov-doc-grid">
                  <label class="fld">
                    <span>Tipo doc.</span>
                    <select v-model="formProveedor.tipo_doc" class="inp">
                      <option value="RUC">RUC</option>
                      <option value="DNI">DNI</option>
                    </select>
                  </label>
                  <div class="fld fld-doc-combo">
                    <span>Número doc.</span>
                    <div class="doc-num-row" @focusin="onProvDocFocusIn" @focusout="onProvDocFocusOut">
                      <div class="doc-num-input-wrap">
                        <input
                          v-model="formProveedor.documento"
                          class="inp"
                          maxlength="20"
                          autocomplete="off"
                          :placeholder="formProveedor.tipo_doc === 'RUC' ? '20123456789' : '12345678'"
                          @input="provSuggestOpen = true"
                        />
                        <ul
                          v-if="provSuggestOpen && proveedoresMatches.length"
                          class="doc-suggest"
                          role="listbox"
                          aria-label="Proveedores que coinciden"
                        >
                          <li
                            v-for="p in proveedoresMatches"
                            :key="p.id"
                            role="option"
                            class="doc-suggest__item"
                            @mousedown.prevent="pickProveedorCatalogo(p)"
                          >
                            <span class="doc-suggest__doc">{{ p.documento?.trim() || '—' }}</span>
                            <span class="doc-suggest__rs">{{ p.razon_social?.trim() || '—' }}</span>
                          </li>
                        </ul>
                      </div>
                      <button
                        type="button"
                        class="btn-consult-padron"
                        :disabled="!puedeConsultarPadronProv || consultProvLoading"
                        :title="
                          formProveedor.tipo_doc === 'RUC'
                            ? 'Consultar razón social en SUNAT (11 dígitos)'
                            : 'Consultar nombre en RENIEC (8 dígitos)'
                        "
                        :aria-label="
                          consultProvLoading
                            ? 'Consultando padrón'
                            : formProveedor.tipo_doc === 'RUC'
                              ? 'Consultar SUNAT'
                              : 'Consultar RENIEC'
                        "
                        @click="consultarPadronProveedor"
                      >
                        <template v-if="consultProvLoading">…</template>
                        <template v-else>
                          <!-- Sol = mnemónico SUNAT (no es el logotipo oficial) -->
                          <svg
                            v-if="formProveedor.tipo_doc === 'RUC'"
                            class="btn-consult-padron__ico"
                            viewBox="0 0 24 24"
                            fill="none"
                            aria-hidden="true"
                          >
                            <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.75" />
                            <path
                              stroke="currentColor"
                              stroke-width="1.75"
                              stroke-linecap="round"
                              d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.93 4.93l1.77 1.77M17.3 17.3l1.77 1.77M19.07 4.93l-1.77 1.77M6.7 17.3l-1.77 1.77"
                            />
                          </svg>
                          <svg
                            v-else
                            class="btn-consult-padron__ico"
                            viewBox="0 0 24 24"
                            fill="none"
                            aria-hidden="true"
                          >
                            <rect
                              x="3"
                              y="5"
                              width="18"
                              height="14"
                              rx="2"
                              stroke="currentColor"
                              stroke-width="1.75"
                            />
                            <circle cx="9" cy="12" r="2.25" stroke="currentColor" stroke-width="1.5" />
                            <path
                              stroke="currentColor"
                              stroke-width="1.5"
                              stroke-linecap="round"
                              d="M14 10h4M14 14h4"
                            />
                          </svg>
                          <span class="btn-consult-padron__text">{{
                            formProveedor.tipo_doc === 'RUC' ? 'SUNAT' : 'RENIEC'
                          }}</span>
                        </template>
                      </button>
                    </div>
                    <p
                      v-if="proveedorConsultMsg"
                      class="doc-num-feedback"
                      :class="{ 'doc-num-feedback--err': proveedorConsultIsError }"
                    >
                      {{ proveedorConsultMsg }}
                    </p>
                  </div>
                </div>
                <label class="fld">
                  <span>Razón social / nombre</span>
                  <input
                    v-model="formProveedor.razon_social"
                    class="inp"
                    maxlength="255"
                    placeholder="Razón social o nombre completo"
                  />
                </label>
                <button
                  type="button"
                  class="btn-guardar-prov"
                  :disabled="crearProvLoading"
                  @click="crearProveedorDesdeForm"
                >
                  {{ crearProvLoading ? '…' : 'Guardar proveedor y usar' }}
                </button>
              </div>
              <label class="fld">
                <span>Tipo de comprobante</span>
                <select v-model="formCab.tipo" class="inp">
                  <option v-for="opt in tipoComprobanteCompraOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </label>
              <div class="grid-2">
                <label class="fld">
                  <span>Serie (opc.)</span>
                  <input v-model="formCab.serie" class="inp" maxlength="10" placeholder="Ej. F001" />
                </label>
                <label class="fld">
                  <span>Número (opc.)</span>
                  <input v-model="formCab.numero" class="inp" maxlength="20" placeholder="Correlativo proveedor" />
                </label>
              </div>
              <label class="fld">
                <span>Fecha del documento</span>
                <input v-model="formCab.fecha" type="date" class="inp" />
              </label>
              <label class="fld">
                <span>Condición de pago</span>
                <select v-model="formCab.condicion_pago" class="inp">
                  <option value="CONTADO">Contado (sin obligación en cronograma)</option>
                  <option value="CREDITO">Crédito (aparece en tesorería al ingresar stock)</option>
                </select>
              </label>
              <label v-if="compraEsCredito" class="fld">
                <span>Vencimiento del pago al proveedor</span>
                <input v-model="formCab.fecha_vencimiento" type="date" class="inp" />
              </label>
            </section>

            <section class="block">
              <div class="block-head">
                <h3 class="block-title">Líneas</h3>
                <button type="button" class="btn-add-line" @click="addLinea">+ Línea</button>
              </div>
              <label class="fld fld-check-igv">
                <input v-model="formCab.precio_incluye_igv" type="checkbox" />
                <span>El precio unitario incluye IGV (18%)</span>
              </label>
              <label class="fld fld-check-igv">
                <input v-model="formCab.afecta_stock" type="checkbox" />
                <span
                  >Este documento <strong>mueve inventario</strong> al registrarlo (ingreso en kardex). Desmarque si es
                  solo contable o no afecta stock.</span
                >
              </label>
              <div class="lineas-wrap">
                <div v-for="(ln, i) in lineasForm" :key="i" class="linea-row">
                  <select v-model="ln.item_id" class="inp inp-item">
                    <option disabled value="">— Producto —</option>
                    <option v-for="it in itemCatalog" :key="it.id" :value="it.id">{{ itemLabel(it) }}</option>
                  </select>
                  <input v-model="ln.cantidad" class="inp inp-qty" type="text" inputmode="decimal" />
                  <input
                    v-model="ln.precio_unit"
                    class="inp inp-price"
                    type="text"
                    inputmode="decimal"
                    :title="precioUnitHint"
                    :placeholder="formCab.precio_incluye_igv ? 'Con IGV' : 'Sin IGV'"
                  />
                  <button
                    v-if="lineasForm.length > 1"
                    type="button"
                    class="btn-icon-del"
                    title="Quitar línea"
                    @click="removeLinea(i)"
                  >
                    ×
                  </button>
                </div>
              </div>
              <p class="line-hint">
                Cantidad y {{ precioUnitHint.toLowerCase() }}; el almacenamiento interno usa siempre valor
                <strong>sin IGV</strong> por línea.
              </p>
              <div class="totals-preview">
                <div>
                  <span class="tot-label">T. gravado</span>
                  <span class="tot-val">S/ {{ totalGravada.toFixed(2) }}</span>
                </div>
                <div>
                  <span class="tot-label">IGV 18%</span>
                  <span class="tot-val">S/ {{ totalIgvPreview.toFixed(2) }}</span>
                </div>
                <div class="tot-row-total">
                  <span class="tot-label">Total</span>
                  <span class="tot-val tot-grand">S/ {{ totalDocPreview.toFixed(2) }}</span>
                </div>
              </div>
            </section>

            <section class="block block--almacen">
              <label class="fld">
                <span>Almacén (solo si registra stock ahora)</span>
                <select v-model="formAlmacenId" class="inp" :disabled="!almacenesCatalog.length">
                  <option disabled value="">— Opcional para “Solo borrador” —</option>
                  <option v-for="a in almacenesCatalog" :key="a.id" :value="a.id">
                    {{ (a.nombre || '').trim() || `Almacén #${a.id}` }}
                  </option>
                </select>
              </label>
              <p v-if="!almacenesCatalog.length" class="almacen-hint">
                No hay almacenes activos. Créelos en
                <RouterLink to="/inventario/almacenes">Inventario → Almacenes y ubicaciones</RouterLink>
                (asigne uno a su sucursal, p. ej. «Sucursal principal») y vuelva a abrir esta factura.
              </p>
            </section>

            <p v-if="submitError" class="form-err">{{ submitError }}</p>
            <div class="modal-foot">
              <button type="button" class="btn-ghost" :disabled="submitting" @click="cerrarModal">Cerrar</button>
              <button type="button" class="btn-secondary" :disabled="submitting" @click="guardarBorrador">
                {{ submitting ? '…' : 'Solo borrador' }}
              </button>
              <button type="button" class="btn-primary" :disabled="submitting" @click="guardarEIngresarStock">
                {{ submitting ? '…' : 'Registrar e ingresar stock' }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showEmitModal" class="modal-backdrop" @click.self="cerrarEmitModal">
        <div class="modal-panel modal-panel--sm" role="dialog" aria-modal="true">
          <h2 class="modal-title">{{ emitModalAfectaStock ? 'Ingresar stock' : 'Registrar documento' }}</h2>
          <p class="modal-lead">
            <template v-if="emitModalAfectaStock">
              Se registrará el ingreso de mercadería según las líneas del documento
              <strong>{{ emitRow ? numeroCompra(emitRow) : '' }}</strong>.
            </template>
            <template v-else>
              El documento <strong>{{ emitRow ? numeroCompra(emitRow) : '' }}</strong> está marcado
              <strong>sin movimiento de inventario</strong>: no se crearán líneas en kardex. Solo se confirmará como
              registrado (y tesorería si aplica).
            </template>
          </p>
          <label class="fld">
            <span>Almacén</span>
            <select v-model="emitAlmacenId" class="inp" :disabled="!almacenesCatalog.length">
              <option disabled value="">— Seleccione —</option>
              <option v-for="a in almacenesCatalog" :key="a.id" :value="a.id">
                {{ (a.nombre || '').trim() || `Almacén #${a.id}` }}
              </option>
            </select>
          </label>
          <p v-if="!almacenesCatalog.length" class="almacen-hint">
            No hay almacenes activos.
            <RouterLink to="/inventario/almacenes">Registre un almacén</RouterLink>
            en Inventario y vuelva a intentar.
          </p>
          <p v-if="emitError" class="form-err">{{ emitError }}</p>
          <div class="modal-foot">
            <button type="button" class="btn-ghost" :disabled="emitSubmitting" @click="cerrarEmitModal">
              Cancelar
            </button>
            <button type="button" class="btn-primary" :disabled="emitSubmitting" @click="confirmarEmitir">
              {{ emitSubmitting ? '…' : emitModalAfectaStock ? 'Confirmar ingreso' : 'Confirmar registro' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showReabrirModal"
        class="modal-backdrop"
        role="presentation"
        @click.self="cerrarModalReabrirParaEditar"
      >
        <div
          class="modal-panel modal-panel--sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="cmp-reabrir-title"
        >
          <h2 id="cmp-reabrir-title" class="modal-title">Reabrir para editar</h2>
          <p class="modal-lead">
            El documento
            <strong>{{ reabrirRow ? numeroCompra(reabrirRow) : '' }}</strong>
            volverá a <strong>borrador</strong>. Después deberá registrar de nuevo el ingreso a stock o el pago si
            corresponde.
          </p>
          <ul v-if="reabrirResumenReversion.length" class="reabrir-checklist">
            <li v-for="(t, i) in reabrirResumenReversion" :key="i">{{ t }}</li>
          </ul>
          <p v-if="reabrirError" class="form-err">{{ reabrirError }}</p>
          <div class="modal-foot">
            <button type="button" class="btn-ghost" :disabled="reabrirSubmitting" @click="cerrarModalReabrirParaEditar">
              Cancelar
            </button>
            <button type="button" class="btn-primary" :disabled="reabrirSubmitting" @click="confirmarReabrirParaEditar">
              {{ reabrirSubmitting ? '…' : 'Continuar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="modalPagoOpen" class="modal-pago-root" role="presentation" @click.self="closeModalPagoCompras">
        <div class="modal-pago-card" role="dialog" aria-modal="true" aria-labelledby="cmp-pago-modal-title">
          <h2 id="cmp-pago-modal-title" class="modal-pago-title">Registrar pago a proveedor</h2>
          <p class="modal-pago-lead">
            Se aplicará a la <strong>obligación pendiente</strong> de cada documento y figurará en Pagos realizados.
          </p>
          <label class="modal-pago-field">
            <span class="modal-pago-field__lab">Medio de pago</span>
            <select v-model="modalPagoMetodo" class="modal-pago-field__sel">
              <option v-for="o in metodoPagoOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>
          <div class="modal-pago-table-wrap">
            <table class="modal-pago-table">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th class="num">Total doc.</th>
                  <th class="num">Monto a pagar</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="line in modalPagoLines" :key="line.documentoId">
                  <td>{{ line.label }}</td>
                  <td class="num modal-pago-muted">{{ line.totalFmt }}</td>
                  <td class="num">
                    <input
                      v-model="line.monto"
                      type="text"
                      class="modal-pago-inp"
                      inputmode="decimal"
                      autocomplete="off"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="modalPagoError" class="modal-pago-err">{{ modalPagoError }}</p>
          <div class="modal-pago-actions">
            <button type="button" class="btn-ghost" :disabled="modalPagoSaving" @click="closeModalPagoCompras">
              Cancelar
            </button>
            <button type="button" class="btn-primary" :disabled="modalPagoSaving" @click="submitModalPagoCompras">
              {{ modalPagoSaving ? 'Guardando…' : 'Grabar pago(s)' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.cmp-page {
  width: 100%;
  max-width: 100%;
  color: #0f172a;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.toolbar-left {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.head-text .title {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
  font-weight: 700;
}

.head-text .lead {
  margin: 0;
  max-width: 44rem;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #64748b;
}

.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  width: fit-content;
  padding: 0.55rem 1.1rem;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #0d9488, #0f766e);
  color: #fff;
  font-weight: 700;
  font-size: 0.82rem;
  text-transform: none;
  letter-spacing: 0.02em;
  cursor: pointer;
  font: inherit;
  box-shadow: 0 4px 14px rgba(13, 148, 136, 0.35);
}

.btn-create:hover {
  filter: brightness(1.06);
}

.toolbar-actions-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.btn-tool-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.95rem;
  border-radius: 10px;
  border: 1px solid #0d9488;
  background: #fff;
  color: #0f766e;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  font: inherit;
}

.btn-tool-secondary:hover:not(:disabled) {
  background: #f0fdfa;
}

.btn-tool-secondary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-tool-ghost {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 0.85rem;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #475569;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  font: inherit;
}

.btn-tool-ghost:hover:not(:disabled) {
  border-color: #94a3b8;
  color: #334155;
}

.btn-tool-ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.import-notice {
  margin: 0 0 0.65rem;
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  font-size: 0.84rem;
  line-height: 1.45;
}

.import-notice--ok {
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  color: #166534;
}

.import-notice--warn {
  background: #fffbeb;
  border: 1px solid #fcd34d;
  color: #92400e;
}

.plus {
  font-size: 1.25rem;
  font-weight: 300;
  line-height: 1;
}

.icon-btn {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #475569;
  font-size: 1.1rem;
  cursor: pointer;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
  margin-bottom: 0.75rem;
  padding: 0.65rem 0.85rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.filter-grow {
  flex: 1 1 220px;
  min-width: 180px;
}

.filter-sm {
  flex: 0 0 160px;
}

.filter-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.filter-inp {
  padding: 0.4rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.85rem;
}

.filter-select {
  cursor: pointer;
}

.compras-pay-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1rem;
  margin-bottom: 0.65rem;
  padding: 0.65rem 0.85rem;
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  border-radius: 10px;
}

.compras-pay-panel__hint {
  margin: 0;
  flex: 1 1 220px;
  font-size: 0.8rem;
  line-height: 1.45;
  color: #334155;
}

.compras-pay-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.cmp-pay-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: none;
  color: #475569;
  border: 1px solid #cbd5e1;
  background: #fff;
  cursor: pointer;
  font-family: inherit;
}

.cmp-pay-pill:hover:not(:disabled) {
  border-color: #94a3b8;
  color: #0f172a;
}

.cmp-pay-pill:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cmp-pay-pill--accent {
  color: #0f766e;
  border-color: #5eead4;
  background: #ecfdf5;
}

.cmp-pay-pill--primary {
  color: #fff;
  background: linear-gradient(135deg, #0d9488, #0f766e);
  border-color: transparent;
}

.cmp-pay-pill--primary:hover {
  filter: brightness(1.06);
  color: #fff;
}

.selection-bar {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #0f766e;
}

.th-check,
.td-check {
  width: 2.35rem;
  text-align: center;
  vertical-align: middle;
}

.modal-pago-root {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgb(15 23 42 / 45%);
}

.modal-pago-card {
  width: 100%;
  max-width: 34rem;
  max-height: min(90vh, 640px);
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  padding: 1.2rem 1.3rem;
  box-shadow: 0 20px 50px rgb(15 23 42 / 25%);
}

.modal-pago-title {
  margin: 0 0 0.35rem;
  font-size: 1.1rem;
  font-weight: 800;
  color: #020617;
}

.modal-pago-lead {
  margin: 0 0 0.9rem;
  font-size: 0.8rem;
  line-height: 1.5;
  color: #475569;
}

.modal-pago-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.85rem;
}

.modal-pago-field__lab {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.modal-pago-field__sel {
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #94a3b8;
  font-size: 0.85rem;
}

.modal-pago-table-wrap {
  overflow-x: auto;
  margin-bottom: 0.65rem;
}

.modal-pago-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.modal-pago-table th,
.modal-pago-table td {
  padding: 0.4rem 0.45rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-pago-table th {
  text-align: left;
  font-weight: 700;
  color: #475569;
  font-size: 0.7rem;
  text-transform: uppercase;
}

.modal-pago-table th.num,
.modal-pago-table td.num {
  text-align: right;
}

.modal-pago-muted {
  color: #64748b;
}

.modal-pago-inp {
  width: 100%;
  max-width: 7.5rem;
  margin-left: auto;
  display: block;
  padding: 0.3rem 0.4rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.82rem;
}

.modal-pago-err {
  margin: 0 0 0.6rem;
  font-size: 0.8rem;
  color: #b91c1c;
}

.modal-pago-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.45rem;
}

.err-banner {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.85rem;
}

.table-head {
  margin-bottom: 0.5rem;
}

.total {
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
}

.table-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  min-height: 10rem;
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
  padding: 0.45rem 0.5rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: middle;
}

.data-table th {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
  font-weight: 700;
  background: #f8fafc;
}

.td-strong {
  font-weight: 600;
  color: #0f172a;
}

.cell-clip {
  max-width: 11rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.muted-sm {
  font-size: 0.78rem;
  color: #94a3b8;
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
  background: #d1fae5;
  color: #065f46;
}

.pill--muted {
  background: #f1f5f9;
  color: #64748b;
  text-transform: none;
  font-weight: 600;
}

.td-actions {
  white-space: normal;
  vertical-align: top;
}

.td-gestion {
  vertical-align: middle;
  width: 5.5rem;
}

.cmp-gestion-icons {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.cmp-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.1rem;
  height: 2.1rem;
  padding: 0;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
}

.cmp-icon-btn svg {
  width: 1.05rem;
  height: 1.05rem;
}

.cmp-icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cmp-icon-btn--edit {
  color: #0e7490;
  border-color: rgba(14, 116, 144, 0.35);
}

.cmp-icon-btn--edit:hover:not(:disabled) {
  background: rgba(14, 116, 144, 0.08);
}

.cmp-icon-btn--del {
  color: #b91c1c;
  border-color: rgba(185, 28, 28, 0.35);
}

.cmp-icon-btn--del:hover:not(:disabled) {
  background: rgba(185, 28, 28, 0.08);
}

.btn-row {
  display: inline-block;
  margin: 0 0.25rem 0.25rem 0;
  padding: 0.28rem 0.5rem;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
}

.btn-row--primary {
  background: #0d9488;
  border-color: #0d9488;
  color: #fff;
}

.btn-row--danger {
  background: #fff;
  border-color: #fecaca;
  color: #b91c1c;
}

.btn-row--cronograma {
  text-decoration: none;
  background: #ecfdf5;
  border-color: #5eead4;
  color: #115e59;
}

.btn-row--cronograma:hover {
  background: #d1fae5;
  border-color: #2dd4bf;
  color: #0f766e;
}

.state {
  padding: 1.5rem;
  text-align: center;
}

.state.empty {
  color: #94a3b8;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.65rem;
  border-top: 1px solid #e2e8f0;
}

.btn-page {
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  cursor: pointer;
  font-size: 0.8rem;
}

.btn-page:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 1.5rem 1rem;
  overflow-y: auto;
}

.modal-panel {
  width: 100%;
  max-width: 640px;
  margin: 0.5rem auto 2rem;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.2);
  padding: 1.15rem 1.25rem 1rem;
}

.modal-panel--sm {
  max-width: 400px;
}

.modal-title {
  margin: 0 0 0.35rem;
  font-size: 1.1rem;
  font-weight: 700;
}

.modal-lead {
  margin: 0 0 0.85rem;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #64748b;
}

.reabrir-checklist {
  margin: 0 0 0.85rem 1rem;
  padding: 0;
  font-size: 0.82rem;
  line-height: 1.5;
  color: #334155;
}

.reabrir-checklist li {
  margin-bottom: 0.35rem;
}

.reabrir-checklist li::marker {
  color: #0d9488;
}

.block {
  margin-bottom: 1rem;
}

.block--almacen {
  padding-top: 0.25rem;
  border-top: 1px dashed #e2e8f0;
}

.almacen-hint {
  margin: 0.45rem 0 0;
  font-size: 0.8rem;
  line-height: 1.45;
  color: #9a3412;
  background: #ffedd5;
  border: 1px solid #fdba74;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
}

.almacen-hint a {
  color: #c2410c;
  font-weight: 700;
  text-decoration: underline;
}

.block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.45rem;
}

.block-title {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 700;
}

.fld {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.55rem;
}

.fld > span {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
}

.inp {
  padding: 0.45rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.85rem;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

@media (max-width: 520px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}

.lineas-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.linea-row {
  display: grid;
  grid-template-columns: 1fr 4.5rem 5.5rem auto;
  gap: 0.35rem;
  align-items: center;
}

@media (max-width: 560px) {
  .linea-row {
    grid-template-columns: 1fr;
  }
}

.inp-item {
  min-width: 0;
}

.inp-qty,
.inp-price {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.btn-add-line {
  padding: 0.25rem 0.55rem;
  border-radius: 6px;
  border: 1px solid #99f6e4;
  background: #f0fdfa;
  color: #0f766e;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
}

.btn-icon-del {
  width: 2rem;
  height: 2rem;
  border-radius: 6px;
  border: 1px solid #fecaca;
  background: #fff;
  color: #b91c1c;
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
}

.fld.fld-check-igv {
  flex-direction: row;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.45rem;
  cursor: pointer;
  font-size: 0.82rem;
  color: #334155;
}

.fld.fld-check-igv input {
  width: 1rem;
  height: 1rem;
  accent-color: #0d9488;
}

.line-hint {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: #64748b;
}

.totals-preview {
  margin-top: 0.65rem;
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

.form-err {
  margin: 0 0 0.5rem;
  padding: 0.4rem 0.5rem;
  border-radius: 6px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.8rem;
}

.modal-foot {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.45rem;
  margin-top: 0.5rem;
  padding-top: 0.65rem;
  border-top: 1px solid #e2e8f0;
}

.btn-ghost {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
  font: inherit;
}

.btn-secondary {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #334155;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
  font: inherit;
}

.btn-primary {
  padding: 0.45rem 0.95rem;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #0d9488, #0f766e);
  color: #fff;
  font-weight: 700;
  font-size: 0.82rem;
  cursor: pointer;
  font: inherit;
}

.btn-ghost:disabled,
.btn-secondary:disabled,
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.prov-registro {
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  border: 1px dashed #99f6e4;
  background: #f8fffc;
}

.prov-registro__title {
  margin: 0 0 0.55rem;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #0f766e;
}

/* Misma cuadrícula que «Cliente receptor» en VentasDocumentosView (.cliente-doc-grid) */
.prov-doc-grid {
  display: grid;
  grid-template-columns: minmax(5.5rem, 7.5rem) 1fr;
  gap: 0.65rem 0.85rem;
  align-items: start;
  margin-bottom: 0.65rem;
}

.prov-doc-grid > .fld {
  margin-bottom: 0;
}

@media (max-width: 36rem) {
  .prov-doc-grid {
    grid-template-columns: 1fr;
  }
}

.fld-doc-combo {
  margin-bottom: 0;
  min-width: 0;
}

.doc-num-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.doc-num-input-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
}

.doc-num-input-wrap .inp {
  width: 100%;
  box-sizing: border-box;
}

/* Misma altura mínima que el botón de padrón en la fila */
.prov-doc-grid select.inp,
.doc-num-row .inp {
  min-height: 2.375rem;
  line-height: 1.25;
  box-sizing: border-box;
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
  z-index: 15;
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

/* Compacto, misma altura que .inp; texto corto + title/aria con la acción completa */
.btn-consult-padron {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  height: 2.375rem;
  min-height: 2.375rem;
  padding: 0 0.6rem;
  box-sizing: border-box;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #0c4a6e;
  font-weight: 600;
  font-size: 0.78rem;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  font: inherit;
  box-shadow: 0 1px 2px rgb(15 23 42 / 5%);
}

.btn-consult-padron__ico {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  opacity: 0.92;
}

.btn-consult-padron__text {
  letter-spacing: 0.02em;
}

.btn-consult-padron:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #38bdf8;
  color: #0369a1;
}

.btn-consult-padron:focus-visible {
  outline: none;
  border-color: #0ea5e9;
  box-shadow: 0 0 0 2px rgb(14 165 233 / 22%);
}

.btn-consult-padron:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
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

.btn-guardar-prov {
  margin-top: 0.25rem;
  padding: 0.42rem 0.85rem;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #0284c7, #0369a1);
  color: #fff;
  font-weight: 700;
  font-size: 0.78rem;
  cursor: pointer;
  font: inherit;
}

.btn-guardar-prov:hover:not(:disabled) {
  filter: brightness(1.05);
}

.btn-guardar-prov:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
