<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { fetchAllPages } from '@/utils/fetchAllPages'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

type Row = {
  id: number
  nombre: string
  codigo?: string
  unidad_medida?: number
  unidad_medida_codigo?: string
  categoria?: number | null
  marca?: number | null
  es_servicio?: boolean
  activo?: boolean
}

type MaestroOpt = { id: number; nombre: string; codigo?: string }

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const rows = ref<Row[]>([])
const unidades = ref<MaestroOpt[]>([])
const categorias = ref<MaestroOpt[]>([])
const marcas = ref<MaestroOpt[]>([])
const loading = ref(true)
const err = ref('')
const filtroNombre = ref('')
const filtroCodigo = ref('')

const importInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const importMsg = ref('')
const importErr = ref('')

const showModal = ref(false)
const saving = ref(false)
const formErr = ref('')
const editingId = ref<number | null>(null)
const form = ref({
  codigo: '',
  nombre: '',
  unidad_medida_id: '' as number | '',
  categoria_id: '' as number | '',
  marca_id: '' as number | '',
  es_servicio: false,
  activo: true,
})

const rowBusy = ref<number | null>(null)

const filtradas = computed(() => {
  const n = filtroNombre.value.trim().toLowerCase()
  const c = filtroCodigo.value.trim().toLowerCase()
  return rows.value.filter((r) => {
    if (n && !r.nombre.toLowerCase().includes(n)) return false
    if (c && !(r.codigo || '').toLowerCase().includes(c)) return false
    return true
  })
})

const importBloqueado = computed(
  () => isSuperuser.value && !empresaId.value,
)

const unidadesOrdenadas = computed(() =>
  [...unidades.value].sort((a, b) => (a.codigo || '').localeCompare(b.codigo || '', 'es')),
)

async function loadMaestros() {
  try {
    const [u, c, m] = await Promise.all([
      api.get<{ results?: MaestroOpt[] }>('/inventario/unidades-medida/?page_size=500&ordering=codigo'),
      api.get<{ results?: MaestroOpt[] }>('/inventario/categorias/?page_size=500&ordering=nombre'),
      api.get<{ results?: MaestroOpt[] }>('/inventario/marcas/?page_size=500&ordering=nombre'),
    ])
    unidades.value = Array.isArray(u.data) ? u.data : (u.data.results ?? [])
    categorias.value = Array.isArray(c.data) ? c.data : (c.data.results ?? [])
    marcas.value = Array.isArray(m.data) ? m.data : (m.data.results ?? [])
  } catch {
    /* maestros opcionales para el modal */
  }
}

function itemsListPath() {
  const params = new URLSearchParams({ ordering: 'nombre' })
  if (isSuperuser.value && empresaId.value) {
    params.set('empresa', String(empresaId.value))
  }
  return `/inventario/items/?${params}`
}

async function fetchRows() {
  rows.value = await fetchAllPages<Row>(itemsListPath())
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    await fetchRows()
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el catálogo de productos y servicios')
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  loading.value = true
  err.value = ''
  try {
    await Promise.all([fetchRows(), loadMaestros()])
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'el catálogo o los maestros asociados')
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

async function descargarPlantilla() {
  err.value = ''
  try {
    const { data } = await api.get('/inventario/items/plantilla-excel/', { responseType: 'blob' })
    const blob = new Blob([data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'plantilla_productos_servicios.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    err.value = 'No se pudo descargar la plantilla.'
  }
}

function abrirSelectorImport() {
  importMsg.value = ''
  importErr.value = ''
  if (importBloqueado.value) return
  importInput.value?.click()
}

async function onImportFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (importBloqueado.value) return

  const fd = new FormData()
  fd.append('file', file)
  if (isSuperuser.value && empresaId.value) {
    fd.append('empresa', empresaId.value)
  }

  importing.value = true
  importMsg.value = ''
  importErr.value = ''
  err.value = ''
  try {
    const { data } = await api.post<{
      creados: number
      actualizados: number
      errores: { fila: number; mensaje: string }[]
    }>('/inventario/items/importar-excel/', fd)

    await load()
    importMsg.value = `Listo: ${data.creados} creados, ${data.actualizados} actualizados. Catálogo: ${rows.value.length} ítem(s).`
    if (data.errores?.length) {
      importErr.value = data.errores
        .map((e) => `Fila ${e.fila}: ${e.mensaje}`)
        .join('\n')
    }
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data
      if (d instanceof Blob) {
        importErr.value = 'Error al importar (revise el archivo).'
      } else {
        importErr.value = drfMsg(d)
      }
    } else {
      importErr.value = 'Error de conexión al importar.'
    }
  } finally {
    importing.value = false
  }
}

function openNuevo() {
  if (importBloqueado.value) return
  editingId.value = null
  formErr.value = ''
  const firstUm = unidadesOrdenadas.value[0]
  form.value = {
    codigo: '',
    nombre: '',
    unidad_medida_id: firstUm ? firstUm.id : '',
    categoria_id: '',
    marca_id: '',
    es_servicio: false,
    activo: true,
  }
  showModal.value = true
}

async function openEdit(r: Row) {
  editingId.value = r.id
  formErr.value = ''
  try {
    const { data } = await api.get<{
      codigo?: string
      nombre?: string
      unidad_medida?: number
      categoria?: number | null
      marca?: number | null
      es_servicio?: boolean
      activo?: boolean
    }>(`/inventario/items/${r.id}/`)
    form.value = {
      codigo: (data.codigo ?? '').toString(),
      nombre: (data.nombre ?? '').toString(),
      unidad_medida_id: data.unidad_medida != null ? data.unidad_medida : '',
      categoria_id: data.categoria != null ? data.categoria : '',
      marca_id: data.marca != null ? data.marca : '',
      es_servicio: Boolean(data.es_servicio),
      activo: data.activo !== false,
    }
    showModal.value = true
  } catch {
    err.value = 'No se pudo cargar el ítem para editar.'
  }
}

function closeModal() {
  if (!saving.value) showModal.value = false
}

async function guardar() {
  formErr.value = ''
  const f = form.value
  if (!f.nombre.trim()) {
    formErr.value = 'El nombre es obligatorio.'
    return
  }
  if (f.unidad_medida_id === '') {
    formErr.value = 'Seleccione una unidad de medida.'
    return
  }
  saving.value = true
  try {
    const body: Record<string, unknown> = {
      codigo: f.codigo.trim().slice(0, 50),
      nombre: f.nombre.trim(),
      unidad_medida: f.unidad_medida_id,
      categoria: f.categoria_id === '' ? null : f.categoria_id,
      marca: f.marca_id === '' ? null : f.marca_id,
      es_servicio: f.es_servicio,
      activo: f.activo,
    }
    if (editingId.value == null && isSuperuser.value && empresaId.value) {
      body.empresa = Number(empresaId.value)
    }
    if (editingId.value == null) {
      await api.post('/inventario/items/', body)
    } else {
      await api.patch(`/inventario/items/${editingId.value}/`, body)
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
    `¿Inactivar «${r.nombre}»? No se elimina de la base de datos; puede reactivarlo desde Editar.`,
  )
  if (!ok) return
  rowBusy.value = r.id
  err.value = ''
  try {
    await api.patch(`/inventario/items/${r.id}/`, { activo: false })
    await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo inactivar el ítem.'
    }
  } finally {
    rowBusy.value = null
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title">Productos y servicios</h1>
        <p class="lead">
          Ítems que puede usar en ventas e inventario: alta manual, descarga de plantilla Excel e importación masiva. La
          unidad de medida, categoría y marca deben estar definidas previamente en sus maestros.
        </p>
      </div>
      <div class="head-actions">
        <button
          type="button"
          class="btn-add"
          :disabled="loading || importBloqueado"
          :title="importBloqueado ? 'Seleccione empresa en la barra (modo plataforma)' : ''"
          @click="openNuevo"
        >
          + Nuevo ítem
        </button>
        <button type="button" class="btn-tpl" :disabled="loading" @click="descargarPlantilla">
          Descargar plantilla
        </button>
        <button
          type="button"
          class="btn-imp"
          :disabled="loading || importing || importBloqueado"
          :title="
            importBloqueado
              ? 'Seleccione una empresa en la barra superior (modo plataforma)'
              : 'Subir Excel .xlsx completado'
          "
          @click="abrirSelectorImport"
        >
          {{ importing ? 'Importando…' : 'Importar Excel' }}
        </button>
        <input
          ref="importInput"
          type="file"
          class="sr-only"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          @change="onImportFile"
        />
        <button type="button" class="btn-ref" :disabled="loading" @click="loadAll">
          {{ loading ? '…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="importBloqueado" class="warn">
      Modo administrador global sin empresa en contexto: elija una empresa en la barra superior para crear, importar o
      editar ítems.
    </p>
    <p v-if="importMsg" class="ok-msg">{{ importMsg }}</p>
    <p v-if="importErr" class="import-err">{{ importErr }}</p>
    <p v-if="err" class="err">{{ err }}</p>

    <div class="filters">
      <label class="f">
        <span class="flab">Nombre</span>
        <input v-model="filtroNombre" type="text" class="inp" placeholder="Filtrar…" />
      </label>
      <label class="f">
        <span class="flab">Código</span>
        <input v-model="filtroCodigo" type="text" class="inp" placeholder="Filtrar…" />
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
              <th>Nombre</th>
              <th>UM</th>
              <th>Servicio</th>
              <th>Activo</th>
              <th class="th-act">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in filtradas" :key="r.id">
              <td>
                <code class="code">{{ r.codigo?.trim() || '—' }}</code>
              </td>
              <td class="td-name">{{ r.nombre }}</td>
              <td>{{ r.unidad_medida_codigo?.trim() || '—' }}</td>
              <td>
                <span class="pill" :class="r.es_servicio ? 'pill--svc' : 'pill--prod'">{{
                  r.es_servicio ? 'Sí' : 'No'
                }}</span>
              </td>
              <td>
                <span class="pill" :class="r.activo !== false ? 'pill--ok' : 'pill--off'">{{
                  r.activo !== false ? 'Sí' : 'No'
                }}</span>
              </td>
              <td class="td-act">
                <div class="act-icons" role="group" :aria-label="`Acciones para ${r.nombre}`">
                  <button
                    type="button"
                    class="icon-act icon-act--edit"
                    title="Editar"
                    :aria-label="`Editar ${r.nombre}`"
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
                    title="Eliminar (inactivar)"
                    :aria-label="`Inactivar ${r.nombre}`"
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
        <p v-if="!filtradas.length" class="muted inner">Sin registros que coincidan.</p>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showModal" class="backdrop" @click.self="closeModal">
        <div class="modal" role="dialog" aria-modal="true">
          <h2 class="mt">{{ editingId == null ? 'Nuevo ítem' : 'Editar ítem' }}</h2>
          <p v-if="formErr" class="form-err">{{ formErr }}</p>
          <label class="field">
            <span class="lab">Código (opcional)</span>
            <input v-model="form.codigo" class="inp" maxlength="50" />
          </label>
          <label class="field">
            <span class="lab">Nombre</span>
            <input v-model="form.nombre" class="inp" maxlength="255" />
          </label>
          <label class="field">
            <span class="lab">Unidad de medida</span>
            <select v-model="form.unidad_medida_id" class="inp inp--select">
              <option v-for="u in unidadesOrdenadas" :key="u.id" :value="u.id">
                {{ u.codigo }} — {{ u.nombre }}
              </option>
            </select>
          </label>
          <label class="field">
            <span class="lab">Categoría (opcional)</span>
            <select v-model="form.categoria_id" class="inp inp--select">
              <option value="">— Sin categoría —</option>
              <option v-for="c in categorias" :key="c.id" :value="c.id">{{ c.nombre }}</option>
            </select>
          </label>
          <label class="field">
            <span class="lab">Marca (opcional)</span>
            <select v-model="form.marca_id" class="inp inp--select">
              <option value="">— Sin marca —</option>
              <option v-for="m in marcas" :key="m.id" :value="m.id">{{ m.nombre }}</option>
            </select>
          </label>
          <label class="field row-check">
            <input v-model="form.es_servicio" type="checkbox" />
            <span>Es servicio (no descuenta stock típico en ventas)</span>
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
  max-width: 1100px;
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
}
.btn-add:hover:not(:disabled) {
  filter: brightness(1.05);
}
.btn-add:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.btn-tpl {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #0369a1;
  background: #f0f9ff;
  color: #0369a1;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
}
.btn-tpl:hover:not(:disabled) {
  background: #e0f2fe;
}
.btn-imp {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  color: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
}
.btn-imp:hover:not(:disabled) {
  filter: brightness(1.05);
}
.btn-imp:disabled,
.btn-tpl:disabled {
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
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
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
.ok-msg {
  font-size: 0.85rem;
  color: #166534;
  margin: 0 0 0.35rem;
}
.import-err {
  font-size: 0.8rem;
  color: #b91c1c;
  white-space: pre-wrap;
  margin: 0 0 0.75rem;
  line-height: 1.4;
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
.code {
  background: #e2e8f0;
  color: #0f172a;
  padding: 0.12rem 0.35rem;
  border-radius: 4px;
  font-size: 0.82rem;
}
.td-name {
  font-weight: 600;
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
.pill--svc {
  background: #e0e7ff;
  color: #3730a3;
}
.pill--prod {
  background: #f1f5f9;
  color: #475569;
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
  max-width: 480px;
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
