import axios from 'axios'

import { AUTH_TOKEN_KEY } from '@/auth/session'

/** Base URL: en desarrollo usa proxy de Vite hacia Django. */
const baseURL = import.meta.env.VITE_API_BASE ?? '/api/v1'

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const t = sessionStorage.getItem(AUTH_TOKEN_KEY)
  if (t) {
    config.headers.Authorization = `Token ${t}`
  }
  return config
})
