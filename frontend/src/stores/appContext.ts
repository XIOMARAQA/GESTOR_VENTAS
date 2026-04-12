import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'
import { readEmpresaFromStorage, readIsSuperuser, saveEmpresaContext } from '@/auth/session'

/**
 * Contexto multi-empresa tras login (token + empresa del perfil).
 * Superusuario: sin empresa concreta, acceso global vía API.
 */
export const useAppContextStore = defineStore('appContext', () => {
  const empresaId = ref<string | null>(null)
  const empresaNombre = ref<string>('')
  const sucursalNombre = ref<string>('Sucursal principal')
  const isSuperuser = ref(false)

  function hydrateFromSession() {
    isSuperuser.value = readIsSuperuser()
    const { id, nombre } = readEmpresaFromStorage()
    if (id) empresaId.value = id
    else empresaId.value = null
    if (nombre) empresaNombre.value = nombre
    else empresaNombre.value = ''
  }

  async function ensureEmpresa() {
    hydrateFromSession()
    if (isSuperuser.value || empresaId.value) return
    try {
      const { data } = await api.get<{ results?: { id: string; razon_social: string }[] }>(
        '/core/empresas/',
      )
      const first = data.results?.[0]
      if (first) {
        empresaId.value = String(first.id)
        empresaNombre.value = first.razon_social
      }
    } catch {
      /* sin API o sin permiso */
    }
  }

  function setEmpresa(id: string, nombre: string) {
    empresaId.value = id || null
    empresaNombre.value = nombre
  }

  /** Modo plataforma: sin tenant seleccionado (misma etiqueta que en login sin RUC). */
  function resetPlataformaEmpresa() {
    empresaId.value = null
    empresaNombre.value = 'Plataforma (todas las empresas)'
    saveEmpresaContext('', 'Plataforma (todas las empresas)')
  }

  /** Superusuario entra al panel de un tenant concreto. */
  function selectEmpresaForSession(id: string, nombre: string) {
    setEmpresa(id, nombre)
    saveEmpresaContext(id, nombre)
  }

  function setSuperuser(v: boolean) {
    isSuperuser.value = v
  }

  function clearEmpresa() {
    empresaId.value = null
    empresaNombre.value = ''
    isSuperuser.value = false
  }

  return {
    empresaId,
    empresaNombre,
    sucursalNombre,
    isSuperuser,
    hydrateFromSession,
    ensureEmpresa,
    setEmpresa,
    resetPlataformaEmpresa,
    selectEmpresaForSession,
    setSuperuser,
    clearEmpresa,
  }
})
