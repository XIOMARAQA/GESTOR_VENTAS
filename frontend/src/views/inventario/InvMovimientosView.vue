<script setup lang="ts">
import type { AxiosResponse } from 'axios'
import ExcelJS from 'exceljs'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type MovLinea = {
  id?: number
  item?: number
  cantidad?: string | number
}

type MovRow = {
  id: number
  tipo?: string
  creado_en?: string
  referencia_tipo?: string
  tipo_comprobante?: string
  almacen_nombre?: string
  producto_nombre?: string
  comprobante_serie?: string
  comprobante_numero?: string
  glosa?: string
  lineas?: MovLinea[]
}

type MovPaginated = { results?: MovRow[]; next?: string | null; count?: number }

type KardexRow = {
  linea_id?: number | null
  movimiento_id?: number | null
  tipo?: string
  creado_en?: string
  referencia_tipo?: string
  tipo_comprobante?: string
  almacen_nombre?: string
  glosa?: string
  item_id?: number
  item_codigo?: string
  item_nombre?: string
  comprobante_serie?: string
  comprobante_numero?: string
  entradas?: string | number
  salidas?: string | number
  saldo?: string | number
}

type KardexPayload = {
  count: number
  truncado: boolean
  results: KardexRow[]
  item: { id: number; codigo: string; nombre: string } | null
  almacen: { id: number; nombre: string } | null
  /** YYYY-MM si se filtró por mes; null = todo el historial en el almacén */
  mes: string | null
  saldo_inicial?: string | number
  /** Saldo al fin del período listado (cierre); con filtro mensual = apertura del siguiente mes */
  saldo_cierre?: string | number
}

type AlmOpt = { id: number; nombre: string }
type ItemOpt = { id: number; codigo?: string; nombre: string }

const REF_TIPO_LABELS: Record<string, string> = {
  DOCUMENTO_VENTA: 'Documento de venta',
  DOCUMENTO_COMPRA: 'Documento de compra',
}

const TIPO_MOV_LABELS: Record<string, string> = {
  INGRESO: 'Ingreso',
  SALIDA: 'Salida',
  AJUSTE: 'Ajuste',
  TRANSFERENCIA: 'Transferencia',
  SALDO_INICIAL: 'Saldo inicial',
}

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const rows = ref<MovRow[]>([])
const kardex = ref<KardexPayload | null>(null)
const almacenes = ref<AlmOpt[]>([])
const items = ref<ItemOpt[]>([])
const filtroAlmacenId = ref<number | ''>('')
const filtroProductoId = ref<number | ''>('')
const productoBusqueda = ref('')
const productoSuggestOpen = ref(false)
let productoSuggestCloseTimer: ReturnType<typeof setTimeout> | null = null
/** YYYY-MM (input type="month"); vacío = todo el historial */
const filtroMes = ref('')
const loading = ref(true)
const exporting = ref(false)
const err = ref('')
const page = ref(1)
const totalCount = ref(0)
const hasNext = ref(false)
const hasPrev = ref(false)

const bloqueadoSinEmpresa = computed(() => isSuperuser.value && !empresaId.value)

/** Kardex: producto + almacén; tabla con fila de apertura y orden cronológico ascendente. */
const kardexListo = computed(
  () =>
    filtroProductoId.value !== '' &&
    filtroAlmacenId.value !== '' &&
    !bloqueadoSinEmpresa.value,
)

/** Suma de entradas/salidas del kardex y saldo de la última fila (para pie de tabla). */
const kardexTotales = computed(() => {
  const rows = kardex.value?.results
  if (!rows?.length) return null
  const { entradas, salidas } = kardexSumEntradasSalidas(rows)
  const last = rows[rows.length - 1]
  return { entradas, salidas, saldoFinal: last?.saldo }
})

function appendKardexQueryParams(params: URLSearchParams) {
  appendEmpresaParams(params)
  params.set('item', String(filtroProductoId.value))
  params.set('almacen', String(filtroAlmacenId.value))
  const m = filtroMes.value.trim()
  if (m) params.set('mes', m)
}

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
  if (t === 'SALDO_INICIAL') return 'tipo-mov tipo-mov--apertura'
  if (t === 'SALIDA') return 'tipo-mov tipo-mov--salida'
  if (t === 'INGRESO') return 'tipo-mov tipo-mov--ingreso'
  return 'tipo-mov'
}

function formatQty(v: unknown): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return n.toLocaleString('es-PE', { minimumFractionDigits: 0, maximumFractionDigits: 4 })
}

function kardexSumEntradasSalidas(results: KardexRow[]): { entradas: number; salidas: number } {
  let entradas = 0
  let salidas = 0
  for (const r of results) {
    const e = Number(r.entradas)
    const s = Number(r.salidas)
    if (Number.isFinite(e)) entradas += e
    if (Number.isFinite(s)) salidas += s
  }
  return { entradas, salidas }
}

/** Suma de cantidades en las líneas del movimiento (API ya envía `lineas`). */
function sumLineasCantidad(r: MovRow): number {
  const lis = r.lineas
  if (!Array.isArray(lis) || !lis.length) return 0
  let s = 0
  for (const ln of lis) {
    const n = Number(ln.cantidad)
    if (Number.isFinite(n)) s += n
  }
  return s
}

/** Vista general: totales del comprobante según tipo (todos los ítems del movimiento). */
function movEntradasTotales(r: MovRow): string {
  if (r.tipo === 'INGRESO') return formatQty(sumLineasCantidad(r))
  return formatQty(0)
}

function movSalidasTotales(r: MovRow): string {
  if (r.tipo === 'SALIDA') return formatQty(sumLineasCantidad(r))
  return formatQty(0)
}

function textoOGuion(v: unknown): string {
  if (v == null) return '—'
  const t = String(v).trim()
  return t ? t : '—'
}

function movNombreProducto(r: MovRow): string {
  const api = (r.producto_nombre || '').trim()
  if (api) return api
  return '—'
}

/** YYYY-MM del mes natural siguiente (para texto de corte contable). */
function etiquetaMesSiguiente(mes: string): string {
  const parts = mes.trim().split('-')
  if (parts.length !== 2) return ''
  const y = Number(parts[0])
  const m = Number(parts[1])
  if (!Number.isFinite(y) || !Number.isFinite(m) || m < 1 || m > 12) return ''
  const d = new Date(y, m - 1, 1)
  d.setMonth(d.getMonth() + 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function itemLabel(it: ItemOpt): string {
  const c = (it.codigo || '').trim()
  return c ? `${c} — ${it.nombre}` : it.nombre
}

const MAX_PRODUCTO_SUGGEST = 40

const itemsMatches = computed(() => {
  const q = productoBusqueda.value.trim().toLowerCase()
  const pool = !q
    ? items.value
    : items.value.filter((it) => {
        const label = itemLabel(it).toLowerCase()
        const codigo = (it.codigo || '').trim().toLowerCase()
        const nombre = it.nombre.trim().toLowerCase()
        return label.includes(q) || codigo.includes(q) || nombre.includes(q)
      })
  return pool.slice(0, MAX_PRODUCTO_SUGGEST)
})

function syncProductoBusquedaFromId() {
  if (filtroProductoId.value === '') {
    productoBusqueda.value = ''
    return
  }
  const it = items.value.find((i) => i.id === filtroProductoId.value)
  if (it) productoBusqueda.value = itemLabel(it)
}

function onProductoFocusIn() {
  if (productoSuggestCloseTimer) {
    clearTimeout(productoSuggestCloseTimer)
    productoSuggestCloseTimer = null
  }
  productoSuggestOpen.value = true
}

function onProductoFocusOut() {
  productoSuggestCloseTimer = setTimeout(() => {
    productoSuggestOpen.value = false
    productoSuggestCloseTimer = null
    syncProductoFromBusqueda()
  }, 220)
}

function syncProductoFromBusqueda() {
  const q = productoBusqueda.value.trim()
  if (!q) {
    filtroProductoId.value = ''
    return
  }
  if (filtroProductoId.value !== '') {
    const current = items.value.find((i) => i.id === filtroProductoId.value)
    if (current && itemLabel(current) === q) return
  }
  const exact = items.value.find((it) => itemLabel(it).toLowerCase() === q.toLowerCase())
  if (exact) {
    filtroProductoId.value = exact.id
    productoBusqueda.value = itemLabel(exact)
    return
  }
  filtroProductoId.value = ''
}

function onProductoInput() {
  productoSuggestOpen.value = true
  const q = productoBusqueda.value.trim()
  if (!q) {
    filtroProductoId.value = ''
    return
  }
  if (filtroProductoId.value !== '') {
    const current = items.value.find((i) => i.id === filtroProductoId.value)
    if (current && itemLabel(current) !== productoBusqueda.value) {
      filtroProductoId.value = ''
    }
  }
}

function pickProducto(it: ItemOpt) {
  filtroProductoId.value = it.id
  productoBusqueda.value = itemLabel(it)
  productoSuggestOpen.value = false
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
    if (kardexListo.value) {
      const params = new URLSearchParams()
      appendKardexQueryParams(params)
      const { data } = await api.get<KardexPayload>(`/inventario/movimientos/kardex/?${params}`)
      kardex.value = data
      rows.value = []
      totalCount.value = data.count
      hasNext.value = false
      hasPrev.value = false
      return
    }

    kardex.value = null
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
    kardex.value = null
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

function limpiarFiltrosKardex() {
  filtroAlmacenId.value = ''
  filtroProductoId.value = ''
  productoBusqueda.value = ''
  filtroMes.value = ''
  page.value = 1
  void load()
}

watch(empresaId, async () => {
  page.value = 1
  filtroProductoId.value = ''
  productoBusqueda.value = ''
  filtroMes.value = ''
  await Promise.all([loadAlmacenes(), loadItems()])
  void load()
})

watch(items, () => syncProductoBusquedaFromId())

watch([filtroAlmacenId, filtroProductoId, filtroMes], () => {
  page.value = 1
  void load()
})

onMounted(async () => {
  await ctx.ensureEmpresa()
  await Promise.all([loadAlmacenes(), loadItems()])
  void load()
})

function cellDisplayLength(value: ExcelJS.CellValue): number {
  if (value === null || value === undefined) return 0
  if (typeof value === 'string') return value.length
  if (typeof value === 'number') return String(value).length
  if (typeof value === 'boolean') return value ? 4 : 5
  if (value instanceof Date) return 22
  if (typeof value === 'object' && value !== null) {
    const o = value as unknown as Record<string, unknown>
    if (Array.isArray(o.richText)) {
      return (o.richText as { text?: string }[]).reduce(
        (acc: number, r: { text?: string }) => acc + (r.text?.length ?? 0),
        0,
      )
    }
    if (o.result != null) return String(o.result).length
    if (typeof o.text === 'string') return o.text.length
  }
  return 0
}

function autofitColumns(ws: ExcelJS.Worksheet, headers: string[]) {
  const n = headers.length
  for (let c = 1; c <= n; c++) {
    const h = headers[c - 1] ?? ''
    let max = h.length + 1
    ws.getColumn(c).eachCell({ includeEmpty: true }, (cell) => {
      max = Math.max(max, cellDisplayLength(cell.value))
    })
    ws.getColumn(c).width = Math.min(56, Math.max(10, max + 1.5))
  }
}

/** Exportación real a Excel: encabezado con estilo y anchos según contenido. */
async function workbookBlobStyled(
  sheetName: string,
  headers: string[],
  rows: (string | number)[][],
  options?: { footerRow?: (string | number)[] },
): Promise<Blob> {
  const wb = new ExcelJS.Workbook()
  wb.created = new Date()
  const name = sheetName.slice(0, 31)
  const ws = wb.addWorksheet(name, {
    views: [{ state: 'frozen', ySplit: 1 }],
  })

  const grid = {
    top: { style: 'thin' as const, color: { argb: 'FF64748B' } },
    left: { style: 'thin' as const, color: { argb: 'FF64748B' } },
    bottom: { style: 'thin' as const, color: { argb: 'FF64748B' } },
    right: { style: 'thin' as const, color: { argb: 'FF64748B' } },
  }
  const hair = {
    top: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
    left: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
    bottom: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
    right: { style: 'hair' as const, color: { argb: 'FFE2E8F0' } },
  }

  const headerRow = ws.addRow(headers)
  headerRow.height = 26
  headerRow.eachCell((cell) => {
    cell.font = { bold: true, size: 11, color: { argb: 'FFFFFFFF' } }
    cell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF1E3A5F' },
    }
    cell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true }
    cell.border = grid
  })

  const firstNumericCol = Math.max(1, headers.length - 2)
  for (const r of rows) {
    const row = ws.addRow(r)
    row.eachCell((cell, colNumber) => {
      cell.border = hair
      cell.alignment =
        colNumber >= firstNumericCol
          ? { vertical: 'middle', horizontal: 'right' }
          : { vertical: 'middle', horizontal: 'left', wrapText: true }
    })
  }

  const foot = options?.footerRow
  if (foot?.length) {
    const footerExcelRow = ws.addRow(foot)
    const r = footerExcelRow.number
    footerExcelRow.height = 24

    const footFill = {
      type: 'pattern' as const,
      pattern: 'solid' as const,
      fgColor: { argb: 'FFE8EEF4' },
    }
    const footBorderBase = {
      left: { style: 'thin' as const, color: { argb: 'FF94A3B8' } },
      bottom: { style: 'thin' as const, color: { argb: 'FF94A3B8' } },
      right: { style: 'thin' as const, color: { argb: 'FF94A3B8' } },
    }
    const footTop = {
      top: { style: 'medium' as const, color: { argb: 'FF64748B' } },
      ...footBorderBase,
    }

    const n = foot.length
    for (let c = 1; c <= n; c++) {
      const cell = ws.getCell(r, c)
      const raw = foot[c - 1]
      cell.value = raw === '' ? null : raw

      const cellVal = foot[c - 1]
      const isTotalesLabel = typeof cellVal === 'string' && cellVal.trim() === 'Totales'
      const isLastThree = c >= n - 2

      if (c <= 7) {
        cell.border = hair
        cell.font = { size: 11, color: { argb: 'FF0F172A' } }
        cell.alignment = { vertical: 'middle', horizontal: 'left' }
        continue
      }

      cell.fill = footFill
      cell.border = footTop

      if (isLastThree) {
        let numColor = 'FF0F172A'
        if (c === n - 2) numColor = 'FF15803d'
        else if (c === n - 1) numColor = 'FFb91c1c'
        cell.font = { bold: true, size: 11, color: { argb: numColor } }
        cell.alignment = { vertical: 'middle', horizontal: 'right' }
        if (typeof cell.value === 'number' && Number.isFinite(cell.value)) {
          const v = cell.value
          const hasFrac = Math.abs(v % 1) > 1e-9
          cell.numFmt = hasFrac ? '#,##0.####' : '#,##0'
        }
      } else if (isTotalesLabel) {
        cell.font = { bold: true, size: 11, color: { argb: 'FF1E293B' } }
        cell.alignment = { vertical: 'middle', horizontal: 'right', wrapText: false }
      }
    }
  }

  autofitColumns(ws, headers)

  const buf = await wb.xlsx.writeBuffer()
  return new Blob([buf], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
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
    const d = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

    if (kardexListo.value) {
      const params = new URLSearchParams()
      appendKardexQueryParams(params)
      const { data } = await api.get<KardexPayload>(`/inventario/movimientos/kardex/?${params}`)
      const headers = [
        'Almacén',
        'Nombre producto',
        'Tipo',
        'Fecha',
        'Origen',
        'Tipo comprobante',
        'Serie',
        'Número',
        'Entradas',
        'Salidas',
        'Saldo',
      ]
      const body: (string | number)[][] = []
      for (const r of data.results) {
        const fechaIso = r.creado_en ? formatFechaHora(r.creado_en) : ''
        body.push([
          (r.almacen_nombre || '').trim() || '—',
          (r.item_nombre || '').trim() || '—',
          labelTipoMov(r.tipo),
          fechaIso,
          labelRefTipo(r.referencia_tipo),
          (r.tipo_comprobante || '').trim() || '—',
          textoOGuion(r.comprobante_serie),
          textoOGuion(r.comprobante_numero),
          formatQty(r.entradas),
          formatQty(r.salidas),
          formatQty(r.saldo),
        ])
      }
      let footerRow: (string | number)[] | undefined
      if (data.results.length) {
        const { entradas: sumEnt, salidas: sumSal } = kardexSumEntradasSalidas(data.results)
        const last = data.results[data.results.length - 1]
        const saldoFin = Number(last?.saldo)
        footerRow = [
          '',
          '',
          '',
          '',
          '',
          '',
          '',
          'Totales',
          sumEnt,
          sumSal,
          Number.isFinite(saldoFin) ? saldoFin : '',
        ]
      }
      const blob = await workbookBlobStyled('Kardex', headers, body, footerRow ? { footerRow } : undefined)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `kardex_${stamp}.xlsx`
      a.click()
      URL.revokeObjectURL(a.href)
      return
    }

    const dataRows = await fetchAllMovimientosForExport()
    const headers = [
      'Almacén',
      'Nombre producto',
      'Tipo',
      'Fecha',
      'Origen ref.',
      'Tipo comprobante',
      'Serie',
      'Número',
      'Entradas (total mov.)',
      'Salidas (total mov.)',
      'Saldo (ver kardex con filtros)',
    ]
    const body: (string | number)[][] = []
    for (const r of dataRows) {
      const fechaIso = r.creado_en ? formatFechaHora(r.creado_en) : ''
      body.push([
        (r.almacen_nombre || '').trim() || '—',
        movNombreProducto(r),
        labelTipoMov(r.tipo),
        fechaIso,
        labelRefTipo(r.referencia_tipo),
        (r.tipo_comprobante || '').trim() || '—',
        textoOGuion(r.comprobante_serie),
        textoOGuion(r.comprobante_numero),
        movEntradasTotales(r),
        movSalidasTotales(r),
        '',
      ])
    }
    const blob = await workbookBlobStyled('Movimientos inventario', headers, body)
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `movimientos_inventario_${stamp}.xlsx`
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
          Vista general: <strong>Entradas</strong> y <strong>Salidas</strong> por comprobante. Para el
          <strong>kardex</strong> elija <strong>almacén</strong> y <strong>producto</strong>: primera fila
          <strong>saldo inicial</strong>, luego movimientos del más antiguo al más reciente y <strong>saldo</strong> en
          cada línea. Opcional: filtro <strong>mes</strong> para corte mensual.
        </p>
      </div>
      <div class="head-actions">
        <button
          type="button"
          class="btn-excel"
          :disabled="loading || exporting || bloqueadoSinEmpresa"
          title="Descargar listado en Excel (.xlsx)"
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

    <div class="filters">
      <label class="f">
        <span class="flab">Almacén (para saldo por ítem)</span>
        <select
          v-model="filtroAlmacenId"
          class="inp inp--select"
          :disabled="bloqueadoSinEmpresa"
          :title="bloqueadoSinEmpresa ? 'Seleccione empresa en la barra superior' : ''"
        >
          <option value="">Elija almacén…</option>
          <option v-for="a in almacenes" :key="a.id" :value="a.id">{{ a.nombre }}</option>
        </select>
      </label>
      <label class="f f--producto">
        <span class="flab">Producto (para saldo por ítem)</span>
        <div
          class="producto-combo"
          @focusin="onProductoFocusIn"
          @focusout="onProductoFocusOut"
        >
          <input
            v-model="productoBusqueda"
            type="text"
            class="inp inp--producto"
            placeholder="Escriba código o nombre…"
            autocomplete="off"
            :disabled="bloqueadoSinEmpresa"
            :title="
              bloqueadoSinEmpresa
                ? 'Seleccione empresa en la barra superior'
                : 'Busque por código o nombre y elija de la lista'
            "
            @input="onProductoInput"
          />
          <ul
            v-if="productoSuggestOpen && itemsMatches.length && !bloqueadoSinEmpresa"
            class="producto-suggest"
            role="listbox"
            aria-label="Productos que coinciden"
          >
            <li
              v-for="it in itemsMatches"
              :key="it.id"
              role="option"
              class="producto-suggest__item"
              @mousedown.prevent="pickProducto(it)"
            >
              <span v-if="(it.codigo || '').trim()" class="producto-suggest__cod">{{ (it.codigo || '').trim() }}</span>
              <span class="producto-suggest__nom">{{ it.nombre }}</span>
            </li>
          </ul>
        </div>
      </label>
      <label class="f">
        <span class="flab">Mes (opcional)</span>
        <input
          v-model="filtroMes"
          type="month"
          class="inp inp--month"
          :disabled="bloqueadoSinEmpresa"
          title="Vacío = todo el historial en el almacén elegido"
        />
      </label>
      <div class="filters-end">
        <button
          type="button"
          class="btn-clear"
          :disabled="
            loading || exporting || (filtroAlmacenId === '' && filtroProductoId === '' && filtroMes === '')
          "
          @click="limpiarFiltrosKardex"
        >
          Quitar kardex
        </button>
      </div>
    </div>

    <p v-if="!bloqueadoSinEmpresa && (filtroAlmacenId === '' || filtroProductoId === '')" class="hint">
      Elija <strong>almacén</strong> y <strong>producto</strong> para el kardex: primera fila de <strong>saldo inicial</strong>,
      luego movimientos por fecha ascendente con <strong>saldo</strong> acumulado. Use <strong>Mes</strong> para acotar al
      corte mensual.
    </p>
    <p v-if="kardex?.truncado" class="warn warn--mb">
      El historial supera el límite de visualización. Use el filtro por <strong>mes</strong> o exporte por partes.
    </p>
    <div v-if="kardexListo && kardex?.item && kardex?.almacen" class="kardex-banner">
      <span class="kardex-banner__label">Kardex</span>
      <span class="kardex-banner__text">
        <strong>{{ (kardex.item.codigo || '').trim() || '—' }}</strong>
        — {{ kardex.item.nombre || '—' }}
        <span class="kardex-banner__sep">·</span>
        {{ kardex.almacen.nombre || '—' }}
        <template v-if="kardex.mes">
          <span class="kardex-banner__sep">·</span>
          Mes {{ kardex.mes }}
        </template>
      </span>
    </div>
    <div v-if="kardexListo && kardex" class="kardex-corte">
      <template v-if="kardex.mes">
        <p class="kardex-corte__title">Corte mensual ({{ kardex.mes }})</p>
        <p class="kardex-corte__line">
          <span class="kardex-corte__lab">Saldo inicial del mes</span> (reproducido en la primera fila de la tabla; cierre
          del mes anterior):
          <strong>{{ formatQty(kardex.saldo_inicial) }}</strong>
        </p>
        <p class="kardex-corte__line">
          <span class="kardex-corte__lab">Saldo cierre / apertura siguiente mes</span>
          ({{ etiquetaMesSiguiente(kardex.mes) }}):
          <strong>{{ formatQty(kardex.saldo_cierre) }}</strong>
        </p>
        <p class="kardex-corte__hint">
          Contablemente, el valor de cierre debe coincidir con el <strong>saldo inicial</strong> del kardex del mes
          siguiente al filtrar el mismo producto y almacén.
        </p>
      </template>
      <template v-else>
        <p class="kardex-corte__title">Saldos del período mostrado</p>
        <p class="kardex-corte__line">
          <span class="kardex-corte__lab">Saldo inicial</span> (primera fila del cuadro; antes del movimiento más antiguo
          listado):
          <strong>{{ formatQty(kardex.saldo_inicial) }}</strong>
        </p>
        <p class="kardex-corte__line">
          <span class="kardex-corte__lab">Saldo cierre</span> (tras el último movimiento cronológico mostrado):
          <strong>{{ formatQty(kardex.saldo_cierre) }}</strong>
        </p>
        <p class="kardex-corte__hint">
          Para cierres mensuales estrictos, use el filtro <strong>Mes</strong>; así el cierre queda alineado al
          calendario.
        </p>
      </template>
      <p v-if="kardex.truncado" class="kardex-corte__warn">
        Listado truncado: los saldos de cierre pueden no reflejar el mes o el historial completo.
      </p>
    </div>

    <div class="meta-row">
      <span class="count">
        <template v-if="kardexListo && kardex">{{ kardex.count }} fila(s) (incluye saldo inicial)</template>
        <template v-else>{{ totalCount }} movimiento(s)</template>
      </span>
    </div>

    <div class="card">
      <div v-if="loading" class="muted">Cargando…</div>
      <div v-else class="table-wrap">
        <template v-if="kardexListo">
          <table v-if="kardex" class="t">
            <thead>
              <tr>
                <th>Almacén</th>
                <th>Nombre del producto</th>
                <th>Tipo</th>
                <th>Fecha</th>
                <th>Origen</th>
                <th>Tipo de comprobante</th>
                <th>Serie</th>
                <th>Número</th>
                <th>Entradas</th>
                <th>Salidas</th>
                <th>Saldo</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, idx) in kardex.results" :key="r.linea_id != null ? r.linea_id : `ap-${idx}`">
                <td>{{ (r.almacen_nombre || '').trim() || '—' }}</td>
                <td class="td-product">{{ (r.item_nombre || '').trim() || '—' }}</td>
                <td>
                  <span :class="tipoMovClass(r.tipo)">{{ labelTipoMov(r.tipo) }}</span>
                </td>
                <td class="td-fecha">{{ formatFechaHora(r.creado_en) }}</td>
                <td>{{ labelRefTipo(r.referencia_tipo) }}</td>
                <td>{{ (r.tipo_comprobante || '').trim() || '—' }}</td>
                <td class="td-mono">{{ textoOGuion(r.comprobante_serie) }}</td>
                <td class="td-mono">{{ textoOGuion(r.comprobante_numero) }}</td>
                <td class="td-num td-num--in">{{ formatQty(r.entradas) }}</td>
                <td class="td-num td-num--out">{{ formatQty(r.salidas) }}</td>
                <td class="td-num td-num--bal">{{ formatQty(r.saldo) }}</td>
              </tr>
              <tr v-if="kardexTotales" class="tr-kardex-totales">
                <td class="td-kardex-totales-empty" />
                <td class="td-kardex-totales-empty" />
                <td class="td-kardex-totales-empty" />
                <td class="td-kardex-totales-empty" />
                <td class="td-kardex-totales-empty" />
                <td class="td-kardex-totales-empty" />
                <td class="td-kardex-totales-empty" />
                <td class="td-kardex-totales-label">Totales</td>
                <td class="td-num td-num--in td-kardex-totales-num">{{ formatQty(kardexTotales.entradas) }}</td>
                <td class="td-num td-num--out td-kardex-totales-num">{{ formatQty(kardexTotales.salidas) }}</td>
                <td class="td-num td-num--bal td-kardex-totales-num">{{ formatQty(kardexTotales.saldoFinal) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="kardex && kardex.results.length === 1" class="empty">
            No hay movimientos en el período; solo se muestra el saldo inicial.
          </p>
        </template>
        <template v-else>
          <table class="t">
            <thead>
              <tr>
                <th>Almacén</th>
                <th>Nombre del producto</th>
                <th>Tipo</th>
                <th>Fecha</th>
                <th>Origen</th>
                <th>Tipo de comprobante</th>
                <th>Serie</th>
                <th>Número</th>
                <th>Entradas</th>
                <th>Salidas</th>
                <th class="th-saldo" title="Saldo acumulado solo al filtrar un producto y un almacén arriba">
                  Saldo
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.id">
                <td>{{ (r.almacen_nombre || '').trim() || '—' }}</td>
                <td class="td-product">{{ movNombreProducto(r) }}</td>
                <td>
                  <span :class="tipoMovClass(r.tipo)">{{ labelTipoMov(r.tipo) }}</span>
                </td>
                <td class="td-fecha">{{ formatFechaHora(r.creado_en) }}</td>
                <td>{{ labelRefTipo(r.referencia_tipo) }}</td>
                <td>{{ (r.tipo_comprobante || '').trim() || '—' }}</td>
                <td class="td-mono">{{ textoOGuion(r.comprobante_serie) }}</td>
                <td class="td-mono">{{ textoOGuion(r.comprobante_numero) }}</td>
                <td class="td-num td-num--in">{{ movEntradasTotales(r) }}</td>
                <td class="td-num td-num--out">{{ movSalidasTotales(r) }}</td>
                <td class="td-num td-num--muted" title="Elija producto y almacén para ver el saldo acumulado por ítem">
                  —
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!rows.length" class="empty">No hay movimientos para mostrar en esta página.</p>
        </template>
      </div>
      <div v-if="!loading && !kardexListo && rows.length && (hasNext || hasPrev)" class="pager">
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
  max-width: 1320px;
  color: #0f172a;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 0.75rem;
  font-size: 0.8125rem;
  line-height: 1.45;
  font-family: inherit;
  color: #0f172a;
}

.f {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.flab {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #475569;
  letter-spacing: 0.01em;
}

.inp {
  padding: 0.45rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.8125rem;
  min-width: 10rem;
  color: #0f172a;
  background: #fff;
  font-family: inherit;
  line-height: 1.4;
}

.inp--select {
  min-width: 12rem;
  cursor: pointer;
}

.f--producto {
  min-width: 14rem;
  max-width: 22rem;
}

.inp--producto {
  width: 100%;
  min-width: 14rem;
  max-width: 22rem;
}

.producto-combo {
  position: relative;
  width: 100%;
}

.producto-suggest {
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
  max-height: 14rem;
  overflow-y: auto;
  z-index: 20;
}

.producto-suggest__item {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  padding: 0.45rem 0.6rem;
  cursor: pointer;
  font-size: 0.78rem;
  border-bottom: 1px solid #f1f5f9;
}

.producto-suggest__item:last-child {
  border-bottom: none;
}

.producto-suggest__item:hover {
  background: #e0f2fe;
}

.producto-suggest__cod {
  font-weight: 700;
  color: #0f172a;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
}

.producto-suggest__nom {
  color: #475569;
  line-height: 1.25;
}

.inp--month {
  min-width: 9.75rem;
  font-family: inherit;
}

.filters-end {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.5rem;
  margin-left: auto;
}

.btn-clear {
  padding: 0.45rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-weight: 600;
  font-size: 0.8125rem;
  cursor: pointer;
  font-family: inherit;
  color: #475569;
  line-height: 1.4;
}

.btn-clear:hover:not(:disabled) {
  border-color: #cbd5e1;
  color: #0f172a;
}

.btn-clear:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.hint {
  margin: 0 0 0.75rem;
  padding: 0.55rem 0.75rem;
  font-size: 0.82rem;
  line-height: 1.5;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.warn--mb {
  margin-bottom: 0.75rem;
}

.kardex-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: linear-gradient(180deg, #ecfeff, #f0fdfa);
  border: 1px solid #99f6e4;
  border-radius: 8px;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: #134e4a;
}

.kardex-banner__label {
  font-size: 0.65rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #0f766e;
}

.kardex-banner__text {
  font-weight: 500;
}

.kardex-banner__sep {
  opacity: 0.5;
  padding: 0 0.15rem;
}

.kardex-corte {
  margin: 0 0 0.75rem;
  padding: 0.65rem 0.85rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: #334155;
}

.kardex-corte__title {
  margin: 0 0 0.45rem;
  font-size: 0.8125rem;
  font-weight: 700;
  color: #0f172a;
}

.kardex-corte__line {
  margin: 0 0 0.35rem;
}

.kardex-corte__lab {
  font-weight: 600;
  color: #475569;
}

.kardex-corte__hint {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  color: #64748b;
}

.kardex-corte__warn {
  margin: 0.5rem 0 0;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #9a3412;
}

.td-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.td-num--in {
  color: #15803d;
  font-weight: 600;
}

.td-num--out {
  color: #b91c1c;
  font-weight: 600;
}

.td-num--bal {
  color: #0f172a;
  font-weight: 700;
}

.th-saldo {
  max-width: 5.5rem;
}

.td-num--muted {
  color: #94a3b8;
  font-weight: 500;
}

.tr-kardex-totales .td-kardex-totales-empty {
  padding: 0.5rem 0.35rem;
  background: transparent;
}

.tr-kardex-totales .td-kardex-totales-label,
.tr-kardex-totales .td-kardex-totales-num {
  background: #f8fafc;
  border-top: 2px solid #e2e8f0;
}

.tr-kardex-totales .td-kardex-totales-label {
  text-align: right;
  font-weight: 700;
  font-size: 0.8125rem;
  color: #334155;
  padding-right: 0.35rem;
}

.tr-kardex-totales .td-kardex-totales-num {
  font-weight: 800;
}

.td-product {
  max-width: 14rem;
  font-weight: 600;
  color: #334155;
  font-size: 0.8rem;
  line-height: 1.35;
}

.td-mono {
  font-family: ui-monospace, monospace;
  font-size: 0.78rem;
  color: #475569;
  white-space: nowrap;
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
  font-size: 0.8125rem;
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

.tipo-mov--apertura {
  color: #475569;
}

.td-fecha {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: #334155;
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
