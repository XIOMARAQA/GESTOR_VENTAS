import axios from 'axios'

/** Mensaje legible cuando falla el GET de un listado (red, auth, servidor). */
export function listLoadErrorMessage(e: unknown, recurso: string): string {
  if (axios.isAxiosError(e)) {
    if (e.code === 'ERR_NETWORK' || e.response == null) {
      return `No hubo respuesta del servidor al cargar ${recurso}. Compruebe que el API esté en marcha, la URL del front coincida con el backend y que no haya bloqueos de red o CORS.`
    }
    const st = e.response.status
    if (st === 401) {
      return 'La sesión no es válida o expiró. Cierre sesión, vuelva a entrar e intente de nuevo.'
    }
    if (st === 403) {
      return `No tiene permiso para ver ${recurso}. Si gestiona varias empresas, confirme la empresa activa en la barra superior.`
    }
    if (st === 404) {
      return 'El servidor no expone este recurso. Verifique que el backend esté actualizado.'
    }
    if (st >= 500) {
      return `El servidor respondió con un error al cargar ${recurso}. Intente más tarde o revise los registros del backend.`
    }
    const d = e.response.data as Record<string, unknown>
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) return d.detail.map(String).join(' ')
  }
  return `No se pudo cargar ${recurso}. Actualice la página o inténtelo de nuevo.`
}
