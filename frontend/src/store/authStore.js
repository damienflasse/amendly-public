/**
 * authStore — Zustand store for the authenticated user's session.
 *
 * State:
 *   user             — The authenticated user object from GET /api/auth/me, or null.
 *   sessionResolved  — Whether the app has already checked the current browser session.
 *
 * Actions:
 *   setUser(user)  — Persist the user profile after successful auth.
 *   clearUser()    — Remove the user profile on logout.
 *
 * The store is intentionally lightweight: it holds the in-memory user object.
 * The authenticated browser session itself lives in the httpOnly session cookie.
 */

import { create } from 'zustand'

const useAuthStore = create((set) => ({
  /** @type {{ id: string; email: string; name: string|null; avatar_url: string|null; plan: string }|null} */
  user: null,
  sessionResolved: false,

  /**
   * Persist the user profile.
   * @param {{ id: string; email: string; name: string|null; avatar_url: string|null; plan: string }} user
   */
  setUser: (user) => set({ user, sessionResolved: true }),

  /** Clear the user profile (used on logout). */
  clearUser: () => set({ user: null, sessionResolved: true }),

  /** Mark the browser session as checked without changing the user payload. */
  setSessionResolved: (sessionResolved) => set({ sessionResolved }),
}))

export default useAuthStore
