<script setup lang="ts">
import axios from 'axios'
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api/client'
import { readUserEmail, saveAuthSession, saveUserEmail, type AuthPayload } from '@/auth/session'
import { useAppContextStore } from '@/stores/appContext'

import logoLogin from '../../../img/logo.png'

const router = useRouter()
const route = useRoute()
const ctx = useAppContextStore()

const ruc = ref('')
const email = ref('')
const password = ref('')
const showPass = ref(false)
const loading = ref(false)
const errorMsg = ref('')

const showRegistro = ref(false)
const reg = ref({
  ruc: '',
  razon_social: '',
  apellido_paterno: '',
  apellido_materno: '',
  nombres: '',
  telefono_contacto: '',
  email: '',
  password: '',
  password_confirm: '',
})
const regShowPass = ref(false)
const regLoading = ref(false)
const regSunatLoading = ref(false)
const regError = ref('')
const regOk = ref('')
const regAlertRef = ref<HTMLElement | null>(null)

const logoSrc = logoLogin

/** Texto legible a partir de errores DRF (p. ej. `{ ruc: ["mensaje"] }` → solo el mensaje). */
function drfErrorsToMessage(data: unknown): string {
  if (data == null || typeof data !== 'object') return 'Error al registrar.'
  const d = data as Record<string, unknown>
  const detail = d.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((x) => (typeof x === 'string' ? x : ''))
      .filter(Boolean)
    if (parts.length) return parts.join(' ')
  }
  const messages: string[] = []
  for (const [key, val] of Object.entries(d)) {
    if (key === 'detail') continue
    if (Array.isArray(val)) {
      for (const item of val) {
        if (typeof item === 'string') messages.push(item)
      }
    } else if (typeof val === 'string') messages.push(val)
  }
  return messages.join(' ').trim() || 'Error al registrar.'
}

const passStrength = computed(() => {
  const p = reg.value.password
  let n = 0
  if (p.length >= 8) n++
  if (/[a-z]/.test(p)) n++
  if (/[A-Z]/.test(p)) n++
  if (/\d/.test(p)) n++
  if (/[^A-Za-z0-9]/.test(p)) n++
  return n
})

/** RUC Perú 11 dígitos: 20… = persona jurídica; otro prefijo = persona natural con negocio. */
const regTipoContribuyente = computed<'pj' | 'pn' | null>(() => {
  const r = reg.value.ruc.trim()
  if (!/^\d{11}$/.test(r)) return null
  return r.startsWith('20') ? 'pj' : 'pn'
})

/** Al pasar de RUC empresa (20) a persona u viceversa, limpiar campos del otro flujo para no mezclar datos. */
watch(
  () => reg.value.ruc,
  (newRuc, oldRuc) => {
    const n = newRuc.trim()
    const o = (oldRuc ?? '').trim()
    if (!/^\d{11}$/.test(n)) return
    const nowPj = n.startsWith('20')
    if (!/^\d{11}$/.test(o)) return
    const wasPj = o.startsWith('20')
    if (wasPj === nowPj) return
    if (nowPj) {
      reg.value.apellido_paterno = ''
      reg.value.apellido_materno = ''
      reg.value.nombres = ''
    } else {
      reg.value.razon_social = ''
    }
  },
)

function applyAuth(data: AuthPayload) {
  saveAuthSession(data)
  if (!readUserEmail() && email.value.trim()) {
    saveUserEmail(email.value)
  }
  ctx.setSuperuser(!!data.is_superuser)
  ctx.setEmpresa(data.empresa_id ?? '', data.empresa_razon_social)
}

async function ingresar() {
  errorMsg.value = ''
  if (!email.value.trim() || !password.value) {
    errorMsg.value = 'Completa correo y contraseña.'
    return
  }
  const rucTrim = ruc.value.trim()
  if (rucTrim && !/^\d{11}$/.test(rucTrim)) {
    errorMsg.value =
      'El RUC debe tener 11 dígitos, o déjelo vacío si es administración de plataforma.'
    return
  }
  loading.value = true
  try {
    const { data } = await api.post<AuthPayload>('/auth/login/', {
      ruc: rucTrim,
      email: email.value.trim().toLowerCase(),
      password: password.value,
    })
    applyAuth(data)
    const defaultPath = data.is_superuser ? '/plataforma' : '/panel'
    const redir = typeof route.query.redirect === 'string' ? route.query.redirect : defaultPath
    router.replace(redir || defaultPath)
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      const d = e.response.data as { detail?: string }
      errorMsg.value =
        typeof d.detail === 'string' ? d.detail : 'No se pudo iniciar sesión. Revise los datos.'
    } else {
      errorMsg.value = 'No hay conexión con el servidor.'
    }
  } finally {
    loading.value = false
  }
}

function abrirRegistro() {
  regError.value = ''
  regOk.value = ''
  reg.value = {
    ruc: ruc.value.trim(),
    razon_social: '',
    apellido_paterno: '',
    apellido_materno: '',
    nombres: '',
    telefono_contacto: '',
    email: email.value.trim().toLowerCase(),
    password: '',
    password_confirm: '',
  }
  showRegistro.value = true
}

function cerrarRegistro() {
  showRegistro.value = false
}

/** Heurística SUNAT persona natural: "APELLIDO_PATERNO APELLIDO_MATERNO NOMBRES…". */
function repartirNombrePadronPersonaNatural(texto: string) {
  const parts = texto.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return
  if (parts.length === 1) {
    reg.value.apellido_paterno = ''
    reg.value.apellido_materno = ''
    reg.value.nombres = parts[0] ?? ''
    return
  }
  if (parts.length === 2) {
    reg.value.apellido_paterno = parts[0] ?? ''
    reg.value.apellido_materno = ''
    reg.value.nombres = parts[1] ?? ''
    return
  }
  reg.value.apellido_paterno = parts[0] ?? ''
  reg.value.apellido_materno = parts[1] ?? ''
  reg.value.nombres = parts.slice(2).join(' ')
}

async function consultarSunatRegistro() {
  regError.value = ''
  regOk.value = ''
  const n = reg.value.ruc.trim()
  if (!/^\d{11}$/.test(n)) {
    regError.value = 'Escriba los 11 dígitos del RUC y luego pulse «Consultar SUNAT».'
    return
  }
  regSunatLoading.value = true
  try {
    const { data } = await api.get<{
      ok?: boolean
      es_persona_juridica?: boolean
      razon_social?: string
      nombre_padron?: string
      sunat_estado?: string
      detail?: string
    }>('/core/consultar-ruc/', { params: { numero: n } })
    if (data.ok) {
      const pad = (data.nombre_padron || data.razon_social || '').trim()
      if (!pad) {
        regError.value =
          'SUNAT no devolvió un nombre para este RUC. Revise el número o intente más tarde.'
        return
      }
      const esPj = data.es_persona_juridica ?? n.startsWith('20')
      if (esPj) {
        reg.value.razon_social = (data.razon_social || pad).trim()
      } else {
        repartirNombrePadronPersonaNatural(pad)
        reg.value.razon_social = ''
      }
      const st = data.sunat_estado?.trim()
      const estadoTxt =
        st && st !== 'ACTIVO'
          ? ` En SUNAT aparece como: «${st}».`
          : st === 'ACTIVO'
            ? ' En SUNAT consta como activo.'
            : ''
      regOk.value = esPj
        ? `Consulta exitosa: ya tenemos la razón social de la empresa.${estadoTxt} Revise que sea correcta y siga con el registro.`
        : `Consulta exitosa: completamos apellidos y nombres con los datos de SUNAT.${estadoTxt} Compruebe que coincidan con su documento de identidad.`
    } else {
      regError.value =
        typeof data.detail === 'string' && data.detail.trim()
          ? data.detail
          : 'No pudimos obtener datos de SUNAT. Intente de nuevo en unos segundos.'
    }
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data != null) {
      const d = e.response.data as { detail?: string; error?: string }
      const msg =
        (typeof d.detail === 'string' && d.detail.trim()) ||
        (typeof d.error === 'string' && d.error.trim()) ||
        ''
      regError.value = msg || 'No pudimos consultar el RUC. Intente de nuevo.'
    } else {
      regError.value = 'No pudimos conectar con el servidor. Revise su internet e intente otra vez.'
    }
  } finally {
    regSunatLoading.value = false
    void nextTick(() => regAlertRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }))
  }
}

async function enviarRegistro() {
  regError.value = ''
  regOk.value = ''
  const v = reg.value
  const rucDigits = v.ruc.trim()
  const esPj = rucDigits.startsWith('20')
  if (!/^\d{11}$/.test(rucDigits)) {
    regError.value = 'El RUC debe tener exactamente 11 dígitos.'
    return
  }
  if (esPj) {
    if (v.razon_social.trim().length < 2) {
      regError.value =
        'Escriba la razón social de la empresa o use «Consultar SUNAT» para traerla.'
      return
    }
  } else if (!v.apellido_paterno.trim() || !v.apellido_materno.trim() || !v.nombres.trim()) {
    regError.value = 'Faltan apellidos o nombres. Complételos o use «Consultar SUNAT».'
    return
  }
  if (!v.email.trim() || !v.password) {
    regError.value = 'Correo y contraseña son obligatorios.'
    return
  }
  if (v.password !== v.password_confirm) {
    regError.value = 'Las contraseñas no coinciden.'
    return
  }
  if (passStrength.value < 5) {
    regError.value =
      'La contraseña debe tener al menos 8 caracteres, 1 minúscula, 1 mayúscula, 1 número y 1 carácter especial.'
    return
  }
  regLoading.value = true
  try {
    const { data } = await api.post<{
      mensaje?: string
      pendiente_aprobacion?: boolean
      email?: string
    }>('/auth/registro/', {
      ruc: rucDigits,
      razon_social: esPj ? v.razon_social.trim() : '',
      apellido_paterno: esPj ? '' : v.apellido_paterno.trim(),
      apellido_materno: esPj ? '' : v.apellido_materno.trim(),
      nombres: esPj ? '' : v.nombres.trim(),
      telefono_contacto: v.telefono_contacto.trim() || undefined,
      email: v.email.trim().toLowerCase(),
      password: v.password,
      password_confirm: v.password_confirm,
    })
    regOk.value =
      typeof data.mensaje === 'string' && data.mensaje.trim()
        ? data.mensaje
        : 'Registro enviado. Le avisaremos cuando su cuenta esté lista.'
    regError.value = ''
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data != null) {
      regError.value = drfErrorsToMessage(e.response.data)
      await nextTick()
      regAlertRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    } else {
      regError.value = 'No pudimos conectar con el servidor. Revise su internet e intente otra vez.'
    }
  } finally {
    regLoading.value = false
  }
}
</script>

<template>
  <div class="brand-bg login-page login-page--airy">
    <div class="login-inner">
      <div class="login-card">
        <div class="login-split">
          <section class="login-brand" aria-label="Marca">
            <div class="brand-stack">
              <div class="brand-mark">
                <img
                  :src="logoSrc"
                  width="256"
                  height="256"
                  alt=""
                  class="logo-img"
                  decoding="async"
                  fetchpriority="high"
                />
              </div>
              <div class="brand-copy">
                <h1 class="title exp-gradient-text">Gestor de Ventas</h1>
                <p class="tagline">Tu operación al instante</p>
                <p class="sub">ERP para pymes en la nube · multi-empresa</p>
              </div>
            </div>
          </section>

          <section class="login-form" aria-label="Inicio de sesión">
            <div class="login-form-inner">
              <h2 class="form-title">Inicio de sesión</h2>

              <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

              <label class="field">
                <span class="lab">
                  <svg
                    class="ico-svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.65"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <rect x="3.5" y="5" width="17" height="14" rx="2" />
                    <path d="M8 9h3M8 12.5h8M8 16h5" />
                    <circle cx="16.5" cy="9.5" r="1.35" fill="currentColor" stroke="none" />
                  </svg>
                  Número de RUC
                </span>
                <input
                  v-model="ruc"
                  type="text"
                  class="inp"
                  maxlength="11"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  placeholder="20100123456 (vacío = admin. plataforma)"
                  autocomplete="username"
                />
              </label>
              <label class="field">
                <span class="lab"><span class="ico">✉</span> Correo electrónico</span>
                <input
                  v-model="email"
                  type="email"
                  class="inp"
                  placeholder="usuario@empresa.com"
                  autocomplete="email"
                />
              </label>
              <label class="field">
                <span class="lab"><span class="ico">🔒</span> Contraseña</span>
                <div class="pass-wrap">
                  <input
                    v-model="password"
                    :type="showPass ? 'text' : 'password'"
                    class="inp"
                    placeholder="••••••••"
                    autocomplete="current-password"
                  />
                  <button type="button" class="eye" tabindex="-1" @click="showPass = !showPass">
                    {{ showPass ? '🙈' : '👁' }}
                  </button>
                </div>
              </label>

              <button type="button" class="btn-exp-primary" :disabled="loading" @click="ingresar">
                {{ loading ? 'Ingresando…' : 'Ingresar' }}
              </button>
              <button type="button" class="btn-exp-secondary" @click="abrirRegistro">Registrarse</button>

              <p class="hint">
                <strong>Clientes:</strong> RUC de 11 dígitos + correo + contraseña.
                <strong>Administración de plataforma:</strong> deje el RUC vacío y use el usuario superusuario.
                Tras <strong>Registrarse</strong>, el acceso queda pendiente hasta aprobación.
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showRegistro"
        class="modal-backdrop modal-backdrop--airy"
        @click.self="cerrarRegistro"
      >
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="reg-title">
          <h2 id="reg-title" class="modal-title exp-gradient-text">Crea tu cuenta</h2>
          <p class="modal-sub">Datos de la empresa y del usuario que administrará la cuenta</p>

          <label class="field">
            <span class="lab">Número de RUC (11 dígitos)</span>
            <div class="ruc-row">
              <input
                v-model="reg.ruc"
                type="text"
                class="inp inp-ruc"
                maxlength="11"
                inputmode="numeric"
                placeholder="20100123456"
              />
              <button
                type="button"
                class="btn-sunat"
                :disabled="regSunatLoading || regLoading"
                :title="
                  regTipoContribuyente === 'pn'
                    ? 'Rellenar apellidos y nombres con los datos que tiene SUNAT'
                    : regTipoContribuyente === 'pj'
                      ? 'Rellenar la razón social con los datos que tiene SUNAT'
                      : 'Escriba primero los 11 dígitos del RUC'
                "
                @click="consultarSunatRegistro"
              >
                {{ regSunatLoading ? '…' : 'Consultar SUNAT' }}
              </button>
            </div>
          </label>
          <div ref="regAlertRef" class="reg-alerts" role="alert" aria-live="polite">
            <p v-if="regError" class="err reg-err-prominent">{{ regError }}</p>
            <p v-if="regOk" class="ok reg-ok-box">{{ regOk }}</p>
          </div>

          <label v-if="regTipoContribuyente === 'pj'" class="field">
            <span class="lab">Razón social de la empresa (obligatoria)</span>
            <input
              v-model="reg.razon_social"
              type="text"
              class="inp"
              placeholder="Ej. MI EMPRESA SAC — o use Consultar SUNAT"
            />
          </label>
          <template v-if="regTipoContribuyente === 'pn'">
            <label class="field">
              <span class="lab">Apellido paterno</span>
              <input v-model="reg.apellido_paterno" type="text" class="inp" placeholder="Apellido paterno" />
            </label>
            <label class="field">
              <span class="lab">Apellido materno</span>
              <input v-model="reg.apellido_materno" type="text" class="inp" placeholder="Apellido materno" />
            </label>
            <label class="field">
              <span class="lab">Nombres</span>
              <input v-model="reg.nombres" type="text" class="inp" placeholder="Nombres" />
            </label>
          </template>
          <label class="field">
            <span class="lab">Teléfono de contacto</span>
            <input
              v-model="reg.telefono_contacto"
              type="tel"
              class="inp"
              placeholder="Opcional — para devolverle la llamada"
              maxlength="30"
              autocomplete="tel"
            />
          </label>
          <label class="field">
            <span class="lab">Correo electrónico</span>
            <input v-model="reg.email" type="email" class="inp" placeholder="correo@empresa.com" />
          </label>
          <label class="field">
            <span class="lab">Contraseña</span>
            <div class="pass-wrap">
              <input
                v-model="reg.password"
                :type="regShowPass ? 'text' : 'password'"
                class="inp"
                autocomplete="new-password"
              />
              <button type="button" class="eye" tabindex="-1" @click="regShowPass = !regShowPass">
                {{ regShowPass ? '🙈' : '👁' }}
              </button>
            </div>
          </label>
          <label class="field">
            <span class="lab">Confirmar contraseña</span>
            <input
              v-model="reg.password_confirm"
              type="password"
              class="inp"
              autocomplete="new-password"
            />
          </label>
          <div class="strength">
            <div class="strength-bar" :class="'s' + passStrength" />
            <span class="strength-hint"
              >Mín. 8 caracteres, 1 minúscula, 1 mayúscula, 1 número y 1 especial</span
            >
          </div>

          <button type="button" class="btn-exp-primary" :disabled="regLoading" @click="enviarRegistro">
            {{ regLoading ? 'Enviando…' : 'Enviar solicitud de registro' }}
          </button>
          <button type="button" class="btn-modal-close" @click="cerrarRegistro">Cerrar</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.login-inner {
  width: 100%;
  max-width: 920px;
}

.login-card {
  padding: 0;
  overflow: hidden;
  border-radius: 18px;
  background: var(--exp-glass);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--exp-glass-border);
  box-shadow: var(
    --login-shadow,
    0 0 0 1px rgba(251, 146, 60, 0.12),
    0 24px 48px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.06)
  );
}

.login-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  align-items: stretch;
  min-height: 0;
}

.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2.25rem 1.5rem 2.25rem;
  text-align: center;
  background: linear-gradient(
    165deg,
    rgba(255, 255, 255, 0.52) 0%,
    rgba(var(--shell-cyan-rgb), 0.14) 52%,
    rgba(var(--shell-orange-rgb), 0.03) 100%
  );
  border-radius: 17px 0 0 17px;
  border-right: 1px solid var(--shell-border-mid);
}

.brand-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: min(22rem, 100%);
  gap: 1.35rem;
}

/* Celeste/teal oscuro (tonos tipo escudo del logo), legible sobre panel claro. */
.login-brand .title.exp-gradient-text,
.modal-card .modal-title.exp-gradient-text {
  background: linear-gradient(118deg, #0a4d5c 0%, #0c5c6e 32%, #0d6f82 55%, #0f7a8c 78%, #0e7490 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.login-form {
  padding: 2rem 2rem 1.75rem 1.75rem;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: rgba(255, 255, 255, 0.98);
}

.login-form-inner {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.brand-mark {
  flex-shrink: 0;
  width: min(82%, clamp(11.5rem, 32vmin, 15.5rem));
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.6);
  box-shadow:
    inset 0 0 0 1px rgba(var(--shell-cyan-rgb), 0.32),
    0 8px 28px rgba(8, 51, 68, 0.1);
}

.logo-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center;
  image-rendering: auto;
  filter: drop-shadow(0 5px 16px rgba(var(--shell-cyan-rgb), 0.28));
}

.brand-copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  width: 100%;
  max-width: 100%;
}

.title {
  margin: 0;
  width: 100%;
  text-align: center;
  text-wrap: balance;
  font-size: clamp(1.35rem, 2.6vw + 0.35rem, 2rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.tagline {
  margin: 0.45rem 0 0;
  width: 100%;
  text-align: center;
  text-wrap: balance;
  font-size: clamp(0.92rem, 1.6vw + 0.2rem, 1.12rem);
  font-weight: 700;
  color: var(--exp-text);
  line-height: 1.32;
}

.sub {
  margin: 0.4rem 0 0;
  width: 100%;
  text-align: center;
  text-wrap: balance;
  font-size: clamp(0.78rem, 1.2vw + 0.15rem, 0.9rem);
  line-height: 1.38;
  color: var(--exp-text-muted);
}

@media (max-width: 720px) {
  .login-split {
    grid-template-columns: 1fr;
  }

  .login-brand {
    padding: 1.75rem 1.25rem 1.5rem;
    border-radius: 17px 17px 0 0;
    border-right: none;
    border-bottom: 1px solid var(--shell-border-mid);
  }

  .brand-stack {
    max-width: 19rem;
    gap: 1.1rem;
  }

  .brand-mark {
    width: min(62vw, 12.5rem);
  }

  .login-form {
    padding: 1.5rem 1.25rem 1.5rem;
  }
}

@media (max-width: 360px) {
  .brand-mark {
    width: min(64vw, 10rem);
  }
}

.form-title {
  margin: 0 0 1rem;
  width: 100%;
  text-align: center;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--exp-text-muted);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.85rem;
}

.lab {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--exp-text-muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.ico {
  opacity: 0.85;
  font-size: 0.85rem;
}

.ico-svg {
  width: 1.05rem;
  height: 1.05rem;
  flex-shrink: 0;
  opacity: 0.92;
  color: var(--shell-teal-deep);
}

.inp {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  border: 1px solid var(--login-inp-border, rgba(34, 211, 238, 0.25));
  background: var(--login-inp-bg, rgba(5, 11, 20, 0.55));
  color: var(--exp-text);
  font-size: 0.9rem;
  outline: none;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.inp::placeholder {
  color: var(--login-inp-placeholder, rgba(240, 249, 255, 0.35));
}

.inp:focus {
  border-color: var(--exp-cyan);
  box-shadow: 0 0 0 3px rgba(var(--shell-cyan-rgb), 0.22);
}

.pass-wrap {
  position: relative;
}

.pass-wrap .inp {
  padding-right: 2.75rem;
}

.eye {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 1rem;
  opacity: 0.75;
}

/* Botón principal: azul sky sólido (armoniza con el celeste; sin gradiente cyan–naranja). */
.login-form .btn-exp-primary,
.modal-card .btn-exp-primary {
  margin-top: 0.5rem;
  margin-bottom: 0.65rem;
  color: #fff;
  background: linear-gradient(180deg, var(--exp-cyan) 0%, var(--shell-teal-deep) 100%);
  box-shadow: 0 4px 16px rgba(var(--shell-cyan-rgb), 0.32);
}

.login-form .btn-exp-primary:hover:not(:disabled),
.modal-card .btn-exp-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 22px rgba(var(--shell-cyan-rgb), 0.38);
  background: linear-gradient(180deg, #67e8f9 0%, var(--exp-cyan) 100%);
  color: #fff;
}

.login-form .btn-exp-primary:disabled,
.modal-card .btn-exp-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.login-form .btn-exp-secondary {
  color: var(--shell-teal-deep);
  background: rgba(var(--shell-cyan-rgb), 0.1);
  border-color: var(--shell-border-strong);
}

.login-form .btn-exp-secondary:hover {
  background: rgba(var(--shell-cyan-rgb), 0.16);
  border-color: rgba(var(--shell-cyan-rgb), 0.45);
}

.err {
  color: #dc2626;
  font-size: 0.8rem;
  margin: 0 0 0.75rem;
  text-align: center;
}

.login-form-inner .err {
  text-align: left;
}

.ok {
  color: #15803d;
  font-size: 0.8rem;
  margin: 0 0 0.75rem;
  text-align: center;
}

.hint {
  margin: 1rem 0 0;
  font-size: 0.72rem;
  line-height: 1.45;
  color: var(--exp-text-muted);
  text-align: center;
  max-width: 100%;
}

.login-form-inner .hint {
  text-align: left;
}

/* Modal (Teleport a body: mismas variables que login claro) */
.modal-backdrop--airy {
  --exp-text: #0f172a;
  --exp-text-muted: #64748b;
  --exp-glass: rgba(255, 255, 255, 0.98);
  --exp-glass-border: var(--shell-border-strong);
  --login-inp-bg: #f0fdff;
  --login-inp-border: rgba(var(--shell-cyan-rgb), 0.38);
  --login-inp-placeholder: #94a3b8;
  --login-shadow: 0 2px 0 rgba(255, 255, 255, 0.95) inset, 0 22px 48px rgba(8, 51, 68, 0.08),
    0 0 0 1px var(--shell-border-divider);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.modal-card {
  width: 100%;
  max-width: 440px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 1.5rem 1.35rem;
  border-radius: 16px;
  background: var(--exp-glass);
  border: 1px solid var(--exp-glass-border);
  box-shadow: var(
    --login-shadow,
    0 24px 64px rgba(0, 0, 0, 0.45)
  );
}

.modal-title {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
  font-weight: 800;
  text-align: center;
}

.modal-sub {
  margin: 0 0 1rem;
  text-align: center;
  font-size: 0.8rem;
  color: var(--exp-text-muted);
}

.ruc-row {
  display: flex;
  align-items: stretch;
  gap: 0.45rem;
}

.inp-ruc {
  flex: 1;
  min-width: 0;
}

.btn-sunat {
  flex-shrink: 0;
  align-self: stretch;
  padding: 0 0.55rem;
  max-width: 42%;
  border-radius: 10px;
  border: 1px solid rgba(var(--shell-cyan-rgb), 0.42);
  background: rgba(var(--shell-cyan-rgb), 0.12);
  color: var(--shell-teal-deep);
  font-size: 0.65rem;
  font-weight: 700;
  line-height: 1.2;
  text-align: center;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.btn-sunat:hover:not(:disabled) {
  background: rgba(var(--shell-cyan-rgb), 0.2);
  border-color: var(--exp-cyan);
}

.btn-sunat:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.reg-alerts {
  min-height: 0;
  margin: 0.4rem 0 0.85rem;
}

.reg-err-prominent {
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  background: rgba(244, 63, 94, 0.12);
  border: 1px solid rgba(244, 63, 94, 0.35);
  font-size: 0.85rem;
  line-height: 1.4;
}

.reg-ok-box {
  padding: 0.75rem 0.85rem;
  border-radius: 10px;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  font-size: 0.82rem;
  line-height: 1.45;
  text-align: left;
}

.strength {
  margin: -0.25rem 0 1rem;
}

.strength-bar {
  height: 6px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.08);
  margin-bottom: 0.35rem;
  overflow: hidden;
}

.strength-bar::after {
  content: '';
  display: block;
  height: 100%;
  border-radius: 4px;
  transition:
    width 0.2s ease,
    background 0.2s ease;
}

.strength-bar.s0::after,
.strength-bar.s1::after {
  width: 20%;
  background: #64748b;
}
.strength-bar.s2::after {
  width: 40%;
  background: #f87171;
}
.strength-bar.s3::after {
  width: 60%;
  background: #fbbf24;
}
.strength-bar.s4::after {
  width: 80%;
  background: #a3e635;
}
.strength-bar.s5::after {
  width: 100%;
  background: #4ade80;
}

.strength-hint {
  font-size: 0.65rem;
  color: var(--exp-text-muted);
  line-height: 1.3;
}

.btn-modal-close {
  display: block;
  width: 100%;
  margin-top: 0.75rem;
  padding: 0.5rem;
  border: none;
  background: transparent;
  color: var(--shell-teal-deep);
  font-size: 0.8rem;
  cursor: pointer;
  text-decoration: underline;
}
</style>
