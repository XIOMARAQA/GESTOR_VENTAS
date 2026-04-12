<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '@/api/client'

type SuperRow = {
  id: number
  username?: string
  email?: string
  nombres?: string
  apellido_paterno?: string
  apellido_materno?: string
  is_active?: boolean
  date_joined?: string
  last_login?: string | null
}

const rows = ref<SuperRow[]>([])
const loading = ref(true)
const err = ref('')
const showModal = ref(false)
const saving = ref(false)
const formErr = ref('')
const modalMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)

const form = ref({
  email: '',
  nombres: '',
  apellido_paterno: '',
  apellido_materno: '',
  password: '',
  password_confirm: '',
})

function drfToMsg(data: unknown): string {
  if (data == null || typeof data !== 'object') return 'No pudimos guardar los cambios.'
  const d = data as Record<string, unknown>
  const detail = d.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  const parts: string[] = []
  for (const [k, val] of Object.entries(d)) {
    if (k === 'detail') continue
    if (Array.isArray(val)) {
      for (const x of val) {
        if (typeof x === 'string') parts.push(x)
      }
    } else if (typeof val === 'string') parts.push(val)
  }
  return parts.join(' ').trim() || 'No pudimos guardar los cambios.'
}

function openModal() {
  modalMode.value = 'create'
  editingId.value = null
  formErr.value = ''
  form.value = {
    email: '',
    nombres: '',
    apellido_paterno: '',
    apellido_materno: '',
    password: '',
    password_confirm: '',
  }
  showModal.value = true
}

function openEdit(u: SuperRow) {
  modalMode.value = 'edit'
  editingId.value = u.id
  formErr.value = ''
  const nom = (u.nombres ?? '').trim()
  const ap = (u.apellido_paterno ?? '').trim()
  const am = (u.apellido_materno ?? '').trim()
  form.value = {
    email: u.email || u.username || '',
    nombres: nom,
    apellido_paterno: ap,
    apellido_materno: am,
    password: '',
    password_confirm: '',
  }
  showModal.value = true
}

function closeModal() {
  if (saving.value) return
  showModal.value = false
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await api.get<{ results?: SuperRow[] }>('/core/plataforma/superusuarios/')
    rows.value = data.results ?? []
  } catch {
    err.value = 'No pudimos cargar la lista. Pulse Actualizar o revise su conexión.'
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function submitModal() {
  formErr.value = ''
  const f = form.value
  if (modalMode.value === 'create') {
    if (!f.email.trim()) {
      formErr.value = 'Escriba un correo electrónico válido.'
      return
    }
    if (!f.nombres.trim() || !f.apellido_paterno.trim() || !f.apellido_materno.trim()) {
      formErr.value = 'Complete apellido paterno, apellido materno y nombres.'
      return
    }
    if (!f.password || f.password !== f.password_confirm) {
      formErr.value = 'Las contraseñas no coinciden.'
      return
    }
    saving.value = true
    try {
      await api.post('/core/plataforma/superusuarios/', {
        email: f.email.trim().toLowerCase(),
        nombres: f.nombres.trim(),
        apellido_paterno: f.apellido_paterno.trim(),
        apellido_materno: f.apellido_materno.trim(),
        password: f.password,
        password_confirm: f.password_confirm,
      })
      showModal.value = false
      await load()
    } catch (e: unknown) {
      const ax = e as { response?: { data?: unknown } }
      formErr.value = drfToMsg(ax.response?.data)
    } finally {
      saving.value = false
    }
    return
  }

  if (editingId.value == null) return
  if (!f.nombres.trim() || !f.apellido_paterno.trim() || !f.apellido_materno.trim()) {
    formErr.value = 'Complete apellido paterno, apellido materno y nombres.'
    return
  }
  if (f.password && f.password !== f.password_confirm) {
    formErr.value = 'Las contraseñas no coinciden.'
    return
  }
  saving.value = true
  try {
    const body: Record<string, string | boolean> = {
      nombres: f.nombres.trim(),
      apellido_paterno: f.apellido_paterno.trim(),
      apellido_materno: f.apellido_materno.trim(),
    }
    if (f.password) {
      body.password = f.password
      body.password_confirm = f.password_confirm
    }
    await api.patch(`/core/plataforma/superusuarios/${editingId.value}/`, body)
    showModal.value = false
    await load()
  } catch (e: unknown) {
    const ax = e as { response?: { data?: unknown } }
    formErr.value = drfToMsg(ax.response?.data)
  } finally {
    saving.value = false
  }
}

async function inactivar(u: SuperRow) {
  const mail = u.email || u.username || 'este usuario'
  if (
    !confirm(
      `¿Desactivar la cuenta de ${mail}? No podrá iniciar sesión hasta que usted la reactive. El registro no se elimina.`,
    )
  ) {
    return
  }
  err.value = ''
  try {
    await api.patch(`/core/plataforma/superusuarios/${u.id}/`, { is_active: false })
    await load()
  } catch (e: unknown) {
    const ax = e as { response?: { data?: unknown } }
    err.value = drfToMsg(ax.response?.data)
  }
}

async function activar(u: SuperRow) {
  err.value = ''
  try {
    await api.patch(`/core/plataforma/superusuarios/${u.id}/`, { is_active: true })
    await load()
  } catch (e: unknown) {
    const ax = e as { response?: { data?: unknown } }
    err.value = drfToMsg(ax.response?.data)
  }
}

onMounted(load)

function fmtDate(v?: string | null): string {
  if (!v) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v)
  if (!m) return v.slice(0, 10)
  return `${m[3]}/${m[2]}/${m[1]}`
}

function cell(v?: string): string {
  const s = (v ?? '').trim()
  return s || '—'
}
</script>

<template>
  <div class="page">
    <header class="head">
      <div class="head-text">
        <h1 class="title">Superusuarios de la plataforma</h1>
        <p class="lead">
          Personas con acceso total a la gestión global (todas las empresas). Desde aquí las da de alta,
          edita o desactiva. Los usuarios que solo pertenecen a un cliente se administran al abrir el panel
          de esa empresa.
        </p>
      </div>
      <div class="head-actions">
        <button type="button" class="btn-add" @click="openModal">Nuevo superusuario</button>
        <button type="button" class="btn-ref" :disabled="loading" @click="load">
          {{ loading ? '…' : 'Actualizar lista' }}
        </button>
      </div>
    </header>

    <p v-if="err" class="err">{{ err }}</p>

    <div class="card">
      <div class="table-wrap">
        <div v-if="loading" class="muted">Cargando…</div>
        <table v-else class="table">
          <thead>
            <tr>
              <th>Correo / usuario</th>
              <th>Apellido paterno</th>
              <th>Apellido materno</th>
              <th>Nombres</th>
              <th>Activo</th>
              <th>Alta</th>
              <th>Último acceso</th>
              <th class="th-actions">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in rows" :key="u.id">
              <td class="td-strong">{{ u.email || u.username || '—' }}</td>
              <td>{{ cell(u.apellido_paterno) }}</td>
              <td>{{ cell(u.apellido_materno) }}</td>
              <td>{{ cell(u.nombres) }}</td>
              <td>
                <span class="pill" :class="u.is_active ? 'pill--ok' : 'pill--off'">{{
                  u.is_active ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-muted">{{ fmtDate(u.date_joined) }}</td>
              <td class="td-muted">{{ fmtDate(u.last_login ?? undefined) }}</td>
              <td class="td-actions">
                <div class="act-icons" role="group" :aria-label="`Acciones para ${u.email || u.username}`">
                  <button
                    type="button"
                    class="icon-act icon-act--edit"
                    title="Editar"
                    aria-label="Editar usuario"
                    @click="openEdit(u)"
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
                    v-if="u.is_active"
                    type="button"
                    class="icon-act icon-act--off"
                    title="Desactivar cuenta (no borra el usuario)"
                    aria-label="Desactivar cuenta"
                    @click="inactivar(u)"
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
                  <button
                    v-else
                    type="button"
                    class="icon-act icon-act--on"
                    title="Volver a activar la cuenta"
                    aria-label="Activar cuenta"
                    @click="activar(u)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path
                        stroke="currentColor"
                        stroke-width="1.75"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!loading && !rows.length" class="muted inner">No hay superusuarios que mostrar.</p>
    </div>

    <Teleport to="body">
      <div
        v-if="showModal"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeModal"
      >
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="sup-modal-title">
          <h2 id="sup-modal-title" class="modal-title">
            {{ modalMode === 'create' ? 'Nuevo superusuario' : 'Editar superusuario' }}
          </h2>
          <p v-if="modalMode === 'create'" class="modal-lead">
            Tendrá acceso a toda la plataforma. El correo será su usuario de acceso (al entrar, deje el RUC
            en blanco si aplica).
          </p>
          <p v-else class="modal-lead">
            Modifique nombres o contraseña. El correo de acceso no se puede cambiar desde esta pantalla.
          </p>
          <p v-if="formErr" class="form-err">{{ formErr }}</p>
          <label class="field">
            <span class="lab">Correo electrónico</span>
            <input
              v-model="form.email"
              type="email"
              class="inp"
              :disabled="modalMode === 'edit'"
              autocomplete="off"
            />
          </label>
          <label class="field">
            <span class="lab">Apellido paterno</span>
            <input v-model="form.apellido_paterno" type="text" class="inp" autocomplete="off" />
          </label>
          <label class="field">
            <span class="lab">Apellido materno</span>
            <input v-model="form.apellido_materno" type="text" class="inp" autocomplete="off" />
          </label>
          <label class="field">
            <span class="lab">Nombres</span>
            <input v-model="form.nombres" type="text" class="inp" autocomplete="off" />
          </label>
          <label class="field">
            <span class="lab">Contraseña</span>
            <input v-model="form.password" type="password" class="inp" autocomplete="new-password" />
            <span v-if="modalMode === 'edit'" class="field-hint">
              Si no desea cambiar la contraseña, deje estos campos vacíos.
            </span>
          </label>
          <label class="field">
            <span class="lab">Confirmar contraseña</span>
            <input
              v-model="form.password_confirm"
              type="password"
              class="inp"
              autocomplete="new-password"
            />
          </label>
          <div class="modal-actions">
            <button type="button" class="btn-ref" :disabled="saving" @click="closeModal">Cancelar</button>
            <button type="button" class="btn-add" :disabled="saving" @click="submitModal">
              {{
                saving
                  ? 'Guardando…'
                  : modalMode === 'create'
                    ? 'Crear superusuario'
                    : 'Guardar cambios'
              }}
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
  max-width: 1100px;
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.head-text {
  flex: 1;
  min-width: 220px;
}

.head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
}

.lead {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  color: #64748b;
  line-height: 1.45;
}

.lead code {
  font-size: 0.78rem;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  background: #f1f5f9;
  color: #475569;
}

.btn-ref {
  padding: 0.45rem 0.9rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
}

.btn-ref:hover:not(:disabled) {
  border-color: #0e7490;
  color: #0e7490;
}

.btn-ref:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-add {
  padding: 0.45rem 0.9rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  font-size: 0.8rem;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
}

.btn-add:hover:not(:disabled) {
  background: #0f766e;
  border-color: #0f766e;
}

.btn-add:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.err {
  color: #b91c1c;
  font-size: 0.875rem;
  margin: 0 0 0.75rem;
}

.card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  overflow: hidden;
}

.table-wrap {
  overflow-x: auto;
}

.table {
  width: 100%;
  min-width: 880px;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.th-actions {
  width: 1%;
  white-space: nowrap;
}

.td-actions {
  white-space: nowrap;
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

.icon-act--edit {
  color: #0e7490;
  border-color: rgba(14, 116, 144, 0.35);
}

.icon-act--edit:hover {
  background: rgba(14, 116, 144, 0.08);
  border-color: #0e7490;
  color: #115e59;
}

.icon-act--off {
  color: #b91c1c;
  border-color: rgba(185, 28, 28, 0.35);
}

.icon-act--off:hover {
  background: rgba(185, 28, 28, 0.08);
  border-color: #b91c1c;
  color: #991b1b;
}

.icon-act--on {
  color: #15803d;
  border-color: rgba(21, 128, 61, 0.35);
}

.icon-act--on:hover {
  background: rgba(21, 128, 61, 0.08);
  border-color: #15803d;
  color: #166534;
}

.field-hint {
  font-size: 0.72rem;
  color: #64748b;
  margin-top: 0.15rem;
}

.table th,
.table td {
  padding: 0.65rem 0.85rem;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
}

.table th {
  background: #f8fafc;
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.td-strong {
  font-weight: 600;
  color: #0f172a;
}

.td-muted {
  color: #64748b;
  font-size: 0.82rem;
}

.pill {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
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
  padding: 1.25rem;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.45);
}

.modal-card {
  width: 100%;
  max-width: 420px;
  padding: 1.25rem 1.35rem;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 20px 50px rgb(15 23 42 / 18%);
}

.modal-title {
  margin: 0 0 0.35rem;
  font-size: 1.15rem;
  font-weight: 700;
  color: #0f172a;
}

.modal-lead {
  margin: 0 0 1rem;
  font-size: 0.82rem;
  color: #64748b;
  line-height: 1.4;
}

.form-err {
  margin: 0 0 0.75rem;
  font-size: 0.82rem;
  color: #b91c1c;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.75rem;
}

.lab {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
}

.inp {
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 0.875rem;
}

.inp:focus {
  outline: none;
  border-color: #0e7490;
  box-shadow: 0 0 0 2px rgba(14, 116, 144, 0.2);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>
