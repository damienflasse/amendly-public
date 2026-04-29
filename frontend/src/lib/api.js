/**
 * Shared fetch helpers for Amendly frontend API calls.
 *
 * Browser auth is cookie-backed only. Every authenticated request includes
 * credentials so the httpOnly session cookie is sent automatically.
 */

export const AUTH_UNAUTHORIZED_EVENT = 'auth:unauthorized'

export function buildApiError(res, data, fallbackMessage) {
  const error = new Error(data?.detail ?? fallbackMessage)
  error.status = res.status
  error.detail = data?.detail ?? null
  return error
}

function dispatchUnauthorized() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT))
  }
}

function buildHeaders(options) {
  const headers = new Headers(options.headers ?? {})
  const body = options.body
  const hasJsonBody = body != null && !(body instanceof FormData)

  if (hasJsonBody && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  return headers
}

export async function authFetch(input, options = {}) {
  const res = await fetch(input, {
    credentials: 'include',
    ...options,
    headers: buildHeaders(options),
  })

  if (res.status === 401) dispatchUnauthorized()
  return res
}

export async function authJsonFetch(input, options = {}) {
  const res = await authFetch(input, options)
  if (res.status === 204) return null

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw buildApiError(res, data, `Request failed with status ${res.status}`)
  }
  return data
}

export async function publicJsonFetch(input, options = {}) {
  const res = await fetch(input, {
    ...options,
    headers: buildHeaders(options),
  })
  if (res.status === 204) return null

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw buildApiError(res, data, `Request failed with status ${res.status}`)
  }
  return data
}
