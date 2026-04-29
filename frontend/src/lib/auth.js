/**
 * Amendly Auth client — thin wrapper around the /api/auth/* backend endpoints.
 *
 * This module mirrors the API contract exposed by backend/app/api/auth.py.
 * It deliberately avoids a third-party SDK dependency so the token storage
 * and session model are fully under our control.
 *
 * Session strategy:
 *   - Browser sessions are stored server-side in an httpOnly cookie.
 *   - Frontend code never reads or writes auth tokens in browser storage.
 *
 * Usage:
 *   import { authClient } from '@/lib/auth'
 *   await authClient.requestMagicLink('user@example.com')
 *   const user = await authClient.getMe()
 */

import { authJsonFetch } from './api'

const API_BASE = '/api/auth'

// ---------------------------------------------------------------------------
// Auth client
// ---------------------------------------------------------------------------

export const authClient = {
  /**
   * Request a magic-link login email.
   *
   * @param {string} email - The user's email address.
   * @returns {Promise<{ message: string }>}
   */
  requestMagicLink: (email, turnstileToken = null) =>
    authJsonFetch(`${API_BASE}/magic-link/request`, {
      method: 'POST',
      body: JSON.stringify({ email, ...(turnstileToken ? { turnstile_token: turnstileToken } : {}) }),
    }),

  /**
   * Verify a magic-link token and establish a server-side cookie session.
   *
   * @param {string} token - One-time token from the magic-link URL.
   * @returns {Promise<{ access_token: string; token_type: string }>}
   */
  verifyMagicLink: async (token) => {
    return authJsonFetch(`${API_BASE}/magic-link/verify`, {
      method: 'POST',
      body: JSON.stringify({ token }),
    })
  },

  /**
   * Redirect the browser to the Google OAuth authorisation page.
   */
  signInWithGoogle: () => {
    window.location.href = `${API_BASE}/oauth/google`
  },


  /**
   * Clean up a legacy OAuth URL fragment if one is present.
   *
   * @returns {boolean} True if a token was found and saved.
   */
  handleOAuthCallback: () => {
    if (window.location.hash) {
      window.history.replaceState({}, '', `${window.location.pathname}${window.location.search}`)
    }
    return true
  },

  /**
   * Fetch the authenticated user's profile from /api/auth/me.
   *
   * @returns {Promise<{ id: string; email: string; name: string|null; company: string|null; job_position: string|null; avatar_url: string|null; plan: string }>}
   */
  getMe: () => authJsonFetch(`${API_BASE}/me`),

  /**
   * Sign the current user out and clear any legacy local token.
   *
   * @returns {Promise<void>}
   */
  logout: async () => {
    await authJsonFetch(`${API_BASE}/logout`, { method: 'POST' })
  },

  /**
   * Permanently delete (anonymise) the authenticated user's account.
   *
   * @returns {Promise<void>}
   */
  deleteAccount: async () => {
    await authJsonFetch(`${API_BASE}/me`, { method: 'DELETE' })
  },

  /**
   * Update the current user's notification preferences.
   *
   * @param {{ email_notifications_enabled: boolean }} prefs - Preferences payload.
   * @returns {Promise<{ id: string; email: string; name: string|null; company: string|null; job_position: string|null; avatar_url: string|null; plan: string; email_notifications_enabled: boolean }>}
   */
  updatePreferences: (prefs) =>
    authJsonFetch(`${API_BASE}/me/preferences`, {
      method: 'PATCH',
      body: JSON.stringify(prefs),
    }),

  /**
   * Update the current user's public profile information.
   *
   * @param {{ name?: string|null; company?: string|null; job_position?: string|null; avatar_url?: string|null }} profile - Profile payload.
   * @returns {Promise<{ id: string; email: string; name: string|null; company: string|null; job_position: string|null; avatar_url: string|null; plan: string; email_notifications_enabled: boolean }>}
   */
  updateProfile: (profile) =>
    authJsonFetch(`${API_BASE}/me/profile`, {
      method: 'PATCH',
      body: JSON.stringify(profile),
    }),

  /**
   * Mark the onboarding wizard as completed for the current user.
   * Called when the user finishes or dismisses the post-signup wizard.
   *
   * @returns {Promise<{ id: string; email: string; onboarding_completed: boolean }>}
   */
  completeOnboarding: () =>
    authJsonFetch(`${API_BASE}/me/onboarding/complete`, { method: 'POST' }),
}
