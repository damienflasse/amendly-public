/**
 * AdminEmailTemplates — superadmin page for editing transactional email templates.
 *
 * Route: /admin/email-templates
 *
 * Accessible to platform superusers only. Non-superusers are redirected to
 * /dashboard on mount (403 response from the admin API).
 *
 * On mount it fetches:
 *   GET /api/admin/email-templates — loads all template definitions.
 *
 * Features:
 *   - Lists all email templates (invite, amendment_accepted, amendment_rejected, magic_link).
 *   - Each template shows:
 *       • template_key (read-only)
 *       • is_customised badge (Custom / Default)
 *       • last updated timestamp (if customised)
 *       • available {variables} list
 *       • subject field (editable)
 *       • html_body textarea (editable)
 *   - Save via PATCH /api/admin/email-templates/{key}.
 *   - Reset to default via DELETE /api/admin/email-templates/{key} (with confirmation).
 *   - Live HTML preview rendered in a sandboxed iframe.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - bg-surface-container-lowest cards with shadow-ambient.
 *   - Manrope for headings, Inter for body/UI text.
 *
 * Props: none
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { emailTemplateClient } from '../lib/organisations'
import { useTranslation } from '../hooks/useTranslation'

// ---------------------------------------------------------------------------
// TemplateCard
// ---------------------------------------------------------------------------

/**
 * Editable card for a single email template.
 *
 * @param {{ template: object, onSaved: function }} props
 *   template — EmailTemplateResponse from the API.
 *   onSaved  — Called with the updated template after a successful save/reset.
 */
function TemplateCard({ template, onSaved }) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')
  const [error, setError] = useState(null)
  const [showPreview, setShowPreview] = useState(false)

  const [subject, setSubject] = useState(template.subject)
  const [htmlBody, setHtmlBody] = useState(template.html_body)

  // Sync local state when parent template changes (e.g. after reset)
  useEffect(() => {
    setSubject(template.subject)
    setHtmlBody(template.html_body)
  }, [template])

  async function handleSave() {
    setError(null)
    setSaving(true)
    try {
      const updated = await emailTemplateClient.upsert(template.template_key, {
        subject: subject.trim(),
        html_body: htmlBody,
      })
      onSaved(updated)
      setEditing(false)
      setSavedMsg(t('admin.template_saved'))
      setTimeout(() => setSavedMsg(''), 2500)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    const label = t(`admin.template_${template.template_key}`) || template.template_key
    if (
      !window.confirm(t('admin.template_reset_confirm').replace('{name}', label))
    )
      return

    setError(null)
    setSaving(true)
    try {
      const reset = await emailTemplateClient.reset(template.template_key)
      onSaved(reset)
      setEditing(false)
      setSavedMsg(t('admin.template_reset_saved'))
      setTimeout(() => setSavedMsg(''), 2500)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  function handleCancel() {
    setSubject(template.subject)
    setHtmlBody(template.html_body)
    setError(null)
    setEditing(false)
  }

  const labelClass = 'font-body text-label-sm text-outline block mb-1'
  const inputClass =
    'w-full bg-surface-container rounded px-3 py-2 font-body text-body-md text-on-surface focus:outline-none focus:ring-1 focus:ring-amendly-blue'

  return (
    <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
            {t(`admin.template_${template.template_key}`) || template.template_key}
          </h2>
          <div className="flex items-center gap-3 mt-2">
            <span className="font-mono text-label-sm text-outline bg-surface-container px-2 py-0.5 rounded">
              {template.template_key}
            </span>
            {template.is_customised ? (
              <span className="font-body text-label-sm text-on-primary-fixed bg-amendly-blue-fixed px-2 py-0.5 rounded-md uppercase tracking-[0.04em]">
                {t('admin.template_badge_custom')}
              </span>
            ) : (
              <span className="font-body text-label-sm text-outline bg-surface-container-highest px-2 py-0.5 rounded-md uppercase tracking-[0.04em]">
                {t('admin.template_badge_default')}
              </span>
            )}
            {template.updated_at && (
              <span className="font-body text-label-sm text-outline">
                {t('admin.template_updated_at').replace('{date}', new Date(template.updated_at).toLocaleString())}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0 ml-4">
          {savedMsg && (
            <span className="font-body text-body-sm text-secondary">{savedMsg}</span>
          )}
          {!editing ? (
            <>
              <button
                type="button"
                onClick={() => setShowPreview((v) => !v)}
                className="px-3 py-2 bg-surface-container text-on-surface rounded-md font-body text-body-sm hover:opacity-90 transition-opacity"
              >
                {showPreview ? t('admin.template_hide_preview') : t('admin.template_preview')}
              </button>
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="px-4 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 transition-opacity"
              >
                {t('admin.template_edit')}
              </button>
            </>
          ) : (
            <>
              {template.is_customised && (
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={saving}
                  className="px-3 py-2 bg-error-container text-on-error-container rounded-md font-body text-body-sm hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {t('admin.template_reset')}
                </button>
              )}
              <button
                type="button"
                onClick={handleCancel}
                disabled={saving}
                className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {t('admin.template_cancel')}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-amendly-blue text-on-primary rounded-md font-body text-body-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {saving ? t('admin.template_saving') : t('admin.template_save')}
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-6">
          {error}
        </p>
      )}

      {/* Variables hint */}
      {template.variables.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          <span className="font-body text-label-sm text-outline self-center">
            {t('admin.template_placeholders')}
          </span>
          {template.variables.map((v) => (
            <span
              key={v}
              className="font-mono text-label-sm text-amendly-blue bg-amendly-blue/10 px-2 py-0.5 rounded"
            >
              {v}
            </span>
          ))}
        </div>
      )}

      {/* Subject */}
      <div className="mb-6">
        <label className={labelClass}>{t('admin.template_subject')}</label>
        {editing ? (
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className={inputClass}
          />
        ) : (
          <p className="font-body text-body-md text-on-surface">{template.subject}</p>
        )}
      </div>

      {/* HTML body */}
      <div>
        <label className={labelClass}>{t('admin.template_html_body')}</label>
        {editing ? (
          <textarea
            rows={18}
            value={htmlBody}
            onChange={(e) => setHtmlBody(e.target.value)}
            className={`${inputClass} resize-y font-mono text-label-sm leading-relaxed`}
            spellCheck={false}
          />
        ) : (
          <p className="font-body text-label-sm text-outline italic">
            {t('admin.template_char_count').replace('{count}', template.html_body.length)}
          </p>
        )}
      </div>

      {/* Live preview */}
      {showPreview && (
        <div className="mt-6">
          <p className={labelClass}>{t('admin.template_preview_label')}</p>
          <div className="rounded-md overflow-hidden border border-surface-container-highest">
            <iframe
              title={`Preview — ${template.template_key}`}
              sandbox="allow-same-origin"
              srcDoc={htmlBody}
              className="w-full h-96 bg-white"
            />
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AdminEmailTemplates page
// ---------------------------------------------------------------------------

/**
 * Admin email templates management page.
 * Protected — ProtectedRoute ensures the user is authenticated before rendering.
 * Redirects to /dashboard if the user is not a superuser (API returns 403).
 */
export default function AdminEmailTemplates() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await emailTemplateClient.list()
        if (!cancelled) setTemplates(data)
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
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSaved(updatedTemplate) {
    setTemplates((prev) =>
      prev.map((tmpl) =>
        tmpl.template_key === updatedTemplate.template_key ? updatedTemplate : tmpl
      )
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
          {t('admin.email_templates_title')}
        </span>
      </header>

      {/* Main content */}
      <main className="max-w-4xl mx-auto px-8 py-12">
        <div className="mb-12">
          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em]">
            {t('admin.email_templates_title')}
          </h1>
          <p className="mt-2 font-body text-body-md text-outline">
            {t('admin.email_templates_subtitle_before')}
            <span className="font-mono text-amendly-blue">{'{variable}'}</span>
            {t('admin.email_templates_subtitle_after')}
          </p>
        </div>

        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-8">
            {error}
          </p>
        )}

        <div className="flex flex-col gap-8">
          {templates.map((tmpl) => (
            <TemplateCard
              key={tmpl.template_key}
              template={tmpl}
              onSaved={handleSaved}
            />
          ))}
          {templates.length === 0 && !error && (
            <p className="font-body text-body-md text-outline">{t('admin.no_templates')}</p>
          )}
        </div>
      </main>
    </div>
  )
}
