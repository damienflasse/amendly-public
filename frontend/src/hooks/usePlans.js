/**
 * usePlans — React hook that fetches active plan configurations from /api/plans.
 *
 * Returns { plans, loading, error } where `plans` is an array of
 * PlanConfigResponse objects sorted by base_price_cents ascending.
 *
 * A module-level cache avoids redundant network requests when multiple
 * components on the same page mount simultaneously (e.g. LandingPage renders
 * both a pricing section and a JSON-LD script that need the same data).
 *
 * SSR / prerender behaviour:
 *   During static prerendering (Node.js, no window), useEffect never runs so
 *   no network request is attempted. STATIC_PLANS is returned immediately so
 *   the prerendered HTML contains real pricing content rather than skeletons.
 *   The client-side bundle fetches live data from the API on hydration and
 *   updates the module-level cache, which is then used by all subsequent
 *   hook instances without another network round-trip.
 *
 * @returns {{ plans: Array, loading: boolean, error: string | null }}
 */

import { useEffect, useState } from 'react'
import { planClient } from '../lib/organisations'

/**
 * Static plan data — used during SSR prerender (no backend available at build
 * time) and as the initial value before the /api/plans fetch resolves.
 * Values must match the latest plan_config defaults after migrations.
 *
 * @type {Array<object>}
 */
const STATIC_PLANS = [
  {
    plan_name: 'solo',
    base_price_cents: 900,
    included_users: 1,
    extra_user_price_cents: 0,
    max_active_documents: 3,
    max_external_contributors: 0,
    stripe_price_id: '',
    stripe_price_id_annual: '',
    features: ['Up to 3 active documents', 'No external contributors', 'Export to Word (DOCX)'],
    is_active: true,
  },
  {
    plan_name: 'team',
    base_price_cents: 2900,
    included_users: 3,
    extra_user_price_cents: 800,
    max_active_documents: 20,
    max_external_contributors: 30,
    stripe_price_id: '',
    stripe_price_id_annual: '',
    features: ['Up to 20 active documents', 'Up to 30 external contributors', 'Export to Word + PDF'],
    is_active: true,
  },
  {
    plan_name: 'organisation',
    base_price_cents: 9900,
    included_users: 10,
    extra_user_price_cents: 600,
    max_active_documents: null,
    max_external_contributors: null,
    stripe_price_id: '',
    stripe_price_id_annual: '',
    features: [
      'Unlimited active documents',
      'Unlimited external contributors',
      'Export to Word + PDF + TXT + CSV + JSON',
      'Member votes on amendments (support / oppose)',
      'Sentiment summary for owners & admins',
    ],
    is_active: true,
  },
]

// Module-level cache — shared across all hook instances for the lifetime of the page.
let _cachedPlans = null
let _cachePromise = null

/**
 * Format a price in euro cents as a display string (e.g. 900 → "€9").
 *
 * @param {number} cents - Price in euro cents.
 * @returns {string} Formatted price string.
 */
export function formatPrice(cents) {
  if (cents === 0) return '€0'
  const euros = cents / 100
  return euros % 1 === 0 ? `€${euros}` : `€${euros.toFixed(2)}`
}

/**
 * Format an extra-user price (e.g. 800 → "+€8 / user / month").
 *
 * @param {number} cents - Extra-user price in euro cents.
 * @returns {string | null} Formatted string, or null if cents is 0.
 */
export function formatExtraUsers(cents) {
  if (!cents) return null
  return `+${formatPrice(cents)} / user / month`
}

/**
 * Calculate the monthly-equivalent price when billed annually (2 months free).
 * Billing annually means paying for 10 months instead of 12.
 *
 * @param {number} cents - Monthly price in euro cents.
 * @returns {number} Annual-billing monthly equivalent in euro cents.
 */
export function annualMonthlyEquivalent(cents) {
  // 2 months free → 10 months paid / 12 displayed
  return Math.round((cents * 10) / 12)
}

/**
 * Format the total annual price (10 months) as a display string.
 *
 * @param {number} cents - Monthly price in euro cents.
 * @returns {string} Formatted annual total (e.g. €90 / year).
 */
export function formatAnnualTotal(cents) {
  const annual = cents * 10
  const euros = annual / 100
  return euros % 1 === 0 ? `€${euros} / year` : `€${euros.toFixed(2)} / year`
}

export function usePlans() {
  // SSR guard: during prerendering there is no window / browser environment.
  // Return the static fallback immediately so the prerendered HTML contains
  // real pricing content.  The real API data is fetched client-side after
  // React hydration via the useEffect below.
  const isSSR = typeof window === 'undefined'

  const [plans, setPlans] = useState(_cachedPlans ?? STATIC_PLANS)
  const [loading, setLoading] = useState(!isSSR && _cachedPlans === null)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Already cached — nothing to do
    if (_cachedPlans !== null) return

    // Deduplicate in-flight requests
    if (!_cachePromise) {
      _cachePromise = planClient.getPlans()
    }

    let cancelled = false
    setLoading(true)

    _cachePromise
      .then((data) => {
        _cachedPlans = data
        if (!cancelled) {
          setPlans(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        _cachePromise = null // allow retry on next mount
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return { plans, loading, error }
}
