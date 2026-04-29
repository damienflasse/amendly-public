/**
 * OnboardingWizard — multi-step onboarding modal for first-time users.
 *
 * Shown on the Dashboard when the authenticated user has
 * `onboarding_completed === false` (server-side flag, persists across devices).
 *
 * Steps:
 *   0. Profile — fill in name (required), company, job_position
 *      → PATCH /api/auth/me/profile
 *   1. Create organisation — name + auto-generated slug
 *      → POST /api/organisations
 *      → Automatically skipped when `organisations.length > 0`
 *   2. Invite a colleague — email
 *      → POST /api/organisations/:slug/invite
 *      → Automatically skipped when no org is available at this point
 *
 * At the end of every path (completion or skip) the wizard calls
 * POST /api/auth/me/onboarding/complete so the flag is set server-side.
 *
 * Props:
 *   organisations — Current list of organisations the user belongs to.
 *                   Used to decide whether to skip step 1.
 *   onClose       — Called when the wizard finishes or is dismissed.
 *                   Receives the newly created org object (or null).
 *   onOrgCreated  — Called with the new org object after successful creation
 *                   so Dashboard can update its store.
 *   onUserUpdated — Called with the updated user object after profile save or
 *                   onboarding completion so authStore stays current.
 *   t             — Translation function from useTranslation.
 */

import { useRef, useState } from 'react'
import { Turnstile } from '@marsidev/react-turnstile'
import { useNavigate } from 'react-router-dom'
import { authClient } from '../lib/auth'
import { orgClient } from '../lib/organisations'
import { getTurnstileSiteKey } from '../lib/turnstile'
import { ArrowRight, Building2, UserCircle, UserPlus, X } from 'lucide-react'

// ---------------------------------------------------------------------------
// Progress indicator
// ---------------------------------------------------------------------------

/**
 * Horizontal progress dots.
 * @param {{ step: number, total: number }} props
 */
function ProgressDots({ step, total }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`rounded-full transition-all duration-300 ${
            i < step
              ? 'w-2 h-2 bg-amendly-blue'
              : i === step
              ? 'w-4 h-2 bg-amendly-blue'
              : 'w-2 h-2 bg-surface-container-highest'
          }`}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Step 0 — Profile
// ---------------------------------------------------------------------------

/**
 * Profile form — name (required), company, job_position.
 * @param {{ t: Function, initialName: string|null, onDone: Function, onSkip: Function }} props
 */
function StepProfile({ t, initialName, initialCompany, initialJobPosition, onDone, onSkip }) {
  const [name, setName] = useState(initialName || '')
  const [company, setCompany] = useState(initialCompany || '')
  const [jobPosition, setJobPosition] = useState(initialJobPosition || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const updated = await authClient.updateProfile({
        name: name.trim() || null,
        company: company.trim() || null,
        job_position: jobPosition.trim() || null,
      })
      onDone(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 bg-amendly-blue/10 rounded-lg flex items-center justify-center">
          <UserCircle className="w-5 h-5 text-amendly-blue" />
        </div>
        <h2 className="font-display text-xl font-bold text-on-surface">
          {t('onboarding.step1_title')}
        </h2>
      </div>
      <p className="text-sm text-outline mb-6 leading-relaxed">
        {t('onboarding.step1_subtitle')}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('onboarding.step1_name_label')} <span className="text-error normal-case">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={255}
            placeholder={t('onboarding.step1_name_placeholder')}
            className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest"
          />
        </div>

        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('onboarding.step1_company_label')}
          </label>
          <input
            type="text"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            maxLength={255}
            placeholder={t('onboarding.step1_company_placeholder')}
            className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest"
          />
        </div>

        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('onboarding.step1_job_label')}
          </label>
          <input
            type="text"
            value={jobPosition}
            onChange={(e) => setJobPosition(e.target.value)}
            maxLength={255}
            placeholder={t('onboarding.step1_job_placeholder')}
            className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest"
          />
        </div>

        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-lg px-4 py-3">
            {error}
          </p>
        )}

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 py-3 bg-amendly-blue text-white rounded-lg font-semibold disabled:opacity-50 hover:opacity-90 transition-opacity inline-flex items-center justify-center gap-2"
          >
            {loading ? t('common.saving') : t('onboarding.step1_cta')}
            {!loading && <ArrowRight className="w-4 h-4" />}
          </button>
          <button
            type="button"
            onClick={onSkip}
            className="px-6 py-3 text-outline font-body text-sm hover:text-on-surface transition-colors"
          >
            {t('onboarding.skip')}
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Step 1 — Create organisation
// ---------------------------------------------------------------------------

/**
 * Organisation creation form.
 * @param {{ t: Function, onCreated: Function, onSkip: Function }} props
 */
function StepCreateOrg({ t, onCreated, onSkip }) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function handleNameChange(e) {
    const val = e.target.value
    setName(val)
    if (!slugEdited) {
      setSlug(
        val
          .toLowerCase()
          .trim()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-+|-+$/g, '')
      )
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const org = await orgClient.createOrg({ name: name.trim(), slug: slug.trim() })
      onCreated(org)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 bg-amendly-blue/10 rounded-lg flex items-center justify-center">
          <Building2 className="w-5 h-5 text-amendly-blue" />
        </div>
        <h2 className="font-display text-xl font-bold text-on-surface">
          {t('onboarding.step2_title')}
        </h2>
      </div>
      <p className="text-sm text-outline mb-6 leading-relaxed">
        {t('onboarding.step2_desc')}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('org.org_name_label')}
          </label>
          <input
            type="text"
            value={name}
            onChange={handleNameChange}
            required
            maxLength={255}
            placeholder={t('org.org_name_placeholder')}
            className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest"
          />
        </div>

        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('org.url_slug_label')}
          </label>
          <div className="flex items-center gap-2 bg-surface rounded-lg border border-surface-container-highest focus-within:ring-2 focus-within:ring-amendly-blue px-4 py-3">
            <span className="font-body text-body-md text-outline shrink-0">amendly.eu/</span>
            <input
              type="text"
              value={slug}
              onChange={(e) => { setSlug(e.target.value); setSlugEdited(true) }}
              required
              minLength={3}
              maxLength={100}
              pattern="[a-z0-9][a-z0-9\-]{1,98}[a-z0-9]"
              placeholder="acme-federation"
              className="flex-1 bg-transparent font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none"
            />
          </div>
          <p className="mt-1 font-body text-label-sm text-outline">
            {t('org.url_slug_hint')}
          </p>
        </div>

        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-lg px-4 py-3">
            {error}
          </p>
        )}

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 py-3 bg-amendly-blue text-white rounded-lg font-semibold disabled:opacity-50 hover:opacity-90 transition-opacity inline-flex items-center justify-center gap-2"
          >
            {loading ? t('org.creating') : t('org.create_organisation')}
            {!loading && <ArrowRight className="w-4 h-4" />}
          </button>
          <button
            type="button"
            onClick={onSkip}
            className="px-6 py-3 text-outline font-body text-sm hover:text-on-surface transition-colors"
          >
            {t('onboarding.skip')}
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Step 2 — Invite a colleague
// ---------------------------------------------------------------------------

/**
 * Invite a colleague by email.
 * @param {{ t: Function, orgSlug: string, onDone: Function, onSkip: Function }} props
 */
function StepInvite({ t, orgSlug, onDone, onSkip }) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sent, setSent] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState('')
  const turnstileRef = useRef(null)
  const turnstileSiteKey = getTurnstileSiteKey()

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await orgClient.inviteMember(orgSlug, email.trim(), turnstileToken || null)
      setSent(true)
      turnstileRef.current?.reset()
      setTurnstileToken('')
    } catch (err) {
      turnstileRef.current?.reset()
      setTurnstileToken('')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="text-center">
        <div className="mb-6">
          <div className="w-16 h-16 bg-emerald-50 rounded-full flex items-center justify-center mx-auto">
            <UserPlus className="w-8 h-8 text-emerald-600" />
          </div>
        </div>
        <h2 className="font-display text-xl font-bold text-on-surface mb-2">
          {t('onboarding.step3_sent_title')}
        </h2>
        <p className="text-sm text-outline mb-8">
          {t('onboarding.step3_sent_desc').replace('{email}', email)}
        </p>
        <button
          type="button"
          onClick={onDone}
          className="inline-flex items-center justify-center gap-2 px-8 py-3 bg-amendly-blue text-white rounded-lg font-semibold hover:opacity-90 transition-opacity"
        >
          {t('onboarding.done_cta')}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 bg-amendly-blue/10 rounded-lg flex items-center justify-center">
          <UserPlus className="w-5 h-5 text-amendly-blue" />
        </div>
        <h2 className="font-display text-xl font-bold text-on-surface">
          {t('onboarding.step3_title')}
        </h2>
      </div>
      <p className="text-sm text-outline mb-6 leading-relaxed">
        {t('onboarding.step3_desc')}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('onboarding.step3_email_label')}
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            maxLength={255}
            placeholder={t('onboarding.step3_email_placeholder')}
            className="w-full bg-surface rounded-lg px-4 py-3 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-amendly-blue border border-surface-container-highest"
          />
        </div>

        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-lg px-4 py-3">
            {error}
          </p>
        )}

        {turnstileSiteKey && (
          <Turnstile
            ref={turnstileRef}
            siteKey={turnstileSiteKey}
            onSuccess={(token) => setTurnstileToken(token)}
            onExpire={() => setTurnstileToken('')}
            onError={() => setTurnstileToken('')}
            options={{ theme: 'light', size: 'flexible', action: 'org_invite' }}
          />
        )}

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            type="submit"
            disabled={loading || !email.trim()}
            className="flex-1 py-3 bg-amendly-blue text-white rounded-lg font-semibold disabled:opacity-50 hover:opacity-90 transition-opacity inline-flex items-center justify-center gap-2"
          >
            {loading ? t('common.sending') : t('onboarding.step3_cta')}
          </button>
          <button
            type="button"
            onClick={onSkip}
            className="px-6 py-3 text-outline font-body text-sm hover:text-on-surface transition-colors"
          >
            {t('onboarding.skip')}
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * OnboardingWizard — post-signup multi-step modal.
 *
 * @param {{
 *   organisations: Array,
 *   onClose: (org: object|null) => void,
 *   onOrgCreated: (org: object) => void,
 *   onUserUpdated: (user: object) => void,
 *   t: Function
 * }} props
 */
export default function OnboardingWizard({ user, organisations, onClose, onOrgCreated, onUserUpdated, t }) {
  const navigate = useNavigate()

  // Logical steps: 0=profile, 1=org, 2=invite
  // Step 1 is skipped if the user already belongs to an org.
  const TOTAL_STEPS = 3
  const [step, setStep] = useState(0)
  const [createdOrg, setCreatedOrg] = useState(null)

  // The org slug to use for the invite step:
  // prefer the newly created org; fall back to first existing org.
  function getInviteSlug() {
    return createdOrg?.slug ?? organisations?.[0]?.slug ?? null
  }

  async function markComplete() {
    try {
      const updated = await authClient.completeOnboarding()
      onUserUpdated(updated)
    } catch {
      // Non-blocking — the server will re-show the wizard if it fails,
      // but we don't want to block the user from continuing.
    }
  }

  async function finish(org = null) {
    await markComplete()
    onClose(org ?? createdOrg)
    if (createdOrg) {
      navigate(`/orgs/${createdOrg.slug}`)
    }
  }

  // Advance to next logical step; skip step 1 if user already has orgs.
  function goNext() {
    if (step === 0) {
      // Go to org step — but skip it if user already has orgs
      if (organisations && organisations.length > 0) {
        const inviteSlug = getInviteSlug()
        if (inviteSlug) {
          setStep(2)
        } else {
          finish()
        }
      } else {
        setStep(1)
      }
    } else if (step === 1) {
      // After org creation/skip — go to invite if there's a slug
      const inviteSlug = createdOrg?.slug ?? organisations?.[0]?.slug ?? null
      if (inviteSlug) {
        setStep(2)
      } else {
        finish()
      }
    } else {
      // step 2 done
      finish()
    }
  }

  function handleProfileDone(updatedUser) {
    onUserUpdated(updatedUser)
    goNext()
  }

  function handleOrgCreated(org) {
    setCreatedOrg(org)
    onOrgCreated(org)
    // Always offer invite after creating org
    setStep(2)
  }

  // "Passer" on any step: just advance without saving
  function handleSkip() {
    if (step === 0) {
      // Determine next step same as goNext
      if (organisations && organisations.length > 0) {
        const inviteSlug = getInviteSlug()
        inviteSlug ? setStep(2) : finish()
      } else {
        setStep(1)
      }
    } else if (step === 1) {
      const inviteSlug = organisations?.[0]?.slug ?? null
      inviteSlug ? setStep(2) : finish()
    } else {
      finish()
    }
  }

  // Visible progress: map logical step to dot index
  const dotIndex = step  // 0, 1, 2

  const inviteSlug = getInviteSlug()

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      role="dialog"
      aria-modal="true"
      aria-label={t('onboarding.step1_title')}
    >
      {/* Panel */}
      <div className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-lg p-8 animate-fade-in-up">

        {/* Close button — available on step 0 only */}
        {step === 0 && (
          <button
            type="button"
            onClick={() => finish()}
            aria-label="Close"
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full text-outline hover:bg-surface-container-highest transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Progress dots */}
        <ProgressDots step={dotIndex} total={TOTAL_STEPS} />

        {/* Step content */}
        {step === 0 && (
          <StepProfile
            t={t}
            initialName={user?.name ?? null}
            initialCompany={user?.company ?? null}
            initialJobPosition={user?.job_position ?? null}
            onDone={handleProfileDone}
            onSkip={handleSkip}
          />
        )}

        {step === 1 && (
          <StepCreateOrg
            t={t}
            onCreated={handleOrgCreated}
            onSkip={handleSkip}
          />
        )}

        {step === 2 && inviteSlug && (
          <StepInvite
            t={t}
            orgSlug={inviteSlug}
            onDone={() => finish()}
            onSkip={() => finish()}
          />
        )}
      </div>
    </div>
  )
}
