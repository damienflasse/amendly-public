// @vitest-environment jsdom

import { act } from 'react'
import ReactDOM from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './ProtectedRoute'
import useAuthStore from '../store/authStore'

vi.mock('../lib/auth', () => ({
  authClient: {
    getMe: vi.fn(),
  },
}))

import { authClient } from '../lib/auth'

function renderRoute(initialEntry = '/private') {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = ReactDOM.createRoot(container)

  act(() => {
    root.render(
      <MemoryRouter
        initialEntries={[initialEntry]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/login" element={<div>login screen</div>} />
          <Route
            path="/private"
            element={
              <ProtectedRoute>
                <div>private screen</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    )
  })

  return { container, root }
}

beforeEach(() => {
  useAuthStore.setState({ user: null, sessionResolved: false })
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.clearAllMocks()
})

describe('ProtectedRoute', () => {
  it('redirects to /login when the cookie session is missing', async () => {
    authClient.getMe.mockRejectedValueOnce({ status: 401 })
    const { container, root } = renderRoute()

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(container.textContent).toContain('login screen')
    act(() => root.unmount())
  })

  it('renders the protected content when the cookie session resolves', async () => {
    authClient.getMe.mockResolvedValueOnce({ id: 'u1', email: 'user@example.com', plan: 'solo' })
    const { container, root } = renderRoute()

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(container.textContent).toContain('private screen')
    act(() => root.unmount())
  })
})
