<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type SucOpt = { id: number; nombre: string }
type Row = {
  id: number
  dni?: string
  apellido_paterno?: string
  apellido_materno?: string
  nombres?: string
  nombre_completo?: string
  sucursal?: number | null
  activo?: boolean
}

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const rows = ref<Row[]>([])
const sucursales = ref<SucOpt[]>([])
const loading = ref(true)
const err = ref('')
const filtroDni = ref('')
const filtroNombre = ref('')

const showModal = ref(false)
const saving = ref(false)
const formErr = ref('')
const editingId = ref<number | null>(null)
const form = ref({
  dni: '',
  apellido_paterno: '',
  apellido_materno: '',
  nombres: '',
  sucursal_id: '' as number | '',
  activo: true,
})

const rowBusy = ref<number | null>(null)
const importBloqueado = computed(() => isSuperuser.value && !empresaId.value)

const consultReniecLoading = ref(false)
const reniecMsg = ref('')
const reniecIsError = ref(false)

const dniDigitsModal = computed(() => form.value.dni.replace(/\D/g, ''))
const puedeConsultarReniec = computed(() => /^\d{8}$/.test(dniDigitsModal.value))

function nombreMostrar(r: Row): string {
  if (r.nombre_completo?.trim()) return r.nombre_completo.trim()
  const p = [r.apellido_paterno, r.apellido_materno, r.nombres].filter(Boolean).join(' ')
  return p.trim() || '—'
}

function sucursalNombre(id: number | null | undefined): string {
  if (id == null) return '—'
  const s = sucursales.value.find((x) => x.id === id)
  return s?.nombre?.trim() || `ID ${id}`
}

const filtradas = computed(() => {
  const d = filtroDni.value.trim().toLowerCase()
  const n = filtroNombre.value.trim().toLowerCase()
  return rows.value.filter((r) => {
    if (d && !(r.dni || '').toLowerCase().includes(d)) return false
    if (n && !nombreMostrar(r).toLowerCase().includes(n)) return false
    return true
  })
})

async function loadSucursales() {
  try {
    const { data } = await api.get<{ results?: SucOpt[] }>('/core/sucursales/?page_size=200&ordering=nombre')
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
    const { data } = await api.get<{ results?: Row[] }>('/core/vendedores/?page_size=500&ordering=apellido_paterno')
    rows.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el listado de vendedores')
    rows.value = []
  } finally {
    loading.value = false
  }
}

function drfMsg(data: unknown): string {
  if (data == null || typeof data !== 'object') return 'Operación no completada.'
  const d = data as Record<string, unknown>
  if (typeof d.detail === 'string') return d.detail
  const parts: string[] = []
  for (const val of Object.values(d)) {
    if (Array.isArray(val)) {
      for (const x of val) {
        if (typeof x === 'string') parts.push(x)
      }
    }
  }
  return parts.join(' ') || 'Operación no completada.'
}

function clearReniecFeedback() {
  reniecMsg.value = ''
  reniecIsError.value = false
}

async function consultarReniec() {
  clearReniecFeedback()
  const n = dniDigitsModal.value
  if (!/^\d{8}$/.test(n)) {
    reniecMsg.value = 'Ingrese un DNI de 8 dígitos para consultar RENIEC.'
    reniecIsError.value = true
    return
  }
  consultReniecLoading.value = true
  try {
    const { data } = await api.get<{
      ok?: boolean
      nombre_completo?: string
      apellido_paterno?: string | null
      apellido_materno?: string | null
      nombres?: string | null
      detail?: string
    }>('/core/consultar-reniec-dni/', { params: { numero: n } })
    if (data.ok) {
      const ap1 = (data.apellido_paterno ?? '').trim()
      const ap2 = (data.apellido_materno ?? '').trim()
      const nom = (data.nombres ?? '').trim()
      if (ap1 || ap2 || nom) {
        form.value.apellido_paterno = ap1.slice(0, 80)
        form.value.apellido_materno = ap2.slice(0, 80)
        form.value.nombres = nom.slice(0, 120)
      } else {
        const nc = (data.nombre_completo ?? '').trim()
        if (nc) {
          form.value.nombres = nc.slice(0, 120)
        }
      }
      form.value.dni = n
      reniecMsg.value = 'Datos sugeridos por RENIEC (revise antes de guardar).'
      reniecIsError.value = false
    } else {
      reniecMsg.value =
        typeof data.detail === 'string' && data.detail.trim()
          ? data.detail
          : 'No se pudo consultar el DNI.'
      reniecIsError.value = true
    }
  } catch (e) {
    reniecIsError.value = true
    if (axios.isAxiosError(e) && e.response?.data && typeof e.response.data === 'object') {
      const d = e.response.data as { detail?: string }
      reniecMsg.value =
        typeof d.detail === 'string' && d.detail.trim() ? d.detail : 'Error al consultar RENIEC.'
    } else {
      reniecMsg.value = 'Error de conexión al consultar RENIEC.'
    }
  } finally {
    consultReniecLoading.value = false
  }
}

function openNuevo() {
  if (importBloqueado.value) return
  editingId.value = null
  formErr.value = ''
  clearReniecFeedback()
  form.value = {
    dni: '',
    apellido_paterno: '',
    apellido_materno: '',
    nombres: '',
    sucursal_id: '',
    activo: true,
  }
  showModal.value = true
}

function openEdit(r: Row) {
  editingId.value = r.id
  formErr.value = ''
  clearReniecFeedback()
  form.value = {
    dni: (r.dni ?? '').toString(),
    apellido_paterno: (r.apellido_paterno ?? '').toString(),
    apellido_materno: (r.apellido_materno ?? '').toString(),
    nombres: (r.nombres ?? '').toString(),
    sucursal_id: r.sucursal != null ? r.sucursal : '',
    activo: r.activo !== false,
  }
  showModal.value = true
}

function closeModal() {
  if (!saving.value) {
    showModal.value = false
    clearReniecFeedback()
  }
}

async function guardar() {
  formErr.value = ''
  const f = form.value
  if (!f.dni.trim() && !f.apellido_paterno.trim() && !f.nombres.trim()) {
    formErr.value = 'Indique al menos DNI o apellido paterno / nombres.'
    return
  }
  saving.value = true
  try {
    const body: Record<string, unknown> = {
      dni: f.dni.trim().slice(0, 20),
      apellido_paterno: f.apellido_paterno.trim().slice(0, 80),
      apellido_materno: f.apellido_materno.trim().slice(0, 80),
      nombres: f.nombres.trim().slice(0, 120),
      sucursal: f.sucursal_id === '' ? null : f.sucursal_id,
      activo: f.activo,
    }
    if (editingId.value == null && isSuperuser.value && empresaId.value) {
      body.empresa = Number(empresaId.value)
    }
    if (editingId.value == null) {
      await api.post('/core/vendedores/', body)
    } else {
      await api.patch(`/core/vendedores/${editingId.value}/`, body)
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
  const ok = window.confirm(
    `¿Desactivar a «${nombreMostrar(r)}»? Dejará de aparecer al emitir comprobantes; no se borra el registro y puede reactivarlo desde Editar.`,
  )
  if (!ok) return
  rowBusy.value = r.id
  err.value = ''
  try {
    await api.patch(`/core/vendedores/${r.id}/`, { activo: false })
    await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo desactivar el vendedor.'
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
        <h1 class="title">Vendedores</h1>
        <p class="lead">
          Equipo de ventas de su empresa: se asocian al emitir comprobantes. Capture DNI y apellidos y nombres, o use
          <strong>Consultar RENIEC</strong> en el formulario con un DNI de 8 dígitos. Inactivar no borra el registro; puede
          volver a activar desde <strong>Editar</strong>.
        </p>
      </div>
      <div class="head-actions">
        <button
          type="button"
          class="btn-add"
          :disabled="loading || importBloqueado"
          :title="importBloqueado ? 'Seleccione empresa en la barra' : ''"
          @click="openNuevo"
        >
          + Agregar vendedor
        </button>
        <button type="button" class="btn-ref" :disabled="loading" @click="load">
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="importBloqueado" class="warn">
      Modo administrador global: elija una empresa en la barra superior para crear o editar vendedores.
    </p>
    <p v-if="err" class="err">{{ err }}</p>

    <div class="filters">
      <label class="f">
        <span class="flab">DNI</span>
        <input v-model="filtroDni" type="text" class="inp" placeholder="Filtrar…" />
      </label>
      <label class="f">
        <span class="flab">Nombres / apellidos</span>
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
              <th>DNI</th>
              <th>Nombre</th>
              <th>Sucursal</th>
              <th>Activo</th>
              <th class="th-act">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in filtradas" :key="r.id">
              <td>
                <code class="code">{{ r.dni?.trim() || '—' }}</code>
              </td>
              <td class="td-name">{{ nombreMostrar(r) }}</td>
              <td>{{ sucursalNombre(r.sucursal ?? undefined) }}</td>
              <td>
                <span class="pill" :class="r.activo !== false ? 'pill--ok' : 'pill--off'">{{
                  r.activo !== false ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-act">
                <div
                  class="act-icons"
                  role="group"
                  :aria-label="`Acciones para ${nombreMostrar(r)}`"
                >
                  <button
                    type="button"
                    class="icon-act icon-act--edit"
                    title="Editar"
                    :aria-label="`Editar vendedor ${nombreMostrar(r)}`"
                    :disabled="importBloqueado"
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
                    title="Desactivar (baja lógica)"
                    :aria-label="`Desactivar vendedor ${nombreMostrar(r)}`"
                    :disabled="rowBusy === r.id || importBloqueado"
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
        <p v-if="!filtradas.length && !loading" class="empty-state inner">
          <template v-if="rows.length === 0">
            No hay vendedores cargados. Use <strong>Agregar vendedor</strong> para el primero.
          </template>
          <template v-else>
            Ningún registro coincide con el filtro. Pruebe otros criterios o limpie los campos.
          </template>
        </p>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showModal" class="backdrop" @click.self="closeModal">
        <div class="modal" role="dialog" aria-modal="true">
          <h2 class="mt">{{ editingId == null ? 'Nuevo vendedor' : 'Editar vendedor' }}</h2>
          <p v-if="formErr" class="form-err">{{ formErr }}</p>
          <div class="field field-dni">
            <span class="lab">DNI</span>
            <div class="dni-reniec-row">
              <input
                v-model="form.dni"
                class="inp inp-dni"
                maxlength="20"
                inputmode="numeric"
                autocomplete="off"
                placeholder="12345678"
                @input="clearReniecFeedback"
              />
              <button
                type="button"
                class="btn-reniec"
                :disabled="consultReniecLoading || saving || !puedeConsultarReniec"
                title="Consultar nombre en RENIEC (8 dígitos)"
                @click="consultarReniec"
              >
                {{ consultReniecLoading ? '…' : 'Consultar RENIEC' }}
              </button>
            </div>
            <p v-if="reniecMsg" class="reniec-feedback" :class="{ 'reniec-feedback--err': reniecIsError }">
              {{ reniecMsg }}
            </p>
          </div>
          <label class="field">
            <span class="lab">Apellido paterno</span>
            <input v-model="form.apellido_paterno" class="inp" maxlength="80" />
          </label>
          <label class="field">
            <span class="lab">Apellido materno</span>
            <input v-model="form.apellido_materno" class="inp" maxlength="80" />
          </label>
          <label class="field">
            <span class="lab">Nombres</span>
            <input v-model="form.nombres" class="inp" maxlength="120" />
          </label>
          <label class="field">
            <span class="lab">Sucursal (opcional)</span>
            <select v-model="form.sucursal_id" class="inp inp--select">
              <option value="">— Sin asignar —</option>
              <option v-for="s in sucursales" :key="s.id" :value="s.id">{{ s.nombre }}</option>
            </select>
          </label>
          <label class="field row-check">
            <input v-model="form.activo" type="checkbox" />
            <span>Activo (visible al emitir comprobantes)</span>
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
  max-width: 1000px;
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
.head-actions .btn-add {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  color: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  line-height: 1.25;
  font-family: inherit;
  cursor: pointer;
}
.head-actions .btn-add:hover:not(:disabled) {
  filter: brightness(1.05);
}
.head-actions .btn-add:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.head-actions .btn-ref {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #0f172a;
  font-weight: 600;
  font-size: 0.8rem;
  line-height: 1.25;
  font-family: inherit;
  cursor: pointer;
}
.head-actions .btn-ref:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
/* Modal y otros usos fuera de .head-actions */
.btn-add {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  color: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  line-height: 1.25;
  font-family: inherit;
  cursor: pointer;
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
  color: #0f172a;
  font-weight: 600;
  font-size: 0.8rem;
  line-height: 1.25;
  font-family: inherit;
  cursor: pointer;
}
.btn-ref:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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
}
.inp--select {
  min-width: 100%;
  box-sizing: border-box;
}
.total {
  margin: 0 0 0 auto;
  font-size: 0.8rem;
  color: #64748b;
}
.card {
  background: #fff;
  border-radius: 10px;
  padding: 0;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  overflow: hidden;
}
.table-wrap {
  overflow-x: auto;
}
.t {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
.t th,
.t td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}
.t th {
  background: #f8fafc;
  font-size: 0.72rem;
  text-transform: uppercase;
  color: #64748b;
}
.th-act {
  width: 1%;
  white-space: nowrap;
  text-align: right;
}
.td-act {
  text-align: right;
  vertical-align: middle;
}
.act-icons {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
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
  font-family: inherit;
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
.empty-state {
  margin: 0;
  padding: 1.75rem 1rem;
  text-align: center;
  font-size: 0.88rem;
  color: #64748b;
  line-height: 1.5;
}
.empty-state strong {
  color: #0f172a;
  font-weight: 600;
}
.code {
  background: #e2e8f0;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-size: 0.82rem;
}
.td-name {
  font-weight: 500;
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
  max-width: 440px;
  border: 1px solid #e2e8f0;
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
.field-dni {
  margin-bottom: 0.65rem;
}
.dni-reniec-row {
  display: flex;
  align-items: stretch;
  gap: 0.45rem;
}
.inp-dni {
  flex: 1;
  min-width: 0;
}
.btn-reniec {
  flex-shrink: 0;
  padding: 0.4rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #0369a1;
  background: #f0f9ff;
  color: #0369a1;
  font-weight: 600;
  font-size: 0.72rem;
  line-height: 1.2;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.btn-reniec:hover:not(:disabled) {
  background: #e0f2fe;
  border-color: #0284c7;
}
.btn-reniec:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.reniec-feedback {
  margin: 0.35rem 0 0;
  font-size: 0.72rem;
  color: #047857;
  line-height: 1.35;
}
.reniec-feedback--err {
  color: #b91c1c;
}
.modal-act {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
</style>
