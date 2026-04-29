/**
 * Dashboard — the main post-login screen for authenticated users.
 *
 * On mount it fetches:
 *   1. GET /api/auth/me          — populates authStore with the user profile.
 *   2. GET /api/organisations/me — populates orgStore with the user's orgs.
 *
 * If the user has no organisations a "Create organisation" CTA is shown.
 * Clicking it opens an inline creation form. On success the new org is added
 * to the store and the form closes.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Tonal layering — surface base, surface-container-low sidebar, cards on white.
 *   - Manrope for headings, Inter for body/UI text.
 *   - No 1px borders; structure through background shifts and ambient shadows.
 *   - Status badges use soft-fill colours.
 *
 * Props: none
 * Side effects:
 *   - Reads/writes authStore and orgStore via Zustand.
 *   - Makes authenticated API calls to backend.
 *   - Redirects to /login if GET /api/auth/me returns 401.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authClient } from '../lib/auth'
import { orgClient } from '../lib/organisations'
import useAuthStore from '../store/authStore'
import useOrgStore from '../store/orgStore'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import OnboardingWizard from '../components/OnboardingWizard'
import NotificationBell from '../components/NotificationBell'

// ---------------------------------------------------------------------------
// Role badge
// ---------------------------------------------------------------------------

/**
 * Soft-fill badge showing the user's role in an organisation.
 * @param {{ role: string }} props
 */
function RoleBadge({ role }) {
  const styles = {
    owner:  'bg-tertiary-fixed text-on-tertiary-fixed',
    admin:  'bg-primary-fixed text-on-primary-fixed',
    member: 'bg-surface-container-highest text-on-surface',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[role] ?? styles.member}`}
    >
      {role}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Create organisation form (inline)
// ---------------------------------------------------------------------------

/**
 * Inline form for creating a new organisation.
 *
 * Props:
 *   onCreated  — Called with the new org object after successful creation.
 *   onCancel   — Called when the user dismisses the form without saving.
 *   t          — Translation function from useTranslation.
 */
function CreateOrgForm({ onCreated, onCancel, t }) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  /** Auto-generate a slug from the name unless the user has manually edited it. */
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
    <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mt-8">
      <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-8">
        {t('org.new_org_form_title')}
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name */}
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
            className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
          />
        </div>

        {/* Slug */}
        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('org.url_slug_label')}
          </label>
          <div className="flex items-center gap-2">
            <span className="font-body text-body-md text-outline">amendly.eu/</span>
            <input
              type="text"
              value={slug}
              onChange={(e) => { setSlug(e.target.value); setSlugEdited(true) }}
              required
              minLength={3}
              maxLength={100}
              pattern="[a-z0-9][a-z0-9\-]{1,98}[a-z0-9]"
              placeholder="acme-federation"
              className="flex-1 bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
            />
          </div>
          <p className="mt-1 font-body text-label-sm text-outline">
            {t('org.url_slug_hint')}
          </p>
        </div>

        {/* Error */}
        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
            {error}
          </p>
        )}

        {/* Actions */}
        <div className="flex gap-4 pt-4">
          <button
            type="submit"
            disabled={loading}
            className="px-8 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md disabled:opacity-50"
          >
            {loading ? t('org.creating') : t('org.create_organisation')}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-8 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md"
          >
            {t('org.cancel')}
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Organisation card
// ---------------------------------------------------------------------------

/**
 * Single organisation row displayed on the dashboard.
 * Clicking the card navigates to /orgs/:slug (the org document list).
 *
 * @param {{ org: { id: string; name: string; slug: string; plan: string; role: string } }} props
 */
function OrgCard({ org }) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={() => navigate(`/orgs/${org.slug}`)}
      className="w-full text-left bg-surface-container-lowest rounded-md shadow-ambient p-8 flex items-center justify-between hover:bg-surface-container-low transition-colors"
    >
      <div className="space-y-1">
        <h3 className="font-display text-title-sm text-on-surface">{org.name}</h3>
        <p className="font-body text-label-sm text-outline tracking-[0.02em]">
          amendly.eu/{org.slug}
        </p>
      </div>
      <div className="flex items-center gap-4">
        <RoleBadge role={org.role} />
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

/**
 * Dashboard page component.
 * Protected — users without a JWT are redirected to /login by ProtectedRoute.
 */
export default function Dashboard() {
  const navigate = useNavigate()
  const { user, setUser, clearUser } = useAuthStore()
  const { organisations, setOrganisations } = useOrgStore()
  const { t, lang, setLang } = useTranslation()

  useSeoMeta({
    title: 'Dashboard — Amendly',
    description: 'Manage your organisations and amendment workflows in Amendly.',
  })

  const [loading, setLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [userStats, setUserStats] = useState(null)
  const [loadError, setLoadError] = useState(null)

  // -------------------------------------------------------------------------
  // Bootstrap: fetch user + orgs on mount
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setLoadError(null)
      try {
        const [me, orgs] = await Promise.all([
          authClient.getMe(),
          orgClient.listMyOrgs(),
        ])
        const stats = await fetch('/api/users/me/stats', {
          credentials: 'include',
        })
          .then(async (response) => {
            if (!response.ok) {
              const data = await response.json().catch(() => ({}))
              const error = new Error(data?.detail ?? `Request failed with status ${response.status}`)
              error.status = response.status
              throw error
            }
            return response.json()
          })
          .catch((error) => {
            console.warn('[Dashboard] stats bootstrap failed; continuing without stats', error)
            return null
          })
        if (!cancelled) {
          setUser(me)
          setOrganisations(orgs)
          setUserStats(stats)
          // Show onboarding wizard until the server flag is set
          if (!me.onboarding_completed) {
            setShowOnboarding(true)
          }
        }
      } catch (error) {
        if (error?.status === 401) {
          // Token invalid or expired — redirect to login
          clearUser()
          authClient.logout()
          navigate('/login', { replace: true })
          return
        }
        if (!cancelled) {
          setLoadError(error?.message ?? t('common.error'))
          setUserStats(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    bootstrap()
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  async function handleLogout() {
    await authClient.logout()
    clearUser()
    setOrganisations([])
    navigate('/login', { replace: true })
  }

  function handleOrgCreated(org) {
    // The new org comes from the creation endpoint — it doesn't include a role
    // field. We know the creator is always the owner.
    setOrganisations([...organisations, { ...org, role: 'owner' }])
    setShowCreateForm(false)
  }

  function handleOnboardingClose() {
    setShowOnboarding(false)
  }

  function handleOnboardingUserUpdated(updatedUser) {
    setUser(updatedUser)
  }

  function handleOnboardingOrgCreated(org) {
    setOrganisations([...organisations, { ...org, role: 'owner' }])
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

  if (loadError) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-8">
        <div className="max-w-lg w-full bg-surface-container-lowest rounded-md shadow-ambient p-8 space-y-4">
          <h1 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
            Unable to load your workspace
          </h1>
          <p className="font-body text-body-md text-outline">
            {loadError}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const displayName = user?.name || user?.email || 'there'
  const initials = (user?.name ?? user?.email ?? '?')
    .split(/[\s@]+/)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('')

  return (
    <div className="min-h-screen bg-surface">

      {/* Onboarding wizard — shown until onboarding_completed is set server-side */}
      {showOnboarding && (
        <OnboardingWizard
          t={t}
          user={user}
          organisations={organisations}
          onClose={handleOnboardingClose}
          onOrgCreated={handleOnboardingOrgCreated}
          onUserUpdated={handleOnboardingUserUpdated}
        />
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Top navigation bar                                                  */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-surface-container-low px-8 py-4 flex items-center justify-between">
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          Amendly
        </span>

        <div className="flex items-center gap-4">
          {/* Notification center */}
          <NotificationBell orgSlug={null} />

          {/* Language switcher */}
          <LanguageSwitcher lang={lang} setLang={setLang} />

          {/* Avatar / initials */}
          <div
            aria-label={`Signed in as ${displayName}`}
            className="w-8 h-8 rounded-full bg-surface-container-highest flex items-center justify-center font-body text-label-sm text-on-surface select-none"
          >
            {initials}
          </div>

          {user?.is_superuser && (
            <button
              type="button"
              onClick={() => navigate('/admin/dashboard')}
              className="font-body text-body-md text-amendly-blue hover:underline"
            >
              Admin
            </button>
          )}

          <button
            type="button"
            onClick={() => navigate('/account/settings')}
            className="font-body text-body-md text-amendly-blue hover:underline"
          >
            {t('account.settings_title')}
          </button>

          <button
            type="button"
            onClick={handleLogout}
            className="font-body text-body-md text-secondary hover:underline"
          >
            {t('auth.logout')}
          </button>
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="max-w-3xl mx-auto px-8 py-12">
        {/* Welcome headline */}
        <div className="mb-12">
          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em]">
            {t('common.welcome_back').replace('{name}', user?.name ? `, ${user.name.split(' ')[0]}` : '')}
          </h1>
          <p className="mt-2 font-body text-body-md text-outline">{user?.email}</p>

        </div>

        {/* Organisations section */}
        <section>
          <div className="flex items-center justify-between mb-8">
            <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
              {t('org.your_organisations')}
            </h2>
            {organisations.length > 0 && !showCreateForm && (
              <button
                type="button"
                onClick={() => setShowCreateForm(true)}
                className="font-body text-body-md text-secondary hover:underline"
              >
                {t('org.new_organisation')}
              </button>
            )}
          </div>

          {/* Org list */}
          {organisations.length > 0 ? (
            <div className="space-y-4">
              {organisations.map((org) => (
                <OrgCard key={org.id} org={org} />
              ))}
            </div>
          ) : (
            /* Welcome empty state */
            !showCreateForm && (
              <div className="bg-surface-container-low rounded-xl p-16 flex flex-col items-center text-center gap-6">
                {/* Illustration: building + blue plus circle */}
                <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
                  {/* Building outline */}
                  <rect x="12" y="22" width="40" height="46" rx="3" fill="#dbe1ff" />
                  <rect x="18" y="30" width="8" height="8" rx="1" fill="#2563EB" opacity="0.4" />
                  <rect x="32" y="30" width="8" height="8" rx="1" fill="#2563EB" opacity="0.4" />
                  <rect x="18" y="44" width="8" height="8" rx="1" fill="#2563EB" opacity="0.4" />
                  <rect x="32" y="44" width="8" height="8" rx="1" fill="#2563EB" opacity="0.4" />
                  <rect x="22" y="56" width="20" height="12" rx="1" fill="#2563EB" opacity="0.3" />
                  {/* Roof */}
                  <path d="M8 24L32 10L56 24" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  {/* Plus circle */}
                  <circle cx="60" cy="58" r="14" fill="#2563EB" />
                  <path d="M60 52v12M54 58h12" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
                </svg>

                <div>
                  <h3 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-2">
                    {t('dashboard.welcome_empty_title')}
                  </h3>
                  <p className="font-body text-body-md text-outline max-w-xs">
                    {t('dashboard.welcome_empty_body')}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setShowCreateForm(true)}
                  className="px-8 py-2.5 bg-amendly-blue text-white rounded-md font-body text-body-md hover:opacity-90 transition-opacity"
                >
                  {t('org.create_first_org')}
                </button>
              </div>
            )
          )}

          {/* Inline create form */}
          {showCreateForm && (
            <CreateOrgForm
              onCreated={handleOrgCreated}
              onCancel={() => setShowCreateForm(false)}
              t={t}
            />
          )}
        </section>

        {/* At-a-glance stats row — totals across all orgs */}
        {userStats && organisations.length > 0 && (
          <div className="mt-10">
            <p className="font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-3">
              {t('dashboard.at_a_glance')}
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary-fixed text-on-primary-fixed font-body text-label-sm tracking-[0.02em]">
                <span aria-hidden="true">📄</span>
                {userStats.docs_count === 1
                  ? t('dashboard.stats_docs').replace('{n}', userStats.docs_count)
                  : t('dashboard.stats_docs_plural').replace('{n}', userStats.docs_count)}
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-highest text-on-surface font-body text-label-sm tracking-[0.02em]">
                <span aria-hidden="true">✏️</span>
                {t('dashboard.stats_pending_amendments').replace('{n}', userStats.pending_amendments_count)}
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-highest text-on-surface font-body text-label-sm tracking-[0.02em]">
                <span aria-hidden="true">🏢</span>
                {userStats.orgs_count === 1
                  ? t('dashboard.stats_orgs').replace('{n}', userStats.orgs_count)
                  : t('dashboard.stats_orgs_plural').replace('{n}', userStats.orgs_count)}
              </span>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
