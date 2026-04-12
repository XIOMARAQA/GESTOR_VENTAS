<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { api } from '@/api/client'
import { clearAuthSession, readUserEmail, saveUserEmail } from '@/auth/session'
import { navPlataformaSuperuser, navSections, type NavItem } from '@/navigation/modules'
import { useAppContextStore } from '@/stores/appContext'

import logoMark from '../../img/logo.png'

const STORAGE_KEY = 'gestor-nav-sections-open'

const route = useRoute()
const router = useRouter()
const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const visibleNav = computed(() => {
  if (isSuperuser.value && !empresaId.value) return navPlataformaSuperuser
  return navSections
})

const logoSrc = logoMark

const userEmail = ref(readUserEmail())
const userMenuOpen = ref(false)
const userMenuRoot = ref<HTMLElement | null>(null)

const notifOpen = ref(false)
const notifRoot = ref<HTMLElement | null>(null)
const notifCount = ref(0)
const notifList = ref<
  { id: number; titulo: string; mensaje: string; leida: boolean; creado_en?: string }[]
>([])
const notifLoading = ref(false)

const NOTIF_REFRESH = 'gestor-refresh-notificaciones'

const displayEmail = computed(() => userEmail.value || 'Usuario')
const avatarLetter = computed(() => {
  const e = userEmail.value
  if (!e) return '?'
  return e.charAt(0).toUpperCase()
})

function closeUserMenu() {
  userMenuOpen.value = false
}

function toggleUserMenu(e: MouseEvent) {
  e.stopPropagation()
  userMenuOpen.value = !userMenuOpen.value
}

function onDocumentPointerDown(e: MouseEvent) {
  const t = e.target
  if (!(t instanceof Node)) return
  if (userMenuOpen.value && userMenuRoot.value && !userMenuRoot.value.contains(t)) {
    userMenuOpen.value = false
  }
  if (notifOpen.value && notifRoot.value && !notifRoot.value.contains(t)) {
    notifOpen.value = false
  }
}

async function logout() {
  closeUserMenu()
  try {
    await api.post('/auth/logout/')
  } catch {
    /* ignorar si la sesión ya expiró */
  }
  clearAuthSession()
  ctx.clearEmpresa()
  router.replace('/login')
}

const openSections = reactive<Record<string, boolean>>({})

function loadOpen(): Record<string, boolean> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {}
  } catch {
    return {}
  }
}

function saveOpen() {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(openSections))
}

function toggleSection(id: string) {
  openSections[id] = !openSections[id]
  saveOpen()
}

function isSectionOpen(id: string) {
  return openSections[id] === true
}

function isNavItemActive(item: NavItem) {
  if (item.exact) {
    return route.path === item.to || route.path === `${item.to}/`
  }
  return route.path === item.to || route.path.startsWith(item.to + '/')
}

function volverModoPlataforma() {
  ctx.resetPlataformaEmpresa()
  router.push('/plataforma')
}

function syncOpenSections() {
  const saved = loadOpen()
  const defaultsOpen = new Set([
    'panel',
    'maestros',
    'ventas',
    'plataforma-inicio',
    'plataforma-empresas',
    'plataforma-equipo',
  ])
  for (const s of visibleNav.value) {
    if (openSections[s.id] === undefined) {
      openSections[s.id] = saved[s.id] ?? defaultsOpen.has(s.id)
    }
  }
}

async function hydrateUserEmail() {
  userEmail.value = readUserEmail()
  if (userEmail.value) return
  try {
    const { data } = await api.get<{ email?: string }>('/auth/session/')
    if (data?.email) {
      saveUserEmail(data.email)
      userEmail.value = readUserEmail()
    }
  } catch {
    /* sin sesión o red */
  }
}

async function loadNotifResumen() {
  try {
    const { data } = await api.get<{ no_leidas?: number }>('/core/notificaciones/resumen/')
    notifCount.value = typeof data?.no_leidas === 'number' ? data.no_leidas : 0
  } catch {
    notifCount.value = 0
  }
}

async function loadNotifList() {
  notifLoading.value = true
  try {
    const { data } = await api.get<{
      results?: typeof notifList.value
    }>('/core/notificaciones/?page_size=30')
    const list = Array.isArray(data) ? data : (data.results ?? [])
    notifList.value = list
  } catch {
    notifList.value = []
  } finally {
    notifLoading.value = false
  }
}

function toggleNotif(e: MouseEvent) {
  e.stopPropagation()
  notifOpen.value = !notifOpen.value
  if (notifOpen.value) void loadNotifList()
}

function closeNotif() {
  notifOpen.value = false
}

function fmtNotifDate(iso?: string): string {
  if (!iso) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return iso.slice(0, 10)
  return `${m[3]}/${m[2]}/${m[1]}`
}

async function marcarNotifLeida(id: number) {
  try {
    await api.patch(`/core/notificaciones/${id}/`, { leida: true })
    await loadNotifList()
    await loadNotifResumen()
  } catch {
    /* ignorar */
  }
}

async function marcarTodasNotif() {
  try {
    await api.post('/core/notificaciones/marcar_todas_leidas/')
    await loadNotifList()
    await loadNotifResumen()
  } catch {
    /* ignorar */
  }
}

function onNotifRefresh() {
  void loadNotifResumen()
}

let notifPoll: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  void hydrateUserEmail()
  void loadNotifResumen()
  window.addEventListener(NOTIF_REFRESH, onNotifRefresh)
  notifPoll = setInterval(() => void loadNotifResumen(), 45000)
  document.addEventListener('pointerdown', onDocumentPointerDown, true)
  ctx.hydrateFromSession()
  ctx.ensureEmpresa()
  syncOpenSections()
})

watch(visibleNav, () => syncOpenSections(), { flush: 'post' })

onUnmounted(() => {
  window.removeEventListener(NOTIF_REFRESH, onNotifRefresh)
  if (notifPoll) clearInterval(notifPoll)
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
})
</script>

<template>
  <div class="shell brand-bg">
    <aside class="sidebar">
      <div class="sidebar-head">
        <img :src="logoSrc" width="72" height="72" alt="Gestor de Ventas" class="sidebar-logo" />
      </div>

      <nav class="sections" aria-label="Módulos">
        <div
          v-for="sec in visibleNav"
          v-show="!sec.superuserOnly || ctx.isSuperuser"
          :key="sec.id"
          class="section"
        >
          <button
            type="button"
            class="section-head"
            :class="{ 'section-head--open': isSectionOpen(sec.id) }"
            @click="toggleSection(sec.id)"
          >
            <span class="chev" aria-hidden="true">{{ isSectionOpen(sec.id) ? '▼' : '▶' }}</span>
            <span class="section-label">{{ sec.label }}</span>
          </button>
          <Transition name="nav-slide">
            <div v-show="isSectionOpen(sec.id)" class="section-body">
              <RouterLink
                v-for="item in sec.children"
                :key="item.to"
                :to="item.to"
                class="sublink"
                :class="{ 'sublink--active': isNavItemActive(item) }"
                :title="item.hint || item.label"
              >
                <span class="sublink-dot" aria-hidden="true" />
                <span class="sublink-label">{{ item.label }}</span>
              </RouterLink>
            </div>
          </Transition>
        </div>
      </nav>
    </aside>

    <div class="content-col">
      <header class="topbar">
        <div class="topbar-left">
          <div class="ctx">
            <span class="ctx-item">
              <svg class="ctx-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  stroke="currentColor"
                  stroke-width="1.75"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M4 21V9.5L12 5l8 4.5V21M9 21v-6h6v6M7 21h10"
                />
              </svg>
              <span class="ctx-label">Empresa</span>
              <span class="ctx-value" :title="ctx.empresaNombre || ''">{{
                ctx.empresaNombre || '—'
              }}</span>
            </span>
            <span class="ctx-sep" aria-hidden="true">|</span>
            <span class="ctx-item">
              <svg class="ctx-ico ctx-ico--suc" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  stroke="currentColor"
                  stroke-width="1.75"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M12 21s7-4.35 7-10a7 7 0 10-14 0c0 5.65 7 10 7 10z"
                />
                <circle cx="12" cy="11" r="2.25" stroke="currentColor" stroke-width="1.75" fill="none" />
              </svg>
              <span class="ctx-label">Sucursal</span>
              <span class="ctx-value" :title="ctx.isSuperuser ? '' : ctx.sucursalNombre">{{
                ctx.isSuperuser ? '—' : ctx.sucursalNombre
              }}</span>
            </span>
          </div>
          <button
            v-if="ctx.isSuperuser && ctx.empresaId"
            type="button"
            class="btn-volver-plataforma"
            title="Cierra la vista de esta empresa y vuelve al panel de superadministrador"
            aria-label="Volver a la administración de la plataforma"
            @click="volverModoPlataforma"
          >
            <svg class="btn-volver-plataforma-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15 18 9 12l6-6"
              />
            </svg>
            Volver a plataforma
          </button>
        </div>
        <div class="top-actions">
          <RouterLink
            v-if="!ctx.isSuperuser || ctx.empresaId"
            to="/panel"
            class="top-link top-link--panel"
          >
            <svg class="top-link-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linejoin="round"
                d="M4 4.5h7v7H4v-7Zm9 0h7v4h-7v-4ZM4 13.5h7v6.5H4V13.5Zm9 3.5h7v3h-7v-3Z"
              />
            </svg>
            Panel
          </RouterLink>
          <RouterLink
            v-else
            to="/plataforma"
            class="top-link top-link--panel"
          >
            <svg class="top-link-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linejoin="round"
                d="M4 4.5h7v7H4v-7Zm9 0h7v4h-7v-4ZM4 13.5h7v6.5H4V13.5Zm9 3.5h7v3h-7v-3Z"
              />
            </svg>
            Resumen
          </RouterLink>

          <div ref="notifRoot" class="notif-wrap">
            <button
              type="button"
              class="notif-trigger"
              :aria-expanded="notifOpen"
              aria-label="Notificaciones"
              @click="toggleNotif"
            >
              <svg class="notif-bell" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  stroke="currentColor"
                  stroke-width="1.75"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 1 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
                />
              </svg>
              <span v-if="notifCount > 0" class="notif-badge">{{ notifCount > 99 ? '99+' : notifCount }}</span>
            </button>
            <Transition name="notif-slide">
              <div
                v-show="notifOpen"
                class="notif-panel"
                role="dialog"
                aria-label="Lista de notificaciones"
              >
                <div class="notif-panel-head">
                  <span class="notif-panel-title">Notificaciones</span>
                  <div class="notif-head-actions">
                    <button
                      v-if="notifList.some((n) => !n.leida)"
                      type="button"
                      class="notif-mark-all"
                      @click="marcarTodasNotif"
                    >
                      Marcar leídas
                    </button>
                    <button
                      type="button"
                      class="notif-close"
                      aria-label="Cerrar notificaciones"
                      @click="closeNotif"
                    >
                      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          stroke="currentColor"
                          stroke-width="2"
                          stroke-linecap="round"
                          d="M6 6 18 18M18 6 6 18"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
                <div class="notif-panel-body">
                  <p v-if="notifLoading" class="notif-muted">Cargando…</p>
                  <template v-else>
                    <button
                      v-for="n in notifList"
                      :key="n.id"
                      type="button"
                      class="notif-item"
                      :class="{ 'notif-item--unread': !n.leida }"
                      @click="marcarNotifLeida(n.id)"
                    >
                      <div class="notif-item-row">
                        <span class="notif-item-date">{{ fmtNotifDate(n.creado_en) }}</span>
                        <svg class="notif-item-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                          <path
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            d="m9 6 6 6-6 6"
                          />
                        </svg>
                      </div>
                      <span class="notif-item-title">{{ n.titulo }}</span>
                      <span class="notif-item-msg">{{ n.mensaje }}</span>
                    </button>
                    <p v-if="!notifList.length" class="notif-muted">No hay notificaciones.</p>
                  </template>
                </div>
              </div>
            </Transition>
          </div>

          <div ref="userMenuRoot" class="user-menu">
            <button
              type="button"
              class="user-trigger"
              :aria-expanded="userMenuOpen"
              aria-haspopup="true"
              :title="userEmail || undefined"
              @click="toggleUserMenu"
            >
              <span class="user-text">
                <span class="user-welcome">Bienvenido</span>
                <span class="user-email">{{ displayEmail }}</span>
              </span>
              <svg class="user-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="m6 9 6 6 6-6"
                />
              </svg>
              <span class="user-avatar" aria-hidden="true">{{ avatarLetter }}</span>
            </button>
            <Transition name="menu-fade">
              <div v-show="userMenuOpen" class="user-dropdown" role="menu">
                <button type="button" class="user-dropdown-item" role="menuitem" @click="logout">
                  <svg class="ico-logout" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      stroke="currentColor"
                      stroke-width="1.75"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M18 9l3 3m0 0-3 3m3-3H9"
                    />
                  </svg>
                  Cerrar sesión
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </header>
      <main class="main">
        <RouterView :key="route.fullPath" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 18.5rem minmax(0, 1fr);
  width: 100%;
  height: 100vh;
  max-height: 100vh;
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
}

.sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 1rem 0.75rem 1rem 0.85rem;
  background: linear-gradient(
    185deg,
    var(--shell-sidebar-bg-top) 0%,
    var(--shell-sidebar-bg-mid) 48%,
    var(--shell-sidebar-bg-bottom) 100%
  );
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-right: 1px solid var(--shell-sidebar-border-outer);
  box-shadow: 4px 0 28px rgba(6, 28, 36, 0.28);
}

.sidebar-head {
  flex-shrink: 0;
  text-align: center;
  padding-bottom: 1rem;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid rgba(var(--shell-cyan-rgb), 0.2);
}

.sidebar-logo {
  display: block;
  margin: 0 auto;
  max-width: 100%;
  height: auto;
  object-fit: contain;
  filter: drop-shadow(0 6px 20px rgba(var(--shell-cyan-rgb), 0.2));
}

.sections {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding-right: 0.15rem;
  -webkit-overflow-scrolling: touch;
}

.section {
  margin-bottom: 0.35rem;
}

.section-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  border: none;
  background: var(--shell-sidebar-chrome);
  color: var(--shell-sidebar-text-heading);
  font-size: 0.72rem;
  font-weight: 700;
  text-align: left;
  padding: 0.55rem 0.5rem;
  border-radius: 8px;
  cursor: pointer;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: 1px solid transparent;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.section-head:hover {
  background: var(--shell-sidebar-chrome-hover);
}

.section-head--open {
  background: rgba(var(--shell-cyan-rgb), 0.14);
  border-color: var(--shell-border-mid);
  color: #f8fffe;
}

.section-label {
  flex: 1;
  line-height: 1.25;
}

.chev {
  font-size: 0.55rem;
  opacity: 0.75;
  width: 0.85rem;
  flex-shrink: 0;
  color: var(--shell-sidebar-text-item-muted);
}

.section-body {
  padding: 0.35rem 0 0.5rem 0.4rem;
  margin-left: 0.15rem;
  border-left: 2px solid rgba(var(--shell-orange-rgb), 0.42);
}

.nav-slide-enter-active,
.nav-slide-leave-active {
  transition: opacity 0.2s ease;
}

.nav-slide-enter-from,
.nav-slide-leave-to {
  opacity: 0;
}

.sublink {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  padding: 0.5rem 0.45rem 0.5rem 0.35rem;
  border-radius: 8px;
  color: var(--shell-sidebar-text-item);
  text-decoration: none;
  font-size: 0.82rem;
  line-height: 1.35;
  margin-bottom: 2px;
  border: 1px solid transparent;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.sublink:hover {
  background: var(--shell-sidebar-link-hover-bg);
  color: var(--shell-sidebar-text-item-hover);
  border-color: rgba(var(--shell-cyan-rgb), 0.18);
}

.sublink--active {
  background: linear-gradient(
    90deg,
    rgba(var(--shell-cyan-rgb), 0.22),
    rgba(var(--shell-orange-rgb), 0.14)
  );
  color: #fff;
  font-weight: 600;
  border-color: var(--shell-border-strong);
}

.sublink-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-top: 0.45em;
  flex-shrink: 0;
  background: rgba(var(--shell-cyan-rgb), 0.5);
  box-shadow: 0 0 8px rgba(var(--shell-cyan-rgb), 0.4);
}

.sublink--active .sublink-dot {
  background: var(--exp-orange);
  box-shadow: 0 0 8px rgba(var(--shell-orange-rgb), 0.5);
}

.sublink-label {
  flex: 1;
}

.content-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  width: 100%;
  flex: 1;
  overflow: hidden;
  background: rgba(248, 250, 252, 0.97);
  backdrop-filter: blur(8px);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 1.25rem;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid rgba(14, 116, 144, 0.15);
  font-size: 0.85rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.ctx {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}

.btn-volver-plataforma {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
  padding: 0.42rem 0.85rem;
  border-radius: 999px;
  border: 1px solid #0e7490;
  background: rgba(14, 116, 144, 0.1);
  color: #0f766e;
  font-weight: 600;
  font-size: 0.78rem;
  cursor: pointer;
  font-family: inherit;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.btn-volver-plataforma:hover {
  background: rgba(14, 116, 144, 0.18);
  border-color: #0f766e;
  color: #115e59;
}

.btn-volver-plataforma-ico {
  width: 1.05rem;
  height: 1.05rem;
  flex-shrink: 0;
}

.ctx-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.ctx-ico {
  width: 1.15rem;
  height: 1.15rem;
  flex-shrink: 0;
  color: #0e7490;
  opacity: 0.9;
}

.ctx-ico--suc {
  color: #c2410c;
  opacity: 0.88;
}

.ctx-label {
  color: #64748b;
  flex-shrink: 0;
}

.ctx-value {
  font-weight: 600;
  color: #0f172a;
  max-width: min(20rem, 32vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ctx-sep {
  color: #cbd5e1;
  margin: 0 0.1rem;
  flex-shrink: 0;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.top-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #0e7490;
  font-weight: 600;
  text-decoration: none;
  font-size: 0.8rem;
}

button.top-link {
  border: none;
  background: none;
  cursor: pointer;
  font: inherit;
  padding: 0;
}

.top-link-ico {
  width: 1.1rem;
  height: 1.1rem;
  flex-shrink: 0;
  opacity: 0.9;
}

.top-link:hover {
  text-decoration: underline;
}

.notif-wrap {
  position: static;
}

.notif-trigger {
  position: relative;
  width: 2.35rem;
  height: 2.35rem;
  padding: 0;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    border-color 0.15s ease,
    color 0.15s ease;
}

.notif-trigger:hover {
  border-color: #0e7490;
  color: #0e7490;
}

.notif-bell {
  width: 1.2rem;
  height: 1.2rem;
}

.notif-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 1.15rem;
  height: 1.15rem;
  padding: 0 4px;
  border-radius: 999px;
  background: #dc2626;
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  line-height: 1.15rem;
  text-align: center;
  box-shadow: 0 1px 3px rgb(220 38 38 / 45%);
}

.notif-panel {
  position: fixed;
  top: 3.5rem;
  right: 0.75rem;
  width: min(22rem, calc(100vw - 1.25rem));
  max-height: calc(100vh - 4.25rem);
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid rgb(14 116 144 / 22%);
  border-radius: 12px;
  box-shadow:
    0 8px 24px -4px rgb(15 23 42 / 12%),
    0 20px 48px -12px rgb(15 23 42 / 18%);
  z-index: 200;
  overflow: hidden;
}

@media (max-width: 640px) {
  .notif-panel {
    top: auto;
    bottom: 0.75rem;
    right: 0.5rem;
    left: 0.5rem;
    width: auto;
    max-height: min(70vh, 28rem);
  }
}

.notif-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.55rem 0.65rem 0.55rem 0.85rem;
  flex-shrink: 0;
  background: linear-gradient(135deg, #0e7490 0%, #0891b2 100%);
  border-bottom: 1px solid rgb(0 0 0 / 8%);
}

.notif-panel-title {
  font-size: 0.88rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.01em;
}

.notif-head-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.notif-mark-all {
  border: none;
  background: transparent;
  color: rgb(255 255 255 / 92%);
  font-size: 0.68rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0.25rem 0.4rem;
  border-radius: 6px;
  white-space: nowrap;
}

.notif-mark-all:hover {
  background: rgb(255 255 255 / 12%);
  color: #fff;
}

.notif-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.85rem;
  height: 1.85rem;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: rgb(255 255 255 / 14%);
  color: #fff;
  cursor: pointer;
  transition: background 0.15s ease;
}

.notif-close:hover {
  background: rgb(255 255 255 / 26%);
}

.notif-close svg {
  width: 1rem;
  height: 1rem;
}

.notif-panel-body {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.notif-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 0.5rem;
}

.notif-item-date {
  font-size: 0.68rem;
  font-weight: 500;
  color: #94a3b8;
}

.notif-item-chev {
  width: 0.85rem;
  height: 0.85rem;
  flex-shrink: 0;
  color: #cbd5e1;
}

.notif-item:hover .notif-item-chev {
  color: #0e7490;
}

.notif-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.2rem;
  width: 100%;
  text-align: left;
  padding: 0.65rem 0.85rem;
  border: none;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
  cursor: pointer;
  transition: background 0.12s ease;
}

.notif-item:hover {
  background: #f8fafc;
}

.notif-item--unread {
  background: #ecfeff;
}

.notif-item--unread:hover {
  background: #cffafe;
}

.notif-item-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: #0f172a;
}

.notif-item-msg {
  font-size: 0.75rem;
  color: #64748b;
  line-height: 1.4;
  white-space: pre-wrap;
}

.notif-muted {
  padding: 1rem;
  text-align: center;
  font-size: 0.8rem;
  color: #94a3b8;
  margin: 0;
}

.notif-slide-enter-active,
.notif-slide-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.22s cubic-bezier(0.33, 1, 0.68, 1);
}

.notif-slide-enter-from,
.notif-slide-leave-to {
  opacity: 0;
  transform: translateX(12px) scale(0.98);
}

.user-menu {
  position: relative;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.5rem 0.35rem 0.65rem;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
  max-width: min(44rem, calc(100vw - 2rem));
  min-width: min(16rem, 100%);
}

.user-trigger:hover {
  border-color: #cbd5e1;
  box-shadow: 0 1px 3px rgb(15 23 42 / 6%);
}

.user-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.05rem;
  min-width: 0;
  flex: 1;
  text-align: left;
}

.user-welcome {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.user-email {
  font-size: 0.82rem;
  font-weight: 600;
  color: #0f172a;
  width: 100%;
  max-width: min(36rem, calc(100vw - 9rem));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-chev {
  width: 1rem;
  height: 1rem;
  color: #94a3b8;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.user-trigger[aria-expanded='true'] .user-chev {
  transform: rotate(180deg);
  color: #0e7490;
}

.user-avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: linear-gradient(135deg, #0d9488, #0e7490);
  color: #fff;
  font-size: 0.85rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgb(14 116 144 / 35%);
}

.user-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  min-width: 12rem;
  padding: 0.35rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow:
    0 4px 6px -1px rgb(15 23 42 / 8%),
    0 10px 24px -4px rgb(15 23 42 / 12%);
  z-index: 50;
}

.user-dropdown-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 0.65rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #334155;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s ease;
}

.user-dropdown-item:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.ico-logout {
  width: 1.25rem;
  height: 1.25rem;
  flex-shrink: 0;
  color: #64748b;
}

.user-dropdown-item:hover .ico-logout {
  color: #dc2626;
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.main {
  flex: 1;
  min-height: 0;
  padding: 1.25rem;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}
</style>
