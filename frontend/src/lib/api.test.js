// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'

import { authFetch, publicJsonFetch } from './api'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('authFetch', () => {
  it('sends cookie credentials for authenticated browser requests', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })
    )

    await authFetch('/api/auth/me')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/auth/me',
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('dispatches auth:unauthorized on 401 responses', async () => {
    const listener = vi.fn()
    window.addEventListener('auth:unauthorized', listener)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }))

    await authFetch('/api/auth/me')

    expect(listener).toHaveBeenCalledTimes(1)
    window.removeEventListener('auth:unauthorized', listener)
  })
})

describe('publicJsonFetch', () => {
  it('keeps public contribution calls unauthenticated', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('{"ok":true}', { status: 200, headers: { 'Content-Type': 'application/json' } })
    )

    await publicJsonFetch('/api/contribute/token', {
      method: 'POST',
      body: JSON.stringify({ contributor_name: 'Alice' }),
    })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/contribute/token',
      expect.not.objectContaining({ credentials: 'include' }),
    )
  })
})
