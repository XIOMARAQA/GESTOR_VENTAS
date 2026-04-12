export const AUTH_TOKEN_KEY = 'gestor-token'
export const USER_EMAIL_KEY = 'gestor-user-email'
export const EMPRESA_ID_KEY = 'gestor-empresa-id'
export const EMPRESA_NOMBRE_KEY = 'gestor-empresa-nombre'
export const IS_SUPERUSER_KEY = 'gestor-is-superuser'

export type AuthPayload = {
  token: string
  empresa_id: string
  empresa_razon_social: string
  email?: string
  is_superuser?: boolean
  sucursal_id?: string | null
}

export function saveAuthSession(p: AuthPayload) {
  sessionStorage.setItem(AUTH_TOKEN_KEY, p.token)
  sessionStorage.setItem(EMPRESA_ID_KEY, p.empresa_id)
  sessionStorage.setItem(EMPRESA_NOMBRE_KEY, p.empresa_razon_social)
  sessionStorage.setItem(IS_SUPERUSER_KEY, p.is_superuser ? '1' : '0')
  if (p.email && p.email.trim()) {
    sessionStorage.setItem(USER_EMAIL_KEY, p.email.trim().toLowerCase())
  }
}

export function clearAuthSession() {
  sessionStorage.removeItem(AUTH_TOKEN_KEY)
  sessionStorage.removeItem(USER_EMAIL_KEY)
  sessionStorage.removeItem(EMPRESA_ID_KEY)
  sessionStorage.removeItem(EMPRESA_NOMBRE_KEY)
  sessionStorage.removeItem(IS_SUPERUSER_KEY)
}

export function readUserEmail(): string {
  return sessionStorage.getItem(USER_EMAIL_KEY) || ''
}

/** Persiste correo (p. ej. respaldo tras login o respuesta GET /auth/session/). */
export function saveUserEmail(email: string) {
  const t = email.trim().toLowerCase()
  if (t) sessionStorage.setItem(USER_EMAIL_KEY, t)
}

export function isLoggedIn() {
  return Boolean(sessionStorage.getItem(AUTH_TOKEN_KEY))
}

export function readIsSuperuser(): boolean {
  return sessionStorage.getItem(IS_SUPERUSER_KEY) === '1'
}

export function readEmpresaFromStorage(): { id: string | null; nombre: string } {
  return {
    id: sessionStorage.getItem(EMPRESA_ID_KEY),
    nombre: sessionStorage.getItem(EMPRESA_NOMBRE_KEY) || '',
  }
}

/** Hay empresa concreta seleccionada (no modo solo plataforma). */
export function readHasTenantEmpresa(): boolean {
  const id = readEmpresaFromStorage().id
  return Boolean(id && String(id).trim())
}

/** Actualiza solo empresa en sesión (p. ej. superusuario elige tenant sin volver a loguear). */
export function saveEmpresaContext(empresaId: string, razonSocial: string) {
  sessionStorage.setItem(EMPRESA_ID_KEY, empresaId)
  sessionStorage.setItem(EMPRESA_NOMBRE_KEY, razonSocial)
}
