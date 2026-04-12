<script setup lang="ts">
import type { AxiosResponse } from 'axios'
import axios from 'axios'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type EmpresaRow = {
  id: number
  razon_social?: string
  ruc?: string
  activo?: boolean
  registro_aprobado?: boolean
  telefono_contacto?: string
  apellido_paterno?: string
  apellido_materno?: string
  nombres?: string
}

type SucursalRow = {
  id: number
  nombre?: string
  direccion?: string
  activo?: boolean
  empresa?: number
  empresa_razon_social?: string
}

type Paginated<T> = { results?: T[]; next?: string | null }

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const empresas = ref<EmpresaRow[]>([])
const sucursales = ref<SucursalRow[]>([])
const loadingEmp = ref(true)
const loadingSuc = ref(true)
const err = ref('')
const exporting = ref(false)
const rowBusyEmp = ref<number | null>(null)
const rowBusySuc = ref<number | null>(null)

const showEmpModal = ref(false)
const showSucModal = ref(false)
const savingEmp = ref(false)
const savingSuc = ref(false)
const formEmpErr = ref('')
const formSucErr = ref('')
const editingEmpId = ref<number | null>(null)
const editingSucId = ref<number | null>(null)

const formEmp = ref({
  razon_social: '',
  ruc: '',
  telefono_contacto: '',
  activo: true,
  registro_aprobado: true,
})

const formSuc = ref({
  empresa: null as number | null,
  nombre: '',
  direccion: '',
  activo: true,
})

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

function drfRelativePath(next: string): string {
  const u = new URL(next)
  const idx = u.pathname.indexOf('/api/v1/')
  if (idx >= 0) return u.pathname.slice(idx + '/api/v1'.length) + u.search
  return u.pathname + u.search
}

async function fetchAllPages<T>(basePath: string): Promise<T[]> {
  const acc: T[] = []
  let path: string | null = `${basePath}${basePath.includes('?') ? '&' : '?'}page_size=500`
  while (path) {
    const res: AxiosResponse<T[] | Paginated<T>> = await api.get<T[] | Paginated<T>>(path)
    const data = res.data
    const chunk: T[] = Array.isArray(data) ? data : (data.results ?? [])
    acc.push(...chunk)
    const nextUrl: string | null =
      !Array.isArray(data) && typeof data.next === 'string' && data.next ? data.next : null
    path = nextUrl ? drfRelativePath(nextUrl) : null
  }
  return acc
}

async function loadEmpresas() {
  loadingEmp.value = true
  err.value = ''
  try {
    empresas.value = await fetchAllPages<EmpresaRow>('/core/empresas/')
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el listado de empresas')
    empresas.value = []
  } finally {
    loadingEmp.value = false
  }
}

async function loadSucursales() {
  loadingSuc.value = true
  err.value = ''
  try {
    sucursales.value = await fetchAllPages<SucursalRow>('/core/sucursales/')
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el listado de sucursales')
    sucursales.value = []
  } finally {
    loadingSuc.value = false
  }
}

function loadAll() {
  void loadEmpresas()
  void loadSucursales()
}

onMounted(() => {
  loadAll()
})

function escapeCsvCell(s: string): string {
  if (/[;"\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function boolTxt(v: unknown): string {
  if (v === true) return 'Sí'
  if (v === false) return 'No'
  return ''
}

function pad(n: number) {
  return String(n).padStart(2, '0')
}

async function descargarCsvTodo() {
  exporting.value = true
  err.value = ''
  try {
    const [eRows, sRows] = await Promise.all([
      fetchAllPages<EmpresaRow>('/core/empresas/'),
      fetchAllPages<SucursalRow>('/core/sucursales/'),
    ])
    const sep = ';'
    const lines: string[] = []
    lines.push(escapeCsvCell('EMPRESAS'))
    lines.push(['Razón social', 'RUC', 'Activo', 'Reg. aprobado', 'Teléfono contacto'].map(escapeCsvCell).join(sep))
    for (const r of eRows) {
      lines.push(
        [
          (r.razon_social || '').trim(),
          (r.ruc || '').trim(),
          boolTxt(r.activo),
          boolTxt(r.registro_aprobado),
          (r.telefono_contacto || '').trim(),
        ]
          .map((x) => escapeCsvCell(String(x)))
          .join(sep),
      )
    }
    lines.push('')
    lines.push(escapeCsvCell('SUCURSALES'))
    lines.push(['Nombre', 'Empresa', 'Empresa ID', 'Activo', 'Dirección'].map(escapeCsvCell).join(sep))
    for (const r of sRows) {
      lines.push(
        [
          (r.nombre || '').trim(),
          (r.empresa_razon_social || '').trim(),
          r.empresa != null ? String(r.empresa) : '',
          boolTxt(r.activo),
          (r.direccion || '').trim(),
        ]
          .map((x) => escapeCsvCell(String(x)))
          .join(sep),
      )
    }
    const bom = '\uFEFF'
    const blob = new Blob([bom + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    const d = new Date()
    a.href = URL.createObjectURL(blob)
    a.download = `organizacion_${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'la exportación')
  } finally {
    exporting.value = false
  }
}

function closeEmpModal() {
  showEmpModal.value = false
}

function closeSucModal() {
  showSucModal.value = false
}

function openEditEmpresa(r: EmpresaRow) {
  editingEmpId.value = r.id
  formEmpErr.value = ''
  formEmp.value = {
    razon_social: (r.razon_social || '').trim(),
    ruc: (r.ruc || '').trim(),
    telefono_contacto: (r.telefono_contacto || '').trim(),
    activo: r.activo !== false,
    registro_aprobado: r.registro_aprobado !== false,
  }
  showEmpModal.value = true
}

async function guardarEmpresa() {
  formEmpErr.value = ''
  const f = formEmp.value
  if (!f.razon_social.trim()) {
    formEmpErr.value = 'La razón social es obligatoria.'
    return
  }
  if (editingEmpId.value == null) return
  savingEmp.value = true
  try {
    const body: Record<string, unknown> = {
      razon_social: f.razon_social.trim().slice(0, 255),
      ruc: f.ruc.trim().slice(0, 11),
      telefono_contacto: f.telefono_contacto.trim().slice(0, 30),
      activo: f.activo,
    }
    if (isSuperuser.value) {
      body.registro_aprobado = f.registro_aprobado
    }
    await api.patch(`/core/empresas/${editingEmpId.value}/`, body)
    showEmpModal.value = false
    await loadEmpresas()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      formEmpErr.value = drfMsg(e.response.data)
    } else {
      formEmpErr.value = 'Error de conexión.'
    }
  } finally {
    savingEmp.value = false
  }
}

async function inactivarEmpresa(r: EmpresaRow) {
  if (r.activo === false) return
  const nombre = (r.razon_social || '').trim() || `ID ${r.id}`
  const ok = window.confirm(
    `¿Desactivar la empresa «${nombre}»? Es una baja lógica: puede reactivarla desde Editar.`,
  )
  if (!ok) return
  rowBusyEmp.value = r.id
  err.value = ''
  try {
    await api.patch(`/core/empresas/${r.id}/`, { activo: false })
    await loadEmpresas()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo desactivar la empresa.'
    }
  } finally {
    rowBusyEmp.value = null
  }
}

/** Superusuario sin empresa en barra: hace falta el desplegable y el listado de empresas cargado. */
const nuevaSucursalDeshabilitada = computed(() => {
  if (!isSuperuser.value) return false
  if (empresaId.value) return false
  return empresas.value.length === 0
})

function openNuevaSucursal() {
  if (nuevaSucursalDeshabilitada.value) return
  editingSucId.value = null
  formSucErr.value = ''
  const soloUna = empresas.value.length === 1 ? empresas.value[0] : undefined
  const preEmp: number | null =
    isSuperuser.value && !empresaId.value && soloUna != null ? soloUna.id : null
  formSuc.value = {
    empresa: preEmp,
    nombre: '',
    direccion: '',
    activo: true,
  }
  showSucModal.value = true
}

function openEditSucursal(r: SucursalRow) {
  editingSucId.value = r.id
  formSucErr.value = ''
  formSuc.value = {
    empresa: typeof r.empresa === 'number' ? r.empresa : null,
    nombre: (r.nombre || '').trim(),
    direccion: (r.direccion || '').trim(),
    activo: r.activo !== false,
  }
  showSucModal.value = true
}

async function guardarSucursal() {
  formSucErr.value = ''
  const f = formSuc.value
  if (!f.nombre.trim()) {
    formSucErr.value = 'El nombre de la sucursal es obligatorio.'
    return
  }
  let empresaPost: number | undefined
  if (editingSucId.value == null && isSuperuser.value) {
    if (empresaId.value) {
      empresaPost = Number(empresaId.value)
    } else if (typeof f.empresa === 'number' && Number.isFinite(f.empresa)) {
      empresaPost = f.empresa
    }
    if (empresaPost == null || !Number.isFinite(empresaPost)) {
      formSucErr.value = 'Seleccione la empresa a la que pertenece la sucursal.'
      return
    }
  }
  savingSuc.value = true
  try {
    if (editingSucId.value == null) {
      const body: Record<string, unknown> = {
        nombre: f.nombre.trim().slice(0, 120),
        direccion: f.direccion.trim(),
        activo: f.activo,
      }
      if (isSuperuser.value && empresaPost != null) {
        body.empresa = empresaPost
      }
      await api.post('/core/sucursales/', body)
    } else {
      await api.patch(`/core/sucursales/${editingSucId.value}/`, {
        nombre: f.nombre.trim().slice(0, 120),
        direccion: f.direccion.trim(),
        activo: f.activo,
      })
    }
    showSucModal.value = false
    await loadSucursales()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      formSucErr.value = drfMsg(e.response.data)
    } else {
      formSucErr.value = 'Error de conexión.'
    }
  } finally {
    savingSuc.value = false
  }
}

async function inactivarSucursal(r: SucursalRow) {
  if (r.activo === false) return
  const nombre = (r.nombre || '').trim() || `ID ${r.id}`
  const ok = window.confirm(
    `¿Desactivar la sucursal «${nombre}»? Es una baja lógica: puede reactivarla desde Editar.`,
  )
  if (!ok) return
  rowBusySuc.value = r.id
  err.value = ''
  try {
    await api.patch(`/core/sucursales/${r.id}/`, { activo: false })
    await loadSucursales()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo desactivar la sucursal.'
    }
  } finally {
    rowBusySuc.value = null
  }
}
</script>

<template>
  <div class="page">
    <header class="head">
      <div class="head-text">
        <h1 class="title">Empresa y sucursales</h1>
        <p class="lead">
          Revise y mantenga los datos de <strong>contribuyente (empresa)</strong> y los
          <strong>locales o puntos de venta</strong>. Use la sección inferior para actualizar listados y exportar a
          Excel (CSV), crear sucursales y aplicar baja lógica sin borrar el historial.
        </p>
      </div>
    </header>

    <p v-if="err" class="err">{{ err }}</p>

    <section class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">Empresas</h2>
          <p class="card-sub">
            Listado de empresas registradas. «Activo» y «Reg. aprobado» indican si la empresa puede operar en el sistema.
          </p>
        </div>
      </div>
      <div v-if="loadingEmp" class="muted inner">Cargando…</div>
      <div v-else class="table-wrap">
        <table class="t">
          <thead>
            <tr>
              <th>Razón social</th>
              <th>RUC</th>
              <th class="th-c">Activo</th>
              <th class="th-c">Reg. aprobado</th>
              <th class="th-act">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in empresas" :key="r.id">
              <td class="td-strong">{{ r.razon_social?.trim() || '—' }}</td>
              <td><code class="code">{{ r.ruc?.trim() || '—' }}</code></td>
              <td class="td-c">
                <span class="pill" :class="r.activo !== false ? 'pill--ok' : 'pill--off'">{{
                  r.activo !== false ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-c">
                <span class="pill" :class="r.registro_aprobado !== false ? 'pill--ok' : 'pill--off'">{{
                  r.registro_aprobado !== false ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-act">
                <div class="act-icons" role="group" :aria-label="`Acciones empresa ${r.id}`">
                  <button
                    type="button"
                    class="icon-act icon-act--edit"
                    title="Editar"
                    @click="openEditEmpresa(r)"
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
                    :disabled="rowBusyEmp === r.id"
                    @click="inactivarEmpresa(r)"
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
        <p v-if="!empresas.length" class="muted inner">No hay empresas registradas o no tiene permiso para verlas.</p>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">Sucursales</h2>
          <p class="card-sub">
            Locales o puntos de venta. Cada fila pertenece a la empresa indicada en la columna Empresa.
          </p>
        </div>
        <div class="card-actions">
          <button
            type="button"
            class="btn-add"
            :disabled="loadingSuc || nuevaSucursalDeshabilitada"
            :title="
              nuevaSucursalDeshabilitada
                ? 'Elija una empresa en la barra o espere a cargar el listado de empresas'
                : 'Registrar una nueva sucursal'
            "
            @click="openNuevaSucursal"
          >
            + Nueva sucursal
          </button>
          <button
            type="button"
            class="btn-excel btn-excel--sm"
            :disabled="loadingEmp || loadingSuc || exporting"
            title="Descargar empresas y sucursales (Excel / CSV)"
            aria-label="Exportar organización a Excel"
            @click="descargarCsvTodo"
          >
            <svg class="btn-excel__ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                fill="#217346"
                d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
              />
              <path stroke="#fff" stroke-width="1.2" stroke-linecap="round" d="M14 2v6h6M8 10h8M8 14h8M8 18h5" />
            </svg>
          </button>
          <button
            type="button"
            class="btn-ref"
            :disabled="loadingEmp || loadingSuc"
            @click="loadAll"
          >
            {{ loadingEmp || loadingSuc ? '…' : 'Actualizar' }}
          </button>
        </div>
      </div>
      <p v-if="isSuperuser && !empresaId && !loadingEmp && !empresas.length" class="warn inner">
        No hay empresas visibles: no puede dar de alta sucursales hasta que exista al menos una empresa o elija una en
        la barra superior.
      </p>
      <div v-if="loadingSuc" class="muted inner">Cargando…</div>
      <div v-else class="table-wrap">
        <table class="t">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Empresa</th>
              <th>Dirección</th>
              <th class="th-c">Activo</th>
              <th class="th-act">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in sucursales" :key="r.id">
              <td class="td-strong">{{ r.nombre?.trim() || '—' }}</td>
              <td>{{ r.empresa_razon_social?.trim() || '—' }}</td>
              <td class="td-dir">{{ (r.direccion || '').trim() || '—' }}</td>
              <td class="td-c">
                <span class="pill" :class="r.activo !== false ? 'pill--ok' : 'pill--off'">{{
                  r.activo !== false ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-act">
                <div class="act-icons" role="group" :aria-label="`Acciones sucursal ${r.id}`">
                  <button type="button" class="icon-act icon-act--edit" title="Editar" @click="openEditSucursal(r)">
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
                    :disabled="rowBusySuc === r.id"
                    @click="inactivarSucursal(r)"
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
        <p v-if="!sucursales.length" class="muted inner">No hay sucursales o no tiene permiso para verlas.</p>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="showEmpModal" class="backdrop" @click.self="closeEmpModal">
        <div class="modal" role="dialog" aria-modal="true">
          <h2 class="mt">Editar empresa</h2>
          <p v-if="formEmpErr" class="form-err">{{ formEmpErr }}</p>
          <label class="field">
            <span class="lab">Razón social</span>
            <input v-model="formEmp.razon_social" class="inp" maxlength="255" autocomplete="organization" />
          </label>
          <label class="field">
            <span class="lab">RUC</span>
            <input v-model="formEmp.ruc" class="inp" maxlength="11" autocomplete="off" />
          </label>
          <label class="field">
            <span class="lab">Teléfono de contacto</span>
            <input v-model="formEmp.telefono_contacto" class="inp" maxlength="30" autocomplete="tel" />
          </label>
          <label class="check">
            <input v-model="formEmp.activo" type="checkbox" />
            <span>Activa</span>
          </label>
          <label v-if="isSuperuser" class="check">
            <input v-model="formEmp.registro_aprobado" type="checkbox" />
            <span>Registro aprobado</span>
          </label>
          <div class="modal-actions">
            <button type="button" class="btn-cancel" @click="closeEmpModal">Cancelar</button>
            <button type="button" class="btn-save" :disabled="savingEmp" @click="guardarEmpresa">
              {{ savingEmp ? '…' : 'Guardar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showSucModal" class="backdrop" @click.self="closeSucModal">
        <div class="modal" role="dialog" aria-modal="true">
          <h2 class="mt">{{ editingSucId == null ? 'Nueva sucursal' : 'Editar sucursal' }}</h2>
          <p v-if="formSucErr" class="form-err">{{ formSucErr }}</p>
          <label v-if="isSuperuser && editingSucId == null && !empresaId" class="field">
            <span class="lab">Empresa</span>
            <select v-model="formSuc.empresa" class="inp inp--select">
              <option disabled :value="null">Seleccione…</option>
              <option v-for="e in empresas" :key="e.id" :value="e.id">{{ e.razon_social?.trim() || `ID ${e.id}` }}</option>
            </select>
          </label>
          <p v-if="isSuperuser && editingSucId == null && empresaId" class="ctx-hint">
            La sucursal se asociará a la empresa seleccionada en la barra superior.
          </p>
          <label class="field">
            <span class="lab">Nombre</span>
            <input v-model="formSuc.nombre" class="inp" maxlength="120" autocomplete="off" />
          </label>
          <label class="field">
            <span class="lab">Dirección</span>
            <textarea v-model="formSuc.direccion" class="inp inp--area" rows="3" />
          </label>
          <label class="check">
            <input v-model="formSuc.activo" type="checkbox" />
            <span>Activa</span>
          </label>
          <div class="modal-actions">
            <button type="button" class="btn-cancel" @click="closeSucModal">Cancelar</button>
            <button type="button" class="btn-save" :disabled="savingSuc" @click="guardarSucursal">
              {{ savingSuc ? '…' : 'Guardar' }}
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
  max-width: 1200px;
  color: #0f172a;
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

.btn-add {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #f0fdfa;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  font-family: inherit;
  color: #0f766e;
}

.btn-add:hover:not(:disabled) {
  background: #ccfbf1;
}

.btn-add:disabled {
  opacity: 0.5;
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

.btn-excel--sm {
  width: 2rem;
  height: 2rem;
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

.btn-excel--sm .btn-excel__ico {
  width: 1.05rem;
  height: 1.05rem;
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

.warn {
  font-size: 0.85rem;
  color: #9a3412;
  background: #ffedd5;
  border: 1px solid #fdba74;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  margin: 0 1rem 0.75rem;
}

.card {
  background: #fff;
  border-radius: 12px;
  margin-bottom: 1.25rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.card-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1.1rem 1.25rem 0.85rem;
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(180deg, #fafbfc 0%, #fff 100%);
}

.card-title {
  margin: 0 0 0.25rem;
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.card-sub {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.5;
  color: #64748b;
  max-width: 40rem;
}

.card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
}

.table-wrap {
  overflow-x: auto;
  min-height: 5rem;
}

.t {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.t th,
.t td {
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid #e8edf3;
  text-align: left;
  color: #0f172a;
}

.t th {
  background: #f1f5f9;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #475569;
}

.t td {
  font-weight: 500;
  font-size: 0.8125rem;
}

.t tbody tr:hover {
  background: #f8fafc;
}

.th-c,
.td-c {
  text-align: center;
  vertical-align: middle;
}

.th-act {
  width: 5.5rem;
  white-space: nowrap;
  text-align: center;
}

.td-act {
  vertical-align: middle;
  text-align: center;
}

.td-strong {
  font-weight: 600;
  color: #0f172a;
}

.td-dir {
  max-width: 16rem;
  word-break: break-word;
  color: #475569;
  font-size: 0.8rem;
  line-height: 1.4;
}

.act-icons {
  display: inline-flex;
  align-items: center;
  justify-content: center;
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

.code {
  background: #e2e8f0;
  color: #0f172a;
  padding: 0.12rem 0.35rem;
  border-radius: 4px;
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
  color: #94a3b8;
  text-align: center;
}

.inner {
  padding: 1.25rem 1rem;
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
  padding: 1.25rem 1.35rem;
  max-width: 26rem;
  width: 100%;
  box-shadow: 0 20px 50px rgb(15 23 42 / 18%);
  border: 1px solid #e2e8f0;
}

.mt {
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
  font-weight: 800;
}

.form-err {
  color: #b91c1c;
  font-size: 0.84rem;
  margin: 0 0 0.65rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.75rem;
}

.lab {
  font-size: 0.78rem;
  font-weight: 600;
  color: #475569;
}

.inp {
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 0.875rem;
  font-family: inherit;
}

.inp--select {
  cursor: pointer;
}

.inp--area {
  resize: vertical;
  min-height: 4rem;
}

.ctx-hint {
  margin: 0 0 0.75rem;
  font-size: 0.82rem;
  color: #64748b;
  line-height: 1.45;
}

.check {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.65rem;
  font-size: 0.875rem;
  color: #334155;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.btn-cancel {
  padding: 0.4rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  font-family: inherit;
}

.btn-save {
  padding: 0.4rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  color: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  font-family: inherit;
}

.btn-save:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
