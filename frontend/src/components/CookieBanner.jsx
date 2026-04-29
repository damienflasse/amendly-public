/**
 * CookieBanner — GDPR cookie consent banner.
 *
 * Shown on first visit to any route. Persists the user's choice to localStorage
 * under the key `amendly_cookie_consent` with value "accepted" or "declined".
 *
 * Once dismissed (either accepted or declined) the banner is hidden for the
 * remainder of the session and all future sessions.
 *
 * Analytics (or any other non-essential tracking) must check this key before
 * loading. No analytics are loaded until the user explicitly accepts.
 *
 * SSR-safe: localStorage access is guarded by an isClient check so this
 * component can be rendered during prerendering without throwing.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Fixed to the bottom of the viewport, full width.
 *   - Tonal layering — surface-container-low background, no 1px borders.
 *   - Manrope not used (body/UI text only here).
 *   - Two actions: primary "Accept" button, ghost "Decline" link-style button.
 *
 * Props: none
 * Side effects:
 *   - Reads `amendly_cookie_consent` from localStorage on mount.
 *   - Writes `amendly_cookie_consent` to localStorage on user action.
 */

import { useState } from 'react'
import { useTranslation } from '../hooks/useTranslation'

const CONSENT_KEY = 'amendly_cookie_consent'

/** Guard for SSR environments (Node.js prerendering) */
const isClient = typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'

export default function CookieBanner() {
  const { t } = useTranslation()

  // Initialise: if a consent decision is already stored, don't show the banner.
  // During SSR (isClient = false) always treat as "not visible" — the banner is
  // a client-only UX element and should not appear in prerendered HTML.
  const [visible, setVisible] = useState(() => {
    if (!isClient) return false
    return !localStorage.getItem(CONSENT_KEY)
  })

  if (!visible) return null

  function handleAccept() {
    if (isClient) localStorage.setItem(CONSENT_KEY, 'accepted')
    setVisible(false)
  }

  function handleDecline() {
    if (isClient) localStorage.setItem(CONSENT_KEY, 'declined')
    setVisible(false)
  }

  return (
    <div
      role="region"
      aria-label="Cookie consent"
      className="fixed bottom-0 inset-x-0 z-50 bg-surface-container-low px-8 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
    >
      <p className="font-body text-body-md text-on-surface max-w-2xl">
        {t('cookie.message')}
      </p>

      <div className="flex items-center gap-4 shrink-0">
        <button
          type="button"
          onClick={handleAccept}
          className="px-6 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 transition-opacity focus-visible:outline focus-visible:outline-2 focus-visible:outline-secondary"
        >
          {t('cookie.accept')}
        </button>
        <button
          type="button"
          onClick={handleDecline}
          className="font-body text-body-md text-secondary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-secondary rounded"
        >
          {t('cookie.decline')}
        </button>
      </div>
    </div>
  )
}
