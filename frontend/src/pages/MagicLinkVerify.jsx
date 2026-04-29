/**
 * MagicLinkVerify — exchange a magic-link token for a cookie-backed session.
 *
 * Route: /auth/verify?token=<one-time-token>
 *
 * The backend sends magic-link emails pointing to this route.
 * On mount the component:
 *   1. Reads ?token from the URL search params.
 *   2. Calls POST /api/auth/magic-link/verify via authClient.verifyMagicLink().
 *   3. On success: resolves the current user and navigates to the saved redirect destination (sessionStorage
 *      key "amendly_redirect_after_login") or /dashboard if none is set.
 *   4. On failure: shows an error card with a link back to /login.
 *
 * Props: none
 * Side effects:
 *   - Calls authClient.verifyMagicLink() on mount.
 *   - Navigates to /dashboard (or saved redirect) on success.
 */

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authClient } from '../lib/auth'
import useAuthStore from '../store/authStore'

const REDIRECT_KEY = 'amendly_redirect_after_login'

export default function MagicLinkVerify() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')
  const setUser = useAuthStore((s) => s.setUser)

  const [error, setError] = useState(null)

  useEffect(() => {
    if (!token) {
      setError('No token found in the URL.')
      return
    }

    let cancelled = false

    async function verify() {
      try {
        await authClient.verifyMagicLink(token)
        const me = await authClient.getMe()
        if (cancelled) return
        setUser(me)

        // Consume any saved redirect destination
        const saved = sessionStorage.getItem(REDIRECT_KEY)
        sessionStorage.removeItem(REDIRECT_KEY)
        navigate(saved || '/dashboard', { replace: true })
      } catch (err) {
        if (!cancelled) setError(err.message ?? 'Invalid or expired login link.')
      }
    }

    verify()
    return () => { cancelled = true }
  }, [navigate, setUser, token])

  if (error) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-8">
        <div className="w-full max-w-sm bg-surface-container-lowest rounded-md shadow-ambient px-8 py-12 text-center">
          <h1 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-4">
            Link expired or invalid
          </h1>
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-3 mb-8">
            {error}
          </p>
          <a
            href="/login"
            className="font-body text-body-md text-secondary underline underline-offset-2"
          >
            Back to sign in
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <p className="font-body text-body-md text-outline">Signing you in…</p>
    </div>
  )
}
