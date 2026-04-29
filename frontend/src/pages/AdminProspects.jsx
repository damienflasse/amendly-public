/**
 * AdminProspects — superadmin page for managing sales prospects (mini-CRM).
 *
 * Route: /admin/prospects
 *
 * Accessible to platform superusers only. Non-superusers are redirected to
 * /dashboard on mount (403 response from the admin API).
 *
 * On mount it fetches:
 *   GET /api/admin/prospects — loads all prospects (newest first).
 *
 * Features:
 *   - Summary stats: total prospects, breakdown by pipeline status.
 *   - Add prospect form: email (required), name, org name, notes.
 *   - Prospect table with inline status selector and notes editing.
 *   - Delete prospect with confirmation.
 *   - Pipeline statuses: new → contacted → demo_booked → converted | lost.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *
 * Props: none
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { prospectClient, emailTemplateClient } from '../lib/organisations'
import { useTranslation } from '../hooks/useTranslation'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUSES = ['new', 'contacted', 'demo_booked', 'converted', 'lost']

const PROSPECT_LABELS = {
  prospect_intro:        '1 — Intro',
  prospect_relance_1:    '2 — Relance 1',
  prospect_relance_2:    '3 — Relance 2',
  prospect_relance_3:    '4 — Clôture',
  prospect_intro_en:     '1 — Intro',
  prospect_relance_1_en: '2 — Follow-up 1',
  prospect_relance_2_en: '3 — Follow-up 2',
  prospect_relance_3_en: '4 — Closing',
}

const STATUS_STYLES = {
  new: 'bg-surface-container-highest text-on-surface',
  contacted: 'bg-amendly-blue-fixed text-on-primary-fixed',
  demo_booked: 'bg-secondary-fixed text-on-secondary-fixed',
  converted: 'bg-tertiary-fixed text-on-tertiary-fixed',
  lost: 'bg-error-container text-on-error-container',
}

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

/** @param {{ status: string }} props */
function StatusBadge({ status }) {
  const { t } = useTranslation()
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.03em] uppercase ${STATUS_STYLES[status] ?? STATUS_STYLES.new}`}
    >
      {t(`admin.status_${status}`) || status}
    </span>
  )
}

// ---------------------------------------------------------------------------
// SendEmailModal
// ---------------------------------------------------------------------------

/**
 * Modal for sending an email to a single prospect.
 * Lets the admin pick a stored template or write a free-form subject + body.
 * Variables {nom} and {org_name} are substituted server-side.
 *
 * @param {{ prospect: object; onClose: function; onSent: function }} props
 *   prospect  — the prospect to email
 *   onClose   — called when the modal is dismissed
 *   onSent    — called with the updated prospect after a successful send
 */
function SendEmailModal({ prospect, onClose, onSent }) {
  const { t } = useTranslation()
  const [templates, setTemplates] = useState([])
  const [loadingTemplates, setLoadingTemplates] = useState(true)

  const [mode, setMode] = useState('template') // 'template' | 'freeform'
  const [templateKey, setTemplateKey] = useState('')
  const [subject, setSubject] = useState('')
  const [htmlBody, setHtmlBody] = useState('')

  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    emailTemplateClient.list()
      .then((data) => { setTemplates(data); setLoadingTemplates(false) })
      .catch(() => setLoadingTemplates(false))
  }, [])

  async function handleSend(e) {
    e.preventDefault()
    setError(null)
    setSending(true)
    try {
      const payload =
        mode === 'template'
          ? { template_key: templateKey }
          : { subject: subject.trim(), html_body: htmlBody.trim() }
      const updated = await prospectClient.sendEmail(prospect.id, payload)
      onSent(updated)
      setSuccess(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const inputClass =
    'w-full bg-surface-container rounded px-3 py-2 font-body text-body-md text-on-surface focus:outline-none focus:ring-1 focus:ring-amendly-blue'
  const labelClass = 'font-body text-label-sm text-outline block mb-1'

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.45)' }}
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-lg p-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-display text-title-md text-on-surface">
            {t('admin.email_modal_heading')} — {prospect.name || prospect.email}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full text-outline hover:bg-surface-container-highest transition-colors"
            aria-label={t('admin.email_close')}
          >
            ✕
          </button>
        </div>

        {success ? (
          <div className="text-center py-6">
            <p className="font-body text-body-md text-on-surface mb-2">
              {t('admin.email_sent_to').replace('{email}', prospect.email)}
            </p>
            <p className="font-body text-label-sm text-outline mb-6">
              {t('admin.email_sent_note')}
            </p>
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90"
            >
              {t('admin.email_close')}
            </button>
          </div>
        ) : (
          <form onSubmit={handleSend} className="space-y-4">
            {/* Recipient info */}
            <div className="bg-surface-container rounded-md px-4 py-3">
              <p className="font-body text-label-sm text-outline">{t('admin.email_to_label')}</p>
              <p className="font-body text-body-md text-on-surface">
                {prospect.name ? `${prospect.name} ` : ''}&lt;{prospect.email}&gt;
              </p>
              {prospect.org_name && (
                <p className="font-body text-label-sm text-outline">{prospect.org_name}</p>
              )}
            </div>

            {/* Mode selector */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode('template')}
                className={`px-3 py-1.5 rounded-md font-body text-body-sm transition-colors ${
                  mode === 'template'
                    ? 'bg-amendly-blue text-on-primary'
                    : 'bg-surface-container-highest text-on-surface hover:opacity-80'
                }`}
              >
                {t('admin.email_use_template')}
              </button>
              <button
                type="button"
                onClick={() => setMode('freeform')}
                className={`px-3 py-1.5 rounded-md font-body text-body-sm transition-colors ${
                  mode === 'freeform'
                    ? 'bg-amendly-blue text-on-primary'
                    : 'bg-surface-container-highest text-on-surface hover:opacity-80'
                }`}
              >
                {t('admin.email_freeform')}
              </button>
            </div>

            {mode === 'template' ? (
              <div>
                <label className={labelClass}>{t('admin.email_template_label')}</label>
                {loadingTemplates ? (
                  <p className="font-body text-body-sm text-outline">{t('admin.email_loading_templates')}</p>
                ) : (
                  <select
                    value={templateKey}
                    onChange={(e) => setTemplateKey(e.target.value)}
                    required
                    className={inputClass}
                  >
                    <option value="">{t('admin.email_select_template')}</option>
                    {/* Prospect FR */}
                    {templates.some((tmpl) => tmpl.key.startsWith('prospect_') && !tmpl.key.endsWith('_en')) && (
                      <optgroup label="🇫🇷 Prospects — FR">
                        {templates
                          .filter((tmpl) => tmpl.key.startsWith('prospect_') && !tmpl.key.endsWith('_en'))
                          .map((tmpl) => (
                            <option key={tmpl.key} value={tmpl.key}>
                              {PROSPECT_LABELS[tmpl.key] ?? tmpl.key} — {tmpl.subject}
                            </option>
                          ))}
                      </optgroup>
                    )}
                    {/* Prospect EN */}
                    {templates.some((tmpl) => tmpl.key.endsWith('_en')) && (
                      <optgroup label="🇬🇧 Prospects — EN">
                        {templates
                          .filter((tmpl) => tmpl.key.endsWith('_en'))
                          .map((tmpl) => (
                            <option key={tmpl.key} value={tmpl.key}>
                              {PROSPECT_LABELS[tmpl.key] ?? tmpl.key} — {tmpl.subject}
                            </option>
                          ))}
                      </optgroup>
                    )}
                    {/* System templates */}
                    {templates.some((tmpl) => !tmpl.key.startsWith('prospect_')) && (
                      <optgroup label="Système">
                        {templates
                          .filter((tmpl) => !tmpl.key.startsWith('prospect_'))
                          .map((tmpl) => (
                            <option key={tmpl.key} value={tmpl.key}>
                              {tmpl.key} — {tmpl.subject}
                            </option>
                          ))}
                      </optgroup>
                    )}
                  </select>
                )}
                <p className="mt-1 font-body text-label-sm text-outline">
                  {t('admin.email_variables_auto')}
                </p>
              </div>
            ) : (
              <>
                <div>
                  <label className={labelClass}>{t('admin.email_subject')}</label>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    required
                    className={inputClass}
                    placeholder={t('admin.email_subject_placeholder')}
                  />
                </div>
                <div>
                  <label className={labelClass}>{t('admin.email_body_html')}</label>
                  <textarea
                    rows={6}
                    value={htmlBody}
                    onChange={(e) => setHtmlBody(e.target.value)}
                    required
                    className={`${inputClass} resize-y font-mono text-body-sm`}
                    placeholder="<p>{nom},</p>"
                  />
                  <p className="mt-1 font-body text-label-sm text-outline">
                    {t('admin.email_variables_available')}
                  </p>
                </div>
              </>
            )}

            {error && (
              <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
                {error}
              </p>
            )}

            <div className="flex gap-3 justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={sending}
                className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:opacity-90 disabled:opacity-50"
              >
                {t('admin.email_cancel')}
              </button>
              <button
                type="submit"
                disabled={sending || (mode === 'template' && !templateKey)}
                className="px-4 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 disabled:opacity-50"
              >
                {sending ? t('admin.email_sending') : t('admin.email_send')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AddProspectForm
// ---------------------------------------------------------------------------

/**
 * Inline form to add a new prospect.
 *
 * @param {{ onAdded: function }} props
 *   onAdded — Called with the newly created prospect.
 */
function AddProspectForm({ onAdded }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [notes, setNotes] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const created = await prospectClient.create({
        email: email.trim(),
        name: name.trim() || undefined,
        org_name: orgName.trim() || undefined,
        notes: notes.trim() || undefined,
      })
      onAdded(created)
      setEmail('')
      setName('')
      setOrgName('')
      setNotes('')
      setOpen(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const inputClass =
    'w-full bg-surface-container rounded px-3 py-2 font-body text-body-md text-on-surface focus:outline-none focus:ring-1 focus:ring-amendly-blue'
  const labelClass = 'font-body text-label-sm text-outline block mb-1'

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 transition-opacity"
      >
        {t('admin.add_prospect')}
      </button>
    )
  }

  return (
    <div className="bg-surface-container-lowest rounded-md shadow-ambient p-6">
      <h3 className="font-display text-title-md text-on-surface mb-6">{t('admin.new_prospect')}</h3>

      {error && (
        <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-4">
          {error}
        </p>
      )}

      <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="sm:col-span-2">
          <label className={labelClass}>
            {t('admin.field_email')} <span className="text-error">*</span>
          </label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
            placeholder="contact@example.org"
          />
        </div>

        <div>
          <label className={labelClass}>{t('admin.field_name')}</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputClass}
            placeholder="Jane Smith"
          />
        </div>

        <div>
          <label className={labelClass}>{t('admin.field_organisation')}</label>
          <input
            type="text"
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            className={inputClass}
            placeholder="ACME Federation"
          />
        </div>

        <div className="sm:col-span-2">
          <label className={labelClass}>{t('admin.field_notes')}</label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className={`${inputClass} resize-y`}
            placeholder={t('admin.field_notes_placeholder')}
          />
        </div>

        <div className="sm:col-span-2 flex items-center gap-3 justify-end">
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              setError(null)
            }}
            disabled={saving}
            className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {saving ? t('admin.adding') : t('admin.add_prospect_btn')}
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProspectRow
// ---------------------------------------------------------------------------

/**
 * A single prospect row with inline status + notes editing.
 *
 * @param {{ prospect: object, onUpdated: function, onDeleted: function }} props
 */
function ProspectRow({ prospect, onUpdated, onDeleted }) {
  const { t } = useTranslation()
  const [editingNotes, setEditingNotes] = useState(false)
  const [notes, setNotes] = useState(prospect.notes || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [showEmailModal, setShowEmailModal] = useState(false)

  // Sync notes when parent prospect changes
  useEffect(() => {
    setNotes(prospect.notes || '')
  }, [prospect.notes])

  async function handleStatusChange(newStatus) {
    setSaving(true)
    setError(null)
    try {
      const updated = await prospectClient.update(prospect.id, { status: newStatus })
      onUpdated(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveNotes() {
    setSaving(true)
    setError(null)
    try {
      const updated = await prospectClient.update(prospect.id, {
        notes: notes.trim() || null,
      })
      onUpdated(updated)
      setEditingNotes(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    const name = prospect.name ? `"${prospect.name}"` : prospect.email
    if (
      !window.confirm(t('admin.delete_prospect_confirm').replace('{name}', name))
    )
      return
    setSaving(true)
    setError(null)
    try {
      await prospectClient.delete(prospect.id)
      onDeleted(prospect.id)
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <>
      {showEmailModal && (
        <SendEmailModal
          prospect={prospect}
          onClose={() => setShowEmailModal(false)}
          onSent={(updated) => { onUpdated(updated); setShowEmailModal(false) }}
        />
      )}

    <div className="bg-surface-container-lowest rounded-md p-5">
      {error && (
        <p className="font-body text-body-sm text-on-error-container bg-error-container/40 rounded px-3 py-1 mb-3">
          {error}
        </p>
      )}

      <div className="flex items-start gap-4">
        {/* Contact info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-body text-body-md text-on-surface font-semibold truncate">
              {prospect.name || prospect.email}
            </span>
            {prospect.name && (
              <span className="font-body text-body-sm text-outline truncate">
                {prospect.email}
              </span>
            )}
            {prospect.org_name && (
              <span className="font-body text-label-sm text-outline bg-surface-container px-2 py-0.5 rounded truncate">
                {prospect.org_name}
              </span>
            )}
          </div>
          <p className="font-body text-label-sm text-outline mt-1">
            {t('admin.added_on').replace('{date}', new Date(prospect.created_at).toLocaleDateString())}
          </p>
        </div>

        {/* Send email button */}
        <button
          type="button"
          onClick={() => setShowEmailModal(true)}
          disabled={saving}
          className="px-3 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-body-sm hover:opacity-80 transition-opacity flex-shrink-0 disabled:opacity-50"
        >
          {t('admin.send_email_btn')}
        </button>

        {/* Status selector */}
        <select
          value={prospect.status}
          onChange={(e) => handleStatusChange(e.target.value)}
          disabled={saving}
          className="bg-surface-container rounded px-3 py-1.5 font-body text-body-sm text-on-surface focus:outline-none focus:ring-1 focus:ring-amendly-blue disabled:opacity-50 flex-shrink-0"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`admin.status_${s}`)}
            </option>
          ))}
        </select>

        {/* Status badge (visual) */}
        <div className="flex-shrink-0">
          <StatusBadge status={prospect.status} />
        </div>

        {/* Delete */}
        <button
          type="button"
          onClick={handleDelete}
          disabled={saving}
          className="font-body text-label-sm text-outline hover:text-error transition-colors flex-shrink-0 disabled:opacity-50"
        >
          ✕
        </button>
      </div>

      {/* Notes */}
      <div className="mt-4">
        {editingNotes ? (
          <div>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-surface-container rounded px-3 py-2 font-body text-body-sm text-on-surface resize-y focus:outline-none focus:ring-1 focus:ring-amendly-blue"
              placeholder="Notes…"
            />
            <div className="flex gap-2 mt-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setNotes(prospect.notes || '')
                  setEditingNotes(false)
                }}
                disabled={saving}
                className="px-3 py-1.5 bg-surface-container-highest text-on-surface rounded font-body text-body-sm hover:opacity-90 disabled:opacity-50"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={handleSaveNotes}
                disabled={saving}
                className="px-3 py-1.5 bg-amendly-blue text-on-primary rounded font-body text-body-sm hover:opacity-90 disabled:opacity-50"
              >
                {saving ? t('admin.saving_notes') : t('admin.save_notes')}
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setEditingNotes(true)}
            className="text-left w-full"
          >
            {prospect.notes ? (
              <p className="font-body text-body-sm text-on-surface/80 bg-surface-container rounded px-3 py-2 hover:bg-surface-container-high transition-colors whitespace-pre-wrap">
                {prospect.notes}
              </p>
            ) : (
              <p className="font-body text-label-sm text-outline italic hover:text-on-surface transition-colors">
                {t('admin.add_notes')}
              </p>
            )}
          </button>
        )}
      </div>
    </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// AdminProspects page
// ---------------------------------------------------------------------------

/**
 * Admin prospects CRM page.
 * Protected — ProtectedRoute ensures the user is authenticated before rendering.
 * Redirects to /dashboard if the user is not a superuser (API returns 403).
 */
export default function AdminProspects() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [prospects, setProspects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filterStatus, setFilterStatus] = useState('all')

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await prospectClient.list()
        if (!cancelled) setProspects(data)
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
    return () => {
      cancelled = true
    }
  }, [navigate])

  function handleAdded(newProspect) {
    setProspects((prev) => [newProspect, ...prev])
  }

  function handleUpdated(updated) {
    setProspects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
  }

  function handleDeleted(id) {
    setProspects((prev) => prev.filter((p) => p.id !== id))
  }

  // Stats
  const countByStatus = STATUSES.reduce((acc, s) => {
    acc[s] = prospects.filter((p) => p.status === s).length
    return acc
  }, {})

  const filtered =
    filterStatus === 'all' ? prospects : prospects.filter((p) => p.status === filterStatus)

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
          {t('admin.nav_dashboard')}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <button
          type="button"
          onClick={() => navigate('/admin/dashboard')}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {t('admin.nav_admin')}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('admin.prospects_title')}
        </span>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-12">
        <div className="mb-8">
          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em]">
            {t('admin.prospects_title')}
          </h1>
          <p className="mt-2 font-body text-body-md text-outline">
            {t('admin.prospects_subtitle')}
          </p>
        </div>

        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-8">
            {error}
          </p>
        )}

        {/* Pipeline stats */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-8">
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFilterStatus(s === filterStatus ? 'all' : s)}
              className={`bg-surface-container-lowest rounded-md p-4 text-left shadow-ambient transition-all hover:opacity-90 ${
                filterStatus === s ? 'ring-2 ring-amendly-blue' : ''
              }`}
            >
              <p className="font-display text-display-sm text-on-surface">
                {countByStatus[s]}
              </p>
              <p className="font-body text-label-sm text-outline mt-1">
                {t(`admin.status_${s}`)}
              </p>
            </button>
          ))}
        </div>

        {/* Total + filter indicator */}
        <div className="flex items-center justify-between mb-6">
          <p className="font-body text-body-md text-outline">
            {filterStatus === 'all'
              ? t('admin.prospects_count').replace('{n}', prospects.length)
              : t('admin.prospects_filtered')
                  .replace('{n}', filtered.length)
                  .replace('{status}', t(`admin.status_${filterStatus}`).toLowerCase())}
            {filterStatus !== 'all' && (
              <button
                type="button"
                onClick={() => setFilterStatus('all')}
                className="ml-2 text-secondary hover:underline"
              >
                ({t('admin.show_all')})
              </button>
            )}
          </p>
          <AddProspectForm onAdded={handleAdded} />
        </div>

        {/* Prospect list */}
        <div className="flex flex-col gap-4">
          {filtered.map((p) => (
            <ProspectRow
              key={p.id}
              prospect={p}
              onUpdated={handleUpdated}
              onDeleted={handleDeleted}
            />
          ))}
          {filtered.length === 0 && (
            <div className="bg-surface-container-lowest rounded-md p-8 text-center">
              <p className="font-body text-body-md text-outline">
                {filterStatus === 'all'
                  ? t('admin.no_prospects_empty')
                  : t('admin.no_prospects_filtered').replace(
                      '{status}',
                      t(`admin.status_${filterStatus}`).toLowerCase()
                    )}
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
