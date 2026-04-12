<script setup lang="ts">
import axios from 'axios'
import { ref } from 'vue'

import { api } from '@/api/client'

const passwordActual = ref('')
const password = ref('')
const passwordConfirm = ref('')
const saving = ref(false)
const err = ref('')
const okMsg = ref('')

/** Contraseña actual: visible por defecto (texto plano en el campo). */
const showActual = ref(true)
const showNueva = ref(false)
const showConfirm = ref(false)

function drfMsg(data: unknown): string {
  if (data == null || typeof data !== 'object') return 'No se pudo actualizar la contraseña.'
  const d = data as Record<string, unknown>
  if (typeof d.detail === 'string') return d.detail
  const parts: string[] = []
  for (const [key, val] of Object.entries(d)) {
    if (Array.isArray(val)) {
      for (const x of val) {
        if (typeof x === 'string') parts.push(`${key}: ${x}`)
      }
    } else if (typeof val === 'string') {
      parts.push(`${key}: ${val}`)
    }
  }
  return parts.join(' ').trim() || 'No se pudo actualizar la contraseña.'
}

async function guardar() {
  err.value = ''
  okMsg.value = ''
  if (!passwordActual.value) {
    err.value = 'Escriba su contraseña actual.'
    return
  }
  if (!password.value || password.value !== passwordConfirm.value) {
    err.value = 'La nueva contraseña y la confirmación deben coincidir.'
    return
  }
  saving.value = true
  try {
    await api.post('/auth/cambiar-password/', {
      password_actual: passwordActual.value,
      password: password.value,
      password_confirm: passwordConfirm.value,
    })
    okMsg.value = 'Contraseña actualizada correctamente.'
    passwordActual.value = ''
    password.value = ''
    passwordConfirm.value = ''
    showActual.value = true
    showNueva.value = false
    showConfirm.value = false
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'Error de conexión.'
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title">Cambiar contraseña</h1>
        <p class="lead">
          Use una contraseña segura: al menos 8 caracteres, con minúscula, mayúscula, número y un carácter especial.
        </p>
      </div>
    </header>

    <p v-if="err" class="err">{{ err }}</p>
    <p v-if="okMsg" class="ok">{{ okMsg }}</p>

    <div class="card">
      <div class="field">
        <span class="lab">Contraseña actual</span>
        <div class="pass-wrap">
          <input
            id="pwd-actual"
            v-model="passwordActual"
            :type="showActual ? 'text' : 'password'"
            class="inp inp--pass"
            autocomplete="current-password"
          />
          <button
            type="button"
            class="btn-eye"
            :title="showActual ? 'Ocultar contraseña' : 'Ver contraseña'"
            :aria-label="showActual ? 'Ocultar contraseña' : 'Ver contraseña'"
            :aria-pressed="showActual"
            @click="showActual = !showActual"
          >
            <svg v-if="showActual" class="eye-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19 12 19c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 5c4.638 0 8.573 2.55 9.963 6.178a11.056 11.056 0 01-4.906 5.238M3 3l18 18"
              />
            </svg>
            <svg v-else class="eye-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 5 12 5c4.638 0 8.573 2.55 9.963 6.178a.99.99 0 010 .644C20.577 16.49 16.64 19 12 19c-4.638 0-8.573-2.51-9.963-6.178z"
              />
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </div>

      <div class="field">
        <span class="lab">Nueva contraseña</span>
        <div class="pass-wrap">
          <input
            id="pwd-nueva"
            v-model="password"
            :type="showNueva ? 'text' : 'password'"
            class="inp inp--pass"
            autocomplete="new-password"
          />
          <button
            type="button"
            class="btn-eye"
            :title="showNueva ? 'Ocultar contraseña' : 'Ver contraseña'"
            :aria-label="showNueva ? 'Ocultar contraseña' : 'Ver contraseña'"
            :aria-pressed="showNueva"
            @click="showNueva = !showNueva"
          >
            <svg v-if="showNueva" class="eye-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19 12 19c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 5c4.638 0 8.573 2.55 9.963 6.178a11.056 11.056 0 01-4.906 5.238M3 3l18 18"
              />
            </svg>
            <svg v-else class="eye-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 5 12 5c4.638 0 8.573 2.55 9.963 6.178a.99.99 0 010 .644C20.577 16.49 16.64 19 12 19c-4.638 0-8.573-2.51-9.963-6.178z"
              />
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </div>

      <div class="field">
        <span class="lab">Confirmar nueva contraseña</span>
        <div class="pass-wrap">
          <input
            id="pwd-confirm"
            v-model="passwordConfirm"
            :type="showConfirm ? 'text' : 'password'"
            class="inp inp--pass"
            autocomplete="new-password"
          />
          <button
            type="button"
            class="btn-eye"
            :title="showConfirm ? 'Ocultar contraseña' : 'Ver contraseña'"
            :aria-label="showConfirm ? 'Ocultar contraseña' : 'Ver contraseña'"
            :aria-pressed="showConfirm"
            @click="showConfirm = !showConfirm"
          >
            <svg v-if="showConfirm" class="eye-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19 12 19c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 5c4.638 0 8.573 2.55 9.963 6.178a11.056 11.056 0 01-4.906 5.238M3 3l18 18"
              />
            </svg>
            <svg v-else class="eye-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 5 12 5c4.638 0 8.573 2.55 9.963 6.178a.99.99 0 010 .644C20.577 16.49 16.64 19 12 19c-4.638 0-8.573-2.51-9.963-6.178z"
              />
              <path
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </div>

      <button type="button" class="btn-save" :disabled="saving" @click="guardar">
        {{ saving ? 'Guardando…' : 'Actualizar contraseña' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: 420px;
  color: #0f172a;
}

.head {
  margin-bottom: 1rem;
}

.title {
  margin: 0 0 0.35rem;
  font-size: 1.2rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.lead {
  margin: 0;
  font-size: 0.88rem;
  color: #475569;
  line-height: 1.55;
}

.err {
  color: #991b1b;
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  padding: 0.55rem 0.75rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.ok {
  color: #166534;
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  padding: 0.55rem 0.75rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
}

.card {
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem 1.35rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
  border: 1px solid #e2e8f0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.85rem;
}

.lab {
  font-size: 0.78rem;
  font-weight: 600;
  color: #475569;
}

.pass-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.inp {
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 0.875rem;
  font-family: inherit;
}

.inp--pass {
  width: 100%;
  padding: 0.5rem 2.65rem 0.5rem 0.6rem;
  box-sizing: border-box;
}

.btn-eye {
  position: absolute;
  right: 0.2rem;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}

.btn-eye:hover {
  color: #0e7490;
  background: rgb(14 116 144 / 8%);
}

.btn-eye:focus-visible {
  outline: 2px solid #0e7490;
  outline-offset: 1px;
}

.eye-ico {
  width: 1.25rem;
  height: 1.25rem;
}

.btn-save {
  margin-top: 0.35rem;
  padding: 0.45rem 1rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  color: #fff;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  font-family: inherit;
}

.btn-save:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
