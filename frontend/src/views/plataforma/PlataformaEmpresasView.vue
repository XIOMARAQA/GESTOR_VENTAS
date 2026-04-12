<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'

const NOTIF_REFRESH = 'gestor-refresh-notificaciones'

type EmpresaRow = {
  id: number
  razon_social?: string
  ruc?: string
  apellido_paterno?: string
  apellido_materno?: string
  nombres?: string
  telefono_contacto?: string
  activo?: boolean
  registro_aprobado?: boolean
  creado_en?: string
  fecha_registro_aprobado?: string | null
}

type TabKey = 'activas' | 'pendientes' | 'inactivas'

const route = useRoute()
const router = useRouter()
const ctx = useAppContextStore()

const allRows = ref<EmpresaRow[]>([])
const loading = ref(false)
const errorMsg = ref('')
const actionKey = ref<string | null>(null)

/** Tres rutas con nombre fijo (evita params con regex que en algunos casos no rellenan `seccion`). */
const tab = computed<TabKey>(() => {
  if (route.name === 'plataforma-empresas-pendientes') return 'pendientes'
  if (route.name === 'plataforma-empresas-inactivas') return 'inactivas'
  return 'activas'
})

const pageTitle = computed(() => {
  if (tab.value === 'activas') return 'Empresas activas'
  if (tab.value === 'pendientes') return 'Pendientes de aprobación'
  return 'Suspendidas o inactivas'
})

const pageLead = computed(() => {
  if (tab.value === 'activas') {
    return 'Clientes dados de alta y aprobados. Pulse una tarjeta para entrar a su sistema (soporte, revisión o gestión delegada).'
  }
  if (tab.value === 'pendientes') {
    return 'Registros web en espera de su decisión. Revise RUC, nombre o razón social y fecha; use Aprobar o Rechazar en cada tarjeta.'
  }
  return 'Empresas inactivas, rechazadas o suspendidas. Solo puede consultarlas; no operan en la plataforma hasta que cambie su estado.'
})

function esPendienteAccion(r: EmpresaRow): boolean {
  return r.registro_aprobado === false && r.activo !== false
}

function esActivaAprobada(r: EmpresaRow): boolean {
  return r.activo === true && r.registro_aprobado === true
}

function esInactiva(r: EmpresaRow): boolean {
  return r.activo === false
}

const rowsActivas = computed(() => allRows.value.filter(esActivaAprobada))
const rowsPendientes = computed(() => allRows.value.filter(esPendienteAccion))
const rowsInactivas = computed(() => allRows.value.filter(esInactiva))

const rows = computed(() => {
  if (tab.value === 'activas') return rowsActivas.value
  if (tab.value === 'pendientes') return rowsPendientes.value
  return rowsInactivas.value
})

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const { data } = await api.get<{ results?: EmpresaRow[] }>('/core/empresas/?page_size=500')
    const list = Array.isArray(data) ? data : (data.results ?? [])
    allRows.value = list
  } catch {
    errorMsg.value = 'No pudimos cargar el listado de empresas. Intente actualizar la página.'
    allRows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  ctx.resetPlataformaEmpresa()
  load()
})

function refreshNotificacionesBarra() {
  window.dispatchEvent(new CustomEvent(NOTIF_REFRESH))
}

function etiquetaRegistro(r: EmpresaRow): { text: string; cls: string } {
  if (r.registro_aprobado) return { text: 'Aprobada', cls: 'pill--ok' }
  if (r.activo === false) return { text: 'Inactiva', cls: 'pill--off' }
  return { text: 'Pendiente', cls: 'pill--warn' }
}

async function aprobar(row: EmpresaRow, ev?: Event) {
  ev?.stopPropagation()
  if (!esPendienteAccion(row)) return
  actionKey.value = `a-${row.id}`
  errorMsg.value = ''
  try {
    await api.patch(`/core/empresas/${row.id}/`, { registro_aprobado: true })
    await load()
    refreshNotificacionesBarra()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as { detail?: string }
      errorMsg.value = typeof d.detail === 'string' ? d.detail : 'No se pudo completar la aprobación.'
    } else {
      errorMsg.value = 'Sin conexión con el servidor.'
    }
  } finally {
    actionKey.value = null
  }
}

async function rechazar(row: EmpresaRow, ev?: Event) {
  ev?.stopPropagation()
  if (!esPendienteAccion(row)) return
  const ok = window.confirm(
    `¿Rechazar la solicitud de «${row.razon_social ?? row.ruc}»? La empresa quedará inactiva y se notificará al contacto.`,
  )
  if (!ok) return
  actionKey.value = `r-${row.id}`
  errorMsg.value = ''
  try {
    await api.patch(`/core/empresas/${row.id}/`, { activo: false })
    await load()
    refreshNotificacionesBarra()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as { detail?: string }
      errorMsg.value = typeof d.detail === 'string' ? d.detail : 'No se pudo registrar el rechazo.'
    } else {
      errorMsg.value = 'Sin conexión con el servidor.'
    }
  } finally {
    actionKey.value = null
  }
}

function lineaTitularNatural(r: EmpresaRow): string {
  const parts = [r.apellido_paterno, r.apellido_materno, r.nombres]
    .map((x) => (typeof x === 'string' ? x.trim() : ''))
    .filter(Boolean)
  return parts.join(' ')
}

function fmtDate(v: unknown): string {
  if (v == null || typeof v !== 'string') return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v)
  if (!m) return v.slice(0, 10)
  return `${m[3]}/${m[2]}/${m[1]}`
}

function subtituloFecha(r: EmpresaRow): { label: string; value: string } {
  if (tab.value === 'pendientes') {
    return { label: 'Solicitud enviada', value: fmtDate(r.creado_en) }
  }
  if (tab.value === 'activas') {
    const v = r.fecha_registro_aprobado || r.creado_en
    return { label: 'Fecha de aprobación', value: fmtDate(v) }
  }
  return { label: 'Registrada', value: fmtDate(r.creado_en) }
}

function puedeEntrarAlPanel(r: EmpresaRow): boolean {
  return esActivaAprobada(r)
}

function entrarEmpresa(r: EmpresaRow) {
  if (!puedeEntrarAlPanel(r)) return
  ctx.selectEmpresaForSession(String(r.id), r.razon_social ?? `Empresa #${r.id}`)
  router.push('/panel')
}

function onCardKeydown(r: EmpresaRow, ev: KeyboardEvent) {
  if (!puedeEntrarAlPanel(r)) return
  if (ev.key !== 'Enter' && ev.key !== ' ') return
  ev.preventDefault()
  entrarEmpresa(r)
}

function onCardClick(r: EmpresaRow) {
  if (puedeEntrarAlPanel(r)) entrarEmpresa(r)
}
</script>

<template>
  <div class="page">
    <header class="head">
      <div class="head-main">
        <h1 class="title">{{ pageTitle }}</h1>
        <p class="lead">{{ pageLead }}</p>
      </div>
      <div class="toolbar">
        <div class="toggle" role="tablist" aria-label="Filtrar empresas por estado">
          <RouterLink
            to="/plataforma/empresas/activas"
            role="tab"
            class="toggle-btn"
            :class="{ 'toggle-btn--on': tab === 'activas' }"
            :aria-current="tab === 'activas' ? 'page' : undefined"
          >
            Activas
            <span class="toggle-count">{{ rowsActivas.length }}</span>
          </RouterLink>
          <RouterLink
            to="/plataforma/empresas/pendientes"
            role="tab"
            class="toggle-btn"
            :class="{ 'toggle-btn--on': tab === 'pendientes' }"
            :aria-current="tab === 'pendientes' ? 'page' : undefined"
          >
            Pendientes
            <span
              class="toggle-count"
              :class="{ 'toggle-count--alert': rowsPendientes.length > 0 }"
              >{{ rowsPendientes.length }}</span
            >
          </RouterLink>
          <RouterLink
            to="/plataforma/empresas/inactivas"
            role="tab"
            class="toggle-btn"
            :class="{ 'toggle-btn--on': tab === 'inactivas' }"
            :aria-current="tab === 'inactivas' ? 'page' : undefined"
          >
            Inactivas
            <span class="toggle-count toggle-count--muted">{{ rowsInactivas.length }}</span>
          </RouterLink>
        </div>
        <button type="button" class="btn-icon" :disabled="loading" title="Actualizar listado" @click="load">
          {{ loading ? '…' : '↻' }}
        </button>
      </div>
    </header>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

    <div class="sheet">
      <div v-if="loading" class="muted">Cargando…</div>
      <div v-else-if="!rows.length" class="empty">
        <p class="empty-title">No hay empresas en esta vista</p>
        <p class="empty-hint">
          <template v-if="tab === 'activas'">Todavía no hay clientes activos y aprobados.</template>
          <template v-else-if="tab === 'pendientes'">No hay solicitudes de registro en espera.</template>
          <template v-else>Ninguna empresa figura como inactiva o rechazada.</template>
        </p>
      </div>
      <ul v-else class="grid" aria-label="Listado de empresas">
        <li v-for="r in rows" :key="r.id" class="cell">
          <div
            class="emp-card"
            :class="{
              'emp-card--click': puedeEntrarAlPanel(r),
              'emp-card--muted': r.activo === false,
            }"
            :role="puedeEntrarAlPanel(r) ? 'button' : undefined"
            :tabindex="puedeEntrarAlPanel(r) ? 0 : -1"
            :aria-label="
              puedeEntrarAlPanel(r)
                ? `Abrir el sistema de ${r.razon_social ?? r.ruc}`
                : undefined
            "
            @click="onCardClick(r)"
            @keydown="onCardKeydown(r, $event)"
          >
            <div class="emp-card-top">
              <span class="emp-ruc">{{ r.ruc?.trim() ? `RUC ${r.ruc}` : 'Sin RUC' }}</span>
              <span class="pill" :class="etiquetaRegistro(r).cls">{{ etiquetaRegistro(r).text }}</span>
            </div>
            <h2 class="emp-name">{{ r.razon_social ?? '—' }}</h2>
            <div class="emp-meta">
              <span class="meta-label">{{ subtituloFecha(r).label }}</span>
              <span class="meta-value">{{ subtituloFecha(r).value }}</span>
            </div>
            <div v-if="lineaTitularNatural(r)" class="emp-meta">
              <span class="meta-label">Titular</span>
              <span class="meta-value">{{ lineaTitularNatural(r) }}</span>
            </div>
            <div v-if="r.telefono_contacto?.trim()" class="emp-meta">
              <span class="meta-label">Teléfono</span>
              <span class="meta-value">{{ r.telefono_contacto }}</span>
            </div>
            <p v-if="puedeEntrarAlPanel(r)" class="emp-hint">Pulse la tarjeta para entrar al panel de este cliente</p>
            <div v-if="esPendienteAccion(r)" class="emp-actions" @click.stop>
              <button
                type="button"
                class="btn-approve"
                :disabled="actionKey === `a-${r.id}` || actionKey === `r-${r.id}`"
                @click="aprobar(r, $event)"
              >
                {{ actionKey === `a-${r.id}` ? '…' : 'Aprobar' }}
              </button>
              <button
                type="button"
                class="btn-reject"
                :disabled="actionKey === `a-${r.id}` || actionKey === `r-${r.id}`"
                @click="rechazar(r, $event)"
              >
                {{ actionKey === `r-${r.id}` ? '…' : 'Rechazar' }}
              </button>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: 100%;
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 1.25rem;
}

.head-main {
  min-width: min(100%, 280px);
}

.title {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.lead {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.45;
  color: #64748b;
  max-width: 36rem;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.toggle {
  display: inline-flex;
  padding: 3px;
  background: #e2e8f0;
  border-radius: 9px;
  flex-wrap: wrap;
}

.toggle-btn {
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.45rem 0.75rem;
  border-radius: 7px;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  text-decoration: none;
}

.toggle-btn:hover {
  color: #0f172a;
}

.toggle-btn--on {
  background: #fff;
  color: #0e7490;
  box-shadow: 0 1px 2px rgb(15 23 42 / 8%);
}

.toggle-count {
  font-size: 0.7rem;
  font-weight: 700;
  color: #94a3b8;
  background: rgb(255 255 255 / 0.65);
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  min-width: 1.25rem;
  text-align: center;
}

.toggle-btn--on .toggle-count {
  color: #0e7490;
  background: rgba(14, 116, 144, 0.12);
}

.toggle-count--alert {
  color: #9a3412;
  background: rgba(251, 146, 60, 0.2);
}

.toggle-count--muted {
  color: #94a3b8;
}

.btn-icon {
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #475569;
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    color 0.15s ease;
}

.btn-icon:hover:not(:disabled) {
  border-color: #0e7490;
  color: #0e7490;
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.err {
  color: #b91c1c;
  font-size: 0.875rem;
  margin: 0 0 0.75rem;
}

.sheet {
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%), 0 4px 12px rgb(15 23 42 / 4%);
  border: 1px solid #e2e8f0;
}

.grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.cell {
  margin: 0;
  padding: 0;
}

.emp-card {
  height: 100%;
  min-height: 10.5rem;
  padding: 1rem 1.1rem;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: linear-gradient(180deg, #fff 0%, #f8fafc 100%);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.emp-card--click {
  cursor: pointer;
}

.emp-card--click:hover {
  border-color: rgba(14, 116, 144, 0.45);
  box-shadow: 0 4px 14px rgb(14 116 144 / 12%);
}

.emp-card--click:focus-visible {
  outline: 2px solid #0e7490;
  outline-offset: 2px;
}

.emp-card--muted {
  opacity: 0.88;
  background: #f8fafc;
}

.emp-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.emp-ruc {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.emp-name {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.emp-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-top: 0.25rem;
}

.meta-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
}

.meta-value {
  font-size: 0.875rem;
  font-weight: 600;
  color: #334155;
}

.emp-hint {
  margin: auto 0 0;
  padding-top: 0.5rem;
  font-size: 0.75rem;
  color: #0e7490;
  font-weight: 600;
}

.emp-actions {
  margin-top: auto;
  padding-top: 0.65rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.pill {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  flex-shrink: 0;
}

.pill--ok {
  background: #dcfce7;
  color: #166534;
}

.pill--warn {
  background: #ffedd5;
  color: #9a3412;
}

.pill--off {
  background: #f1f5f9;
  color: #64748b;
}

.btn-approve {
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #0d9488, #0e7490);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 1px 2px rgb(14 116 144 / 25%);
  transition: filter 0.15s ease;
}

.btn-approve:hover:not(:disabled) {
  filter: brightness(1.05);
}

.btn-approve:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-reject {
  padding: 0.45rem 0.7rem;
  border-radius: 8px;
  border: 1px solid #fecaca;
  background: #fff;
  color: #b91c1c;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.btn-reject:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #f87171;
}

.btn-reject:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.muted {
  padding: 2rem;
  color: #94a3b8;
  text-align: center;
}

.empty {
  padding: 2.5rem 1rem;
  text-align: center;
}

.empty-title {
  margin: 0 0 0.35rem;
  font-size: 1rem;
  font-weight: 700;
  color: #475569;
}

.empty-hint {
  margin: 0;
  font-size: 0.875rem;
  color: #94a3b8;
}
</style>
