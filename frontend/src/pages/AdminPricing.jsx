/**
 * AdminPricing — platform administrator pricing configuration page.
 *
 * Route: /admin/pricing
 *
 * Accessible to platform superusers only. Non-superusers are redirected to
 * /dashboard on mount (403 response from the admin API).
 *
 * On mount it fetches:
 *   GET /api/admin/plans — loads all plan configurations (active and inactive).
 *
 * Features:
 *   - Displays all plan configurations as editable cards.
 *   - Each card supports inline editing of:
 *       • Base price (displayed in €, stored in cents)
 *       • Included users
 *       • Extra user price (displayed in €, stored in cents)
 *       • Max active documents (empty = unlimited)
 *       • Max external contributors (empty = unlimited)
 *       • Stripe Price ID (monthly)
 *       • Stripe Price ID (annual)
 *       • Features (one per line in a textarea)
 *       • Active/inactive toggle
 *   - Save via PATCH /api/admin/plans/{name} with a "Saved." confirmation.
 *   - Prices displayed and edited in euros (converted to/from cents on save).
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - bg-surface-container-lowest cards with shadow-ambient.
 *   - Manrope for headings, Inter for body/UI text.
 *   - No 1px borders; structure through background shifts.
 *
 * Props: none (reads from API via planClient)
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { planClient } from '../lib/organisations'
import { useTranslation } from '../hooks/useTranslation'
import LanguageSwitcher from '../components/LanguageSwitcher'

// ---------------------------------------------------------------------------
// PlanConfigCard — a single editable plan card
// ---------------------------------------------------------------------------

/**
 * Editable card for one plan configuration row.
 *
 * @param {{ plan: object, onSaved: function }} props
 *   plan    — PlanConfigResponse from the API.
 *   onSaved — Called with the updated plan after a successful PATCH.
 */
function PlanConfigCard({ plan, onSaved }) {
  const { t } = useTranslation()
  // Local editing state — values in euros for price fields
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')
  const [error, setError] = useState(null)

  // Form fields
  const [basePrice, setBasePrice] = useState(
    (plan.base_price_cents / 100).toString()
  )
  const [includedUsers, setIncludedUsers] = useState(
    plan.included_users.toString()
  )
  const [extraUserPrice, setExtraUserPrice] = useState(
    (plan.extra_user_price_cents / 100).toString()
  )
  const [maxDocs, setMaxDocs] = useState(
    plan.max_active_documents != null ? plan.max_active_documents.toString() : ''
  )
  const [maxExternalContributors, setMaxExternalContributors] = useState(
    plan.max_external_contributors != null ? plan.max_external_contributors.toString() : ''
  )
  const [stripePriceId, setStripePriceId] = useState(plan.stripe_price_id || '')
  const [stripePriceIdAnnual, setStripePriceIdAnnual] = useState(
    plan.stripe_price_id_annual || ''
  )
  const [featuresText, setFeaturesText] = useState(
    (plan.features || []).join('\n')
  )
  const [isActive, setIsActive] = useState(plan.is_active)

  // Keep local state in sync when the parent refreshes the plan object
  // (e.g. after a successful save from another card or a parent re-fetch).
  useEffect(() => {
    if (!editing) {
      setBasePrice((plan.base_price_cents / 100).toString())
      setIncludedUsers(plan.included_users.toString())
      setExtraUserPrice((plan.extra_user_price_cents / 100).toString())
      setMaxDocs(plan.max_active_documents != null ? plan.max_active_documents.toString() : '')
      setMaxExternalContributors(
        plan.max_external_contributors != null ? plan.max_external_contributors.toString() : ''
      )
      setStripePriceId(plan.stripe_price_id || '')
      setStripePriceIdAnnual(plan.stripe_price_id_annual || '')
      setFeaturesText((plan.features || []).join('\n'))
      setIsActive(plan.is_active)
    }
  }, [plan]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave() {
    setError(null)
    setSaving(true)
    try {
      const payload = {
        base_price_cents: Math.round(parseFloat(basePrice) * 100) || 0,
        included_users: parseInt(includedUsers, 10) || 1,
        extra_user_price_cents: Math.round(parseFloat(extraUserPrice) * 100) || 0,
        // Empty string → -1 sentinel (unlimited); otherwise parse integer
        max_active_documents: maxDocs.trim() === '' ? -1 : parseInt(maxDocs, 10),
        max_external_contributors:
          maxExternalContributors.trim() === ''
            ? -1
            : parseInt(maxExternalContributors, 10),
        stripe_price_id: stripePriceId.trim(),
        stripe_price_id_annual: stripePriceIdAnnual.trim(),
        features: featuresText
          .split('\n')
          .map((f) => f.trim())
          .filter(Boolean),
        is_active: isActive,
      }
      const updated = await planClient.adminUpdatePlan(plan.plan_name, payload)
      onSaved(updated)
      setEditing(false)
      setSavedMsg(t('admin.saved'))
      setTimeout(() => setSavedMsg(''), 2000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  function handleCancel() {
    // Reset to current plan values
    setBasePrice((plan.base_price_cents / 100).toString())
    setIncludedUsers(plan.included_users.toString())
    setExtraUserPrice((plan.extra_user_price_cents / 100).toString())
    setMaxDocs(plan.max_active_documents != null ? plan.max_active_documents.toString() : '')
    setMaxExternalContributors(
      plan.max_external_contributors != null ? plan.max_external_contributors.toString() : ''
    )
    setStripePriceId(plan.stripe_price_id || '')
    setStripePriceIdAnnual(plan.stripe_price_id_annual || '')
    setFeaturesText((plan.features || []).join('\n'))
    setIsActive(plan.is_active)
    setError(null)
    setEditing(false)
  }

  const labelClass = 'font-body text-label-sm text-outline block mb-1'
  const inputClass =
    'w-full bg-surface-container rounded px-3 py-2 font-body text-body-md text-on-surface focus:outline-none focus:ring-1 focus:ring-amendly-blue'

  return (
    <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8">
      {/* Card header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] capitalize">
          {plan.plan_name}
        </h2>
        <div className="flex items-center gap-3">
          {savedMsg && (
            <span className="font-body text-body-sm text-secondary">{savedMsg}</span>
          )}
          {!editing ? (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="px-4 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 transition-opacity"
            >
              {t('admin.edit')}
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCancel}
                disabled={saving}
                className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {t('admin.cancel')}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {saving ? t('admin.saving') : t('admin.save')}
              </button>
            </div>
          )}
        </div>
      </div>

      {error && (
        <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-6">
          {error}
        </p>
      )}

      {/* Fields — read-only or editable depending on `editing` */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Base price */}
        <div>
          <label className={labelClass}>{t('admin.field_base_price')}</label>
          {editing ? (
            <input
              type="number"
              step="0.01"
              min="0"
              value={basePrice}
              onChange={(e) => setBasePrice(e.target.value)}
              className={inputClass}
            />
          ) : (
            <p className="font-body text-body-md text-on-surface">
              €{(plan.base_price_cents / 100).toFixed(2).replace(/\.00$/, '')}
            </p>
          )}
        </div>

        {/* Included users */}
        <div>
          <label className={labelClass}>{t('admin.field_included_users')}</label>
          {editing ? (
            <input
              type="number"
              min="1"
              value={includedUsers}
              onChange={(e) => setIncludedUsers(e.target.value)}
              className={inputClass}
            />
          ) : (
            <p className="font-body text-body-md text-on-surface">{plan.included_users}</p>
          )}
        </div>

        {/* Extra user price */}
        <div>
          <label className={labelClass}>{t('admin.field_extra_user_price')}</label>
          {editing ? (
            <input
              type="number"
              step="0.01"
              min="0"
              value={extraUserPrice}
              onChange={(e) => setExtraUserPrice(e.target.value)}
              className={inputClass}
            />
          ) : (
            <p className="font-body text-body-md text-on-surface">
              {plan.extra_user_price_cents
                ? `€${(plan.extra_user_price_cents / 100).toFixed(2).replace(/\.00$/, '')}`
                : '—'}
            </p>
          )}
        </div>

        {/* Max active documents */}
        <div>
          <label className={labelClass}>{t('admin.field_max_docs')}</label>
          {editing ? (
            <input
              type="number"
              min="1"
              placeholder={t('admin.unlimited').toLowerCase()}
              value={maxDocs}
              onChange={(e) => setMaxDocs(e.target.value)}
              className={inputClass}
            />
          ) : (
            <p className="font-body text-body-md text-on-surface">
              {plan.max_active_documents != null ? plan.max_active_documents : t('admin.unlimited')}
            </p>
          )}
        </div>

        {/* Max external contributors */}
        <div>
          <label className={labelClass}>{t('admin.field_max_contributors')}</label>
          {editing ? (
            <input
              type="number"
              min="0"
              placeholder={t('admin.unlimited').toLowerCase()}
              value={maxExternalContributors}
              onChange={(e) => setMaxExternalContributors(e.target.value)}
              className={inputClass}
            />
          ) : (
            <p className="font-body text-body-md text-on-surface">
              {plan.max_external_contributors != null ? plan.max_external_contributors : t('admin.unlimited')}
            </p>
          )}
        </div>

        {/* Stripe Price ID (monthly) */}
        <div>
          <label className={labelClass}>{t('admin.field_stripe_monthly')}</label>
          {editing ? (
            <input
              type="text"
              placeholder="price_xxxxxx"
              value={stripePriceId}
              onChange={(e) => setStripePriceId(e.target.value)}
              className={inputClass}
            />
          ) : (
            <p className="font-body text-body-md text-on-surface font-mono text-label-sm">
              {plan.stripe_price_id || '—'}
            </p>
          )}
        </div>

        {/* Stripe Price ID (annual) */}
        <div>
          <label className={labelClass}>{t('admin.field_stripe_annual')}</label>
          {editing ? (
            <input
              type="text"
              placeholder="price_xxxxxx"
              value={stripePriceIdAnnual}
              onChange={(e) => setStripePriceIdAnnual(e.target.value)}
              className={inputClass}
            />
          ) : (
            <p className="font-body text-body-md text-on-surface font-mono text-label-sm">
              {plan.stripe_price_id_annual || '—'}
            </p>
          )}
        </div>

        {/* Active toggle */}
        <div>
          <label className={labelClass}>{t('admin.field_active')}</label>
          {editing ? (
            <label className="flex items-center gap-3 cursor-pointer mt-1">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="w-4 h-4 accent-primary"
              />
              <span className="font-body text-body-md text-on-surface">
                {isActive ? t('admin.active') : t('admin.inactive')}
              </span>
            </label>
          ) : (
            <p className="font-body text-body-md text-on-surface">
              {plan.is_active ? t('admin.active') : t('admin.inactive')}
            </p>
          )}
        </div>
      </div>

      {/* Features */}
      <div className="mt-6">
        <label className={labelClass}>{t('admin.field_features')}</label>
        {editing ? (
          <textarea
            rows={4}
            value={featuresText}
            onChange={(e) => setFeaturesText(e.target.value)}
            className={`${inputClass} resize-y`}
            placeholder="Feature 1&#10;Feature 2&#10;Feature 3"
          />
        ) : (
          <ul className="list-disc list-inside space-y-1">
            {(plan.features || []).map((f) => (
              <li key={f} className="font-body text-body-md text-on-surface">
                {f}
              </li>
            ))}
            {(plan.features || []).length === 0 && (
              <li className="font-body text-body-md text-outline">{t('admin.no_features')}</li>
            )}
          </ul>
        )}
      </div>

      {/* Last updated */}
      <p className="mt-6 font-body text-label-sm text-outline">
        {t('admin.last_updated').replace('{date}', new Date(plan.updated_at).toLocaleString())}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AdminPricing page
// ---------------------------------------------------------------------------

/**
 * Admin pricing page component.
 * Protected — ProtectedRoute ensures the user is authenticated before rendering.
 * Redirects to /dashboard if the user is not a superuser (API returns 403).
 */
export default function AdminPricing() {
  const navigate = useNavigate()
  const { t, lang, setLang } = useTranslation()

  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await planClient.adminListPlans()
        if (!cancelled) setPlans(data)
      } catch (err) {
        if (!cancelled) {
          if (err.message.includes('403') || err.message.toLowerCase().includes('superuser')) {
            navigate('/dashboard', { replace: true })
          } else {
            setError(err.message)
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function handlePlanSaved(updatedPlan) {
    setPlans((prev) =>
      prev.map((p) => (p.plan_name === updatedPlan.plan_name ? updatedPlan : p))
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <span className="font-body text-body-md text-outline">{t('common.loading')}</span>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Nav */}
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
          onClick={() => navigate('/admin/dashboard')}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {t('admin.nav_admin_dashboard')}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('admin.pricing_title')}
        </span>
        <LanguageSwitcher lang={lang} setLang={setLang} />
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto px-8 py-12">
        <div className="mb-12">
          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em]">
            {t('admin.pricing_title')}
          </h1>
          <p className="mt-2 font-body text-body-md text-outline">
            {t('admin.pricing_subtitle')}
          </p>
        </div>

        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-8">
            {error}
          </p>
        )}

        <div className="flex flex-col gap-8">
          {plans.map((plan) => (
            <PlanConfigCard
              key={plan.plan_name}
              plan={plan}
              onSaved={handlePlanSaved}
            />
          ))}
          {plans.length === 0 && !error && (
            <p className="font-body text-body-md text-outline">
              {t('admin.no_plans')}
            </p>
          )}
        </div>
      </main>
    </div>
  )
}
