<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type Period = '7d' | '30d' | '90d'

type PorTipo = {
  tipo: string
  etiqueta: string
  total_sin_igv: string
  comprobantes: number
}

const ctx = useAppContextStore()
const period = ref<Period>('30d')
const loading = ref(false)
const porTipo = ref<PorTipo[]>([])
const evolucion = ref<{ fecha: string; total_sin_igv: string }[]>([])
const error = ref('')

const maxMonto = computed(() => {
  let m = 0
  for (const p of porTipo.value) {
    const n = parseFloat(p.total_sin_igv)
    if (n > m) m = n
  }
  return m || 1
})

const maxEvo = computed(() => {
  let m = 0
  for (const p of evolucion.value) {
    const n = parseFloat(p.total_sin_igv)
    if (n > m) m = n
  }
  return m || 1
})

const maxComprobantes = computed(() => {
  let m = 0
  for (const p of porTipo.value) {
    if (p.comprobantes > m) m = p.comprobantes
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
      evolucion: { fecha: string; total_sin_igv: string }[]
    }>('/ventas/reportes/dashboard/', {
      params: { empresa: ctx.empresaId, period: period.value },
    })
    porTipo.value = data.por_tipo ?? []
    evolucion.value = data.evolucion ?? []
  } catch (e) {
    error.value = listLoadErrorMessage(e, 'el resumen de ventas del panel')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(period, load)
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
        Ventas consolidadas por tipo de comprobante (solo documentos <strong>emitidos</strong>), en subtotal
        <strong>sin IGV</strong>, según el periodo elegido.
      </p>
      <div class="filters">
        <span class="lab">Periodo:</span>
        <button
          v-for="p in (['7d', '30d', '90d'] as const)"
          :key="p"
          type="button"
          class="chip"
          :class="{ on: period === p }"
          @click="period = p"
        >
          {{ p === '7d' ? '1S' : p === '30d' ? '1M' : '3M' }}
        </button>
      </div>
    </header>

    <p v-if="loading" class="muted">Cargando…</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <div v-else class="grid">
      <section class="card">
        <h2 class="card-heading">
          <span class="card-ico card-ico--sales" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M3 3v18h18M7 16l4-4 4 4 6-7"
              />
            </svg>
          </span>
          Resumen de ventas (sin IGV)
        </h2>
        <div class="bars">
          <div v-for="row in porTipo" :key="row.tipo" class="row">
            <span class="name">{{ row.etiqueta }}</span>
            <div class="bar-bg">
              <div
                class="bar-fill"
                :style="{
                  width: `${(parseFloat(row.total_sin_igv) / maxMonto) * 100}%`,
                }"
              />
            </div>
            <span class="val">S/ {{ row.total_sin_igv }}</span>
          </div>
        </div>
      </section>
      <section class="card">
        <h2 class="card-heading">
          <span class="card-ico card-ico--docs" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2Z"
              />
            </svg>
          </span>
          Resumen de comprobantes (cantidad)
        </h2>
        <div class="bars">
          <div v-for="row in porTipo" :key="row.tipo + '-c'" class="row">
            <span class="name">{{ row.etiqueta }}</span>
            <div class="bar-bg">
              <div
                class="bar-fill alt"
                :style="{
                  width: `${(row.comprobantes / maxComprobantes) * 100}%`,
                }"
              />
            </div>
            <span class="val">{{ row.comprobantes }}</span>
          </div>
        </div>
      </section>
      <section class="card wide">
        <h2 class="card-heading">
          <span class="card-ico card-ico--trend" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M3 3v18h18M7.5 14.5 12 10l3.5 3.5L21 8"
              />
            </svg>
          </span>
          Evolución de ventas (sin IGV)
        </h2>
        <div class="spark">
          <div
            v-for="pt in evolucion"
            :key="pt.fecha"
            class="dot-col"
            :title="`${pt.fecha}: S/ ${pt.total_sin_igv}`"
          >
            <div
              class="dot"
              :style="{
                height: `${(parseFloat(pt.total_sin_igv) / maxEvo) * 120}px`,
              }"
            />
            <span class="dlabel">{{ pt.fecha.slice(5) }}</span>
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

.card-heading {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 700;
}

.card-ico {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 10px;
  flex-shrink: 0;
}

.card-ico svg {
  width: 1.2rem;
  height: 1.2rem;
}

.card-ico--sales {
  background: linear-gradient(135deg, rgb(14 165 233 / 12%), rgb(14 116 144 / 18%));
  color: #0e7490;
}

.card-ico--docs {
  background: linear-gradient(135deg, rgb(139 92 246 / 12%), rgb(124 58 237 / 15%));
  color: #7c3aed;
}

.card-ico--trend {
  background: linear-gradient(135deg, rgb(16 185 129 / 12%), rgb(5 150 105 / 18%));
  color: #059669;
}

.sub {
  margin: 0 0 1rem;
  color: #64748b;
  font-size: 0.9rem;
}

code {
  background: #f1f5f9;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.lab {
  font-size: 0.85rem;
  color: #475569;
}

.chip {
  border: 1px solid #cbd5e1;
  background: #fff;
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
}

.chip.on {
  background: #0ea5e9;
  color: #fff;
  border-color: #0ea5e9;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.card {
  background: #fff;
  border-radius: 10px;
  padding: 1rem 1.15rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 10%);
}

.card.wide {
  grid-column: 1 / -1;
}

.bars {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.row {
  display: grid;
  grid-template-columns: 7rem 1fr 5rem;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.8rem;
}

.name {
  color: #475569;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-bg {
  height: 10px;
  background: #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #0ea5e9;
  border-radius: 6px;
  min-width: 2px;
}

.bar-fill.alt {
  background: #8b5cf6;
}

.val {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
}

.spark {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  min-height: 140px;
  overflow-x: auto;
  padding-bottom: 1.5rem;
}

.dot-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 0 0 auto;
}

.dot {
  width: 8px;
  min-height: 4px;
  background: #0ea5e9;
  border-radius: 4px 4px 0 0;
}

.dlabel {
  font-size: 0.65rem;
  color: #94a3b8;
  transform: rotate(-45deg);
  margin-top: 0.5rem;
  white-space: nowrap;
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
