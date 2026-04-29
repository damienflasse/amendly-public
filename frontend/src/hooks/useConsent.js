/**
 * useConsent — reads the GDPR cookie consent decision from localStorage.
 *
 * The CookieBanner writes `amendly_cookie_consent = "accepted" | "declined"`
 * when the user makes a choice. This hook exposes that value as a typed object
 * so any component or effect can gate analytics or tracking behind consent.
 *
 * This hook is read-only — it does not write to localStorage. All writes are
 * owned by CookieBanner to keep a single source of truth.
 *
 * SSR-safe: returns `{ accepted: false, declined: false, pending: true }` in
 * Node.js environments (prerendering) where localStorage is unavailable.
 *
 * Usage:
 *   const { accepted, declined, pending } = useConsent()
 *   // pending === true  → user has not yet made a choice
 *   // accepted === true → user clicked "Accept"
 *   // declined === true → user clicked "Decline"
 *
 * @returns {{ accepted: boolean, declined: boolean, pending: boolean }}
 */

const CONSENT_KEY = 'amendly_cookie_consent'

/** Guard for SSR environments (Node.js prerendering) */
const isClient = typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'

export function useConsent() {
  const stored = isClient ? localStorage.getItem(CONSENT_KEY) : null

  return {
    accepted: stored === 'accepted',
    declined: stored === 'declined',
    pending: stored === null,
  }
}
