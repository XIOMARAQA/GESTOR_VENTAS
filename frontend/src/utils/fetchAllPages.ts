import type { AxiosResponse } from 'axios'

import { api } from '@/api/client'

type Paginated<T> = { results?: T[]; next?: string | null; count?: number }

function drfRelativePath(nextUrl: string): string {
  const u = new URL(nextUrl, window.location.origin)
  const idx = u.pathname.indexOf('/api/v1')
  if (idx >= 0) return u.pathname.slice(idx + '/api/v1'.length) + u.search
  return u.pathname + u.search
}

/** Recorre todas las páginas de un listado DRF paginado. */
export async function fetchAllPages<T>(basePath: string, pageSize = 500): Promise<T[]> {
  const acc: T[] = []
  let path: string | null = `${basePath}${basePath.includes('?') ? '&' : '?'}page_size=${pageSize}`
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
