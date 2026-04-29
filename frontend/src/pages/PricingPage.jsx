/**
 * PricingPage — dedicated pricing page at "/pricing".
 *
 * Purpose: improve crawl budget and organic ranking for queries such as
 * "amendment management pricing" and "Amendly price". Provides a permanent,
 * indexable URL distinct from the pricing section embedded in the landing page.
 *
 * Sections:
 *   1. Nav bar   — Amendly wordmark + language switcher + "Sign in" button
 *   2. Hero      — headline + subtitle
 *   3. Plans     — pricing cards loaded dynamically from /api/plans
 *   4. FAQ       — 5 common pricing questions + answers
 *   5. CTA       — call-to-action before footer
 *   6. Footer    — minimal footer with back-to-home link
 *
 * SEO:
 *   - Unique <title> and <meta description> via useSeoMeta
 *   - <link rel="canonical"> pointing to https://amendly.eu/pricing
 *   - hreflang alternate links for all 4 supported locales
 *   - JSON-LD SoftwareApplication structured data (generated from live plan data)
 *
 * Prices and features are fetched from GET /api/plans (no auth required).
 * UI labels (names, periods, CTA, FAQ text) remain in i18n JSON.
 * Design follows "The Editorial Ledger" (frontend/DESIGN.md).
 *
 * Props: none
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import { useTranslation } from '../hooks/useTranslation'
import { usePlans, formatPrice, formatExtraUsers, annualMonthlyEquivalent, formatAnnualTotal } from '../hooks/usePlans'
import { useSeoMeta } from '../hooks/useSeoMeta'
import LanguageSwitcher from '../components/LanguageSwitcher'
import JsonLd from '../components/JsonLd'

// ---------------------------------------------------------------------------
// Plan name → i18n key mapping
// ---------------------------------------------------------------------------

const PLAN_I18N = {
  solo: {
    name: 'landing.plan_solo_name',
    period: 'landing.plan_solo_period',
    cta: 'landing.plan_solo_cta',
  },
  team: {
    name: 'landing.plan_team_name',
    period: 'landing.plan_team_period',
    cta: 'landing.plan_team_cta',
    isHighlighted: true,
  },
  organisation: {
    name: 'landing.plan_org_name',
    period: 'landing.plan_org_period',
    cta: 'landing.plan_org_cta',
  },
}

// ---------------------------------------------------------------------------
// Pricing card (local — mirrors the one in LandingPage.jsx)
// ---------------------------------------------------------------------------

/**
 * Monthly / annual billing period toggle.
 *
 * @param {{ annual: boolean, onToggle: () => void, labelMonthly: string, labelAnnual: string, savingsBadge: string }} props
 */
function BillingToggle({ annual, onToggle, labelMonthly, labelAnnual, savingsBadge }) {
  return (
    <div className="flex items-center gap-3 self-center">
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

/**
 * A single pricing tier card.
 *
 * @param {{ name: string, price: string, annualMonthlyPrice?: string, annualTotal?: string, annual: boolean, period: string, usersLabel: string, extraUsers?: string, features: string[], ctaLabel: string, isHighlighted?: boolean }} props
 */
function PricingCard({ name, price, annualMonthlyPrice, annualTotal, annual, period, usersLabel, extraUsers, features, ctaLabel, isHighlighted }) {
  const displayPrice = annual && annualMonthlyPrice ? annualMonthlyPrice : price
  return (
    <div
      className={[
        'rounded-md px-8 py-8 flex flex-col gap-6',
        isHighlighted
          ? 'bg-amendly-blue text-on-primary shadow-ambient'
          : 'bg-surface-container-lowest text-on-surface shadow-ambient',
      ].join(' ')}
    >
      {/* Plan name */}
      <div>
        <span
          className={[
            'font-body text-label-sm tracking-[0.02em] uppercase',
            isHighlighted ? 'text-on-primary opacity-70' : 'text-outline',
          ].join(' ')}
        >
          {name}
        </span>
        <div className="mt-2 flex items-end gap-2">
          <span className="font-display text-display-md">{displayPrice}</span>
          <span
            className={[
              'font-body text-body-md mb-2',
              isHighlighted ? 'opacity-70' : 'text-outline',
            ].join(' ')}
          >
            {period}
          </span>
        </div>
        <p className={['font-body text-label-sm mt-1', isHighlighted ? 'opacity-70' : 'text-outline'].join(' ')}>
          {usersLabel}
          {extraUsers && <span className="block">{extraUsers}</span>}
          {annual && annualTotal && <span className="block">{annualTotal}</span>}
        </p>
      </div>

      {/* Feature list */}
      <ul className="flex flex-col gap-2">
        {features.map((feat) => (
          <li key={feat} className="flex items-start gap-2 font-body text-body-md">
            <span aria-hidden="true" className={isHighlighted ? 'opacity-70' : 'text-secondary'}>
              ✓
            </span>
            {feat}
          </li>
        ))}
      </ul>

      {/* CTA */}
      <Link
        to="/login"
        className={[
          'mt-auto block text-center rounded-md px-8 py-4 font-body text-title-sm transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-secondary',
          isHighlighted
            ? 'bg-on-primary text-amendly-blue'
            : 'bg-amendly-blue text-on-primary',
        ].join(' ')}
      >
        {ctaLabel}
      </Link>
    </div>
  )
}

// Skeleton card shown during the /api/plans fetch
function PricingCardSkeleton({ isHighlighted }) {
  return (
    <div
      className={[
        'rounded-md px-8 py-8 flex flex-col gap-6 animate-pulse',
        isHighlighted ? 'bg-amendly-blue/30 shadow-ambient' : 'bg-surface-container-lowest shadow-ambient',
      ].join(' ')}
    >
      <div className="h-4 bg-outline/20 rounded w-1/3" />
      <div className="h-12 bg-outline/20 rounded w-1/2" />
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => <div key={i} className="h-4 bg-outline/20 rounded w-full" />)}
      </div>
      <div className="h-12 bg-outline/20 rounded" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// FAQ item
// ---------------------------------------------------------------------------

/**
 * A single FAQ question + answer pair.
 *
 * @param {{ question: string, answer: string }} props
 */
function FaqItem({ question, answer }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-display text-title-md text-on-surface">{question}</h3>
      <p className="font-body text-body-md text-outline">{answer}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildUsersLabel(plan) {
  return plan.included_users === 1
    ? '1 user included'
    : `${plan.included_users} users included`
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PricingPage() {
  const { t, lang, setLang } = useTranslation()
  const { plans, loading } = usePlans()
  const [annual, setAnnual] = useState(true)
  const year = new Date().getFullYear()

  useSeoMeta({
    title: t('pricing.meta_title'),
    description: t('pricing.meta_description'),
    canonical: 'https://amendly.eu/pricing',
    lang: lang || 'en',
  })

  // JSON-LD: SoftwareApplication — built dynamically from live plan data
  const jsonLdApp = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Amendly',
    url: 'https://amendly.eu/',
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    description:
      'Amendly gives associations, NGOs, and federations a structured workflow to collect, review, and consolidate amendments — from first draft to final text.',
    offers: plans.map((plan) => ({
      '@type': 'Offer',
      name: plan.plan_name.charAt(0).toUpperCase() + plan.plan_name.slice(1),
      price: String(plan.base_price_cents / 100),
      priceCurrency: 'EUR',
      priceSpecification: {
        '@type': 'UnitPriceSpecification',
        price: String(plan.base_price_cents / 100),
        priceCurrency: 'EUR',
        billingDuration: 'P1M',
      },
      description: `${buildUsersLabel(plan)}. ${plan.features.join('. ')}.`,
    })),
    publisher: {
      '@type': 'Organization',
      name: 'Amendly',
      url: 'https://amendly.eu/',
      logo: 'https://amendly.eu/og-image.png',
    },
  }

  const faqItems = [
    { q: t('pricing.faq_1_q'), a: t('pricing.faq_1_a') },
    { q: t('pricing.faq_2_q'), a: t('pricing.faq_2_a') },
    { q: t('pricing.faq_3_q'), a: t('pricing.faq_3_a') },
    { q: t('pricing.faq_4_q'), a: t('pricing.faq_4_a') },
    { q: t('pricing.faq_5_q'), a: t('pricing.faq_5_a') },
  ]

  return (
    <div className="min-h-screen bg-surface flex flex-col">

      {/* JSON-LD */}
      <JsonLd data={jsonLdApp} />

      {/* ------------------------------------------------------------------ */}
      {/* Nav bar                                                             */}
      {/* ------------------------------------------------------------------ */}
      <PublicHeader />

      {/* ------------------------------------------------------------------ */}
      {/* Hero                                                                */}
      {/* ------------------------------------------------------------------ */}
      <section className="py-12 bg-surface">
        <div className="max-w-5xl mx-auto px-8 flex flex-col items-start gap-4">
          <Link
            to="/"
            className="font-body text-body-md text-secondary hover:underline underline-offset-2"
          >
            {t('pricing.back_home')}
          </Link>
          <h1 className="font-display text-display-md text-on-surface max-w-2xl">
            {t('pricing.title')}
          </h1>
          <p className="font-body text-title-sm text-outline max-w-xl">
            {t('pricing.subtitle')}
          </p>
          <span className="inline-flex items-center bg-primary-fixed text-on-primary-fixed font-body text-label-sm tracking-[0.02em] rounded-md px-4 py-2">
            {t('pricing.trial_badge')}
          </span>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Pricing cards                                                       */}
      {/* ------------------------------------------------------------------ */}
      <section className="py-12 bg-surface-container-low">
        <div className="max-w-5xl mx-auto px-8 flex flex-col gap-6">
          {/* Billing period toggle */}
          <BillingToggle
            annual={annual}
            onToggle={() => setAnnual((a) => !a)}
            labelMonthly={t('pricing.billing_monthly')}
            labelAnnual={t('pricing.billing_annual')}
            savingsBadge={t('pricing.billing_annual_savings')}
          />

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {loading
              ? [false, true, false].map((h, i) => <PricingCardSkeleton key={i} isHighlighted={h} />)
              : plans.map((plan) => {
                  const i18n = PLAN_I18N[plan.plan_name] ?? {}
                  return (
                    <PricingCard
                      key={plan.plan_name}
                      name={i18n.name ? t(i18n.name) : plan.plan_name}
                      price={formatPrice(plan.base_price_cents)}
                      annualMonthlyPrice={formatPrice(annualMonthlyEquivalent(plan.base_price_cents))}
                      annualTotal={formatAnnualTotal(plan.base_price_cents)}
                      annual={annual}
                      period={i18n.period ? t(i18n.period) : '/ month'}
                      usersLabel={buildUsersLabel(plan)}
                      extraUsers={formatExtraUsers(plan.extra_user_price_cents)}
                      features={plan.features}
                      ctaLabel={i18n.cta ? t(i18n.cta) : t('landing.plan_solo_cta')}
                      isHighlighted={i18n.isHighlighted ?? false}
                    />
                  )
                })}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* FAQ                                                                 */}
      {/* ------------------------------------------------------------------ */}
      <section className="py-12 bg-surface" id="faq">
        <div className="max-w-5xl mx-auto px-8 flex flex-col gap-8">
          <h2 className="font-display text-headline-sm text-on-surface">
            {t('pricing.faq_title')}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
            {faqItems.map((item) => (
              <FaqItem key={item.q} question={item.q} answer={item.a} />
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* CTA banner                                                          */}
      {/* ------------------------------------------------------------------ */}
      <section className="py-12 bg-surface-container-low">
        <div className="max-w-5xl mx-auto px-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-8">
          <h2 className="font-display text-headline-sm text-on-surface">
            {t('pricing.cta_title')}
          </h2>
          <Link
            to="/login"
            className="
              shrink-0
              bg-amendly-blue text-on-primary
              font-body text-title-sm
              rounded-md px-8 py-4
              hover:opacity-90 transition-opacity
              focus-visible:outline focus-visible:outline-2 focus-visible:outline-secondary
            "
          >
            {t('pricing.cta_button')}
          </Link>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Footer                                                              */}
      {/* ------------------------------------------------------------------ */}
      <PublicFooter />
    </div>
  )
}
