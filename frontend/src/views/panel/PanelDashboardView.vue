<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type PeriodResumen = '7d' | '30d' | '90d'
type PeriodEvo = '6m' | '9m' | '12m'
type DetallePeriod = 'm1' | 'm6' | 'm12'
type DetalleMoneda = 'PEN' | 'USD'

type PorTipo = {
  tipo: string
  etiqueta: string
  total_sin_igv: string
  comprobantes: number
  comprobantes_aceptados: number
}

type EvoMes = { periodo: string; pen: string; usd: string }
type TopProducto = {
  item_id: number
  nombre: string
  cantidad: string
  monto_sin_igv: string
}
type PorVendedor = {
  vendedor_id: number
  nombre: string
  total_sin_igv: string
  comprobantes: number
}

const ctx = useAppContextStore()
const periodResumen = ref<PeriodResumen>('30d')
const periodEvolucion = ref<PeriodEvo>('12m')
const detallePeriod = ref<DetallePeriod>('m6')
const detalleMoneda = ref<DetalleMoneda>('PEN')

const loading = ref(false)
const porTipo = ref<PorTipo[]>([])
const evolucionMensual = ref<EvoMes[]>([])
const topProductos = ref<TopProducto[]>([])
const porVendedor = ref<PorVendedor[]>([])
const error = ref('')

const CHART_TEAL = '#14b8a6'
const CHART_GRID = '#e2e8f0'
const LINE_PEN = '#22c55e'
const LINE_USD = '#3b82f6'

const DONUT_COLORS = ['#0ea5e9', '#14b8a6', '#6366f1', '#a78bfa', '#38bdf8']

const ETIQUETA_BARRA: Record<string, string> = {
  FACTURA: 'Factura',
  BOLETA: 'Boleta',
  NOTA_CREDITO_CLIENTE: 'N. crédito',
}

function fmtMoney(n: number, moneda: DetalleMoneda): string {
  if (moneda === 'USD') {
    return new Intl.NumberFormat('es-PE', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(n)
  }
  return `S/ ${new Intl.NumberFormat('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)}`
}

function fmtQty(s: string): string {
  const n = Number(s)
  if (Number.isNaN(n)) return s
  return new Intl.NumberFormat('es-PE', { maximumFractionDigits: 2 }).format(n)
}

const maxMontoBarras = computed(() => {
  let m = 0
  for (const p of porTipo.value) {
    const n = parseFloat(p.total_sin_igv)
    if (n > m) m = n
  }
  return m || 1
})

const maxAceptados = computed(() => {
  let m = 0
  for (const p of porTipo.value) {
    if (p.comprobantes_aceptados > m) m = p.comprobantes_aceptados
  }
  return m || 1
})

const maxEvo = computed(() => {
  let m = 0
  for (const p of evolucionMensual.value) {
    const a = parseFloat(p.pen)
    const b = parseFloat(p.usd)
    if (a > m) m = a
    if (b > m) m = b
  }
  return m || 1
})

const barChart = computed(() => {
  const W = 360
  const H = 200
  const padL = 36
  const padR = 12
  const padB = 36
  const padT = 12
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const n = porTipo.value.length || 1
  const gap = 0.22
  const bw = innerW / (n + (n + 1) * gap)
  const step = bw * (1 + gap)
  const x0 = padL + step * gap
  const bars = porTipo.value.map((row, i) => {
    const v = parseFloat(row.total_sin_igv)
    const h = innerH * (v / maxMontoBarras.value)
    const x = x0 + i * step
    const y = padT + innerH - h
    const label = ETIQUETA_BARRA[row.tipo] ?? row.etiqueta
    return { x, y, w: bw, h, label, raw: v }
  })
  const yTicks = 4
  const gridLines = Array.from({ length: yTicks + 1 }, (_, i) => {
    const y = padT + (innerH * i) / yTicks
    const val = maxMontoBarras.value * (1 - i / yTicks)
    return { y, label: val >= 1000 ? `${(val / 1000).toFixed(0)}k` : String(Math.round(val)) }
  })
  return { W, H, padL, padT, innerW, innerH, bars, gridLines, maxVal: maxMontoBarras.value }
})

const barChartDocs = computed(() => {
  const W = 360
  const H = 200
  const padL = 36
  const padR = 12
  const padB = 36
  const padT = 12
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const n = porTipo.value.length || 1
  const gap = 0.22
  const bw = innerW / (n + (n + 1) * gap)
  const step = bw * (1 + gap)
  const x0 = padL + step * gap
  const bars = porTipo.value.map((row, i) => {
    const v = row.comprobantes_aceptados
    const h = innerH * (v / maxAceptados.value)
    const x = x0 + i * step
    const y = padT + innerH - h
    const label = ETIQUETA_BARRA[row.tipo] ?? row.etiqueta
    return { x, y, w: bw, h, label, raw: v }
  })
  const yTicks = 4
  const gridLines = Array.from({ length: yTicks + 1 }, (_, i) => {
    const y = padT + (innerH * i) / yTicks
    const val = Math.round(maxAceptados.value * (1 - i / yTicks))
    return { y, label: String(val) }
  })
  return { W, H, padL, padT, innerW, innerH, bars, gridLines, maxVal: maxAceptados.value }
})

const lineChart = computed(() => {
  const pts = evolucionMensual.value
  const W = 720
  const H = 240
  const padL = 48
  const padR = 24
  const padB = 44
  const padT = 16
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const maxV = maxEvo.value
  const n = Math.max(pts.length, 1)
  const toX = (i: number) => padL + (innerW * i) / Math.max(n - 1, 1)
  const toY = (v: number) => padT + innerH - (innerH * v) / maxV

  const penPts = pts.map((p, i) => ({
    x: toX(i),
    y: toY(parseFloat(p.pen)),
  }))
  const usdPts = pts.map((p, i) => ({
    x: toX(i),
    y: toY(parseFloat(p.usd)),
  }))

  const linePen =
    penPts.length > 0
      ? penPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
      : ''
  const lineUsd =
    usdPts.length > 0
      ? usdPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
      : ''

  const yTicks = 5
  const gridLines = Array.from({ length: yTicks + 1 }, (_, i) => {
    const y = padT + (innerH * i) / yTicks
    const val = maxV * (1 - i / yTicks)
    const label = val >= 1_000_000 ? `${(val / 1_000_000).toFixed(1)}M` : val >= 1000 ? `${(val / 1000).toFixed(0)}k` : String(Math.round(val))
    return { y, label }
  })

  const xLabels = pts.map((p, i) => ({
    x: toX(i),
    text: p.periodo,
  }))

  return {
    W,
    H,
    padL,
    padT,
    innerW,
    innerH,
    linePen,
    lineUsd,
    penPts,
    usdPts,
    gridLines,
    xLabels,
  }
})

type DonutSeg = { path: string; color: string; midAngle: number; qty: number }
const donut = computed(() => {
  const rows = topProductos.value
  const cx = 110
  const cy = 110
  const R = 88
  const r = 52
  let total = 0
  for (const row of rows) {
    total += Math.max(0, Number(row.cantidad) || 0)
  }
  if (total <= 0 || rows.length === 0) {
    return { cx, cy, R, r, segments: [] as DonutSeg[], hasData: false }
  }
  let angle = -Math.PI / 2
  const segments: DonutSeg[] = []
  rows.forEach((row, idx) => {
    const qty = Math.max(0, Number(row.cantidad) || 0)
    const sweep = (qty / total) * Math.PI * 2
    const a0 = angle
    const a1 = angle + sweep
    const path = donutArc(cx, cy, R, r, a0, a1)
    const midAngle = (a0 + a1) / 2
    const color = DONUT_COLORS[idx % DONUT_COLORS.length] ?? '#0ea5e9'
    segments.push({ path, color, midAngle, qty })
    angle = a1
  })
  return { cx, cy, R, r, segments, hasData: true }
})

function donutArc(cx: number, cy: number, R: number, r: number, a0: number, a1: number): string {
  if (a1 - a0 < 0.0001) return ''
  const x0 = cx + R * Math.cos(a0)
  const y0 = cy + R * Math.sin(a0)
  const x1 = cx + R * Math.cos(a1)
  const y1 = cy + R * Math.sin(a1)
  const x2 = cx + r * Math.cos(a1)
  const y2 = cy + r * Math.sin(a1)
  const x3 = cx + r * Math.cos(a0)
  const y3 = cy + r * Math.sin(a0)
  const large = a1 - a0 > Math.PI ? 1 : 0
  return `M ${x0} ${y0} A ${R} ${R} 0 ${large} 1 ${x1} ${y1} L ${x2} ${y2} A ${r} ${r} 0 ${large} 0 ${x3} ${y3} Z`
}

const maxVendedor = computed(() => {
  let m = 0
  for (const v of porVendedor.value) {
    const n = parseFloat(v.total_sin_igv)
    if (n > m) m = n
  }
  return m || 1
})

async function load() {
  await ctx.ensureEmpresa()
  if (!ctx.empresaId) {
    error.value = 'Crea una empresa en el admin o API para ver el panel.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<{
      por_tipo: PorTipo[]
      evolucion_mensual: EvoMes[]
      top_productos: TopProducto[]
      por_vendedor: PorVendedor[]
    }>('/ventas/reportes/dashboard/', {
      params: {
        empresa: ctx.empresaId,
        period: periodResumen.value,
        evolucion: periodEvolucion.value,
        detalle: detallePeriod.value,
        detalle_moneda: detalleMoneda.value,
      },
    })
    porTipo.value = data.por_tipo ?? []
    evolucionMensual.value = data.evolucion_mensual ?? []
    topProductos.value = data.top_productos ?? []
    porVendedor.value = data.por_vendedor ?? []
  } catch (e) {
    error.value = listLoadErrorMessage(e, 'el resumen de ventas del panel')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([periodResumen, periodEvolucion, detallePeriod, detalleMoneda], load)
</script>

<template>
  <div class="page">
    <header class="top">
      <h1 class="page-title">
        <span class="page-title-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linejoin="round"
              d="M4 4.5h7v7H4v-7Zm9 0h7v4h-7v-4ZM4 13.5h7v6.5H4V13.5Zm9 3.5h7v3h-7v-3Z"
            />
          </svg>
        </span>
        Panel empresarial
      </h1>
      <p class="sub">
        Documentos <strong>emitidos</strong>, montos en subtotal <strong>sin IGV</strong>. Comprobantes
        aceptados: respuesta SUNAT con código <strong>0</strong> (Nubefact).
      </p>
    </header>

    <p v-if="loading" class="muted">Cargando…</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <div v-else class="stack">
      <div class="grid-2">
        <section class="card">
          <h2 class="card-heading card-heading--blue">Resumen de ventas (Sin IGV)</h2>
          <div class="chart-wrap">
            <svg
              class="chart-svg"
              :viewBox="`0 0 ${barChart.W} ${barChart.H}`"
              preserveAspectRatio="xMidYMid meet"
            >
              <line
                v-for="(g, i) in barChart.gridLines"
                :key="'g' + i"
                :x1="barChart.padL"
                :x2="barChart.W - 12"
                :y1="g.y"
                :y2="g.y"
                :stroke="CHART_GRID"
                stroke-width="1"
              />
              <text
                v-for="(g, i) in barChart.gridLines"
                :key="'t' + i"
                :x="4"
                :y="g.y + 4"
                class="axis-y"
              >
                {{ g.label }}
              </text>
              <rect
                v-for="(b, i) in barChart.bars"
                :key="'b' + i"
                :x="b.x"
                :y="b.y"
                :width="b.w"
                :height="Math.max(b.h, 0)"
                :fill="CHART_TEAL"
                rx="3"
              />
              <text
                v-for="(b, i) in barChart.bars"
                :key="'xl' + i"
                :x="b.x + b.w / 2"
                :y="barChart.H - 8"
                text-anchor="middle"
                class="axis-x"
              >
                {{ b.label }}
              </text>
            </svg>
            <div class="legend-row">
              <span class="legend-dot" :style="{ background: CHART_TEAL }" />
              <span class="legend-txt">Soles</span>
            </div>
          </div>
          <div class="card-actions">
            <button
              v-for="p in (['7d', '30d', '90d'] as const)"
              :key="'rs' + p"
              type="button"
              class="pill"
              :class="{ on: periodResumen === p }"
              @click="periodResumen = p"
            >
              {{ p === '7d' ? '1S' : p === '30d' ? '1M' : '3M' }}
            </button>
          </div>
        </section>

        <section class="card">
          <h2 class="card-heading card-heading--blue">Resumen de comprobantes</h2>
          <div class="chart-wrap">
            <svg
              class="chart-svg"
              :viewBox="`0 0 ${barChartDocs.W} ${barChartDocs.H}`"
              preserveAspectRatio="xMidYMid meet"
            >
              <line
                v-for="(g, i) in barChartDocs.gridLines"
                :key="'gd' + i"
                :x1="barChartDocs.padL"
                :x2="barChartDocs.W - 12"
                :y1="g.y"
                :y2="g.y"
                :stroke="CHART_GRID"
                stroke-width="1"
              />
              <text
                v-for="(g, i) in barChartDocs.gridLines"
                :key="'td' + i"
                :x="4"
                :y="g.y + 4"
                class="axis-y"
              >
                {{ g.label }}
              </text>
              <rect
                v-for="(b, i) in barChartDocs.bars"
                :key="'bd' + i"
                :x="b.x"
                :y="b.y"
                :width="b.w"
                :height="Math.max(b.h, 0)"
                :fill="CHART_TEAL"
                rx="3"
              />
              <text
                v-for="(b, i) in barChartDocs.bars"
                :key="'xld' + i"
                :x="b.x + b.w / 2"
                :y="barChartDocs.H - 8"
                text-anchor="middle"
                class="axis-x"
              >
                {{ b.label }}
              </text>
            </svg>
            <div class="legend-row">
              <span class="legend-dot" :style="{ background: CHART_TEAL }" />
              <span class="legend-txt">Aceptados</span>
            </div>
          </div>
          <div class="card-actions">
            <button
              v-for="p in (['7d', '30d', '90d'] as const)"
              :key="'rd' + p"
              type="button"
              class="pill"
              :class="{ on: periodResumen === p }"
              @click="periodResumen = p"
            >
              {{ p === '7d' ? '1S' : p === '30d' ? '1M' : '3M' }}
            </button>
          </div>
        </section>
      </div>

      <section class="card card--wide">
        <h2 class="card-heading card-heading--blue">Evolución de ventas (Sin IGV)</h2>
        <div class="chart-wrap chart-wrap--wide">
          <svg
            class="chart-svg"
            :viewBox="`0 0 ${lineChart.W} ${lineChart.H}`"
            preserveAspectRatio="xMidYMid meet"
          >
            <line
              v-for="(g, i) in lineChart.gridLines"
              :key="'gl' + i"
              :x1="lineChart.padL"
              :x2="lineChart.W - 12"
              :y1="g.y"
              :y2="g.y"
              :stroke="CHART_GRID"
              stroke-width="1"
            />
            <text
              v-for="(g, i) in lineChart.gridLines"
              :key="'gt' + i"
              :x="4"
              :y="g.y + 4"
              class="axis-y"
            >
              {{ g.label }}
            </text>
            <path
              v-if="lineChart.lineUsd"
              :d="lineChart.lineUsd"
              fill="none"
              :stroke="LINE_USD"
              stroke-width="2.5"
              stroke-linejoin="round"
              stroke-linecap="round"
            />
            <path
              v-if="lineChart.linePen"
              :d="lineChart.linePen"
              fill="none"
              :stroke="LINE_PEN"
              stroke-width="2.5"
              stroke-linejoin="round"
              stroke-linecap="round"
            />
            <circle
              v-for="(p, i) in lineChart.penPts"
              :key="'cp' + i"
              :cx="p.x"
              :cy="p.y"
              r="4"
              :fill="LINE_PEN"
            />
            <circle
              v-for="(p, i) in lineChart.usdPts"
              :key="'cu' + i"
              :cx="p.x"
              :cy="p.y"
              r="4"
              :fill="LINE_USD"
            />
            <text
              v-for="(xl, i) in lineChart.xLabels"
              :key="'xl2' + i"
              :x="xl.x"
              :y="lineChart.H - 10"
              text-anchor="middle"
              class="axis-x"
            >
              {{ xl.text }}
            </text>
          </svg>
          <div class="legend-row legend-row--end">
            <span class="legend-item"><span class="legend-dot" :style="{ background: LINE_USD }" /> Dólares</span>
            <span class="legend-item"><span class="legend-dot" :style="{ background: LINE_PEN }" /> Soles</span>
          </div>
        </div>
        <div class="card-actions">
          <button
            v-for="p in (['6m', '9m', '12m'] as const)"
            :key="'evo' + p"
            type="button"
            class="pill"
            :class="{ on: periodEvolucion === p }"
            @click="periodEvolucion = p"
          >
            {{ p === '6m' ? '6M' : p === '9m' ? '9M' : '12M' }}
          </button>
        </div>
      </section>

      <section class="card card--wide">
        <h2 class="card-heading card-heading--blue">Top 5 de Productos más vendidos (Sin IGV)</h2>
        <div class="split-donut">
          <div class="donut-side">
            <svg v-if="donut.hasData" class="donut-svg" viewBox="0 0 220 220">
              <g v-for="(seg, i) in donut.segments" :key="'s' + i">
                <path :d="seg.path" :fill="seg.color" stroke="#fff" stroke-width="1" />
                <text
                  v-if="seg.qty > 0"
                  :x="donut.cx + (donut.R + donut.r) / 2 * Math.cos(seg.midAngle)"
                  :y="donut.cy + (donut.R + donut.r) / 2 * Math.sin(seg.midAngle)"
                  text-anchor="middle"
                  dominant-baseline="middle"
                  class="donut-qty"
                >
                  {{ Math.round(seg.qty) }}
                </text>
              </g>
            </svg>
            <div v-else class="donut-empty muted">Sin datos en el periodo</div>
          </div>
          <div class="table-side">
            <table class="mini-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th class="num">Cantidad</th>
                  <th class="num">Monto</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in topProductos" :key="row.item_id">
                  <td>
                    <span class="swatch" :style="{ background: DONUT_COLORS[i % DONUT_COLORS.length] }" />
                    <span class="cell-name">{{ row.nombre }}</span>
                  </td>
                  <td class="num">{{ fmtQty(row.cantidad) }}</td>
                  <td class="num">{{ fmtMoney(Number(row.monto_sin_igv), detalleMoneda) }}</td>
                </tr>
                <tr v-if="topProductos.length === 0">
                  <td colspan="3" class="muted center">No hay líneas en el periodo</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card-actions card-actions--split">
          <div class="left-pills">
            <button
              type="button"
              class="pill"
              :class="{ on: detalleMoneda === 'PEN' }"
              @click="detalleMoneda = 'PEN'"
            >
              S/
            </button>
            <button
              type="button"
              class="pill"
              :class="{ on: detalleMoneda === 'USD' }"
              @click="detalleMoneda = 'USD'"
            >
              $
            </button>
          </div>
          <div class="right-pills">
            <button
              v-for="p in (['m1', 'm6', 'm12'] as const)"
              :key="'tp' + p"
              type="button"
              class="pill"
              :class="{ on: detallePeriod === p }"
              @click="detallePeriod = p"
            >
              {{ p === 'm1' ? 'M1' : p === 'm6' ? 'M6' : 'M12' }}
            </button>
          </div>
        </div>
      </section>

      <section class="card card--wide">
        <h2 class="card-heading card-heading--blue">Ventas por vendedor</h2>
        <div v-if="porVendedor.length === 0" class="empty-chart">
          <svg viewBox="0 0 24 24" fill="none" class="empty-ico" aria-hidden="true">
            <path
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              d="M4 19V5m0 14h16M8 17V9m4 8V7m4 10v-6"
            />
          </svg>
          <p class="muted">No hay datos para el gráfico</p>
        </div>
        <div v-else class="vend-bars">
          <div v-for="v in porVendedor" :key="v.vendedor_id" class="vend-row">
            <span class="vend-name" :title="v.nombre">{{ v.nombre }}</span>
            <div class="vend-bar-bg">
              <div
                class="vend-bar-fill"
                :style="{ width: `${(parseFloat(v.total_sin_igv) / maxVendedor) * 100}%` }"
              />
            </div>
            <span class="vend-val">{{ fmtMoney(Number(v.total_sin_igv), detalleMoneda) }}</span>
          </div>
        </div>
        <div class="card-actions card-actions--split">
          <div class="left-pills">
            <button
              type="button"
              class="pill"
              :class="{ on: detalleMoneda === 'PEN' }"
              @click="detalleMoneda = 'PEN'"
            >
              S/
            </button>
            <button
              type="button"
              class="pill"
              :class="{ on: detalleMoneda === 'USD' }"
              @click="detalleMoneda = 'USD'"
            >
              $
            </button>
          </div>
          <div class="right-pills">
            <button
              v-for="p in (['m1', 'm6', 'm12'] as const)"
              :key="'vv' + p"
              type="button"
              class="pill"
              :class="{ on: detallePeriod === p }"
              @click="detallePeriod = p"
            >
              {{ p === 'm1' ? 'M1' : p === 'm6' ? 'M6' : 'M12' }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: none;
}

.page-title {
  margin: 0 0 0.25rem;
  font-size: 1.35rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #0f172a;
}

.page-title-ico {
  display: flex;
  color: #0e7490;
}

.page-title-ico svg {
  width: 1.65rem;
  height: 1.65rem;
}

.sub {
  margin: 0 0 1rem;
  color: #64748b;
  font-size: 0.9rem;
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}

.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1rem 1.15rem 0.75rem;
  box-shadow: 0 1px 2px rgb(15 23 42 / 6%);
}

.card--wide {
  grid-column: 1 / -1;
}

.card-heading {
  margin: 0 0 0.65rem;
  font-size: 1rem;
  font-weight: 700;
}

.card-heading--blue {
  color: #1e3a5f;
}

.chart-wrap {
  width: 100%;
  min-height: 200px;
}

.chart-wrap--wide {
  min-height: 260px;
  overflow-x: auto;
}

.chart-svg {
  width: 100%;
  height: auto;
  display: block;
}

.axis-y {
  font-size: 10px;
  fill: #94a3b8;
}

.axis-x {
  font-size: 10px;
  fill: #64748b;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.35rem;
  font-size: 0.8rem;
  color: #475569;
}

.legend-row--end {
  justify-content: flex-end;
  gap: 1rem;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.legend-txt {
  font-weight: 600;
}

.card-actions {
  display: flex;
  justify-content: flex-start;
  gap: 0.4rem;
  padding: 0.65rem 0 0.15rem;
  flex-wrap: wrap;
}

.card-actions--split {
  justify-content: space-between;
  align-items: center;
}

.left-pills,
.right-pills {
  display: flex;
  gap: 0.4rem;
}

.pill {
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border-radius: 50%;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.pill.on {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.split-donut {
  display: grid;
  grid-template-columns: minmax(200px, 260px) 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 768px) {
  .split-donut {
    grid-template-columns: 1fr;
  }
}

.donut-svg {
  width: 100%;
  max-width: 220px;
  height: auto;
  display: block;
  margin: 0 auto;
}

.donut-qty {
  font-size: 11px;
  font-weight: 700;
  fill: #fff;
  text-shadow: 0 0 2px rgb(0 0 0 / 45%);
}

.donut-empty {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 0.9rem;
}

.mini-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.mini-table th,
.mini-table td {
  padding: 0.45rem 0.35rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

.mini-table th {
  color: #64748b;
  font-weight: 600;
}

.mini-table .num {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
  margin-right: 0.35rem;
  vertical-align: middle;
  flex-shrink: 0;
}

.cell-name {
  vertical-align: middle;
}

.center {
  text-align: center;
}

.empty-chart {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 160px;
  color: #94a3b8;
}

.empty-ico {
  width: 48px;
  height: 48px;
}

.vend-bars {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.25rem 0 0.5rem;
}

.vend-row {
  display: grid;
  grid-template-columns: minmax(0, 10rem) 1fr 6.5rem;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.8rem;
}

.vend-name {
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vend-bar-bg {
  height: 10px;
  background: #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}

.vend-bar-fill {
  height: 100%;
  background: #14b8a6;
  border-radius: 6px;
  min-width: 2px;
}

.vend-val {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
  font-weight: 600;
}

.muted {
  color: #94a3b8;
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
</style>
