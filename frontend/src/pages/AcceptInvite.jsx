/**
 * AcceptInvite — invite acceptance page.
 *
 * Route: /invitations/accept?token=<invite-token>
 *
 * Flow:
 *   1. Fetch GET /api/invitations/preview (no auth) to display the org name
 *      and invitee email before the user has authenticated.
 *   2a. If the user is NOT authenticated: render the invitation card with
 *       an "Accept invitation" button that links to /login?redirect=… and
 *       a plain "Sign in first" link below it.
 *   2b. If the user IS authenticated: automatically call POST /api/invitations/accept
 *       and show success or error feedback.
 *
 * All user-visible strings are localised via the "invite" i18n namespace.
 *
 * Props: none (reads ?token from the URL search params)
 * Side effects:
 *   - Calls GET /api/invitations/preview on mount (unauthenticated).
 *   - Calls POST /api/invitations/accept when the user is authenticated.
 *   - Navigates to /dashboard on successful acceptance.
 *   - Navigates to /login (with ?redirect) when the user is not logged in
 *     and clicks the primary CTA.
 */

import { useEffect, useRef, useState } from 'react'
import { Turnstile } from '@marsidev/react-turnstile'
import { useNavigate, useSearchParams } from 'react-router-dom'
import UpgradeCallout from '../components/UpgradeCallout'
import { authClient } from '../lib/auth'
import { orgClient } from '../lib/organisations'
import { getTurnstileSiteKey } from '../lib/turnstile'
import useAuthStore from '../store/authStore'
import { getErrorMessage, isSeatBillingError } from '../lib/upgrade'
import { useTranslation } from '../hooks/useTranslation'

function getInviteUpgradeCallout({ t, orgName, note = null }) {
  return {
    title: t('invite.upgrade_title'),
    body: t('invite.upgrade_body').replace('{org}', orgName),
    benefits: [
      t('invite.upgrade_benefit_1'),
      t('invite.upgrade_benefit_2'),
      t('invite.upgrade_benefit_3'),
    ],
    ctaLabel: t('invite.upgrade_cta'),
    ctaTo: '/pricing',
    note: note ? t('invite.upgrade_note').replace('{message}', note) : null,
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * Shared page shell — centres the card on the Editorial Ledger surface.
 *
 * @param {{ children: React.ReactNode }} props
 */
function InviteShell({ children }) {
  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center px-4 py-12">
      {/* Wordmark */}
      <p className="font-display text-label-sm tracking-[0.12em] uppercase text-outline mb-8 select-none">
        Amendly
      </p>

      {/* Card */}
      <div className="w-full max-w-md bg-surface-container-lowest rounded-md shadow-ambient overflow-hidden">
        {children}
      </div>
    </div>
  )
}

/**
 * Header strip that mirrors the email template design.
 *
 * @param {{ orgName: string | null; t: Function }} props
 */
function InviteHeader({ orgName, t }) {
  return (
    <div className="bg-amendly-blue px-10 py-7">
      <p className="font-body text-label-sm tracking-[0.12em] uppercase text-on-primary opacity-70 mb-2">
        {t('invite.label')}
      </p>
      <h1 className="font-display text-headline-sm text-on-primary">
        {orgName ? t('invite.invited_to_join') : t('invite.org_invitation')}
      </h1>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AcceptInvite() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const token = searchParams.get('token')
  const user = useAuthStore((s) => s.user)
  const sessionResolved = useAuthStore((s) => s.sessionResolved)
  const setUser = useAuthStore((s) => s.setUser)
  const clearUser = useAuthStore((s) => s.clearUser)

  // Preview fetch state
  const [preview, setPreview] = useState(null)       // { org_name, email, expires_at }
  const [previewError, setPreviewError] = useState(null)

  // Accept action state
  const [accepting, setAccepting] = useState(false)
  const [acceptError, setAcceptError] = useState(null)
  const [accepted, setAccepted] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState('')
  const turnstileRef = useRef(null)
  const turnstileSiteKey = getTurnstileSiteKey()

  const isAuthenticated = Boolean(user)

  // ------------------------------------------------------------------
  // Step 1 — fetch the preview (always, no auth needed)
  // ------------------------------------------------------------------
  useEffect(() => {
    if (sessionResolved) return

    let cancelled = false

    async function resolveSession() {
      try {
        const me = await authClient.getMe()
        if (!cancelled) setUser(me)
      } catch {
        if (!cancelled) clearUser()
      }
    }

    resolveSession()
    return () => { cancelled = true }
  }, [clearUser, sessionResolved, setUser])

  useEffect(() => {
    if (!token) {
      setPreviewError(new Error(t('invite.no_token')))
      return
    }

    let cancelled = false

    async function fetchPreview() {
      try {
        const data = await orgClient.getInvitationPreview(token)
        if (!cancelled) setPreview(data)
      } catch (err) {
        if (!cancelled) setPreviewError(err)
      }
    }

    fetchPreview()
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------------------------
  // Step 2 — auto-accept when the user is already authenticated
  // and we have a valid preview (i.e. the invite is not expired)
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!sessionResolved || !preview || !isAuthenticated || accepted || acceptError) return

    let cancelled = false

    async function doAccept() {
      setAccepting(true)
      try {
        await orgClient.acceptInvite(token, turnstileToken || null)
        if (!cancelled) {
          turnstileRef.current?.reset()
          setTurnstileToken('')
          setAccepted(true)
          setTimeout(() => navigate('/dashboard', { replace: true }), 1800)
        }
      } catch (err) {
        turnstileRef.current?.reset()
        setTurnstileToken('')
        if (!cancelled) setAcceptError(err)
      } finally {
        if (!cancelled) setAccepting(false)
      }
    }

    doAccept()
    return () => { cancelled = true }
  }, [acceptError, accepted, isAuthenticated, navigate, preview, sessionResolved, token, turnstileToken])

  // ------------------------------------------------------------------
  // Render — no token
  // ------------------------------------------------------------------
  if (!token) {
    return (
      <InviteShell>
        <InviteHeader orgName={null} t={t} />
        <div className="px-10 py-8 space-y-6">
          <ErrorBanner message={t('invite.no_token')} />
        </div>
      </InviteShell>
    )
  }

  // ------------------------------------------------------------------
  // Render — preview is still loading
  // ------------------------------------------------------------------
  if (!preview && !previewError) {
    return (
      <InviteShell>
        <InviteHeader orgName={null} t={t} />
        <div className="px-10 py-8">
          <p className="font-body text-body-md text-outline">{t('invite.loading')}</p>
        </div>
      </InviteShell>
    )
  }

  // ------------------------------------------------------------------
  // Render — preview fetch failed (expired / invalid token)
  // ------------------------------------------------------------------
  if (previewError) {
    return (
      <InviteShell>
        <InviteHeader orgName={null} t={t} />
        <div className="px-10 py-8 space-y-6">
          <ErrorBanner message={getErrorMessage(previewError)} />
          <a
            href="/dashboard"
            className="block text-center font-body text-body-md text-secondary underline"
          >
            {t('invite.go_dashboard')}
          </a>
        </div>
      </InviteShell>
    )
  }

  const { org_name: orgName, email } = preview
  const showInviteTurnstile = isAuthenticated && Boolean(turnstileSiteKey)

  // ------------------------------------------------------------------
  // Render — accepted successfully
  // ------------------------------------------------------------------
  if (accepted) {
    return (
      <InviteShell>
        <InviteHeader orgName={orgName} t={t} />
        <div className="px-10 py-8 space-y-6">
          <OrgPill name={orgName} t={t} />
          <SuccessBanner
            message={t('invite.joined').replace('{org}', orgName)}
          />
        </div>
      </InviteShell>
    )
  }

  // ------------------------------------------------------------------
  // Render — accept errored (token already used, user already member…)
  // ------------------------------------------------------------------
  if (acceptError) {
    return (
      <InviteShell>
        <InviteHeader orgName={orgName} t={t} />
        <div className="px-10 py-8 space-y-6">
          <OrgPill name={orgName} t={t} />
          {showInviteTurnstile && (
            <Turnstile
              ref={turnstileRef}
              siteKey={turnstileSiteKey}
              onSuccess={(token) => setTurnstileToken(token)}
              onExpire={() => setTurnstileToken('')}
              onError={() => setTurnstileToken('')}
              options={{ theme: 'light', size: 'flexible', action: 'invite_accept' }}
            />
          )}
          {isSeatBillingError(acceptError) ? (
            <UpgradeCallout
              {...getInviteUpgradeCallout({
                t,
                orgName,
                note: getErrorMessage(acceptError),
              })}
            />
          ) : (
            <ErrorBanner message={getErrorMessage(acceptError)} />
          )}
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="w-full py-3 bg-amendly-blue text-on-primary rounded-md font-body text-body-md font-semibold"
          >
            {t('invite.go_to_dashboard')}
          </button>
        </div>
      </InviteShell>
    )
  }

  // ------------------------------------------------------------------
  // Render — auto-accepting (authenticated, waiting for API)
  // ------------------------------------------------------------------
  if (isAuthenticated && accepting) {
    return (
      <InviteShell>
        <InviteHeader orgName={orgName} t={t} />
        <div className="px-10 py-8 space-y-6">
          <OrgPill name={orgName} t={t} />
          {showInviteTurnstile && (
            <Turnstile
              ref={turnstileRef}
              siteKey={turnstileSiteKey}
              onSuccess={(token) => setTurnstileToken(token)}
              onExpire={() => setTurnstileToken('')}
              onError={() => setTurnstileToken('')}
              options={{ theme: 'light', size: 'flexible', action: 'invite_accept' }}
            />
          )}
          <p className="font-body text-body-md text-outline">
            {t('invite.accepting').replace('{org}', orgName)}
          </p>
        </div>
      </InviteShell>
    )
  }

  if (isAuthenticated) {
    return (
      <InviteShell>
        <InviteHeader orgName={orgName} t={t} />
        <div className="px-10 py-8 space-y-6">
          <OrgPill name={orgName} t={t} />
          {showInviteTurnstile && (
            <Turnstile
              ref={turnstileRef}
              siteKey={turnstileSiteKey}
              onSuccess={(token) => setTurnstileToken(token)}
              onExpire={() => setTurnstileToken('')}
              onError={() => setTurnstileToken('')}
              options={{ theme: 'light', size: 'flexible', action: 'invite_accept' }}
            />
          )}
          <p className="font-body text-body-md text-outline">
            {t('invite.accepting').replace('{org}', orgName)}
          </p>
        </div>
      </InviteShell>
    )
  }

  // ------------------------------------------------------------------
  // Render — unauthenticated: show the card, require login first
  // ------------------------------------------------------------------
  const redirectParam = encodeURIComponent(`/invitations/accept?token=${encodeURIComponent(token)}`)

  return (
    <InviteShell>
      <InviteHeader orgName={orgName} t={t} />

      <div className="px-10 py-8 space-y-6">
        {/* Org pill */}
        <OrgPill name={orgName} t={t} />

        {showInviteTurnstile && (
          <Turnstile
            ref={turnstileRef}
            siteKey={turnstileSiteKey}
            onSuccess={(token) => setTurnstileToken(token)}
            onExpire={() => setTurnstileToken('')}
            onError={() => setTurnstileToken('')}
            options={{ theme: 'light', size: 'flexible', action: 'invite_accept' }}
          />
        )}

        {/* Invitee hint */}
        {email && (
          <p className="font-body text-body-md text-outline">
            {t('invite.sent_to').replace('{email}', email)}
          </p>
        )}

        {/* Primary CTA */}
        <button
          type="button"
          onClick={() => navigate(`/login?redirect=${redirectParam}`)}
          className="w-full py-3 bg-amendly-blue text-on-primary rounded-md font-body text-body-md font-semibold hover:opacity-90 transition-opacity"
        >
          {t('invite.accept_button')}
        </button>

        {/* Secondary — sign in link */}
        <p className="text-center font-body text-body-md text-outline">
          {t('invite.already_account')}{' '}
          <a
            href={`/login?redirect=${redirectParam}`}
            className="text-secondary underline"
          >
            {t('invite.sign_in_first')}
          </a>
        </p>
      </div>
    </InviteShell>
  )
}

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

/**
 * Pill card showing the organisation name.
 *
 * @param {{ name: string; t: Function }} props
 */
function OrgPill({ name, t }) {
  return (
    <div className="bg-surface-container-low rounded-md px-5 py-4">
      <p className="font-body text-label-sm tracking-[0.08em] uppercase text-outline mb-1">
        {t('invite.organisation')}
      </p>
      <p className="font-display text-title-sm font-bold text-on-surface">{name}</p>
    </div>
  )
}

/**
 * Error banner using the error-container token.
 *
 * @param {{ message: string }} props
 */
function ErrorBanner({ message }) {
  return (
    <p
      role="alert"
      className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-3"
    >
      {message}
    </p>
  )
}

/**
 * Success banner using the tertiary-fixed token.
 *
 * @param {{ message: string }} props
 */
function SuccessBanner({ message }) {
  return (
    <p
      role="status"
      className="font-body text-body-md text-on-tertiary-fixed bg-tertiary-fixed rounded-md px-4 py-3"
    >
      {message}
    </p>
  )
}
