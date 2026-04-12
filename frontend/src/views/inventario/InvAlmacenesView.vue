<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type SucursalOpt = { id: number; nombre: string; empresa?: number }
type Row = {
  id: number
  nombre: string
  direccion?: string
  sucursal: number
  sucursal_nombre?: string | null
  es_principal?: boolean
  activo?: boolean
}

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const rows = ref<Row[]>([])
const sucursales = ref<SucursalOpt[]>([])
const loading = ref(true)
const err = ref('')
const filtroNombre = ref('')
const filtroEstado = ref<'todos' | 'activos' | 'inactivos'>('todos')
const filtroSucursalId = ref<number | ''>('')

const showModal = ref(false)
const saving = ref(false)
const formErr = ref('')
const editingId = ref<number | null>(null)
const form = ref({
  sucursal_id: '' as number | '',
  nombre: '',
  direccion: '',
  es_principal: false,
  activo: true,
})

const rowBusy = ref<number | null>(null)

const bloqueadoSinEmpresa = computed(() => isSuperuser.value && !empresaId.value)

const sucursalesFiltradas = computed(() => {
  const list = sucursales.value
  if (isSuperuser.value && empresaId.value) {
    const eid = Number(empresaId.value)
    return list.filter((s) => s.empresa === eid || s.empresa == null)
  }
  return list
})

const filtradas = computed(() => {
  const n = filtroNombre.value.trim().toLowerCase()
  const sid = filtroSucursalId.value
  const est = filtroEstado.value
  return rows.value.filter((r) => {
    if (n && !r.nombre.toLowerCase().includes(n)) return false
    if (sid !== '' && r.sucursal !== sid) return false
    if (est === 'activos' && r.activo === false) return false
    if (est === 'inactivos' && r.activo !== false) return false
    return true
  })
})

async function loadSucursales() {
  try {
    const { data } = await api.get<{ results?: SucursalOpt[] }>('/core/sucursales/?page_size=200&ordering=nombre')
    sucursales.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch {
    sucursales.value = []
  }
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    await loadSucursales()
    const { data } = await api.get<{ results?: Row[] }>('/inventario/almacenes/?page_size=500&ordering=nombre')
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'los almacenes')
    rows.value = []
  } finally {
    loading.value = false
  }
}

function openNuevo() {
  if (bloqueadoSinEmpresa.value) return
  editingId.value = null
  formErr.value = ''
  const opts = sucursalesFiltradas.value
  const only = opts.length === 1 ? opts[0] : undefined
  form.value = {
    sucursal_id: only != null ? only.id : '',
    nombre: '',
    direccion: '',
    es_principal: false,
    activo: true,
  }
  showModal.value = true
}

async function openEdit(r: Row) {
  if (bloqueadoSinEmpresa.value) return
  editingId.value = r.id
  formErr.value = ''
  try {
    const { data } = await api.get<Row>(`/inventario/almacenes/${r.id}/`)
    form.value = {
      sucursal_id: data.sucursal,
      nombre: (data.nombre ?? '').toString(),
      direccion: (data.direccion ?? '').toString(),
      es_principal: data.es_principal === true,
      activo: data.activo !== false,
    }
    showModal.value = true
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el almacén para editar')
  }
}

function closeModal() {
  if (!saving.value) showModal.value = false
}

function drfMsg(data: unknown): string {
  if (data == null || typeof data !== 'object') return 'No se pudo guardar.'
  const d = data as Record<string, unknown>
  if (typeof d.detail === 'string') return d.detail
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
  if (f.sucursal_id === '') {
    formErr.value = 'Seleccione una sucursal.'
    return
  }
  if (!f.nombre.trim()) {
    formErr.value = 'El nombre del almacén es obligatorio.'
    return
  }
  saving.value = true
  try {
    const body: Record<string, unknown> = {
      sucursal: f.sucursal_id,
      nombre: f.nombre.trim().slice(0, 120),
      direccion: f.direccion.trim(),
      es_principal: f.es_principal,
      activo: f.activo,
    }
    if (editingId.value == null) {
      await api.post('/inventario/almacenes/', body)
    } else {
      await api.patch(`/inventario/almacenes/${editingId.value}/`, body)
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

async function inactivar(r: Row) {
  if (r.activo === false) return
  const nombre = r.nombre.trim() || `ID ${r.id}`
  const ok = window.confirm(
    `¿Inactivar el almacén «${nombre}»? Dejará de mostrarse al registrar compras; el historial de stock se conserva. Puede reactivarlo desde Editar.`,
  )
  if (!ok) return
  rowBusy.value = r.id
  err.value = ''
  try {
    await api.patch(`/inventario/almacenes/${r.id}/`, { activo: false })
    await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo inactivar el almacén.'
    }
  } finally {
    rowBusy.value = null
  }
}

function sucursalLabel(r: Row): string {
  const s = r.sucursal_nombre?.trim()
  if (s) return s
  const hit = sucursales.value.find((x) => x.id === r.sucursal)
  return hit?.nombre?.trim() || `Sucursal #${r.sucursal}`
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title">Almacenes</h1>
        <p class="lead">
          Ubicaciones de inventario por <strong>sucursal</strong>. El almacén <strong>principal</strong> puede usarse como
          predeterminado en operaciones. <strong>Inactivar</strong> oculta el almacén en nuevos documentos sin borrar
          movimientos ya registrados.
        </p>
      </div>
      <div class="head-actions">
        <button
          type="button"
          class="btn-add"
          :disabled="loading || bloqueadoSinEmpresa"
          :title="bloqueadoSinEmpresa ? 'Seleccione empresa en la barra (modo plataforma)' : ''"
          @click="openNuevo"
        >
          + Nuevo almacén
        </button>
        <button type="button" class="btn-ref" :disabled="loading" @click="load">
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="bloqueadoSinEmpresa" class="warn">
      Modo administrador global: elija una empresa en la barra superior para crear o editar almacenes.
    </p>
    <p v-if="err" class="err">{{ err }}</p>

    <div class="filters">
      <label class="f">
        <span class="flab">Nombre</span>
        <input v-model="filtroNombre" type="text" class="inp" placeholder="Filtrar…" />
      </label>
      <label class="f">
        <span class="flab">Sucursal</span>
        <select v-model="filtroSucursalId" class="inp inp--select">
          <option value="">Todas</option>
          <option v-for="s in sucursalesFiltradas" :key="s.id" :value="s.id">{{ s.nombre }}</option>
        </select>
      </label>
      <label class="f">
        <span class="flab">Estado</span>
        <select v-model="filtroEstado" class="inp inp--select">
          <option value="todos">Todos</option>
          <option value="activos">Solo activos</option>
          <option value="inactivos">Solo inactivos</option>
        </select>
      </label>
      <p class="total">Mostrando {{ filtradas.length }} de {{ rows.length }}</p>
    </div>

    <div class="card">
      <div v-if="loading" class="muted">Cargando…</div>
      <div v-else class="table-wrap">
        <template v-if="rows.length === 0">
          <div class="empty" role="status">
            <div class="empty__ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M4 7.5h16M4 12h10M4 16.5h7M18 10.5v7m0 0l-2.5-2.5M18 17.5l2.5-2.5"
                />
              </svg>
            </div>
            <p class="empty__title">Aún no hay almacenes</p>
            <p class="empty__text">
              Cree el primero con <strong>+ Nuevo almacén</strong> y asígnelo a una sucursal. Luego podrá usarlo al
              registrar compras y movimientos de stock.
            </p>
          </div>
        </template>
        <template v-else>
          <table class="t">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Sucursal</th>
                <th>Dirección</th>
                <th>Principal</th>
                <th>Activo</th>
                <th class="th-act">Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in filtradas" :key="r.id">
                <td class="td-name">{{ r.nombre }}</td>
                <td>{{ sucursalLabel(r) }}</td>
                <td class="td-dir">{{ (r.direccion || '').trim() || '—' }}</td>
                <td>
                  <span class="pill" :class="r.es_principal ? 'pill--pri' : 'pill--off'">{{
                    r.es_principal ? 'Sí' : 'No'
                  }}</span>
                </td>
                <td>
                  <span class="pill" :class="r.activo !== false ? 'pill--ok' : 'pill--off'">{{
                    r.activo !== false ? 'Sí' : 'No'
                  }}</span>
                </td>
                <td class="td-act">
                  <div class="act-icons" role="group" :aria-label="`Acciones almacén ${r.nombre}`">
                    <button
                      type="button"
                      class="icon-act icon-act--edit"
                      title="Editar"
                      :disabled="bloqueadoSinEmpresa"
                      :aria-label="`Editar almacén ${r.nombre}`"
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
                      title="Inhabilitar (inactivar)"
                      :aria-label="`Inactivar almacén ${r.nombre}`"
                      :disabled="rowBusy === r.id || bloqueadoSinEmpresa"
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
                    <span v-else class="act-muted">Inactivo</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!filtradas.length" class="muted inner">Ningún almacén coincide con los filtros. Pruebe limpiar criterios.</p>
        </template>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showModal" class="backdrop" @click.self="closeModal">
        <div class="modal" role="dialog" aria-modal="true">
          <h2 class="mt">{{ editingId == null ? 'Nuevo almacén' : 'Editar almacén' }}</h2>
          <p v-if="formErr" class="form-err">{{ formErr }}</p>

          <label class="field">
            <span class="lab">Sucursal</span>
            <select v-model="form.sucursal_id" class="inp inp--select inp--wide" :disabled="sucursalesFiltradas.length === 0">
              <option value="" disabled>— Seleccione —</option>
              <option v-for="s in sucursalesFiltradas" :key="s.id" :value="s.id">{{ s.nombre }}</option>
            </select>
          </label>
          <label class="field">
            <span class="lab">Nombre</span>
            <input v-model="form.nombre" class="inp inp--wide" maxlength="120" autocomplete="off" />
          </label>
          <label class="field">
            <span class="lab">Dirección</span>
            <textarea v-model="form.direccion" class="inp inp--wide inp--area" rows="2" autocomplete="street-address" />
          </label>
          <label class="field row-check">
            <input v-model="form.es_principal" type="checkbox" />
            <span>Almacén principal de la sucursal</span>
          </label>
          <label class="field row-check">
            <input v-model="form.activo" type="checkbox" />
            <span>Activo (visible al operar)</span>
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
  max-width: 1040px;
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
  flex-wrap: wrap;
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
  color: #0f172a;
  background: #fff;
}
.inp--select {
  min-width: 12rem;
  cursor: pointer;
}
.inp--wide {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
.inp--area {
  resize: vertical;
  min-height: 2.75rem;
  font-family: inherit;
  line-height: 1.4;
}
.total {
  margin: 0;
  font-size: 0.8rem;
  color: #64748b;
  margin-left: auto;
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
  min-height: 8rem;
}
.empty {
  padding: 2.25rem 1.5rem 2.5rem;
  text-align: center;
  max-width: 26rem;
  margin: 0 auto;
}
.empty__ico {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3.25rem;
  height: 3.25rem;
  border-radius: 14px;
  background: linear-gradient(135deg, #ecfdf5, #ccfbf1);
  color: #0f766e;
  margin-bottom: 1rem;
}
.empty__ico svg {
  width: 1.75rem;
  height: 1.75rem;
}
.empty__title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
}
.empty__text {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.55;
  color: #64748b;
}
.empty__text strong {
  color: #475569;
  font-weight: 600;
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
.td-dir {
  max-width: 14rem;
  word-break: break-word;
  color: #475569;
  font-size: 0.78rem;
  line-height: 1.35;
}
.td-act {
  vertical-align: middle;
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
.pill--pri {
  background: #e0f2fe;
  color: #0369a1;
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
}
.icon-act--del {
  color: #b91c1c;
  border-color: rgba(185, 28, 28, 0.35);
}
.icon-act--del:hover:not(:disabled) {
  background: rgba(185, 28, 28, 0.08);
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
  padding: 1rem 1.25rem 1.25rem;
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
  font-weight: 800;
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
