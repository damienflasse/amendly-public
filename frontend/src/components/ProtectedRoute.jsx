/**
 * ProtectedRoute — wraps a route to redirect unauthenticated users to /login.
 *
 * Resolves the current browser session via /api/auth/me before deciding whether
 * to render or redirect to /login.
 *
 * Also injects `<meta name="robots" content="noindex, nofollow">` so that
 * authenticated pages are never indexed by search engines even if a crawler
 * somehow reaches them. The meta tag is removed on unmount.
 *
 * SSR-safe: localStorage and document access are guarded by an isClient check.
 * Protected routes are never included in prerendering anyway.
 *
 * Props:
 *   children — The route element to render when authenticated.
 *
 * Usage:
 *   <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
 */

import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { authClient } from '../lib/auth'
import { AUTH_UNAUTHORIZED_EVENT } from '../lib/api'
import useAuthStore from '../store/authStore'

const isClient = typeof window !== 'undefined' && typeof document !== 'undefined'

/**
 * @param {{ children: React.ReactNode }} props
 * @returns {React.ReactElement}
 */
export default function ProtectedRoute({ children }) {
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const sessionResolved = useAuthStore((s) => s.sessionResolved)
  const setUser = useAuthStore((s) => s.setUser)
  const clearUser = useAuthStore((s) => s.clearUser)
  const setSessionResolved = useAuthStore((s) => s.setSessionResolved)

  // Inject noindex for all authenticated routes so crawlers never index them,
  // even if robots.txt is bypassed or cached. Belt-and-suspenders approach.
  useEffect(() => {
    if (!isClient) return

    let el = document.querySelector('meta[name="robots"]')
    const prev = el ? el.getAttribute('content') : null

    if (!el) {
      el = document.createElement('meta')
      el.setAttribute('name', 'robots')
      document.head.appendChild(el)
    }
    el.setAttribute('content', 'noindex, nofollow')

    return () => {
      if (prev !== null) {
        el.setAttribute('content', prev)
      } else {
        el.remove()
      }
    }
  }, [])

  useEffect(() => {
    if (sessionResolved) return

    let cancelled = false

    async function resolveSession() {
      try {
        const me = await authClient.getMe()
        if (!cancelled) setUser(me)
      } catch (error) {
        if (!cancelled) {
          clearUser()
          if (error?.status !== 401) setSessionResolved(true)
        }
      }
    }

    resolveSession()
    return () => { cancelled = true }
  }, [clearUser, sessionResolved, setSessionResolved, setUser])

  // Global handler for silent 401s (token expiry / sync issue)
  useEffect(() => {
    if (!isClient) return

    function handleUnauthorized() {
      clearUser()
      setSessionResolved(true)
    }

    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized)
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized)
  }, [clearUser, setSessionResolved])

  if (!sessionResolved) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <span className="font-body text-body-md text-outline">Loading…</span>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
