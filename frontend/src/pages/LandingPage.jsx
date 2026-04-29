/**
 * LandingPage — public marketing page for Amendly (route: "/").
 *
 * Accessible to unauthenticated users. Sections:
 *   1. Nav bar          — Amendly wordmark + language switcher + "Sign in" button
 *   2. Hero             — headline, sub-copy, primary CTA
 *   3. Feature grid     — 3-column highlights (structured amendments, word diff, consolidation)
 *   4. Pricing          — Free vs Pro cards
 *   5. CTA banner       — secondary call-to-action before footer
 *   6. Footer           — tagline, product/legal links, copyright
 *
 * All copy is fully localised via the "landing" namespace in the four i18n JSON files.
 * Design follows "The Editorial Ledger" (frontend/DESIGN.md):
 *   - Outfit for display/headline text, Inter for body/UI
 *   - Tonal background shifts — no 1px borders for layout separation
 *   - Colour tokens only — no hardcoded hex values
 *   - Ambient shadow for elevated cards
 *
 * Props: none
 */

import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Turnstile } from '@marsidev/react-turnstile'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import HeroDashboardIllustration from '../components/HeroDashboardIllustration'
import { useTranslation } from '../hooks/useTranslation'
import { usePlans, formatPrice, formatExtraUsers, annualMonthlyEquivalent, formatAnnualTotal } from '../hooks/usePlans'
import { useSeoMeta } from '../hooks/useSeoMeta'
import { getTurnstileSiteKey } from '../lib/turnstile'
import LanguageSwitcher from '../components/LanguageSwitcher'
import JsonLd from '../components/JsonLd'

// ---------------------------------------------------------------------------
// Hero inline waitlist form
// ---------------------------------------------------------------------------

/**
 * Compact email capture form embedded directly in the hero section.
 * Mirrors the WaitlistSection API call but uses source "hero".
 */
function HeroWaitlistForm({ t }) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle')
  const turnstileRef = useRef(null)
  const pendingEmailRef = useRef(null)
  const turnstileSiteKey = getTurnstileSiteKey()

  async function submitWithToken(token) {
    setStatus('loading')
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: pendingEmailRef.current, source: 'hero', turnstile_token: token || null }),
      })
      if (res.status === 201) setStatus('success')
      else if (res.status === 409) setStatus('duplicate')
      else { setStatus('error'); turnstileRef.current?.reset() }
    } catch {
      setStatus('error'); turnstileRef.current?.reset()
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!email.trim()) return
    pendingEmailRef.current = email.trim()
    if (turnstileSiteKey) {
      turnstileRef.current?.execute()
    } else {
      submitWithToken(null)
    }
  }

  if (status === 'success') {
    return (
      <div className="mt-2">
        <p className="font-display text-title-md text-amendly-blue font-semibold">{t('landing.waitlist_success_title')}</p>
        <p className="font-body text-body-md text-gray-500 mt-1">{t('landing.waitlist_success_body')}</p>
      </div>
    )
  }

  return (
    <div className="w-full max-w-md">
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3" noValidate>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t('landing.waitlist_email_placeholder')}
          disabled={status === 'loading'}
          className="flex-1 rounded-lg px-4 py-3 font-body text-body-md text-on-surface bg-white border border-gray-200 placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue/40 disabled:opacity-60 shadow-sm"
          aria-label={t('landing.waitlist_email_placeholder')}
        />
        <button
          type="submit"
          disabled={status === 'loading'}
          className="rounded-lg px-6 py-3 font-body text-title-sm text-white bg-amendly-blue hover:bg-blue-700 shadow-lg hover:-translate-y-0.5 transform transition-all disabled:opacity-60 whitespace-nowrap"
        >
          {status === 'loading' ? '…' : t('landing.waitlist_cta')}
        </button>
      </form>

      {(status === 'duplicate' || status === 'error') && (
        <p className="mt-2 font-body text-body-sm text-red-500">
          {status === 'duplicate' ? t('landing.waitlist_error_duplicate') : t('landing.waitlist_error_generic')}
        </p>
      )}

      {turnstileSiteKey && (
        <Turnstile
          ref={turnstileRef}
          siteKey={turnstileSiteKey}
          onSuccess={(token) => submitWithToken(token)}
          onExpire={() => setStatus('idle')}
          onError={() => { setStatus('error'); turnstileRef.current?.reset() }}
          options={{ size: 'invisible', execution: 'execute', action: 'waitlist' }}
        />
      )}

      <p className="mt-3 font-body text-body-sm text-gray-500">
        <Link to="/login" className="text-amendly-blue hover:underline">{t('landing.hero_cta_signin')}</Link>
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Waitlist section
// ---------------------------------------------------------------------------

/**
 * Full-width waitlist capture section placed just before the footer.
 *
 * @param {{ t: (key: string) => string }} props
 */
function WaitlistSection({ t }) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'success' | 'duplicate' | 'error'
  const inputRef = useRef(null)
  const turnstileRef = useRef(null)
  const pendingEmailRef = useRef(null)
  const turnstileSiteKey = getTurnstileSiteKey()

  async function submitWithToken(token) {
    setStatus('loading')
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: pendingEmailRef.current,
          source: 'landing',
          turnstile_token: token || null,
        }),
      })
      if (res.status === 201) {
        setStatus('success')
      } else if (res.status === 409) {
        setStatus('duplicate')
      } else {
        setStatus('error')
        turnstileRef.current?.reset()
      }
    } catch {
      setStatus('error')
      turnstileRef.current?.reset()
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!email.trim()) return
    pendingEmailRef.current = email.trim()
    if (turnstileSiteKey) {
      turnstileRef.current?.execute()
    } else {
      submitWithToken(null)
    }
  }

  return (
    <section
      id="waitlist"
      className="py-24 bg-amendly-blue"
      data-purpose="waitlist-section"
    >
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="font-display text-display-sm text-on-primary mb-4">
          {t('landing.waitlist_title')}
        </h2>
        <p className="font-body text-body-md text-on-primary opacity-80 mb-10">
          {t('landing.waitlist_subtitle')}
        </p>

        {status === 'success' ? (
          <div className="bg-on-primary/10 rounded-md px-8 py-6 inline-block">
            <p className="font-display text-title-md text-on-primary mb-1">
              {t('landing.waitlist_success_title')}
            </p>
            <p className="font-body text-body-md text-on-primary opacity-80">
              {t('landing.waitlist_success_body')}
            </p>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="flex flex-col items-center gap-4"
            noValidate
          >
            <div className="flex flex-col sm:flex-row gap-3 w-full justify-center">
              <input
                ref={inputRef}
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('landing.waitlist_email_placeholder')}
                disabled={status === 'loading'}
                className="flex-1 max-w-sm rounded-md px-4 py-3 font-body text-body-md text-on-surface bg-white placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-white/60 disabled:opacity-60"
                aria-label={t('landing.waitlist_email_placeholder')}
              />
              <button
                type="submit"
                disabled={status === 'loading'}
                className="rounded-md px-8 py-3 font-body text-title-sm bg-on-primary text-amendly-blue hover:opacity-90 transition-opacity focus-visible:outline focus-visible:outline-2 focus-visible:outline-white disabled:opacity-60 whitespace-nowrap"
              >
                {status === 'loading' ? '…' : t('landing.waitlist_cta')}
              </button>
            </div>

            {/* Cloudflare Turnstile — invisible mode, triggered on submit */}
            {turnstileSiteKey && (
              <Turnstile
                ref={turnstileRef}
                siteKey={turnstileSiteKey}
                onSuccess={(token) => submitWithToken(token)}
                onExpire={() => setStatus('idle')}
                onError={() => { setStatus('error'); turnstileRef.current?.reset() }}
                options={{ size: 'invisible', execution: 'execute', action: 'waitlist' }}
              />
            )}
          </form>
        )}

        {(status === 'duplicate' || status === 'error') && (
          <p className="mt-3 font-body text-body-sm text-on-primary opacity-70">
            {status === 'duplicate'
              ? t('landing.waitlist_error_duplicate')
              : t('landing.waitlist_error_generic')}
          </p>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Feature card
// ---------------------------------------------------------------------------

/**
 * A single feature highlight card.
 *
 * @param {{ icon: React.ReactNode, title: string, desc: string }} props
 */
function FeatureCard({ icon, title, desc }) {
  return (
    <div className="bg-surface-container-lowest rounded-md shadow-ambient px-8 py-8 flex flex-col gap-4">
      <div className="w-10 h-10 flex items-center justify-center bg-primary-fixed rounded-md text-on-primary-fixed">
        {icon}
      </div>
      <h3 className="font-display text-headline-sm text-on-surface">{title}</h3>
      <p className="font-body text-body-md text-outline">{desc}</p>
    </div>
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

// ---------------------------------------------------------------------------
// Pricing card
// ---------------------------------------------------------------------------

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

// Skeleton card shown while /api/plans loads
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
// Main component
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { t, lang, setLang } = useTranslation()
  const { plans, loading: plansLoading } = usePlans()
  const [annual, setAnnual] = useState(true)
  const year = new Date().getFullYear()

  useSeoMeta({
    title: 'Amendly — Amendment management for organisations',
    description:
      'Amendly gives associations, NGOs, and federations a structured workflow to collect, review, and consolidate amendments — from first draft to final text.',
    canonical: 'https://amendly.eu/',
    lang: lang || 'en',
  })

  const features = [
    {
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      ),
      title: t('landing.feature_1_title'),
      desc: t('landing.feature_1_desc'),
    },
    {
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      ),
      title: t('landing.feature_2_title'),
      desc: t('landing.feature_2_desc'),
    },
    {
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ),
      title: t('landing.feature_3_title'),
      desc: t('landing.feature_3_desc'),
    },
  ]

  // ---------------------------------------------------------------------- //
  // JSON-LD structured data                                                //
  // ---------------------------------------------------------------------- //

  /** @type {object} WebSite — enables Google Sitelinks + SearchAction */
  const jsonLdWebSite = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Amendly',
    url: 'https://amendly.eu/',
    description:
      'Collaborative amendment management platform for associations, NGOs, and federations.',
    inLanguage: ['en', 'fr', 'de', 'es'],
  }

  /** @type {object} SoftwareApplication — may trigger rich result in SERP */
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
      description: `${plan.included_users === 1 ? '1 user' : `${plan.included_users} users`} included. ${plan.features.join('. ')}.`,
    })),
    publisher: {
      '@type': 'Organization',
      name: 'Amendly',
      url: 'https://amendly.eu/',
      logo: 'https://amendly.eu/og-image.png',
    },
  }

  return (
    <div className="min-h-screen font-sans text-amendly-dark antialiased bg-white">


<JsonLd data={jsonLdWebSite} />
      <JsonLd data={jsonLdApp} />
      <PublicHeader />


<section className="relative pt-16 pb-24 overflow-hidden bg-dots bg-dot-pattern hero-gradient" data-purpose="landing-hero">
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
<div className="flex flex-col lg:flex-row items-center gap-12">

<div className="flex-1 text-left">
<span className="inline-block px-3 py-1 mb-6 text-xs font-bold tracking-wider text-amendly-blue uppercase bg-blue-50 border border-blue-100 rounded-md">
            {t('landing.hero_badge')}
          </span>
<h1 className="text-5xl lg:text-6xl font-bold text-slate-900 leading-tight mb-6">
            {t('landing.hero_title_new')}
          </h1>
<p className="text-xl text-gray-600 mb-10 max-w-xl">
            {t('landing.hero_subtitle_new')}
          </p>
<HeroWaitlistForm t={t} />
</div>

<div className="flex-1 relative" data-purpose="hero-dashboard-preview">
<div className="relative rounded-2xl shadow-2xl overflow-hidden border border-gray-100 bg-white">
<HeroDashboardIllustration />
</div>

<div className="absolute -z-10 -top-12 -right-12 w-64 h-64 bg-blue-50 rounded-full blur-3xl opacity-50"></div>
</div>
</div>
</div>
</section>

<section className="py-24 bg-surface-container-low" data-purpose="features-section" id="features">
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
<div className="max-w-3xl mb-14">
<h3 className="text-lg font-semibold text-gray-500 mb-2">{t('nav_public.features')}</h3>
<h2 className="text-4xl font-bold text-slate-900">{t('landing.features_title')}</h2>
</div>
<div className="grid grid-cols-1 md:grid-cols-3 gap-8">
{features.map((feature) => (
<FeatureCard key={feature.title} icon={feature.icon} title={feature.title} desc={feature.desc} />
))}
</div>
</div>
</section>


<section className="py-24 bg-white" data-purpose="process-section" id="how-it-works">
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
<div className="mb-16">
<h3 className="text-lg font-semibold text-gray-500 mb-2">{t('landing.how_it_works_badge')}</h3>
<h2 className="text-4xl font-bold text-slate-900">{t('landing.how_it_works_title')}</h2>
</div>
<div className="grid grid-cols-1 md:grid-cols-3 gap-12">

<div className="flex flex-col gap-6" data-purpose="process-step-1">
<div className="aspect-video flex items-center justify-center rounded-2xl overflow-hidden">
<img alt="Step 1 Illustration" className="w-full h-full object-contain" src="/images/how_it_works_step_1.png"/>
</div>
<div className="flex gap-4">
<div className="flex-shrink-0 w-12 h-12 bg-blue-50 text-amendly-blue rounded-xl flex items-center justify-center">
<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
</div>
<div>
<h4 className="text-xl font-bold mb-2">{t('landing.step1_title')}</h4>
<p className="text-gray-600 leading-relaxed">{t('landing.step1_desc')}</p>
</div>
</div>
</div>

<div className="flex flex-col gap-6" data-purpose="process-step-2">
<div className="aspect-video flex items-center justify-center rounded-2xl overflow-hidden">
<img alt="Step 2 Illustration" className="w-full h-full object-contain" src="/images/how_it_works_step_2.png"/>
</div>
<div className="flex gap-4">
<div className="flex-shrink-0 w-12 h-12 bg-blue-50 text-amendly-blue rounded-xl flex items-center justify-center">
<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
</div>
<div>
<h4 className="text-xl font-bold mb-2">{t('landing.step2_title')}</h4>
<p className="text-gray-600 leading-relaxed">{t('landing.step2_desc')}</p>
</div>
</div>
</div>

<div className="flex flex-col gap-6" data-purpose="process-step-3">
<div className="aspect-video flex items-center justify-center rounded-2xl overflow-hidden">
<img alt="Step 3 Illustration" className="w-full h-full object-contain" src="/images/how_it_works_step_3.png"/>
</div>
<div className="flex gap-4">
<div className="flex-shrink-0 w-12 h-12 bg-blue-50 text-amendly-blue rounded-xl flex items-center justify-center">
<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
</div>
<div>
<h4 className="text-xl font-bold mb-2">{t('landing.step3_title')}</h4>
<p className="text-gray-600 leading-relaxed">{t('landing.step3_desc')}</p>
</div>
</div>
</div>
</div>
</div>
</section>



      <WaitlistSection t={t} />

      <PublicFooter />


    </div>
  )
}
