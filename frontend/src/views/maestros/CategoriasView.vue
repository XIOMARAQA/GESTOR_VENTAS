<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type Row = {
  id: number
  nombre: string
  padre: number | null
  activo?: boolean
}

const rows = ref<Row[]>([])
const loading = ref(true)
const err = ref('')
const filtroNombre = ref('')

const showModal = ref(false)
const saving = ref(false)
const formErr = ref('')
const editingId = ref<number | null>(null)
const form = ref({
  nombre: '',
  /** vacío = sin categoría superior */
  padreId: '' as number | '',
  activo: true,
})

const nombrePorId = computed(() => {
  const m = new Map<number, string>()
  for (const r of rows.value) m.set(r.id, r.nombre)
  return m
})

function padreEtiqueta(padreId: number | null | undefined): string {
  if (padreId == null) return '—'
  return nombrePorId.value.get(padreId) ?? `#${padreId}`
}

const opcionesPadre = computed(() => {
  const excluir = editingId.value
  return rows.value
    .filter((r) => excluir == null || r.id !== excluir)
    .slice()
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
})

const filtradas = computed(() => {
  const n = filtroNombre.value.trim().toLowerCase()
  return rows.value.filter((r) => {
    if (n && !r.nombre.toLowerCase().includes(n)) return false
    return true
  })
})

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await api.get<{ results?: Row[] }>(
      '/inventario/categorias/?page_size=500&ordering=nombre',
    )
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el catálogo de categorías')
    rows.value = []
  } finally {
    loading.value = false
  }
}

function openNuevo() {
  editingId.value = null
  formErr.value = ''
  form.value = { nombre: '', padreId: '', activo: true }
  showModal.value = true
}

function openEdit(r: Row) {
  editingId.value = r.id
  formErr.value = ''
  form.value = {
    nombre: r.nombre,
    padreId: r.padre != null ? r.padre : '',
    activo: r.activo !== false,
  }
  showModal.value = true
}

function closeModal() {
  if (!saving.value) showModal.value = false
}

function drfMsg(data: unknown): string {
  if (data == null || typeof data !== 'object') return 'No se pudo guardar.'
  const d = data as Record<string, unknown>
  const parts: string[] = []
  for (const [k, val] of Object.entries(d)) {
    if (k === 'detail' && typeof val === 'string') return val
    if (Array.isArray(val)) {
      for (const x of val) {
        if (typeof x === 'string') parts.push(x)
      }
    }
  }
  return parts.join(' ') || 'No se pudo guardar.'
}

async function guardar() {
  formErr.value = ''
  const f = form.value
  if (!f.nombre.trim()) {
    formErr.value = 'El nombre es obligatorio.'
    return
  }
  saving.value = true
  try {
    const body = {
      nombre: f.nombre.trim(),
      padre: f.padreId === '' ? null : f.padreId,
      activo: f.activo,
    }
    if (editingId.value == null) {
      await api.post('/inventario/categorias/', body)
    } else {
      await api.patch(`/inventario/categorias/${editingId.value}/`, body)
    }
    showModal.value = false
    await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      formErr.value = drfMsg(e.response.data)
    } else {
      formErr.value = 'Error de conexión.'
    }
  } finally {
    saving.value = false
  }
}

const rowBusy = ref<number | null>(null)

async function inactivar(r: Row) {
  if (r.activo === false) return
  const ok = window.confirm(
    `¿Inactivar la categoría «${r.nombre}»? No se elimina de la base de datos; puede reactivarla desde Editar.`,
  )
  if (!ok) return
  rowBusy.value = r.id
  err.value = ''
  try {
    await api.patch(`/inventario/categorias/${r.id}/`, { activo: false })
    await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo inactivar la categoría.'
    }
  } finally {
    rowBusy.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title">Categorías de producto</h1>
        <p class="lead">
          Rubros propios de su empresa (por ejemplo «Bebidas», «Abarrotes»). Puede crear <strong>subcategorías</strong>
          eligiendo una categoría padre. Si un ítem es servicio o bien se define en la ficha de cada producto, no aquí.
        </p>
      </div>
      <div class="head-actions">
        <button type="button" class="btn-add" @click="openNuevo">+ Agregar categoría</button>
        <button type="button" class="btn-ref" :disabled="loading" @click="load">
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="err" class="err">{{ err }}</p>

    <div class="filters">
      <label class="f">
        <span class="flab">Nombre</span>
        <input v-model="filtroNombre" type="text" class="inp" placeholder="Filtrar…" />
      </label>
      <p class="total">Total visibles: {{ filtradas.length }} de {{ rows.length }}</p>
    </div>

    <div class="card">
      <div v-if="loading" class="muted">Cargando…</div>
      <div v-else class="table-wrap">
        <table class="t">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Padre (jerarquía)</th>
              <th>Activo</th>
              <th class="th-act">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in filtradas" :key="r.id">
              <td class="td-name">{{ r.nombre }}</td>
              <td class="td-padre">{{ padreEtiqueta(r.padre) }}</td>
              <td>
                <span class="pill" :class="r.activo !== false ? 'pill--ok' : 'pill--off'">{{
                  r.activo !== false ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-act">
                <div class="act-icons" role="group" :aria-label="`Acciones para categoría ${r.nombre}`">
                  <button
                    type="button"
                    class="icon-act icon-act--edit"
                    title="Editar"
                    :aria-label="`Editar categoría ${r.nombre}`"
                    @click="openEdit(r)"
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
                    v-if="r.activo !== false"
                    type="button"
                    class="icon-act icon-act--del"
                    title="Eliminar (inactivar)"
                    :aria-label="`Inactivar categoría ${r.nombre}`"
                    :disabled="rowBusy === r.id"
                    @click="inactivar(r)"
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
                  <span v-else class="act-muted">Inactiva</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!filtradas.length" class="muted inner">Sin registros que coincidan.</p>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showModal" class="backdrop" @click.self="closeModal">
        <div class="modal" role="dialog" aria-modal="true">
          <h2 class="mt">{{ editingId == null ? 'Nueva categoría' : 'Editar categoría' }}</h2>
          <p v-if="formErr" class="form-err">{{ formErr }}</p>
          <label class="field">
            <span class="lab">Nombre</span>
            <input v-model="form.nombre" class="inp" maxlength="120" />
          </label>
          <label class="field">
            <span class="lab">Dentro de qué categoría va (jerarquía, opcional)</span>
            <select v-model="form.padreId" class="inp inp--select">
              <option value="">— Ninguna: categoría raíz —</option>
              <option v-for="o in opcionesPadre" :key="o.id" :value="o.id">{{ o.nombre }}</option>
            </select>
            <span class="field-hint">
              Solo aparecen <strong>otras categorías que ya creó</strong>, para armar subniveles (ej. Alimentos →
              Lácteos). No es la lista «producto / servicio». Si el desplegable está vacío aparte de «raíz», cree y
              guarde primero la categoría padre.
            </span>
          </label>
          <label class="field row-check">
            <input v-model="form.activo" type="checkbox" />
            <span>Activo</span>
          </label>
          <div class="modal-act">
            <button type="button" class="btn-ref" :disabled="saving" @click="closeModal">Cancelar</button>
            <button type="button" class="btn-add" :disabled="saving" @click="guardar">
              {{ saving ? 'Guardando…' : 'Guardar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: 960px;
  color: #0f172a;
}
.head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
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
  line-height: 1.5;
  max-width: 46rem;
}
.lead strong {
  color: #334155;
  font-weight: 600;
}
.head-actions {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
}
.btn-add {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  color: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  font-family: inherit;
}
.btn-add:hover:not(:disabled) {
  filter: brightness(1.05);
}
.btn-add:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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
.err {
  color: #991b1b;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.5;
  margin: 0 0 0.75rem;
  padding: 0.65rem 0.85rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 1rem;
}
.f {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.flab {
  font-size: 0.72rem;
  font-weight: 600;
  color: #64748b;
}
.inp {
  padding: 0.45rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.875rem;
  min-width: 12rem;
  color: #0f172a;
  background: #fff;
}
.inp--select {
  min-width: 100%;
  box-sizing: border-box;
}
.total {
  margin: 0;
  font-size: 0.8rem;
  color: #64748b;
  margin-left: auto;
}
.card {
  background: #fff;
  border-radius: 10px;
  padding: 0;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  border: 1px solid #e2e8f0;
  overflow: hidden;
}
.table-wrap {
  overflow-x: auto;
}
.t {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}
.t th,
.t td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  color: #0f172a;
}
.t th {
  background: #f1f5f9;
  font-size: 0.8125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #334155;
}
.t td {
  font-weight: 500;
  font-size: 0.8125rem;
}
.th-act {
  width: 5.5rem;
  white-space: nowrap;
}
.td-name {
  font-weight: 600;
}
.td-padre {
  color: #334155;
}
.pill {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
}
.pill--ok {
  background: #dcfce7;
  color: #166534;
}
.pill--off {
  background: #f1f5f9;
  color: #64748b;
}
.td-act {
  vertical-align: middle;
}
.act-icons {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.icon-act {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.15rem;
  height: 2.15rem;
  padding: 0;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    color 0.15s ease,
    background 0.15s ease;
}
.icon-act svg {
  width: 1.1rem;
  height: 1.1rem;
}
.icon-act:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.icon-act--edit {
  color: #0e7490;
  border-color: rgba(14, 116, 144, 0.35);
}
.icon-act--edit:hover:not(:disabled) {
  background: rgba(14, 116, 144, 0.08);
  border-color: #0e7490;
  color: #115e59;
}
.icon-act--del {
  color: #b91c1c;
  border-color: rgba(185, 28, 28, 0.35);
}
.icon-act--del:hover:not(:disabled) {
  background: rgba(185, 28, 28, 0.08);
  border-color: #b91c1c;
  color: #991b1b;
}
.act-muted {
  font-size: 0.75rem;
  color: #64748b;
}
.muted {
  padding: 1.5rem;
  color: #94a3b8;
  text-align: center;
}
.inner {
  padding: 1rem;
}
.backdrop {
  position: fixed;
  inset: 0;
  background: rgb(15 23 42 / 45%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 70;
  padding: 1rem;
}
.modal {
  background: #fff;
  border-radius: 12px;
  padding: 1.15rem 1.25rem;
  width: 100%;
  max-width: 440px;
  border: 1px solid #e2e8f0;
  color: #0f172a;
}
.mt {
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
}
.form-err {
  color: #b91c1c;
  font-size: 0.82rem;
  margin: 0 0 0.75rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.65rem;
}
.lab {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
}
.field-hint {
  font-size: 0.72rem;
  color: #64748b;
  line-height: 1.4;
  margin-top: 0.2rem;
}
.field-hint strong {
  color: #475569;
  font-weight: 600;
}
.row-check {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
.modal-act {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
</style>
