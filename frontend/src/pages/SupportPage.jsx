/**
 * SupportPage — authenticated support contact page at /support.
 *
 * Detects the user's highest plan across all their organisations to determine
 * the support tier:
 *   - "priority"  → Team or Organisation plan  (< 4h response)
 *   - "standard"  → Solo plan                  (< 24h response)
 *   - "community" → Free / no paid plan        (Help Center only)
 *
 * Shows:
 *   - Support tier badge + SLA information
 *   - Contact form (subject category + free-text message)
 *   - Upgrade CTA for community-tier users
 *
 * Props: none
 * Side effects: reads authStore + orgStore and submits requests to /api/support.
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import useAuthStore from '../store/authStore'
import useOrgStore from '../store/orgStore'
import { MessageCircle, Clock, Shield, Star, Send, ArrowUpRight, BookOpen } from 'lucide-react'
import { supportClient } from '../lib/support'

// ---------------------------------------------------------------------------
// Plan tier helpers
// ---------------------------------------------------------------------------

const PLAN_RANK = { free: 0, solo: 1, team: 2, organisation: 3, pro: 2 }

/**
 * Returns the highest-ranked plan name across all of the user's organisations.
 * Falls back to "free".
 */
function getHighestPlan(userPlan, organisations) {
  const initialPlan = userPlan || 'free'
  if (!organisations || organisations.length === 0) return initialPlan
  return organisations.reduce((best, org) => {
    const rank = PLAN_RANK[org.plan] ?? 0
    return rank > (PLAN_RANK[best] ?? 0) ? org.plan : best
  }, initialPlan)
}

/**
 * Maps a plan name to a support tier key: "priority" | "standard" | "community".
 */
function getTier(plan) {
  const rank = PLAN_RANK[plan] ?? 0
  if (rank >= 2) return 'priority'
  if (rank === 1) return 'standard'
  return 'community'
}

// ---------------------------------------------------------------------------
// Tier badge
// ---------------------------------------------------------------------------

/**
 * Styled badge showing the support tier with an icon and label.
 *
 * @param {{ tier: "priority"|"standard"|"community", t: function }} props
 */
function TierBadge({ tier, t }) {
  const styles = {
    priority:  { bg: 'bg-amber-50 border-amber-200',  text: 'text-amber-800',  icon: <Star className="w-4 h-4 text-amber-500" /> },
    standard:  { bg: 'bg-blue-50 border-blue-200',    text: 'text-blue-800',   icon: <Shield className="w-4 h-4 text-blue-500" /> },
    community: { bg: 'bg-slate-50 border-slate-200',  text: 'text-slate-700',  icon: <BookOpen className="w-4 h-4 text-slate-500" /> },
  }
  const s = styles[tier]
  const label = t(`support.${tier}_badge`)
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border font-medium text-sm ${s.bg} ${s.text}`}>
      {s.icon}
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Tier info card
// ---------------------------------------------------------------------------

/**
 * Card showing the SLA and tier description for the user's current tier.
 *
 * @param {{ tier: "priority"|"standard"|"community", t: function }} props
 */
function TierInfoCard({ tier, t }) {
  const sla = t(`support.sla_${tier}`)
  const desc = t(`support.${tier}_desc`)

  const colours = {
    priority:  'bg-amber-50 border-amber-100',
    standard:  'bg-blue-50 border-blue-100',
    community: 'bg-slate-50 border-slate-100',
  }

  return (
    <div className={`rounded-xl border p-5 flex gap-4 ${colours[tier]}`}>
      <Clock className="w-5 h-5 mt-0.5 shrink-0 text-slate-500" />
      <div>
        <p className="font-semibold text-slate-900 text-sm mb-1">{sla}</p>
        <p className="text-slate-600 text-sm leading-relaxed">{desc}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SupportPage
// ---------------------------------------------------------------------------

export default function SupportPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { organisations } = useOrgStore()

  useSeoMeta({
    title: t('support.meta_title'),
    description: t('support.page_subtitle'),
    noindex: true,
  })

  const highestPlan = getHighestPlan(user?.plan, organisations)
  const tier = getTier(highestPlan)

  const [category, setCategory] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'sending' | 'sent'
  const [error, setError] = useState(null)

  const categories = [
    { value: 'billing',   label: t('support.cat_billing') },
    { value: 'account',   label: t('support.cat_account') },
    { value: 'documents', label: t('support.cat_documents') },
    { value: 'export',    label: t('support.cat_export') },
    { value: 'other',     label: t('support.cat_other') },
  ]

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setStatus('sending')
    try {
      await supportClient.sendSupportRequest({ category, subject, message })
      setStatus('sent')
    } catch (err) {
      setError(err?.message ?? t('support.error'))
      setStatus('idle')
    }
  }

  return (
    <div className="min-h-screen bg-surface font-body text-on-surface">

      {/* ------------------------------------------------------------------ */}
      {/* Header                                                               */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-surface-container-low px-6 py-4 flex items-center justify-between border-b border-surface-container-highest/40">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {t('support.back_dashboard')}
        </button>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          Amendly
        </span>
        <div className="w-28" /> {/* spacer */}
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Page body                                                             */}
      {/* ------------------------------------------------------------------ */}
      <main className="max-w-2xl mx-auto px-6 py-12">

        {/* Page title + tier badge */}
        <div className="mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <h1 className="font-display text-display-sm text-on-surface tracking-[-0.02em]">
              {t('support.page_title')}
            </h1>
            <TierBadge tier={tier} t={t} />
          </div>
          <p className="font-body text-body-md text-outline">
            {t('support.page_subtitle')}
          </p>
        </div>

        {/* Tier info */}
        <div className="mb-8">
          <TierInfoCard tier={tier} t={t} />
        </div>

        {/* Community tier — upgrade CTA */}
        {tier === 'community' && (
          <div className="mb-8 bg-amendly-blue/5 border border-amendly-blue/20 rounded-xl p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex-1">
              <p className="font-semibold text-on-surface text-sm mb-1">{t('support.upgrade_cta')}</p>
              <p className="text-outline text-sm">
                {t('billing.pro_active_4')}
              </p>
            </div>
            <Link
              to="/pricing"
              className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-amendly-blue text-white rounded-lg font-semibold text-sm hover:opacity-90 transition-opacity shrink-0"
            >
              {t('billing.upgrade')}
              <ArrowUpRight className="w-4 h-4" />
            </Link>
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Contact form / success                                             */}
        {/* ---------------------------------------------------------------- */}
        <div className="bg-surface-container-lowest rounded-xl shadow-ambient p-8">
          {status === 'sent' ? (
            /* Success state */
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-amendly-blue/10 rounded-full flex items-center justify-center mx-auto mb-5">
                <MessageCircle className="w-7 h-7 text-amendly-blue" />
              </div>
              <h2 className="font-display text-headline-sm text-on-surface mb-3">
                {t('support.success_title')}
              </h2>
              <p className="font-body text-body-md text-outline mb-6 max-w-xs mx-auto leading-relaxed">
                {t('support.success_desc')}
              </p>
              <button
                type="button"
                onClick={() => { setStatus('idle'); setSubject(''); setMessage(''); setCategory(''); setError(null) }}
                className="px-6 py-2.5 bg-surface-container-highest text-on-surface rounded-lg font-body text-body-md hover:bg-surface-container-high transition-colors"
              >
                {t('support.send_another')}
              </button>
            </div>
          ) : (
            /* Form */
            <form onSubmit={handleSubmit} className="space-y-5">
              <h2 className="font-display text-headline-sm text-on-surface mb-1">
                {t('support.form_title')}
              </h2>

              {/* Category */}
              <div>
                <label htmlFor="support-category" className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
                  {t('support.category_label')}
                </label>
                <select
                  id="support-category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  required
                  disabled={status === 'sending'}
                  className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest appearance-none"
                >
                  <option value="" disabled>—</option>
                  {categories.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>

              {/* Subject */}
              <div>
                <label htmlFor="support-subject" className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
                  {t('support.subject_label')}
                </label>
                <input
                  id="support-subject"
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  required
                  maxLength={200}
                  disabled={status === 'sending'}
                  placeholder={t('support.subject_placeholder')}
                  className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest"
                />
              </div>

              {/* Message */}
              <div>
                <label htmlFor="support-message" className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
                  {t('support.message_label')}
                </label>
                <textarea
                  id="support-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  required
                  rows={5}
                  disabled={status === 'sending'}
                  placeholder={t('support.message_placeholder')}
                  className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest resize-none"
                />
              </div>

              {/* Prefilled user info (read-only) */}
              {user?.email && (
                <p className="font-body text-label-sm text-outline">
                  {t('support.sending_as')} <strong className="text-on-surface">{user.email}</strong>
                  {' · '}
                  <span className="capitalize">{t(`support.${tier}_badge`)}</span>
                </p>
              )}

              {error && (
                <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={status === 'sending'}
                className="w-full flex items-center justify-center gap-2 py-3 bg-amendly-blue text-white rounded-lg font-semibold disabled:opacity-60 hover:opacity-90 transition-opacity"
              >
                {status === 'sending' ? (
                  t('support.sending')
                ) : (
                  <>
                    {t('support.send_btn')}
                    <Send className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Help center link                                                   */}
        {/* ---------------------------------------------------------------- */}
        <div className="mt-6 text-center">
          <Link
            to="/help"
            className="font-body text-body-md text-secondary hover:underline inline-flex items-center gap-1"
          >
            <BookOpen className="w-4 h-4" />
            {t('support.help_center_link')}
          </Link>
        </div>

      </main>
    </div>
  )
}
