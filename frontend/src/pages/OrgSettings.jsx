/**
 * OrgSettings — Organisation settings page (owner only).
 *
 * Route: /orgs/:slug/settings
 *
 * On mount it fetches:
 *   1. GET /api/organisations/me  — determines the caller's role; redirects
 *      non-owners to /orgs/:slug.
 *   2. GET /api/organisations/:slug — loads current name and slug.
 *
 * Features:
 *   - Editable "Organisation name" field (pre-filled).
 *   - Editable "URL slug" field with a live preview of the resulting URL
 *     (amendly.eu/{slug}).  Validates format client-side before submit.
 *   - "Save changes" button — on success, navigates to
 *     /orgs/{newSlug}/settings so the URL stays consistent when the slug
 *     was changed.
 *   - Danger zone: "Delete organisation" action.  The user must type the
 *     exact organisation name to unlock the delete button.  On success,
 *     navigates to /dashboard.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *
 * Props: none (reads :slug from React Router params)
 * Side effects:
 *   - Uses cookie-backed authenticated API calls.
 *   - Navigates to /orgs/:slug on 403 (non-owner).
 *   - Navigates to /dashboard on 404 (non-member or org not found).
 */

import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { authFetch } from '../lib/api'
import { orgClient } from '../lib/organisations'
import { useTranslation } from '../hooks/useTranslation'
import LanguageSwitcher from '../components/LanguageSwitcher'
import NotificationBell from '../components/NotificationBell'

/** Validate a slug: lowercase letters, digits, hyphens; 3–60 chars. */
function isValidSlug(value) {
  return /^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(value) && value.length >= 3 && value.length <= 60
}

// ---------------------------------------------------------------------------
// OrgSettings page
// ---------------------------------------------------------------------------

/**
 * OrgSettings page component.
 * Protected — ProtectedRoute ensures the user is authenticated.
 * Owner-only — non-owners are redirected to /orgs/:slug on load.
 */
export default function OrgSettings() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { t, lang, setLang } = useTranslation()

  const [org, setOrg] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Save form state
  const [name, setName] = useState('')
  const [newSlug, setNewSlug] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [slugError, setSlugError] = useState(null)

  // Per-org notification mute
  const [notificationsMuted, setNotificationsMuted] = useState(false)
  const [savingMute, setSavingMute] = useState(false)
  const [muteError, setMuteError] = useState(null)
  const [muteSuccess, setMuteSuccess] = useState(false)

  // Delete confirmation state
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)

  // -------------------------------------------------------------------------
  // Load org + verify owner
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [orgData, myOrgs, notifRes] = await Promise.all([
          orgClient.getOrg(slug),
          orgClient.listMyOrgs(),
          authFetch('/api/me/notifications/settings'),
        ])
        if (cancelled) return

        const membership = myOrgs.find((o) => o.slug === slug)
        if (membership?.role !== 'owner') {
          navigate(`/orgs/${slug}`, { replace: true })
          return
        }

        setOrg(orgData)
        setName(orgData.name)
        setNewSlug(orgData.slug)

        if (notifRes.ok) {
          const notifData = await notifRes.json()
          const orgEntry = (notifData.orgs ?? []).find((o) => o.slug === slug)
          if (orgEntry) setNotificationsMuted(orgEntry.notifications_muted)
        }
      } catch (err) {
        if (cancelled) return
        if (err.message?.includes('404') || err.message?.toLowerCase().includes('not found')) {
          navigate('/dashboard', { replace: true })
        } else {
          setError(err.message)
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

  async function handleMuteToggle() {
    const next = !notificationsMuted
    setSavingMute(true)
    setMuteError(null)
    setMuteSuccess(false)
    try {
      const res = await authFetch(`/api/organisations/${slug}/notification-settings`, {
        method: 'PATCH',
        body: JSON.stringify({ notifications_muted: next }),
      })
      if (!res.ok) throw new Error(t('org.settings_notifications_error'))
      setNotificationsMuted(next)
      setMuteSuccess(true)
      setTimeout(() => setMuteSuccess(false), 3000)
    } catch (err) {
      setMuteError(err.message ?? t('org.settings_notifications_error'))
    } finally {
      setSavingMute(false)
    }
  }

  function handleSlugChange(value) {
    const v = value.toLowerCase()
    setNewSlug(v)
    setSaveSuccess(false)
    if (v && !isValidSlug(v)) {
      setSlugError(t('org.settings_slug_error'))
    } else {
      setSlugError(null)
    }
  }

  async function handleSave(e) {
    e.preventDefault()
    if (slugError) return

    const trimmedName = name.trim()
    const trimmedSlug = newSlug.trim()

    if (!trimmedName || !trimmedSlug) return
    if (!isValidSlug(trimmedSlug)) {
      setSlugError(t('org.settings_slug_error'))
      return
    }

    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)

    try {
      const updated = await orgClient.updateOrg(slug, {
        name: trimmedName,
        slug: trimmedSlug,
      })
      setOrg(updated)
      setName(updated.name)
      setNewSlug(updated.slug)
      setSaveSuccess(true)

      // If the slug changed, update the URL
      if (updated.slug !== slug) {
        navigate(`/orgs/${updated.slug}/settings`, { replace: true })
      }
    } catch (err) {
      setSaveError(err.message ?? t('org.settings_save_error'))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    setDeleteError(null)
    try {
      await orgClient.deleteOrg(slug)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setDeleteError(err.message ?? t('org.settings_delete_error'))
      setDeleting(false)
    }
  }

  // -------------------------------------------------------------------------
  // Render states
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <span className="font-body text-body-md text-outline">{t('common.loading')}</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <p className="font-body text-body-md text-on-error-container">{error}</p>
      </div>
    )
  }

  const slugPreview = t('org.settings_slug_preview').replace('{slug}', newSlug || '…')
  const deleteEnabled = deleteConfirm === org?.name

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-surface">
      {/* ------------------------------------------------------------------ */}
      {/* Top navigation bar                                                  */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-surface-container-low px-8 py-4 flex items-center gap-4">
        <button
          type="button"
          onClick={() => navigate(`/orgs/${newSlug}`)}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {t('nav.back_dashboard')}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-body text-body-md text-on-surface">{org?.name}</span>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('org.settings')}
        </span>

        <div className="ml-auto flex items-center gap-4">
          <button
            type="button"
            onClick={() => navigate(`/orgs/${slug}/billing`)}
            className="font-body text-body-md text-secondary hover:underline"
          >
            {t('nav.billing')}
          </button>
          <NotificationBell orgSlug={slug} />
          <LanguageSwitcher lang={lang} setLang={setLang} />
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="max-w-2xl mx-auto px-8 py-12">
        {/* Page headline */}
        <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em] mb-12">
          {t('org.settings_title')}
        </h1>

        {/* ---------------------------------------------------------------- */}
        {/* General settings form                                             */}
        {/* ---------------------------------------------------------------- */}
        <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mb-8">
          <form onSubmit={handleSave} className="space-y-6">
            {/* Organisation name */}
            <div>
              <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
                {t('org.settings_name_label')} <span className="text-secondary">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => { setName(e.target.value); setSaveSuccess(false) }}
                required
                maxLength={255}
                className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
              />
            </div>

            {/* URL slug */}
            <div>
              <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
                {t('org.settings_slug_label')} <span className="text-secondary">*</span>
              </label>
              <input
                type="text"
                value={newSlug}
                onChange={(e) => handleSlugChange(e.target.value)}
                required
                maxLength={60}
                className={`w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 ${slugError ? 'focus:ring-error ring-1 ring-error' : 'focus:ring-secondary'}`}
              />
              {/* Live URL preview */}
              <p className="mt-2 font-body text-label-sm text-outline">
                {slugPreview}
              </p>
              {/* Slug validation hint */}
              {slugError ? (
                <p className="mt-1 font-body text-label-sm text-on-error-container bg-error-container/40 rounded px-2 py-1">
                  {slugError}
                </p>
              ) : (
                <p className="mt-1 font-body text-label-sm text-outline">
                  {t('org.settings_slug_hint')}
                </p>
              )}
            </div>

            {/* Feedback messages */}
            {saveError && (
              <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
                {saveError}
              </p>
            )}
            {saveSuccess && (
              <p className="font-body text-body-md text-on-primary-fixed bg-primary-fixed/40 rounded-md px-4 py-2">
                {t('org.settings_saved')}
              </p>
            )}

            {/* Submit */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={saving || !!slugError}
                className="px-8 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md disabled:opacity-50"
              >
                {saving ? t('org.settings_saving') : t('org.settings_save')}
              </button>
            </div>
          </form>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Notification mute                                                 */}
        {/* ---------------------------------------------------------------- */}
        <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mb-8">
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-1">
            {t('org.settings_notifications_title')}
          </h2>
          <p className="font-body text-body-md text-outline mb-6">
            {t('org.settings_notifications_desc')}
          </p>

          {muteError && (
            <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-4">
              {muteError}
            </p>
          )}
          {muteSuccess && (
            <p className="font-body text-body-md text-on-primary-fixed bg-primary-fixed/40 rounded-md px-4 py-2 mb-4">
              {t('org.settings_notifications_saved')}
            </p>
          )}

          <label className="flex items-center gap-4 cursor-pointer select-none">
            <button
              type="button"
              role="switch"
              aria-checked={!notificationsMuted}
              aria-label={t('org.settings_notifications_toggle_label')}
              disabled={savingMute}
              onClick={handleMuteToggle}
              className={[
                'relative inline-flex h-6 w-11 flex-shrink-0 rounded-full transition-colors duration-200',
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary',
                'disabled:opacity-50',
                !notificationsMuted ? 'bg-secondary' : 'bg-surface-container-high',
              ].join(' ')}
            >
              <span
                className={[
                  'inline-block h-5 w-5 rounded-full bg-white shadow-ambient transform transition-transform duration-200 mt-0.5',
                  !notificationsMuted ? 'translate-x-5' : 'translate-x-0.5',
                ].join(' ')}
              />
            </button>
            <span className="font-body text-body-md text-on-surface">
              {notificationsMuted
                ? t('org.settings_notifications_muted')
                : t('org.settings_notifications_unmuted')}
            </span>
          </label>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Danger zone                                                        */}
        {/* ---------------------------------------------------------------- */}
        <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 border border-error/30">
          <h2 className="font-display text-headline-sm text-error tracking-[-0.01em] mb-4">
            {t('org.settings_danger_title')}
          </h2>

          <p className="font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-1">
            {t('org.settings_delete_label')}
          </p>
          <p className="font-body text-body-md text-outline mb-6">
            {t('org.settings_delete_desc')}
          </p>

          {/* Confirmation input */}
          <div className="mb-4">
            <input
              type="text"
              value={deleteConfirm}
              onChange={(e) => { setDeleteConfirm(e.target.value); setDeleteError(null) }}
              placeholder={t('org.settings_delete_confirm_placeholder')}
              className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-error"
            />
          </div>

          {deleteError && (
            <p className="mb-4 font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
              {deleteError}
            </p>
          )}

          <button
            type="button"
            disabled={!deleteEnabled || deleting}
            onClick={handleDelete}
            className="px-8 py-2 bg-error text-on-error rounded-md font-body text-body-md disabled:opacity-40"
          >
            {deleting ? t('org.settings_deleting') : t('org.settings_delete_button')}
          </button>
        </div>
      </main>
    </div>
  )
}
