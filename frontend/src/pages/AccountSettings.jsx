/**
 * AccountSettings — personal account management page.
 *
 * Route: /account/settings (protected)
 *
 * Features:
 *   - Displays and edits the user's public profile (name, company, job position, avatar URL).
 *   - Global notification toggle: opt in/out of all amendment status emails.
 *   - Per-org notification mute: silences notifications for a specific org
 *     while keeping the global toggle enabled. Shown below the global toggle,
 *     one row per org the user belongs to.
 *   - "Delete my account" danger-zone action guarded by a confirmation dialog:
 *       1. window.prompt asks the user to type a confirmation keyword (locale-aware).
 *       2. On match, calls DELETE /api/auth/me.
 *       3. On success, clears the token and redirects to /.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Danger zone uses error-container token for the section background tint.
 *   - No 1px borders; structure through tonal shifts.
 *
 * Props: none
 * Side effects:
 *   - Calls authClient.getMe() on mount to populate user data.
 *   - Calls GET /api/me/notifications/settings on mount to load global + per-org settings.
 *   - Calls authClient.updateProfile() when saving profile information.
 *   - Calls authClient.updatePreferences() when toggling the global email notification flag.
 *   - Calls PATCH /api/organisations/{slug}/notification-settings when toggling per-org mute.
 *   - Calls authClient.deleteAccount() on success.
 *   - Navigates to / after successful deletion.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authClient } from '../lib/auth'
import { authFetch } from '../lib/api'
import { useTranslation } from '../hooks/useTranslation'
import LanguageSwitcher from '../components/LanguageSwitcher'
import useAuthStore from '../store/authStore'

/**
 * AccountSettings page component.
 * Protected — ProtectedRoute ensures the user is authenticated before rendering.
 */
export default function AccountSettings() {
  const navigate = useNavigate()
  const { t, lang, setLang } = useTranslation()
  const { user, setUser, clearUser } = useAuthStore()

  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)

  // Profile editing state
  const [profileName, setProfileName] = useState('')
  const [profileCompany, setProfileCompany] = useState('')
  const [profileJobPosition, setProfileJobPosition] = useState('')
  const [profileAvatarUrl, setProfileAvatarUrl] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileError, setProfileError] = useState(null)
  const [profileSuccess, setProfileSuccess] = useState(false)

  // Global notification preference
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const [savingPrefs, setSavingPrefs] = useState(false)
  const [prefsError, setPrefsError] = useState(null)
  const [prefsSuccess, setPrefsSuccess] = useState(false)

  // Per-org mute states — map of slug → boolean (true = muted)
  const [orgSettings, setOrgSettings] = useState([])
  const [savingOrgSlug, setSavingOrgSlug] = useState(null)
  const [orgMuteError, setOrgMuteError] = useState(null)

  // -------------------------------------------------------------------------
  // Bootstrap: fetch user profile + notification settings
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      try {
        // Fetch user if not in store
        let me = user
        if (!me) {
          me = await authClient.getMe()
          if (!cancelled) setUser(me)
        }
        if (!cancelled) setNotificationsEnabled(me.email_notifications_enabled ?? true)
        // Seed profile form fields
        if (!cancelled) {
          setProfileName(me.name ?? '')
          setProfileCompany(me.company ?? '')
          setProfileJobPosition(me.job_position ?? '')
          setProfileAvatarUrl(me.avatar_url ?? '')
        }

        // Fetch notification settings (global + per-org)
        const res = await authFetch('/api/me/notifications/settings')
        if (res.ok) {
          const data = await res.json()
          if (!cancelled) {
            setNotificationsEnabled(data.email_notifications_enabled ?? true)
            setOrgSettings(data.orgs ?? [])
          }
        }
      } catch {
        navigate('/login', { replace: true })
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    bootstrap()
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // -------------------------------------------------------------------------
  // Profile save handler
  // -------------------------------------------------------------------------

  async function handleSaveProfile(e) {
    e.preventDefault()
    setSavingProfile(true)
    setProfileError(null)
    setProfileSuccess(false)
    try {
      const updated = await authClient.updateProfile({
        name: profileName || null,
        company: profileCompany || null,
        job_position: profileJobPosition || null,
        avatar_url: profileAvatarUrl || null,
      })
      setUser({ ...user, ...updated })
      setProfileSuccess(true)
      setTimeout(() => setProfileSuccess(false), 3000)
    } catch (err) {
      setProfileError(err.message ?? t('account.profile_error'))
    } finally {
      setSavingProfile(false)
    }
  }

  // -------------------------------------------------------------------------
  // Global notification preference toggle handler
  // -------------------------------------------------------------------------

  async function handleNotificationsToggle() {
    const next = !notificationsEnabled
    setSavingPrefs(true)
    setPrefsError(null)
    setPrefsSuccess(false)
    try {
      const updated = await authClient.updatePreferences({
        email_notifications_enabled: next,
      })
      setNotificationsEnabled(updated.email_notifications_enabled)
      setUser({ ...user, email_notifications_enabled: updated.email_notifications_enabled })
      setPrefsSuccess(true)
      setTimeout(() => setPrefsSuccess(false), 3000)
    } catch (err) {
      setPrefsError(err.message ?? t('account.prefs_error'))
    } finally {
      setSavingPrefs(false)
    }
  }

  // -------------------------------------------------------------------------
  // Per-org mute toggle handler
  // -------------------------------------------------------------------------

  async function handleOrgMuteToggle(slug) {
    setOrgMuteError(null)
    const current = orgSettings.find(o => o.slug === slug)
    if (!current) return
    const next = !current.notifications_muted

    setSavingOrgSlug(slug)
    try {
      const res = await authFetch(`/api/organisations/${slug}/notification-settings`, {
        method: 'PATCH',
        body: JSON.stringify({ notifications_muted: next }),
      })
      if (!res.ok) throw new Error(t('account.org_mute_error'))
      setOrgSettings(prev =>
        prev.map(o => o.slug === slug ? { ...o, notifications_muted: next } : o)
      )
    } catch (err) {
      setOrgMuteError(err.message ?? t('account.org_mute_error'))
    } finally {
      setSavingOrgSlug(null)
    }
  }

  // -------------------------------------------------------------------------
  // Delete account handler
  // -------------------------------------------------------------------------

  async function handleDeleteAccount() {
    const keyword = t('account.delete_confirm_keyword')
    const message = t('account.delete_confirm')
    const input = window.prompt(message)
    if (input === null) return
    if (input.trim() !== keyword) return

    setDeleteError(null)
    setDeleting(true)
    try {
      await authClient.deleteAccount()
      clearUser()
      navigate('/', { replace: true })
    } catch (err) {
      setDeleteError(err.message ?? t('account.delete_error'))
      setDeleting(false)
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
          {t('account.back_dashboard')}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('account.settings_title')}
        </span>

        {/* Language switcher — rightmost */}
        <div className="ml-auto">
          <LanguageSwitcher lang={lang} setLang={setLang} />
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="max-w-2xl mx-auto px-8 py-12">
        {/* Page headline */}
        <div className="mb-12">
          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em]">
            {t('account.settings_title')}
          </h1>
          <p className="mt-2 font-body text-body-md text-outline">
            {t('account.settings_subtitle')}
          </p>
        </div>

        {/* Profile card */}
        <form onSubmit={handleSaveProfile} className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mb-8">
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-1">
            {t('account.profile_title')}
          </h2>
          <p className="font-body text-body-md text-outline mb-6">
            {t('account.profile_description')}
          </p>

          {/* Avatar preview + URL field */}
          <div className="flex items-center gap-6 mb-6">
            <div className="relative flex-shrink-0">
              {profileAvatarUrl ? (
                <img
                  src={profileAvatarUrl}
                  alt=""
                  className="w-20 h-20 rounded-full object-cover bg-surface-container-high"
                  onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextSibling.style.display = 'flex' }}
                />
              ) : null}
              <div
                className={[
                  'w-20 h-20 rounded-full bg-surface-container-high flex items-center justify-center',
                  profileAvatarUrl ? 'hidden' : 'flex',
                ].join(' ')}
                aria-hidden="true"
              >
                <span className="font-display text-headline-md text-outline select-none">
                  {(profileName || user?.email || '?')[0].toUpperCase()}
                </span>
              </div>
            </div>
            <div className="flex-1">
              <label className="block font-body text-label-sm text-outline tracking-[0.02em] uppercase mb-1" htmlFor="profile-avatar">
                {t('account.profile_avatar_label')}
              </label>
              <input
                id="profile-avatar"
                type="url"
                value={profileAvatarUrl}
                onChange={(e) => setProfileAvatarUrl(e.target.value)}
                placeholder={t('account.profile_avatar_placeholder')}
                className="w-full bg-surface-container-low rounded-md px-4 py-2.5 font-body text-body-md text-on-surface placeholder:text-outline/60 focus:outline-none focus:ring-2 focus:ring-secondary/40"
              />
            </div>
          </div>

          {/* Name */}
          <div className="mb-4">
            <label className="block font-body text-label-sm text-outline tracking-[0.02em] uppercase mb-1" htmlFor="profile-name">
              {t('account.profile_name_label')}
            </label>
            <input
              id="profile-name"
              type="text"
              value={profileName}
              onChange={(e) => setProfileName(e.target.value)}
              placeholder={t('account.profile_name_placeholder')}
              className="w-full bg-surface-container-low rounded-md px-4 py-2.5 font-body text-body-md text-on-surface placeholder:text-outline/60 focus:outline-none focus:ring-2 focus:ring-secondary/40"
            />
          </div>

          {/* Company + Job position — side by side on wider screens */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block font-body text-label-sm text-outline tracking-[0.02em] uppercase mb-1" htmlFor="profile-company">
                {t('account.profile_company_label')}
              </label>
              <input
                id="profile-company"
                type="text"
                value={profileCompany}
                onChange={(e) => setProfileCompany(e.target.value)}
                placeholder={t('account.profile_company_placeholder')}
                className="w-full bg-surface-container-low rounded-md px-4 py-2.5 font-body text-body-md text-on-surface placeholder:text-outline/60 focus:outline-none focus:ring-2 focus:ring-secondary/40"
              />
            </div>
            <div>
              <label className="block font-body text-label-sm text-outline tracking-[0.02em] uppercase mb-1" htmlFor="profile-job">
                {t('account.profile_job_label')}
              </label>
              <input
                id="profile-job"
                type="text"
                value={profileJobPosition}
                onChange={(e) => setProfileJobPosition(e.target.value)}
                placeholder={t('account.profile_job_placeholder')}
                className="w-full bg-surface-container-low rounded-md px-4 py-2.5 font-body text-body-md text-on-surface placeholder:text-outline/60 focus:outline-none focus:ring-2 focus:ring-secondary/40"
              />
            </div>
          </div>

          {profileError && (
            <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-4">
              {profileError}
            </p>
          )}
          {profileSuccess && (
            <p className="font-body text-body-md text-on-primary-fixed bg-primary-fixed/40 rounded-md px-4 py-2 mb-4">
              {t('account.profile_saved')}
            </p>
          )}

          <button
            type="submit"
            disabled={savingProfile}
            className="px-8 py-3 bg-secondary text-on-secondary rounded-md font-body text-body-md disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {savingProfile ? t('account.profile_saving') : t('account.profile_save')}
          </button>
        </form>

        {/* Account info card */}
        <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mb-8">
          <div className="space-y-4">
            {user?.name && (
              <div>
                <p className="font-body text-label-sm text-outline tracking-[0.02em] uppercase mb-1">
                  Name
                </p>
                <p className="font-body text-body-md text-on-surface">{user.name}</p>
              </div>
            )}
            <div>
              <p className="font-body text-label-sm text-outline tracking-[0.02em] uppercase mb-1">
                Email
              </p>
              <p className="font-body text-body-md text-on-surface">{user?.email}</p>
            </div>
          </div>
        </div>

        {/* Notification preferences card */}
        <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mb-8">
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-1">
            {t('account.notifications_title')}
          </h2>
          <p className="font-body text-body-md text-outline mb-6">
            {t('account.notifications_description')}
          </p>

          {prefsError && (
            <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-4">
              {prefsError}
            </p>
          )}
          {prefsSuccess && (
            <p className="font-body text-body-md text-on-primary-fixed bg-primary-fixed/40 rounded-md px-4 py-2 mb-4">
              {t('account.prefs_saved')}
            </p>
          )}

          {/* Global toggle row */}
          <label className="flex items-center gap-4 cursor-pointer select-none mb-6">
            <button
              type="button"
              role="switch"
              aria-checked={notificationsEnabled}
              aria-label={t('account.notifications_toggle_label')}
              disabled={savingPrefs}
              onClick={handleNotificationsToggle}
              className={[
                'relative inline-flex h-6 w-11 flex-shrink-0 rounded-full transition-colors duration-200',
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary',
                'disabled:opacity-50',
                notificationsEnabled ? 'bg-secondary' : 'bg-surface-container-high',
              ].join(' ')}
            >
              <span
                className={[
                  'inline-block h-5 w-5 rounded-full bg-white shadow-ambient transform transition-transform duration-200 mt-0.5',
                  notificationsEnabled ? 'translate-x-5' : 'translate-x-0.5',
                ].join(' ')}
              />
            </button>
            <span className="font-body text-body-md text-on-surface">
              {notificationsEnabled
                ? t('account.notifications_enabled')
                : t('account.notifications_disabled')}
            </span>
          </label>

          {/* Per-org mute toggles — only shown when global notifications are on */}
          {notificationsEnabled && orgSettings.length > 0 && (
            <div className="bg-surface-container-low rounded-md p-6">
              <p className="font-body text-label-sm text-outline tracking-[0.02em] uppercase mb-4">
                {t('account.org_notifications_title')}
              </p>

              {orgMuteError && (
                <p className="font-body text-body-sm text-on-error-container bg-error-container/40 rounded-md px-3 py-2 mb-4">
                  {orgMuteError}
                </p>
              )}

              <ul className="space-y-4">
                {orgSettings.map(org => (
                  <li key={org.slug} className="flex items-center justify-between gap-4">
                    <span className="font-body text-body-md text-on-surface">{org.name}</span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={!org.notifications_muted}
                      aria-label={
                        org.notifications_muted
                          ? t('account.org_unmute_label', { org: org.name })
                          : t('account.org_mute_label', { org: org.name })
                      }
                      disabled={savingOrgSlug === org.slug}
                      onClick={() => handleOrgMuteToggle(org.slug)}
                      className={[
                        'relative inline-flex h-6 w-11 flex-shrink-0 rounded-full transition-colors duration-200',
                        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary',
                        'disabled:opacity-50',
                        !org.notifications_muted ? 'bg-secondary' : 'bg-surface-container-high',
                      ].join(' ')}
                    >
                      <span
                        className={[
                          'inline-block h-5 w-5 rounded-full bg-white shadow-ambient transform transition-transform duration-200 mt-0.5',
                          !org.notifications_muted ? 'translate-x-5' : 'translate-x-0.5',
                        ].join(' ')}
                      />
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-4 font-body text-body-sm text-outline">
                {t('account.org_notifications_hint')}
              </p>
            </div>
          )}
        </div>

        {/* Danger zone */}
        <div className="bg-error-container/20 rounded-md p-8">
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-2">
            {t('account.danger_zone_title')}
          </h2>
          <p className="font-body text-body-md text-outline mb-6">
            {t('account.delete_description')}
          </p>

          {deleteError && (
            <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-6">
              {deleteError}
            </p>
          )}

          <button
            type="button"
            onClick={handleDeleteAccount}
            disabled={deleting}
            className="px-8 py-3 bg-error-container text-on-error-container rounded-md font-body text-body-md disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {deleting ? t('account.deleting') : t('account.delete_account')}
          </button>
        </div>
      </main>
    </div>
  )
}
