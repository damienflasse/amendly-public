/**
 * AuthCallback — silent OAuth post-redirect handler.
 *
 * After a successful Google OAuth flow, the backend redirects
 * the browser to /auth/callback after setting an httpOnly session cookie.
 * This component validates that session and navigates the user onward.
 *
 * Props: none
 * Side effects: validates the session via /api/auth/me and navigates to
 *               /dashboard or /login.
 */

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { authClient } from '../lib/auth'
import useAuthStore from '../store/authStore'

const REDIRECT_KEY = 'amendly_redirect_after_login'

export default function AuthCallback() {
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)
  const clearUser = useAuthStore((s) => s.clearUser)

  useEffect(() => {
    let cancelled = false

    async function finishOAuth() {
      authClient.handleOAuthCallback()
      try {
        const me = await authClient.getMe()
        if (cancelled) return
        setUser(me)
        const saved = sessionStorage.getItem(REDIRECT_KEY)
        sessionStorage.removeItem(REDIRECT_KEY)
        navigate(saved || '/dashboard', { replace: true })
      } catch {
        if (!cancelled) {
          clearUser()
          navigate('/login', { replace: true })
        }
      }
    }

    finishOAuth()
    return () => { cancelled = true }
  }, [clearUser, navigate, setUser])

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <p className="font-body text-body-md text-outline">Signing you in…</p>
    </div>
  )
}
