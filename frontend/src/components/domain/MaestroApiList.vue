<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { api } from '@/api/client'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

const props = withDefaults(
  defineProps<{
    title: string
    endpoint: string
    /** Campos a mostrar (clave del JSON de la API) */
    columns: { field: string; label: string }[]
    /** Nombre de tabla SQL / referencia al esquema */
    tabla?: string
    /** Si false, no muestra la línea «Tabla / origen» (pantallas orientadas al usuario). */
    showTablaMeta?: boolean
    /** Texto breve bajo el título (orientación al usuario). */
    subtitle?: string
    /** Mensaje cuando la tabla no tiene filas */
    emptyText?: string
    /** Botón para volver a cargar sin recargar la página */
    showRefresh?: boolean
  }>(),
  { showTablaMeta: true, emptyText: 'No hay filas para mostrar.', showRefresh: false },
)

const rows = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<{ results?: Record<string, unknown>[] }>(props.endpoint)
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    error.value = listLoadErrorMessage(e, `el listado «${props.title}»`)
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(
  () => props.endpoint,
  () => load(),
)

function cellText(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'Sí' : 'No'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function rowKey(row: Record<string, unknown>, index: number): string | number {
  const id = row.id
  if (typeof id === 'number' && Number.isFinite(id)) return id
  if (typeof id === 'string' && /^\d+$/.test(id)) return id
  return `row-${index}`
}
</script>

<template>
  <div class="wrap">
    <header v-if="title || subtitle || (tabla && showTablaMeta) || showRefresh" class="head">
      <div v-if="title || showRefresh" class="head-row">
        <h2 v-if="title" class="title">{{ title }}</h2>
        <button
          v-if="showRefresh"
          type="button"
          class="btn-refresh"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
      <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
      <p v-if="tabla && showTablaMeta" class="tabla">
        <span class="tabla-badge">Origen de datos</span> <code>{{ tabla }}</code>
      </p>
    </header>
    <p v-if="loading" class="state muted">Cargando…</p>
    <p v-else-if="error" class="state err">{{ error }}</p>
    <div v-else class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th v-for="c in columns" :key="c.field">{{ c.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="rowKey(row, i)">
            <td v-for="c in columns" :key="c.field">
              {{ cellText(row[c.field]) }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!rows.length" class="muted empty-msg">{{ emptyText }}</p>
    </div>
  </div>
</template>

<style scoped>
.wrap {
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem 1.35rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  border: 1px solid #e2e8f0;
  width: 100%;
  max-width: none;
}

.head-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  margin-bottom: 0.35rem;
}

.head-row:has(.title:only-child) {
  margin-bottom: 0;
}

.head-row .title {
  margin: 0;
}

.head .title {
  font-size: 1.2rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.btn-refresh {
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  color: #0f172a;
  cursor: pointer;
  font-family: inherit;
}

.btn-refresh:hover:not(:disabled) {
  border-color: #0e7490;
  color: #0e7490;
}

.btn-refresh:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.subtitle {
  margin: 0 0 0.65rem;
  font-size: 0.88rem;
  line-height: 1.5;
  color: #475569;
  max-width: 48rem;
}

.tabla {
  margin: 0 0 1rem;
  font-size: 0.8rem;
  color: #64748b;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.tabla-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748b;
  background: #f1f5f9;
  padding: 0.2rem 0.45rem;
  border-radius: 6px;
}

code {
  background: #f1f5f9;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.table-wrap {
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
}

.state {
  margin: 0 0 1rem;
  line-height: 1.5;
}

.err {
  color: #991b1b;
  font-weight: 600;
  font-size: 0.875rem;
  padding: 0.65rem 0.85rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}
</style>
