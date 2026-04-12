<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type SunatRow = { codigo: string; descripcion: string }

type Row = {
  id: number
  codigo: string
  nombre: string
  codigo_sunat?: string
  activo?: boolean
}

const rows = ref<Row[]>([])
const loading = ref(true)
const err = ref('')
const filtroCodigo = ref('')
const filtroNombre = ref('')

const showModal = ref(false)
const saving = ref(false)
const formErr = ref('')
const editingId = ref<number | null>(null)
const form = ref({
  codigo: '',
  nombre: '',
  codigo_sunat: '',
  activo: true,
})

const sunatCatalogo = ref<SunatRow[]>([])

const sunatPanelOpen = ref(false)
const sunatFilter = ref('')
const sunatOpciones = computed(() => {
  const list = sunatCatalogo.value
  const t = sunatFilter.value.trim().toLowerCase()
  if (!t) return list
  return list.filter(
    (r) =>
      r.codigo.toLowerCase().includes(t) || r.descripcion.toLowerCase().includes(t),
  )
})

function sunatLabel(codigo: string): string {
  const c = codigo.trim().toUpperCase()
  if (!c) return '—'
  const row = sunatCatalogo.value.find((x) => x.codigo.toUpperCase() === c)
  return row ? `${row.codigo} — ${row.descripcion}` : codigo.trim()
}

function syncSunatFilterFromForm() {
  const c = form.value.codigo_sunat.trim().toUpperCase()
  if (!c) {
    sunatFilter.value = ''
    return
  }
  const row = sunatCatalogo.value.find((x) => x.codigo.toUpperCase() === c)
  sunatFilter.value = row ? row.descripcion : c
}

function onSunatFocus() {
  sunatPanelOpen.value = true
}

function onSunatBlur() {
  window.setTimeout(() => {
    sunatPanelOpen.value = false
    syncSunatFilterFromForm()
  }, 180)
}

function onSunatSpaceKey() {
  sunatPanelOpen.value = true
  sunatFilter.value = ''
}

function pickSunat(opt: { codigo: string; descripcion: string }) {
  form.value.codigo_sunat = opt.codigo
  sunatFilter.value = opt.descripcion
  sunatPanelOpen.value = false
}

function clearSunat() {
  form.value.codigo_sunat = ''
  sunatFilter.value = ''
}

const filtradas = computed(() => {
  const c = filtroCodigo.value.trim().toLowerCase()
  const n = filtroNombre.value.trim().toLowerCase()
  return rows.value.filter((r) => {
    if (c && !r.codigo.toLowerCase().includes(c)) return false
    if (n && !r.nombre.toLowerCase().includes(n)) return false
    return true
  })
})

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await api.get<{ results?: Row[] }>('/inventario/unidades-medida/?page_size=500')
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el catálogo de unidades de medida')
    rows.value = []
  } finally {
    loading.value = false
  }
  try {
    const { data } = await api.get<SunatRow[]>('/inventario/unidades-medida/catalogo-sunat/')
    sunatCatalogo.value = Array.isArray(data) ? data : []
  } catch {
    sunatCatalogo.value = []
  }
}

function openNuevo() {
  editingId.value = null
  formErr.value = ''
  form.value = { codigo: '', nombre: '', codigo_sunat: '', activo: true }
  sunatFilter.value = ''
  sunatPanelOpen.value = false
  showModal.value = true
}

function openEdit(r: Row) {
  editingId.value = r.id
  formErr.value = ''
  form.value = {
    codigo: r.codigo,
    nombre: r.nombre,
    codigo_sunat: r.codigo_sunat ?? '',
    activo: r.activo !== false,
  }
  syncSunatFilterFromForm()
  sunatPanelOpen.value = false
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
  if (!f.codigo.trim() || !f.nombre.trim()) {
    formErr.value = 'Código y nombre son obligatorios.'
    return
  }
  saving.value = true
  try {
    const body = {
      codigo: f.codigo.trim().toUpperCase().slice(0, 20),
      nombre: f.nombre.trim(),
      codigo_sunat: f.codigo_sunat.trim().toUpperCase(),
      activo: f.activo,
    }
    if (editingId.value == null) {
      await api.post('/inventario/unidades-medida/', body)
    } else {
      await api.patch(`/inventario/unidades-medida/${editingId.value}/`, body)
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
    `¿Inactivar la unidad «${r.nombre}» (${r.codigo})? No se elimina de la base de datos; puede reactivarla desde Editar.`,
  )
  if (!ok) return
  rowBusy.value = r.id
  err.value = ''
  try {
    await api.patch(`/inventario/unidades-medida/${r.id}/`, { activo: false })
    await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo inactivar la unidad.'
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
        <h1 class="title">Unidades de medida</h1>
        <p class="lead">
          Cada producto usa una unidad de esta lista. Defina un <strong>código corto</strong> (por ejemplo UND, KG) y un
          nombre claro. El <strong>código SUNAT</strong> (tabla 6) es el que debe figurar en comprobantes electrónicos
          cuando aplique.
        </p>
      </div>
      <div class="head-actions">
        <button type="button" class="btn-add" @click="openNuevo">+ Agregar unidad</button>
        <button type="button" class="btn-ref" :disabled="loading" @click="load">
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="err" class="err">{{ err }}</p>

    <div class="filters">
      <label class="f">
        <span class="flab">Código</span>
        <input v-model="filtroCodigo" type="text" class="inp" placeholder="Filtrar…" />
      </label>
      <label class="f">
        <span class="flab">Nombre de unidad</span>
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
              <th>Código</th>
              <th>Nombre de unidad</th>
              <th>Código SUNAT (Tabla 6)</th>
              <th>Activo</th>
              <th class="th-act">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in filtradas" :key="r.id">
              <td>
                <code class="code">{{ r.codigo }}</code>
              </td>
              <td class="td-name">{{ r.nombre }}</td>
              <td class="td-muted">{{ sunatLabel(r.codigo_sunat?.trim() || '') }}</td>
              <td>
                <span class="pill" :class="r.activo !== false ? 'pill--ok' : 'pill--off'">{{
                  r.activo !== false ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-act">
                <div
                  class="act-icons"
                  role="group"
                  :aria-label="`Acciones para unidad ${r.codigo}`"
                >
                  <button
                    type="button"
                    class="icon-act icon-act--edit"
                    title="Editar"
                    :aria-label="`Editar unidad ${r.codigo}`"
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
                    :aria-label="`Inactivar unidad ${r.codigo}`"
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
          <h2 class="mt">{{ editingId == null ? 'Nueva unidad' : 'Editar unidad' }}</h2>
          <p v-if="formErr" class="form-err">{{ formErr }}</p>
          <label class="field">
            <span class="lab">Código</span>
            <input
              v-model="form.codigo"
              class="inp"
              maxlength="20"
              :disabled="editingId != null"
              title="No se puede cambiar el código al editar (único por empresa)"
            />
          </label>
          <label class="field">
            <span class="lab">Nombre de unidad</span>
            <input v-model="form.nombre" class="inp" maxlength="120" />
          </label>
          <label class="field field-sunat">
            <span class="lab">Código SUNAT — Tabla 6 (recomendado)</span>
            <div class="sunat-wrap">
              <div class="sunat-field">
                <input
                  v-model="sunatFilter"
                  type="text"
                  class="inp sunat-inp"
                  maxlength="120"
                  autocomplete="off"
                  placeholder="Escriba código o descripción; barra espaciadora abre la lista completa"
                  @focus="onSunatFocus"
                  @blur="onSunatBlur"
                  @keydown.escape.stop.prevent="sunatPanelOpen = false"
                  @keydown.space.prevent="onSunatSpaceKey"
                />
                <ul v-show="sunatPanelOpen" class="sunat-dd" role="listbox">
                  <li
                    v-for="opt in sunatOpciones"
                    :key="opt.codigo"
                    role="option"
                    tabindex="-1"
                    class="sunat-opt"
                    @mousedown.prevent="pickSunat(opt)"
                  >
                    <span class="sunat-code">{{ opt.codigo }}</span>
                    <span class="sunat-desc">{{ opt.descripcion }}</span>
                  </li>
                  <li v-if="!sunatOpciones.length" class="sunat-empty">Sin coincidencias</li>
                </ul>
              </div>
              <button type="button" class="sunat-clear" tabindex="-1" @mousedown.prevent @click="clearSunat">
                Quitar
              </button>
            </div>
            <span class="hint">Se guarda el código oficial (p. ej. NIU, KGM); la descripción es solo guía.</span>
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
  /* El shell (.brand-bg) usa texto claro; esta vista va sobre fondo claro y debe forzar texto oscuro. */
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
  min-width: 10rem;
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
}
.t th {
  background: #f1f5f9;
  font-size: 0.8125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #334155;
}
.th-act {
  width: 5.5rem;
  white-space: nowrap;
}
.t td {
  color: #0f172a;
  font-weight: 500;
  font-size: 0.8125rem;
}
.t td.td-name {
  color: #0f172a;
  font-weight: 600;
}
.code {
  background: #e2e8f0;
  color: #0f172a;
  padding: 0.12rem 0.35rem;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
}
.td-muted {
  color: #334155;
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
  max-width: 460px;
  border: 1px solid #e2e8f0;
}
.field-sunat {
  position: relative;
}
.sunat-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.sunat-field {
  position: relative;
}
.sunat-inp {
  width: 100%;
  box-sizing: border-box;
}
.sunat-dd {
  position: absolute;
  left: 0;
  right: 0;
  top: 100%;
  margin: 0.2rem 0 0;
  padding: 0.25rem 0;
  list-style: none;
  max-height: 220px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgb(15 23 42 / 12%);
  z-index: 5;
}
.sunat-opt {
  padding: 0.4rem 0.65rem;
  cursor: pointer;
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
  font-size: 0.82rem;
}
.sunat-opt:hover {
  background: #e0f2fe;
}
.sunat-code {
  font-weight: 700;
  color: #0e7490;
  min-width: 2.25rem;
}
.sunat-desc {
  color: #0f172a;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.sunat-empty {
  padding: 0.5rem 0.65rem;
  color: #94a3b8;
  font-size: 0.8rem;
}
.sunat-clear {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: none;
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
}
.sunat-clear:hover {
  color: #0e7490;
}
.hint {
  font-size: 0.72rem;
  color: #94a3b8;
  line-height: 1.35;
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
