/**
 * Billing — organisation billing management page.
 *
 * Route: /orgs/:slug/billing
 *
 * Accessible to the organisation owner only. Non-owners are redirected to
 * /orgs/:slug on mount (403 response from the billing API).
 *
 * On mount it fetches:
 *   GET /api/organisations/{slug} — loads org name, plan, and metadata.
 *
 * Features:
 *   - Displays the organisation's current plan (Free / Pro) as a badge.
 *   - For free-plan orgs shows a monthly/annual billing toggle (BillingToggle),
 *     a plan selector (radio buttons), and an "Upgrade" CTA that creates a
 *     Stripe Checkout session and redirects to the Stripe-hosted page.
 *     When annual=true, the annual price (stripe_price_id_annual) is used.
 *   - For paid-plan orgs shows the active plan features and a Customer Portal link.
 *   - Success/cancel query params are handled on return from Stripe Checkout:
 *     ?billing=success — shows a success banner and refreshes the org data.
 *     ?billing=cancelled — shows a neutral cancellation message.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Tonal layering — surface base, cards on surface-container-lowest.
 *   - Manrope for headings, Inter for body/UI text.
 *   - Status badges use soft-fill colours matching the plan tier.
 *   - No 1px borders; structure through background shifts and ambient shadows.
 *
 * Props: none (reads :slug from React Router params)
 * Side effects:
 *   - Uses cookie-backed authenticated API calls.
 *   - window.location.href redirect to Stripe Checkout URL.
 *   - Navigates to /orgs/:slug if user is not the org owner.
 */

import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { billingClient, orgClient } from '../lib/organisations'
import { usePlans, formatPrice, annualMonthlyEquivalent, formatAnnualTotal } from '../hooks/usePlans'
import { useTranslation } from '../hooks/useTranslation'
import LanguageSwitcher from '../components/LanguageSwitcher'

// ---------------------------------------------------------------------------
// Plan badge
// ---------------------------------------------------------------------------

/**
 * Soft-fill badge showing an organisation's billing plan.
 *
 * @param {{ plan: 'free' | 'solo' | 'team' | 'organisation' | 'pro' | 'enterprise' }} props
 */
function PlanBadge({ plan }) {
  const styles = {
    free:         'bg-surface-container-highest text-on-surface',
    solo:         'bg-surface-container-highest text-on-surface',
    team:         'bg-primary-fixed text-on-primary-fixed',
    organisation: 'bg-tertiary-fixed text-on-tertiary-fixed',
    pro:          'bg-primary-fixed text-on-primary-fixed',
    enterprise:   'bg-tertiary-fixed text-on-tertiary-fixed',
  }
  const labels = {
    free: 'Free', solo: 'Solo', team: 'Team',
    organisation: 'Organisation', pro: 'Pro', enterprise: 'Enterprise',
  }
  return (
    <span
      className={`inline-flex items-center px-3 py-1 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[plan] ?? styles.free}`}
    >
      {labels[plan] ?? plan}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Billing toggle
// ---------------------------------------------------------------------------

/**
 * Monthly / annual billing period toggle.
 *
 * @param {{ annual: boolean, onToggle: () => void, labelMonthly: string, labelAnnual: string, savingsBadge: string }} props
 */
function BillingToggle({ annual, onToggle, labelMonthly, labelAnnual, savingsBadge }) {
  return (
    <div className="flex items-center gap-3">
      <span className={['font-body text-body-md', !annual ? 'text-on-surface' : 'text-outline'].join(' ')}>
        {labelMonthly}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={annual}
        onClick={onToggle}
        className={[
          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-secondary',
          annual ? 'bg-amendly-blue' : 'bg-outline/30',
        ].join(' ')}
      >
        <span className="sr-only">{annual ? labelAnnual : labelMonthly}</span>
        <span
          className={[
            'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-ambient transition-transform mt-0.5',
            annual ? 'translate-x-5' : 'translate-x-0.5',
          ].join(' ')}
        />
      </button>
      <span className={['font-body text-body-md', annual ? 'text-on-surface' : 'text-outline'].join(' ')}>
        {labelAnnual}
      </span>
      {annual && (
        <span className="inline-flex items-center bg-primary-fixed text-on-primary-fixed font-body text-label-sm tracking-[0.02em] rounded-md px-3 py-1">
          {savingsBadge}
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Billing page
// ---------------------------------------------------------------------------

/**
 * Billing page component.
 * Protected — ProtectedRoute ensures the user is authenticated before rendering.
 */
export default function Billing() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { t, lang, setLang } = useTranslation()
  const { plans } = usePlans()

  const [org, setOrg] = useState(null)
  const [stats, setStats] = useState(null)  // { active_docs, pending_amendments, member_count }
  const [loading, setLoading] = useState(true)
  const [upgrading, setUpgrading] = useState(false)
  const [managingPortal, setManagingPortal] = useState(false)
  const [error, setError] = useState(null)
  const [selectedPlan, setSelectedPlan] = useState('team')
  const [annual, setAnnual] = useState(true)

  // Determine if we've returned from Stripe
  const billingStatus = searchParams.get('billing') // 'success' | 'cancelled' | null

  // -------------------------------------------------------------------------
  // Load org data
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [orgData, myOrgs, statsData] = await Promise.all([
          orgClient.getOrg(slug),
          orgClient.listMyOrgs(),
          orgClient.getOrgStats(slug),
        ])
        const membership = myOrgs.find((o) => o.slug === slug)
        // Only owners may access the billing page
        if (!membership || membership.role !== 'owner') {
          if (!cancelled) navigate(`/orgs/${slug}`, { replace: true })
          return
        }
        if (!cancelled) {
          setOrg(orgData)
          setStats(statsData)
        }
      } catch (err) {
        if (!cancelled) {
          navigate(`/orgs/${slug}`, { replace: true })
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [slug]) // eslint-disable-line react-hooks/exhaustive-deps

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  async function handleManageSubscription() {
    setError(null)
    setManagingPortal(true)
    try {
      const { portal_url } = await billingClient.createPortalSession(slug)
      window.location.href = portal_url
    } catch (err) {
      setError(err.message)
      setManagingPortal(false)
    }
  }

  async function handleUpgrade() {
    setError(null)
    setUpgrading(true)
    try {
      const successUrl = `${window.location.origin}/orgs/${slug}/billing?billing=success`
      const cancelUrl = `${window.location.origin}/orgs/${slug}/billing?billing=cancelled`
      const { checkout_url } = await billingClient.createCheckoutSession(slug, successUrl, cancelUrl, selectedPlan, annual)
      window.location.href = checkout_url
    } catch (err) {
      setError(err.message)
      setUpgrading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <span className="font-body text-body-md text-outline">{t('common.loading')}</span>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* ------------------------------------------------------------------ */}
      {/* Top navigation bar                                                  */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-surface-container-low px-8 py-4 flex items-center gap-4">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {t('nav.back_dashboard')}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <button
          type="button"
          onClick={() => navigate(`/orgs/${slug}`)}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {org?.name}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('billing.title')}
        </span>

        {/* Language switcher — rightmost */}
        <LanguageSwitcher lang={lang} setLang={setLang} />
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="max-w-2xl mx-auto px-8 py-12">
        {/* Page headline */}
        <div className="mb-12">
          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em]">
            {t('billing.title')}
          </h1>
          <p className="mt-2 font-body text-body-md text-outline">
            {t('billing.manage_plan_for')} <strong>{org?.name}</strong>.
          </p>
        </div>

        {/* Return-from-Stripe banners */}
        {billingStatus === 'success' && (
          <div className="mb-8 bg-primary-fixed text-on-primary-fixed rounded-md px-6 py-4 font-body text-body-md">
            {t('billing.success_banner')}
          </div>
        )}
        {billingStatus === 'cancelled' && (
          <div className="mb-8 bg-surface-container-highest text-on-surface rounded-md px-6 py-4 font-body text-body-md">
            {t('billing.cancelled_banner')}
          </div>
        )}

        {/* Current plan card */}
        <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
              {t('billing.current_plan')}
            </h2>
            <PlanBadge plan={org?.plan ?? 'free'} />
          </div>

          {/* Plan usage bar — driven by live max_active_documents from /api/plans */}
          {(() => {
            const planName = org?.plan ?? 'free'
            // Look up the live limit from the API (null = unlimited → no bar)
            const planConfig = plans.find((p) => p.plan_name === planName)
            const limit = planConfig?.max_active_documents ?? null
            const used = stats?.active_docs ?? 0
            if (limit == null) return null
            const pct = Math.min(100, Math.round((used / limit) * 100))
            const isAtLimit   = used >= limit
            const isNearLimit = pct >= 80
            return (
              <div className="mb-6 space-y-2">
                {/* Label row */}
                <p className="font-body text-label-sm text-outline">
                  {t('billing.usage_docs').replace('{used}', used).replace('{limit}', limit)}
                </p>
                {/* Progress bar */}
                <div className="h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
                  <div
                    className={[
                      'h-full rounded-full transition-all duration-300',
                      isAtLimit   ? 'bg-error'             :
                      isNearLimit ? 'bg-on-error-container' :
                      'bg-amendly-blue',
                    ].join(' ')}
                    style={{ width: `${pct}%` }}
                    role="progressbar"
                    aria-valuenow={used}
                    aria-valuemin={0}
                    aria-valuemax={limit}
                  />
                </div>
                {/* Upgrade nudge — visible at ≥ 80 % */}
                {isNearLimit && (
                  <div className="flex items-start gap-3 bg-error-container/20 rounded-md px-4 py-3">
                    <svg className="w-4 h-4 mt-0.5 shrink-0 text-on-error-container" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                    <div>
                      <p className="font-body text-body-sm text-on-error-container">
                        {isAtLimit
                          ? t('billing.usage_docs_limit_reached')
                          : t('billing.usage_docs_warning')}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          // Scroll to the upgrade section if on a paid plan (no selector shown),
                          // otherwise point to the pricing page
                          const isPaid = ['team', 'organisation'].includes(planName)
                          if (isPaid) {
                            window.location.href = '/pricing'
                          } else {
                            document.getElementById('upgrade-section')?.scrollIntoView({ behavior: 'smooth' })
                          }
                        }}
                        className="mt-1 font-body text-body-sm text-on-error-container underline underline-offset-2 hover:opacity-80 transition-opacity"
                      >
                        {t('billing.usage_upgrade_cta')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })()}

          {/* Plan description key mapped from plan value */}
          {(() => {
            const plan = org?.plan ?? 'free'
            const isPaid = ['solo', 'team', 'organisation', 'pro', 'enterprise'].includes(plan)
            const descKey = {
              free: 'billing.plan_free_desc',
              solo: 'billing.plan_solo_desc',
              team: 'billing.plan_team_desc',
              organisation: 'billing.plan_org_desc',
              pro: 'billing.plan_pro_desc',
              enterprise: 'billing.plan_pro_desc',
            }[plan] ?? 'billing.plan_free_desc'

            if (!isPaid) {
              return (
                <>
                  <p className="font-body text-body-md text-on-surface mb-6">
                    {t(descKey)}
                  </p>

                  {/* Plan selector */}
                  {plans.length > 0 && (
                    <div id="upgrade-section" className="flex flex-col gap-3 mb-8">
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-display text-title-sm text-on-surface">
                          {t('billing.pro_title')}
                        </h3>
                        <BillingToggle
                          annual={annual}
                          onToggle={() => setAnnual((a) => !a)}
                          labelMonthly={t('billing.billing_monthly')}
                          labelAnnual={t('billing.billing_annual')}
                          savingsBadge={t('billing.billing_annual_savings')}
                        />
                      </div>
                      {plans.map((p) => {
                        const monthlyPrice = formatPrice(p.base_price_cents)
                        const annualPrice = annual
                          ? `${formatPrice(annualMonthlyEquivalent(p.base_price_cents))} / month`
                          : null
                        const annualTotal = annual ? formatAnnualTotal(p.base_price_cents) : null
                        return (
                          <label
                            key={p.plan_name}
                            className={[
                              'flex items-start gap-4 rounded-md px-5 py-4 cursor-pointer transition-colors',
                              selectedPlan === p.plan_name
                                ? 'bg-amendly-blue text-on-primary'
                                : 'bg-surface-container-low text-on-surface hover:bg-surface-container',
                            ].join(' ')}
                          >
                            <input
                              type="radio"
                              name="plan"
                              value={p.plan_name}
                              checked={selectedPlan === p.plan_name}
                              onChange={() => setSelectedPlan(p.plan_name)}
                              className="mt-1 accent-secondary"
                            />
                            <div className="flex flex-col gap-1 flex-1">
                              <div className="flex items-baseline gap-2">
                                <span className="font-display text-title-sm capitalize">{p.plan_name}</span>
                                <span className={['font-body text-body-md', selectedPlan === p.plan_name ? 'opacity-80' : 'text-outline'].join(' ')}>
                                  {annual ? annualPrice : `${monthlyPrice} / month`}
                                </span>
                              </div>
                              {annual && annualTotal && (
                                <p className={['font-body text-label-sm', selectedPlan === p.plan_name ? 'opacity-70' : 'text-outline'].join(' ')}>
                                  {annualTotal}
                                </p>
                              )}
                              {p.features.length > 0 && (
                                <p className={['font-body text-body-sm', selectedPlan === p.plan_name ? 'opacity-80' : 'text-outline'].join(' ')}>
                                  {p.features.slice(0, 3).join(' · ')}
                                </p>
                              )}
                            </div>
                          </label>
                        )
                      })}
                    </div>
                  )}

                  {error && (
                    <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-6">
                      {error}
                    </p>
                  )}

                  <button
                    type="button"
                    onClick={handleUpgrade}
                    disabled={upgrading}
                    className="px-8 py-3 bg-amendly-blue text-on-primary rounded-md font-body text-body-md disabled:opacity-50 hover:opacity-90 transition-opacity"
                  >
                    {upgrading ? t('billing.redirecting_stripe') : t('billing.upgrade')}
                  </button>
                </>
              )
            }

            const currentPlanConfig = plans.find((p) => p.plan_name === plan)
            return (
              <>
                <p className="font-body text-body-md text-on-surface mb-2">
                  {t(descKey)}
                </p>
                {currentPlanConfig && currentPlanConfig.features.length > 0 ? (
                  <ul className="font-body text-body-md text-outline list-disc list-inside space-y-1 mb-8">
                    {currentPlanConfig.features.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                ) : (
                  <ul className="font-body text-body-md text-outline list-disc list-inside space-y-1 mb-8">
                    <li>{t('billing.pro_active_1')}</li>
                    <li>{t('billing.pro_active_2')}</li>
                    <li>{t('billing.pro_active_3')}</li>
                    <li>{t('billing.pro_active_4')}</li>
                  </ul>
                )}

                {error && (
                  <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-6">
                    {error}
                  </p>
                )}

                <button
                  type="button"
                  onClick={handleManageSubscription}
                  disabled={managingPortal}
                  className="px-8 py-3 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md disabled:opacity-50 hover:opacity-90 transition-opacity"
                >
                  {managingPortal ? t('billing.opening_portal') : t('billing.manage')}
                </button>
              </>
            )
          })()}
        </div>
      </main>
    </div>
  )
}
