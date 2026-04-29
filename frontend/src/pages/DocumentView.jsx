/**
 * DocumentView — single document page with inline edit, amendment list, and diff rendering.
 *
 * Route: /orgs/:slug/documents/:id
 *
 * On mount it fetches:
 *   1. GET /api/organisations/me          — to determine the caller's role in this org.
 *   2. GET /api/organisations/{slug}/documents/{id} — the document itself.
 *   3. GET …/documents/{id}/amendments    — paginated amendment list.
 *
 * Features:
 *   - Shows document title (headline-sm) and status badge.
 *   - Renders document body as a pre-wrapped text block, or "No body yet" empty state.
 *   - Inline edit form for title and body — shown only to owners and admins.
 *   - Export dropdown — shown only to owners and admins, with formats gated by plan.
 *     Triggers a browser download of the consolidated document.
 *   - "Submit amendment" link navigates to /orgs/:slug/documents/:id/contribute (all members).
 *     Hidden when document is closed.
 *   - AmendmentCard — compact header; clicking the chevron expands an inline thread panel
 *     showing the full diff, reactions, and decision reason (one card at a time).
 *   - Amendment list — any member can see the list of pending/accepted/rejected amendments.
 *   - Back button navigates to /orgs/:slug.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Tonal layering — surface base, cards on surface-container-lowest.
 *   - Manrope for headings, Inter for body/UI text.
 *   - Status badges use soft-fill colours.
 *   - No 1px borders; structure through background shifts and ambient shadows.
 *   - Diff tokens: additions = secondary-container bg + on-secondary-fixed bold text.
 *   - Deletions = outline text + line-through, no background.
 *
 * Props: none (reads :slug and :id from React Router params)
 * Side effects:
 *   - Uses cookie-backed authenticated API calls.
 *   - Navigates to /orgs/:slug on 404 (document not found or not a member).
 */

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { orgClient } from '../lib/organisations'
import { authClient } from '../lib/auth'
import {
  autoProposeSectionsFromParagraphs,
  computeSectionNumbers,
} from '../lib/documentSections'
import { useTranslation } from '../hooks/useTranslation'
import useAuthStore from '../store/authStore'
import DocumentImportWorkflow from '../components/DocumentImportWorkflow'
import { SectionManager } from '../components/DocumentStructureEditor'
import RichTextEditor from '../components/RichTextEditor'
import NotificationBell from '../components/NotificationBell'
import { sanitizeHtml } from '../lib/sanitize'
import {
  escapeRegex,
  extractHeadings,
  findRenderedSectionByTop,
  groupAmendmentsBySection,
  highlightHtml,
  injectHeadingIds,
  locateInPane,
} from './document-view/utils'
import { useAmendmentGutter, useDocumentBodyState, useVisibleAmendments } from './document-view/hooks'
import {
  DocumentAmendmentsPane,
  DocumentContentPane,
} from './document-view/sections'

// ---------------------------------------------------------------------------
// Export menu (owner/admin only)
// ---------------------------------------------------------------------------

/**
 * Dropdown button that triggers a document export download.
 *
 * Renders a "Export ▾" button that opens a small menu with the formats
 * available on the organisation plan. Selecting a format calls orgClient.exportDocument()
 * which fetches the consolidated document and triggers a browser download.
 *
 * The menu closes when the user clicks outside it (via a document-level
 * click listener) or after a format is selected.
 *
 * Props:
 *   slug     — Organisation slug.
 *   docId    — Document UUID.
 *   orgPlan  — Organisation billing plan.
 *   t        — Translation function from useTranslation.
 */
const ExportMenu = memo(function ExportMenu({ slug, docId, orgPlan, t }) {
  const [open, setOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(null)
  const [includeAmendments, setIncludeAmendments] = useState('none')
  const menuRef = useRef(null)
  const exportFormats =
    orgPlan === 'organisation'
      ? ['docx', 'pdf', 'txt', 'csv', 'json']
      : orgPlan === 'team'
        ? ['docx', 'pdf']
        : ['pdf']

  // Close menu on outside click
  useEffect(() => {
    if (!open) return
    function handleOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [open])

  async function handleExport(format) {
    setOpen(false)
    setExportError(null)
    setExporting(true)
    try {
      await orgClient.exportDocument(slug, docId, format, includeAmendments)
    } catch (err) {
      setExportError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        disabled={exporting}
        onClick={() => setOpen((v) => !v)}
        className="px-4 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors disabled:opacity-50 flex items-center gap-1"
      >
        {exporting ? t('document.exporting') : t('document.export')}
        {!exporting && <span className="text-outline text-xs">▾</span>}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute right-0 mt-1 w-52 bg-surface-container-lowest rounded-md shadow-ambient z-10">
          {/* Amendment inclusion selector */}
          <div className="px-4 pt-3 pb-2 border-b border-surface-container-highest">
            <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em] mb-2">
              {t('document.export_include_amendments')}
            </p>
            {['none', 'accepted', 'all'].map((opt) => (
              <label key={opt} className="flex items-center gap-2 py-0.5 cursor-pointer">
                <input
                  type="radio"
                  name="export-amendments"
                  value={opt}
                  checked={includeAmendments === opt}
                  onChange={() => setIncludeAmendments(opt)}
                  className="accent-amendly-blue"
                />
                <span className="font-body text-body-md text-on-surface">
                  {t(`document.export_amendments_${opt}`)}
                </span>
              </label>
            ))}
          </div>
          {/* Format buttons */}
          {exportFormats.map((fmt) => (
            <button
              key={fmt}
              type="button"
              onClick={() => handleExport(fmt)}
              className="w-full text-left px-4 py-2 font-body text-body-md text-on-surface hover:bg-surface-container transition-colors first:rounded-t-md last:rounded-b-md uppercase tracking-[0.04em] text-label-sm"
            >
              {fmt.toUpperCase()}
            </button>
          ))}
        </div>
      )}

      {/* Inline error message */}
      {exportError && (
        <p className="absolute right-0 mt-1 w-64 font-body text-label-sm text-on-error-container bg-error-container/40 rounded-md px-3 py-2 z-10">
          {exportError}
        </p>
      )}
    </div>
  )
})

// ---------------------------------------------------------------------------
// Share contribution link
// ---------------------------------------------------------------------------

/**
 * "Share contribution link" button + inline modal for document owners/admins.
 *
 * When the document status is 'open', renders a button that generates (or shows)
 * the public contribution URL.  The modal shows the URL, a "Copy link" button,
 * and a "Revoke link" button.
 *
 * Props:
 *   slug      — Organisation slug.
 *   docId     — Document UUID.
 *   token     — Existing contributor_token from the document (null if none).
 *   linkStatus — Contributor link state: active / expired / revoked.
 *   expiresAt — Link expiry timestamp (ISO string or null).
 *   onChange  — Called with the new token response after generate/revoke.
 *   t         — Translation function from useTranslation.
 */
function ShareContributionLink({ slug, docId, token, linkStatus, expiresAt, onChange, t }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [revoking, setRevoking] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const modalRef = useRef(null)

  const url = token ? `${window.location.origin}/contribute/${token}` : null
  const isExpired = linkStatus === 'expired'
  const hasLink = Boolean(token)
  const expiresLabel = expiresAt
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(expiresAt))
    : null

  // Close modal on outside click
  useEffect(() => {
    if (!open) return
    function handleOutside(e) {
      if (modalRef.current && !modalRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [open])

  async function handleGenerate() {
    setError(null)
    setLoading(true)
    try {
      const result = await orgClient.generateContributorToken(slug, docId)
      onChange(result)
      setOpen(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRevoke() {
    if (!window.confirm(t('document.contrib_link_revoke_confirm'))) return
    setError(null)
    setRevoking(true)
    try {
      const result = await orgClient.revokeContributorToken(slug, docId)
      onChange(result)
      setOpen(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setRevoking(false)
    }
  }

  async function handleCopy() {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback: select the input
    }
  }

  return (
    <div className="relative" ref={modalRef}>
      <button
        type="button"
        disabled={loading}
        onClick={hasLink ? () => setOpen((v) => !v) : handleGenerate}
        className="px-4 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors disabled:opacity-50"
      >
        {loading
          ? t('document.contrib_link_generating')
          : isExpired
            ? t('document.contrib_link_regenerate')
            : t('document.contrib_link_share')}
      </button>

      {error && (
        <p className="absolute right-0 mt-1 w-64 font-body text-label-sm text-on-error-container bg-error-container/40 rounded-md px-3 py-2 z-10">
          {error}
        </p>
      )}

      {open && hasLink && (
        <div className="absolute right-0 mt-1 w-96 bg-surface-container-lowest rounded-md shadow-ambient z-20 p-4 space-y-3">
          <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em]">
            {t('document.contrib_link_modal_title')}
          </p>
          <div className="flex items-center gap-2">
            <span
              className={[
                'inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase',
                isExpired
                  ? 'bg-error-container/60 text-on-error-container'
                  : 'bg-primary-fixed text-on-primary-fixed',
              ].join(' ')}
            >
              {t(`document.contrib_link_status_${linkStatus}`)}
            </span>
            {expiresLabel && (
              <span className="font-body text-label-sm text-outline">
                {t('document.contrib_link_expires_label').replace('{date}', expiresLabel)}
              </span>
            )}
          </div>
          <p className="font-body text-body-sm text-on-surface leading-relaxed">
            {isExpired
              ? t('document.contrib_link_expired_notice')
              : t('document.contrib_link_modal_desc')}
          </p>
          {!isExpired && url && (
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={url}
                className="flex-1 min-w-0 bg-surface rounded-md px-3 py-1.5 font-body text-label-sm text-on-surface truncate focus:outline-none"
                onFocus={(e) => e.target.select()}
              />
              <button
                type="button"
                onClick={handleCopy}
                className="shrink-0 px-3 py-1.5 bg-amendly-blue text-white rounded-md font-body text-label-sm hover:opacity-90 transition-opacity"
              >
                {copied ? t('document.contrib_link_copied') : t('document.contrib_link_copy')}
              </button>
            </div>
          )}
          <div className="flex items-center justify-between gap-3 pt-1">
            {isExpired ? (
              <button
                type="button"
                onClick={handleGenerate}
                disabled={loading}
                className="px-3 py-1.5 bg-amendly-blue text-white rounded-md font-body text-label-sm hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {loading ? t('document.contrib_link_generating') : t('document.contrib_link_regenerate')}
              </button>
            ) : (
              <span className="font-body text-label-sm text-outline">
                {t('document.contrib_link_status_active')}
              </span>
            )}
            <button
              type="button"
              onClick={handleRevoke}
              disabled={revoking}
              className="font-body text-label-sm text-outline hover:text-on-error-container transition-colors disabled:opacity-50"
            >
              {revoking ? t('document.contrib_link_revoking') : t('document.contrib_link_revoke')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

/**
 * Soft-fill badge for document lifecycle status.
 *
 * @param {{ status: 'draft' | 'open' | 'closed' }} props
 */
function DocStatusBadge({ status }) {
  const styles = {
    draft:  'bg-surface-container-highest text-on-surface',
    open:   'bg-primary-fixed text-on-primary-fixed',
    closed: 'bg-tertiary-fixed text-on-tertiary-fixed',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[status] ?? styles.draft}`}
    >
      {status}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Status toggle (owner/admin only)
// ---------------------------------------------------------------------------

/**
 * Status badge + contextual toggle button for document lifecycle management.
 *
 * Shows the current status badge alongside a single-action button whose label
 * reflects the next logical transition:
 *   draft  → "Open for amendments"
 *   open   → "Close for amendments"
 *   closed → "Reopen"
 *
 * Calls PUT …/status and invokes onUpdated with the returned document.
 * Shows an inline error message if the API call fails.
 *
 * Props:
 *   slug      — Organisation slug.
 *   docId     — Document UUID.
 *   current   — Current document status ('draft' | 'open' | 'closed').
 *   onUpdated — Called with the updated document object after a successful change.
 *   t         — Translation function from useTranslation.
 */
function StatusToggle({ slug, docId, current, onUpdated, t }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const nextStatus = current === 'open' ? 'closed' : 'open'
  const buttonLabel = current === 'open'
    ? t('document.close_for_amendments')
    : current === 'closed'
    ? t('document.reopen')
    : t('document.open_for_amendments')

  async function handleToggle() {
    if (
      current === 'draft' &&
      !window.confirm(
        t('document.open_for_amendments_confirm') ??
          'Une fois le document ouvert aux amendements, vous ne pourrez plus modifier son contenu. Continuer ?'
      )
    ) {
      return
    }

    setError(null)
    setSaving(true)
    try {
      const updated = await orgClient.updateDocumentStatus(slug, docId, nextStatus)
      onUpdated(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center gap-3">
      <DocStatusBadge status={current} />
      <div className="flex flex-col items-start gap-0.5">
        <button
          type="button"
          onClick={handleToggle}
          disabled={saving}
          className="px-3 py-1 bg-surface-container-highest text-on-surface rounded-md font-body text-label-sm hover:bg-surface-container transition-colors disabled:opacity-50"
        >
          {saving ? t('document.saving') : buttonLabel}
        </button>
        {current === 'draft' && !error && (
          <p className="font-body text-[10px] text-outline italic leading-snug">
            {t('document.open_for_amendments_warning') ??
              'Le texte sera verrouillé après ouverture.'}
          </p>
        )}
        {error && (
          <p className="font-body text-label-sm text-on-error-container">{error}</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Amendment status badge
// ---------------------------------------------------------------------------

/**
 * Soft-fill badge for amendment lifecycle status.
 *
 * @param {{ status: 'pending' | 'accepted' | 'rejected' | 'withdrawn' }} props
 */
function AmendmentStatusBadge({ status }) {
  const styles = {
    pending:   'bg-primary-fixed text-on-primary-fixed',
    accepted:  'bg-tertiary-fixed text-on-tertiary-fixed',
    rejected:  'bg-error-container/40 text-on-error-container',
    withdrawn: 'bg-surface-container-highest text-outline',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[status] ?? styles.pending}`}
    >
      {status}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Inline edit form
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Document editing guidance
// ---------------------------------------------------------------------------

/**
 * Compact guide that clarifies what can be edited at each document stage.
 *
 * @param {{ docStatus: 'draft' | 'open' | 'closed'; t: (key: string) => string }} props
 */
function EditingModeGuide({ docStatus, t }) {
  const items = [
    {
      id: 'content',
      label: t('document.edit_mode_content_label'),
      body:
        docStatus === 'draft'
          ? t('document.edit_mode_content_body_draft')
          : t('document.edit_mode_content_body_locked'),
      active: docStatus === 'draft',
    },
    {
      id: 'structure',
      label: t('document.edit_mode_structure_label'),
      body:
        docStatus === 'open'
          ? t('document.edit_mode_structure_body_open')
          : t('document.edit_mode_structure_body_available'),
      active: docStatus === 'draft' || docStatus === 'closed',
    },
    {
      id: 'publication',
      label: t('document.edit_mode_publication_label'),
      body:
        docStatus === 'draft'
          ? t('document.edit_mode_publication_body_draft')
          : docStatus === 'open'
            ? t('document.edit_mode_publication_body_open')
            : t('document.edit_mode_publication_body_closed'),
      active: docStatus === 'open',
    },
  ]

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {items.map((item) => (
        <div
          key={item.id}
          className={[
            'rounded-md px-4 py-4',
            item.active ? 'bg-surface-container-highest' : 'bg-surface',
          ].join(' ')}
        >
          <p className="font-body text-label-sm uppercase tracking-[0.02em] text-outline">
            {item.label}
          </p>
          <p className="mt-2 font-body text-body-sm text-on-surface leading-relaxed">
            {item.body}
          </p>
        </div>
      ))}
    </div>
  )
}

/**
 * Inline form to edit the document title and body.
 *
 * Editing rules:
 *   - Title: always editable regardless of document status.
 *   - Body (rich text): only editable when status is 'draft' (before opening).
 *   - Sections (headings): editable in 'draft' or 'closed' via PATCH /sections.
 *
 * Props:
 *   slug      — Organisation slug (used to call the API).
 *   docId     — Document UUID.
 *   docStatus — Current document lifecycle status ('draft' | 'open' | 'closed').
 *   initial   — Object with initial { title, body } values.
 *   onSaved   — Called with the updated document object after successful save.
 *   onCancel  — Called when the user dismisses the form without saving.
 *   t         — Translation function from useTranslation.
 */
function EditDocumentForm({ slug, docId, docStatus, initial, onSaved, onCancel, t }) {
  const [title, setTitle] = useState(initial.title ?? '')
  const [body, setBody] = useState(initial.body ?? '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importKey, setImportKey] = useState(0)

  const saveLabel =
    docStatus === 'draft'
      ? t('document.save_draft')
      : docStatus === 'closed'
        ? t('document.save_structure')
        : t('document.save_title')

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const nextTitle = title.trim() || undefined
      const bodyChanged = body !== (initial.body ?? '')
      const isClosedStructureEdit = docStatus === 'closed' && bodyChanged

      const updated = isClosedStructureEdit
        ? await orgClient.updateDocumentSections(slug, docId, {
            title: nextTitle,
            body,
          })
        : await orgClient.updateDocument(slug, docId, {
            title: nextTitle,
            ...(docStatus === 'draft' ? { body: body.trim() || null } : {}),
          })

      onSaved(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-surface-container-lowest rounded-md shadow-ambient mt-8">
      {/* ── Sticky save bar ── */}
      <div className="sticky top-0 z-10 flex items-center justify-between gap-4 rounded-t-md bg-surface-container-low px-8 py-4">
        <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('document.edit_form_title')}
        </h2>
        <div className="flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading || importBusy}
            className="px-6 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors"
          >
            {t('document.cancel')}
          </button>
          <button
            type="submit"
            form="doc-edit-form"
            disabled={loading || importBusy}
            className="px-8 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {loading ? t('document.saving') : saveLabel}
          </button>
        </div>
      </div>

      <form id="doc-edit-form" onSubmit={handleSubmit} className="px-8 pb-8 pt-6 space-y-4">
        {/* ── Process flow guide ── */}
        <div className="rounded-md bg-surface-container-low px-5 py-4 space-y-2">
          <p className="font-body text-label-sm text-outline uppercase tracking-[0.02em]">
            {t('document.edit_process_guide_title') ?? 'Comment ça marche'}
          </p>
          <div className="flex gap-2 flex-wrap">
            {[
              { status: 'draft',  label: t('document.edit_step_draft')  ?? '1. Brouillon — Rédigez, importez, structurez' },
              { status: 'open',   label: t('document.edit_step_open')   ?? '2. Ouvert — Collectez les amendements' },
              { status: 'closed', label: t('document.edit_step_closed') ?? '3. Clôturé — Révisez et exportez' },
            ].map(({ status, label }) => (
              <span
                key={status}
                className={`rounded-full px-3 py-1 font-body text-label-sm ${
                  docStatus === status
                    ? 'bg-amendly-blue text-white'
                    : 'bg-surface-container-highest text-outline'
                }`}
              >
                {label}
              </span>
            ))}
          </div>
        </div>

        <EditingModeGuide docStatus={docStatus} t={t} />

        {/* Title */}
        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('document.title_label')} <span className="text-secondary">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={500}
            className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
          />
        </div>

        {/* Body — rich text editor + import buttons (draft only) */}
        {docStatus === 'draft' && (
          <div>
            <div>
              <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
                {t('document.body_label')} <span className="text-outline">{t('document.body_optional')}</span>
              </label>
              <p className="mt-0.5 font-body text-label-sm text-outline">
                {t('document.body_section_hint')}
              </p>
              <p className="mt-0.5 font-body text-label-sm text-outline">
                {t('document.body_open_lock_hint')}
              </p>
            </div>

            <DocumentImportWorkflow
              slug={slug}
              currentTitle={title}
              currentBody={body}
              onBusyChange={setImportBusy}
              t={t}
              onApplyImport={({ body: importedBody, suggestedTitle, summary }) => {
                // When the imported file has no headings, auto-propose sections
                // from its paragraphs — h2 headings are inserted directly in
                // the body so they appear in the editor ready to rename.
                const finalBody =
                  summary.headingCount === 0
                    ? autoProposeSectionsFromParagraphs(importedBody)
                    : importedBody
                setBody(finalBody)
                setTitle((current) => current.trim() || suggestedTitle)
                setImportKey((value) => value + 1)
              }}
            />

            <div className="relative mt-4">
              <RichTextEditor
                key={importKey}
                value={body}
                onChange={setBody}
                placeholder={t('document.body_placeholder')}
                minHeight="min-h-[280px]"
              />
            </div>

          </div>
        )}

        {/* When open: body is locked — inform the user */}
        {docStatus === 'open' && (
          <div className="rounded-md bg-surface-container-low px-5 py-4">
            <p className="font-display text-title-md text-on-surface">
              {t('document.edit_locked_open_title')}
            </p>
            <p className="mt-2 font-body text-body-sm text-outline leading-relaxed">
              {t('document.body_locked_open')}
            </p>
            <p className="mt-2 font-body text-body-sm text-outline leading-relaxed">
              {t('document.edit_locked_open_hint')}
            </p>
          </div>
        )}

        {/* When closed: sections only (no full body edit) */}
        {docStatus === 'closed' && (
          <div>
            <div className="rounded-md bg-surface-container-low px-5 py-4">
              <p className="font-display text-title-md text-on-surface">
                {t('document.edit_locked_closed_title')}
              </p>
              <p className="mt-2 font-body text-body-sm text-outline leading-relaxed">
                {t('document.body_locked_closed')}
              </p>
              <p className="mt-2 font-body text-body-sm text-outline leading-relaxed">
                {t('document.edit_locked_closed_hint')}
              </p>
            </div>
            <SectionManager body={body} onChange={setBody} t={t} />
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
            {error}
          </p>
        )}

      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Consolidated view panel
// ---------------------------------------------------------------------------

/**
 * Read-only panel showing the document body with all accepted amendments applied.
 *
 * Fetches GET …/consolidated on mount. Displays the merged text in a pre block.
 * Shows a count of how many amendments were applied. Closed by the onClose callback.
 *
 * Props:
 *   slug    — Organisation slug.
 *   docId   — Document UUID.
 *   onClose — Called when the user closes the panel.
 *   t       — Translation function from useTranslation.
 */
function ConsolidatedPanel({ slug, docId, onClose, t }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const result = await orgClient.getConsolidated(slug, docId)
        if (!cancelled) setData(result)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [slug, docId])

  function appliedLabel(count) {
    if (count === 0) return t('document.no_accepted_amendments')
    const plural = count === 1 ? '' : 's'
    return t('document.amendments_applied')
      .replace('{count}', count)
      .replace('{plural}', plural)
  }

  return (
    <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
            {t('document.consolidated_title')}
          </h2>
          {data && (
            <p className="mt-1 font-body text-label-sm text-outline tracking-[0.02em]">
              {appliedLabel(data.amendments_applied)}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 font-body text-body-md text-secondary hover:underline"
        >
          {t('document.close')}
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <p className="font-body text-body-md text-outline">{t('document.loading_consolidated')}</p>
      ) : error ? (
        <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
          {error}
        </p>
      ) : (
        <div className="bg-surface rounded-md p-6">
          {data?.body_with_amendments_applied ? (
            data.body_with_amendments_applied.trimStart().startsWith('<') ? (
              <div
                className="doc-body font-body text-body-md text-on-surface leading-relaxed
                  [&_h2]:font-display [&_h2]:text-headline-sm [&_h2]:mt-8 [&_h2]:mb-3
                  [&_h3]:font-display [&_h3]:text-title-md [&_h3]:mt-6 [&_h3]:mb-2
                  [&_p]:my-0 [&_p+p]:mt-4
                  [&_ul]:my-4 [&_ul]:pl-5 [&_ul]:list-disc
                  [&_ol]:my-4 [&_ol]:pl-5 [&_ol]:list-decimal
                  [&_li]:my-1
                  [&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-amendly-blue
                  [&_blockquote]:pl-4 [&_blockquote]:text-outline [&_blockquote]:italic
                  [&_hr]:my-6 [&_hr]:h-px [&_hr]:border-0 [&_hr]:bg-surface-container-highest"
                dangerouslySetInnerHTML={{ __html: sanitizeHtml(data.body_with_amendments_applied) }}
              />
            ) : (
              <pre className="font-body text-body-md text-on-surface whitespace-pre-wrap">
                {data.body_with_amendments_applied}
              </pre>
            )
          ) : (
            <p className="font-body text-body-md text-outline">{t('document.no_body_text')}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline diff renderer
// ---------------------------------------------------------------------------

/**
 * Renders a list of diff tokens inline.
 *
 * Each token is a word (or word group) labelled equal, insert, or delete.
 * Insertions are highlighted with secondary-container bg + bold on-secondary-fixed text.
 * Deletions are shown with strikethrough and outline colour (no background).
 * Equal tokens are rendered as plain text.
 *
 * Props:
 *   tokens — Array of { text: string, type: 'equal' | 'insert' | 'delete' }.
 */
function DiffView({ tokens }) {
  return (
    <span className="font-body text-body-md leading-relaxed">
      {tokens.map((token, i) => {
        if (token.type === 'insert') {
          return (
            <mark
              key={i}
              className="bg-secondary-container text-on-secondary-fixed font-bold rounded px-0.5 mx-0.5 not-italic"
            >
              {token.text}
            </mark>
          )
        }
        if (token.type === 'delete') {
          return (
            <span
              key={i}
              className="line-through text-outline mx-0.5"
            >
              {token.text}
            </span>
          )
        }
        return <span key={i} className="text-on-surface mx-0.5">{token.text}</span>
      })}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Reaction summary bar (owner/admin + team/org plan only)
// ---------------------------------------------------------------------------

/**
 * Sentiment summary bar showing aggregated support vs oppose reactions
 * across all pending amendments for the document.
 *
 * Displayed above the amendment list for owners and admins on team/organisation
 * plans. Fetches GET …/documents/{docId}/reaction-summary on mount.
 *
 * Visual: a tonal progress bar with blue (support), error-container (oppose),
 * and surface-container-highest (no vote) segments.
 *
 * Props:
 *   slug  — Organisation slug.
 *   docId — Document UUID.
 *   t     — Translation function from useTranslation.
 */
function ReactionSummary({ slug, docId, t }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await orgClient.getReactionSummary(slug, docId)
        if (!cancelled) setSummary(data)
      } catch {
        // Non-fatal — silently hide on 402 or network error
        if (!cancelled) setSummary(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [slug, docId])

  if (loading || !summary || summary.total_pending === 0) return null

  const { total_pending, support_count, oppose_count } = summary
  const no_vote = total_pending - support_count - oppose_count
  const supportPct = Math.round((support_count / total_pending) * 100)
  const opposePct = Math.round((oppose_count / total_pending) * 100)
  // no-vote fills the rest to always reach 100 %
  const noVotePct = 100 - supportPct - opposePct

  return (
    <div className="mb-6 bg-surface-container-low rounded-md px-5 py-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="font-body text-label-sm text-on-surface tracking-[0.02em] uppercase">
          {t('document.reaction_summary_label')}
        </p>
        <p className="font-body text-label-sm text-outline">
          {t('document.reaction_summary_pending').replace('{n}', total_pending)}
        </p>
      </div>

      {/* Progress bar */}
      <div className="flex h-2 rounded-full overflow-hidden gap-px">
        {supportPct > 0 && (
          <div
            className="bg-amendly-blue transition-all"
            style={{ width: `${supportPct}%` }}
            aria-label={`${support_count} ${t('document.reaction_summary_support')}`}
          />
        )}
        {opposePct > 0 && (
          <div
            className="bg-error-container transition-all"
            style={{ width: `${opposePct}%` }}
            aria-label={`${oppose_count} ${t('document.reaction_summary_oppose')}`}
          />
        )}
        {noVotePct > 0 && (
          <div
            className="bg-surface-container-highest transition-all"
            style={{ width: `${noVotePct}%` }}
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 font-body text-label-sm">
        <span className="flex items-center gap-1.5 text-on-surface">
          <span className="inline-block w-2 h-2 rounded-full bg-amendly-blue" />
          {support_count} {t('document.reaction_summary_support')}
        </span>
        <span className="flex items-center gap-1.5 text-on-surface">
          <span className="inline-block w-2 h-2 rounded-full bg-error-container" />
          {oppose_count} {t('document.reaction_summary_oppose')}
        </span>
        {no_vote > 0 && (
          <span className="flex items-center gap-1.5 text-outline">
            <span className="inline-block w-2 h-2 rounded-full bg-surface-container-highest" />
            {no_vote} {t('document.reaction_summary_no_vote')}
          </span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Comment thread
// ---------------------------------------------------------------------------

/**
 * Threaded comment panel for a single amendment.
 *
 * Fetches comments on mount (when expanded). Lets any member post a new
 * comment. Shows a delete button for the comment's own author or a moderator.
 *
 * Props:
 *   slug          — Organisation slug.
 *   docId         — Document UUID.
 *   amendmentId   — Amendment UUID.
 *   currentUserId — Authenticated user's ID (for showing delete button).
 *   canModerate   — Whether the current user is owner/admin (for delete).
 *   t             — Translation function from useTranslation.
 */
function CommentThread({ slug, docId, amendmentId, currentUserId, canModerate, t }) {
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [draft, setDraft] = useState('')
  const [posting, setPosting] = useState(false)
  const [postError, setPostError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await orgClient.listComments(slug, docId, amendmentId)
        if (!cancelled) setComments(data.items)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [slug, docId, amendmentId])

  async function handlePost(e) {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    setPosting(true)
    setPostError(null)
    try {
      const created = await orgClient.postComment(slug, docId, amendmentId, text)
      setComments((prev) => [...prev, created])
      setDraft('')
    } catch (err) {
      setPostError(err.message)
    } finally {
      setPosting(false)
    }
  }

  async function handleDelete(commentId) {
    setDeletingId(commentId)
    try {
      await orgClient.deleteComment(slug, docId, amendmentId, commentId)
      setComments((prev) => prev.filter((c) => c.id !== commentId))
    } catch {
      // Non-fatal — leave comment in list
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="pt-4 border-t border-surface-container-highest space-y-3">
      <p className="font-body text-label-sm text-outline uppercase tracking-[0.02em]">
        {t('document.comments_label')}
      </p>

      {/* Comment list */}
      {loading ? (
        <p className="font-body text-label-sm text-outline">{t('document.comments_loading')}</p>
      ) : error ? (
        <p className="font-body text-label-sm text-on-error-container">{error}</p>
      ) : comments.length === 0 ? (
        <p className="font-body text-label-sm text-outline">{t('document.comments_empty')}</p>
      ) : (
        <ul className="space-y-3">
          {comments.map((comment) => {
            const commentDate = new Date(comment.created_at).toLocaleString('en-GB', {
              day: 'numeric', month: 'short', year: 'numeric',
              hour: '2-digit', minute: '2-digit',
            })
            const isOwn = comment.author_id === currentUserId
            const canDelete = isOwn || canModerate
            return (
              <li
                key={comment.id}
                className="bg-surface rounded-md px-4 py-3 space-y-1"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 font-body text-label-sm text-outline tracking-[0.02em]">
                    <span className="text-on-surface font-medium">
                      {comment.author_name || comment.author_email || t('document.modal_unknown_author')}
                    </span>
                    <span>·</span>
                    <span>{commentDate}</span>
                  </div>
                  {canDelete && (
                    <button
                      type="button"
                      disabled={deletingId === comment.id}
                      onClick={() => handleDelete(comment.id)}
                      className="font-body text-label-sm text-outline hover:text-on-error-container transition-colors disabled:opacity-40"
                      aria-label={t('document.comment_delete')}
                    >
                      {deletingId === comment.id ? '…' : '×'}
                    </button>
                  )}
                </div>
                <p className="font-body text-body-md text-on-surface whitespace-pre-wrap">
                  {comment.body}
                </p>
              </li>
            )
          })}
        </ul>
      )}

      {/* Post a new comment */}
      <form onSubmit={handlePost} className="flex gap-2 items-start pt-1">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={t('document.comment_placeholder')}
          rows={2}
          maxLength={2000}
          className="flex-1 bg-surface rounded-md px-3 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary resize-none"
        />
        <button
          type="submit"
          disabled={posting || !draft.trim()}
          className="px-4 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md disabled:opacity-50 shrink-0"
        >
          {posting ? '…' : t('document.comment_post')}
        </button>
      </form>
      {postError && (
        <p className="font-body text-label-sm text-on-error-container">{postError}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Amendment card
// ---------------------------------------------------------------------------

/**
 * Card displaying a single amendment with its status badge, inline diff, and reaction votes.
 *
 * On mount it fetches the word-level diff via GET …/amendments/{id}/diff for
 * text_change amendments.  General comments skip the diff and show the
 * justification text directly.
 *
 * Reaction buttons (+1 Support / −1 Oppose) are shown for team/organisation plans.
 * Solo-plan orgs see an upgrade nudge instead. Counts are updated optimistically.
 *
 * Props:
 *   slug          — Organisation slug (needed for the diff API call).
 *   docId         — Document UUID (needed for the diff API call).
 *   amendment     — Amendment object (includes amendment_type, decision_reason,
 *                   support_count, oppose_count, user_reaction).
 *   canModerate   — Whether the current user can accept/reject (owner/admin).
 *   currentUserId — The authenticated user's ID (used to show Withdraw button).
 *   orgPlan       — The organisation's billing plan ('solo' | 'team' | 'organisation').
 *   isExpanded    — Whether this card's thread panel is currently expanded.
 *   onAccept      — Called with (amendmentId, reason) when Accept is confirmed.
 *   onReject      — Called with (amendmentId, reason) when Reject is confirmed.
 *   onWithdraw    — Called when the Withdraw button is clicked.
 *   onReact       — Called with (amendmentId, type) when a reaction button is clicked.
 *   onToggleThread — Called when the user clicks the expand/collapse chevron.
 *   t             — Translation function from useTranslation.
 */
function AmendmentCard({ slug, docId, amendment, isActive, isLocked, onLock, canModerate, currentUserId, orgPlan, isSelected, isExpanded, onToggleSelect, onAccept, onReject, onWithdraw, onReact, onToggleThread, leftPaneRef, docBodyRef, t }) {
  const [diffTokens, setDiffTokens] = useState(null)   // null = loading
  const [diffError, setDiffError] = useState(false)

  // Decision modal state
  const [showDecisionModal, setShowDecisionModal] = useState(null)  // 'accept' | 'reject' | null
  const [decisionReason, setDecisionReason] = useState('')
  const [deciding, setDeciding] = useState(false)

  // Copy-link flash state
  const [copied, setCopied] = useState(false)

  // Locate-in-text state
  const [locateNotFound, setLocateNotFound] = useState(false)
  const locateCleanupRef = useRef(null)
  const locateTimerRef = useRef(null)
  const copiedTimerRef = useRef(null)

  // Clear pending timers on unmount to prevent state updates on unmounted component
  useEffect(() => {
    return () => {
      clearTimeout(locateTimerRef.current)
      clearTimeout(copiedTimerRef.current)
      if (locateCleanupRef.current) locateCleanupRef.current()
    }
  }, [])

  // Optimistic reaction state
  const [supportCount, setSupportCount] = useState(amendment.support_count ?? 0)
  const [opposeCount, setOpposeCount] = useState(amendment.oppose_count ?? 0)
  const [userReaction, setUserReaction] = useState(amendment.user_reaction ?? null)
  const [reacting, setReacting] = useState(false)

  const isGeneralComment = amendment.amendment_type === 'general_comment'
  const hasReactionPlan = orgPlan === 'organisation'

  useEffect(() => {
    // Skip diff fetch for general comments
    if (isGeneralComment) return

    let cancelled = false

    async function fetchDiff() {
      try {
        const data = await orgClient.getAmendmentDiff(slug, docId, amendment.id)
        if (!cancelled) setDiffTokens(data.tokens)
      } catch {
        if (!cancelled) setDiffError(true)
      }
    }

    fetchDiff()
    return () => { cancelled = true }
  }, [slug, docId, amendment.id, isGeneralComment])

  const date = new Date(amendment.created_at).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

  const dateWithTime = new Date(amendment.created_at).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  async function handleDecisionConfirm() {
    setDeciding(true)
    try {
      if (showDecisionModal === 'accept') {
        await onAccept(amendment.id, decisionReason.trim() || undefined)
      } else {
        await onReject(amendment.id, decisionReason.trim() || undefined)
      }
      setShowDecisionModal(null)
      setDecisionReason('')
    } finally {
      setDeciding(false)
    }
  }

  async function handleReact(type) {
    if (reacting) return
    // Optimistic update
    const prevSupport = supportCount
    const prevOppose = opposeCount
    const prevReaction = userReaction
    if (userReaction === type) {
      // Toggle off
      setUserReaction(null)
      if (type === 'support') setSupportCount((n) => Math.max(0, n - 1))
      else setOpposeCount((n) => Math.max(0, n - 1))
    } else {
      // Switch or new reaction
      if (userReaction === 'support') setSupportCount((n) => Math.max(0, n - 1))
      if (userReaction === 'oppose') setOpposeCount((n) => Math.max(0, n - 1))
      if (type === 'support') setSupportCount((n) => n + 1)
      else setOpposeCount((n) => n + 1)
      setUserReaction(type)
    }
    setReacting(true)
    try {
      const updated = await onReact(amendment.id, type)
      // Sync with server truth
      setSupportCount(updated.support_count)
      setOpposeCount(updated.oppose_count)
      setUserReaction(updated.user_reaction)
    } catch {
      // Rollback on error
      setSupportCount(prevSupport)
      setOpposeCount(prevOppose)
      setUserReaction(prevReaction)
    } finally {
      setReacting(false)
    }
  }

  function handleCopyLink(e) {
    e.stopPropagation()
    const url = `${window.location.origin}/orgs/${slug}/documents/${docId}#amendment-${amendment.id}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      clearTimeout(copiedTimerRef.current)
      copiedTimerRef.current = setTimeout(() => setCopied(false), 2000)
    })
  }

  function clearLocateMark() {
    if (locateCleanupRef.current) {
      locateCleanupRef.current()
      locateCleanupRef.current = null
    }
  }

  function handleLocate(e) {
    e.stopPropagation()
    clearLocateMark()
    const cleanup = locateInPane(leftPaneRef, docBodyRef, amendment.original_text, { scroll: true })
    if (cleanup) {
      locateCleanupRef.current = cleanup
      clearTimeout(locateTimerRef.current)
      locateTimerRef.current = setTimeout(() => clearLocateMark(), 1500)
    } else {
      setLocateNotFound(true)
      clearTimeout(locateTimerRef.current)
      locateTimerRef.current = setTimeout(() => setLocateNotFound(false), 2500)
    }
  }

  function handleCardMouseEnter() {
    if (!amendment.original_text || isGeneralComment) return
    clearLocateMark()
    const cleanup = locateInPane(leftPaneRef, docBodyRef, amendment.original_text, { scroll: false })
    if (cleanup) locateCleanupRef.current = cleanup
  }

  function handleCardMouseLeave() {
    if (!isLocked) clearLocateMark()
  }

  function handleCardClick(e) {
    // Don't lock when clicking interactive elements inside the card
    if (e.target.closest('button, input, textarea, a, [role="button"]')) return
    if (!amendment.original_text || isGeneralComment) return
    if (isLocked) {
      onLock(null)
    } else {
      clearLocateMark()
      const cleanup = locateInPane(leftPaneRef, docBodyRef, amendment.original_text, { scroll: true })
      if (cleanup) locateCleanupRef.current = cleanup
      onLock(amendment.id)
    }
  }

  // When this card gets unlocked (another card was locked), clear the highlight
  useEffect(() => {
    if (!isLocked) clearLocateMark()
  }, [isLocked])

  return (
    <div
      id={`amendment-${amendment.id}`}
      className={`bg-surface-container-lowest rounded-md shadow-ambient p-6 space-y-4 transition-shadow ${isActive ? 'ring-2 ring-amendly-blue/50' : ''} ${isLocked ? 'ring-2 ring-secondary/60' : ''} ${!isGeneralComment && amendment.original_text ? 'cursor-pointer' : ''}`}
      onMouseEnter={handleCardMouseEnter}
      onMouseLeave={handleCardMouseLeave}
      onClick={handleCardClick}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        {/* Bulk-select checkbox — owner/admin + pending only — expanded only */}
        {isExpanded && canModerate && amendment.status === 'pending' && (
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(amendment.id)}
            aria-label={`Select amendment`}
            className="mt-1 h-4 w-4 shrink-0 rounded accent-amendly-blue cursor-pointer"
          />
        )}
        <div className="space-y-1 min-w-0 flex-1">
          {/* Type badge, section, date — expanded only */}
          {isExpanded && isGeneralComment && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase bg-surface-container-highest text-outline">
              {t('document.type_general_comment')}
            </span>
          )}
          {isExpanded && amendment.section && (
            <p className="font-body text-label-sm text-outline tracking-[0.02em] uppercase">
              {amendment.section}
            </p>
          )}
          {isExpanded && (
            <p className="font-body text-label-sm text-outline tracking-[0.02em]">{date}</p>
          )}
          {(amendment.author_name || amendment.author_email) && (
            <p className="font-body text-label-sm text-outline tracking-[0.02em]">
              {amendment.author_name || amendment.author_email}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <AmendmentStatusBadge status={amendment.status} />
          {/* Copy link + comment count — expanded only */}
          {isExpanded && (
            <button
              type="button"
              onClick={handleCopyLink}
              title={t('document.review_copy_link')}
              className="font-body text-label-sm text-outline hover:text-secondary px-2 py-0.5 rounded hover:bg-surface-container transition-colors"
            >
              {copied ? t('document.review_link_copied') : '🔗'}
            </button>
          )}
          <button
            type="button"
            onClick={onToggleThread}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? t('document.thread_collapse') : t('document.thread_expand')}
            className="flex items-center justify-center w-6 h-6 rounded-full bg-surface-container-highest text-on-surface hover:bg-surface-container transition-colors text-xs font-body"
          >
            {isExpanded ? '▲' : '▼'}
          </button>
        </div>
      </div>

      {/* Collapsed diff preview — shown only when not expanded */}
      {!isExpanded && (
        <div className="rounded-md bg-surface p-3">
          {isGeneralComment ? (
            amendment.justification && (
              <p className="font-body text-body-sm text-on-surface leading-relaxed line-clamp-3">
                {amendment.justification}
              </p>
            )
          ) : (
            diffTokens === null && !diffError ? (
              <p className="font-body text-body-sm text-outline">{t('document.loading_diff')}</p>
            ) : diffError || diffTokens === null ? (
              <div className="space-y-1">
                <p className="font-body text-body-sm text-on-surface line-through text-outline">{amendment.original_text}</p>
                <p className="font-body text-body-sm bg-secondary-container text-on-secondary-fixed font-bold rounded px-1">{amendment.proposed_text}</p>
              </div>
            ) : (
              <DiffView tokens={diffTokens} />
            )
          )}
        </div>
      )}

      {/* Source excerpt chip + Locate button — text_change only, expanded only */}
      {isExpanded && !isGeneralComment && amendment.original_text && (
        <div className="flex items-start gap-3 flex-wrap">
          <div className="flex-1 min-w-0 rounded-md bg-surface-container-low px-3 py-2">
            <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em] mb-0.5">
              {t('document.source_excerpt')}
            </p>
            <p className="font-body text-body-sm text-outline italic leading-relaxed truncate">
              {amendment.original_text.length > 100
                ? `${amendment.original_text.slice(0, 100)}…`
                : amendment.original_text}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <button
              type="button"
              onClick={handleLocate}
              className="font-body text-label-sm text-secondary hover:underline whitespace-nowrap px-2 py-1 rounded hover:bg-surface-container transition-colors"
            >
              {t('document.locate_in_text')}
            </button>
            {locateNotFound && (
              <p className="font-body text-label-sm text-outline italic">
                {t('document.locate_not_found')}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Thread panel — shown only when expanded */}
      {isExpanded && (<>
      {/* Author + submission timestamp row */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 font-body text-label-sm text-outline tracking-[0.02em]">
        <span>
          <span className="uppercase mr-1">{t('document.modal_author')}</span>
          <span className="text-on-surface">
            {amendment.author_name || amendment.contributor_name || amendment.author_email || t('document.modal_unknown_author')}
          </span>
          {(amendment.author_name || amendment.contributor_name) && (amendment.author_email || amendment.contributor_email) && (
            <span className="ml-1">({amendment.author_email || amendment.contributor_email})</span>
          )}
          {!amendment.author_id && (amendment.contributor_name || amendment.contributor_email) && (
            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-surface-container-highest text-outline text-xs uppercase tracking-wide">
              {t('document.contrib_anonymous_badge')}
            </span>
          )}
        </span>
        <span>
          <span className="uppercase mr-1">{t('document.modal_submitted')}</span>
          <span className="text-on-surface">{dateWithTime}</span>
        </span>
      </div>
      <div className="rounded-md bg-surface p-4 space-y-3">
        {isGeneralComment ? (
          /* General comment — show justification as the comment body */
          <div>
            <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-2">
              {t('document.comment_label')}
            </p>
            <p className="font-body text-body-md text-on-surface leading-relaxed whitespace-pre-wrap">
              {amendment.justification}
            </p>
          </div>
        ) : (
          /* Text change — show diff */
          <>
            {diffTokens === null && !diffError ? (
              <p className="font-body text-body-md text-outline">{t('document.loading_diff')}</p>
            ) : diffError || diffTokens === null ? (
              <>
                <div>
                  <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">
                    {t('document.original_label')}
                  </p>
                  <p className="font-body text-body-md text-on-surface line-through text-outline">
                    {amendment.original_text}
                  </p>
                </div>
                <div>
                  <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">
                    {t('document.proposed_label')}
                  </p>
                  <p className="font-body text-body-md bg-secondary-container text-on-secondary-fixed font-bold rounded px-1">
                    {amendment.proposed_text}
                  </p>
                </div>
              </>
            ) : (
              <div>
                <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-2">
                  {t('document.diff_label')}
                </p>
                <DiffView tokens={diffTokens} />
              </div>
            )}

            {amendment.justification && (
              <div>
                <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">
                  {t('document.justification_block_label')}
                </p>
                <p className="font-body text-body-md text-on-surface">{amendment.justification}</p>
              </div>
            )}
          </>
        )}

        {/* Decision reason (shown after accept/reject) */}
        {amendment.decision_reason && (
          <div className="mt-2 pt-3 border-t border-surface-container-highest">
            <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">
              {t('document.decision_reason_block_label')}
            </p>
            <p className="font-body text-body-md text-on-surface italic">{amendment.decision_reason}</p>
          </div>
        )}
      </div>

      {/* Moderation buttons — owner/admin only, only on pending amendments */}
      {canModerate && amendment.status === 'pending' && !showDecisionModal && (
        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={() => { setShowDecisionModal('accept'); setDecisionReason('') }}
            className="px-6 py-1.5 bg-tertiary-fixed text-on-tertiary-fixed rounded-md font-body text-body-md"
          >
            {t('document.accept')}
          </button>
          <button
            type="button"
            onClick={() => { setShowDecisionModal('reject'); setDecisionReason('') }}
            className="px-6 py-1.5 bg-error-container/40 text-on-error-container rounded-md font-body text-body-md"
          >
            {t('document.reject')}
          </button>
        </div>
      )}

      {/* Decision confirmation panel */}
      {canModerate && showDecisionModal && (
        <div className="pt-2 space-y-3 border-t border-surface-container-highest">
          <p className="font-body text-body-md text-on-surface font-medium">
            {showDecisionModal === 'accept' ? t('document.confirm_accept') : t('document.confirm_reject')}
          </p>
          <textarea
            value={decisionReason}
            onChange={(e) => setDecisionReason(e.target.value)}
            placeholder={t('document.decision_reason_placeholder')}
            rows={2}
            className="w-full bg-surface rounded-md px-3 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary resize-none"
          />
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleDecisionConfirm}
              disabled={deciding}
              className={[
                'px-5 py-1.5 rounded-md font-body text-body-md disabled:opacity-50',
                showDecisionModal === 'accept'
                  ? 'bg-tertiary-fixed text-on-tertiary-fixed'
                  : 'bg-error-container/40 text-on-error-container',
              ].join(' ')}
            >
              {deciding ? '…' : (showDecisionModal === 'accept' ? t('document.accept') : t('document.reject'))}
            </button>
            <button
              type="button"
              onClick={() => setShowDecisionModal(null)}
              disabled={deciding}
              className="px-5 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md"
            >
              {t('document.cancel')}
            </button>
          </div>
        </div>
      )}

      {/* Reaction bar — organisation plan only */}
      {hasReactionPlan ? (
        <>
          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              disabled={reacting}
              onClick={() => handleReact('support')}
              className={[
                'flex items-center gap-1.5 px-4 py-1.5 rounded-md font-body text-body-md transition-colors disabled:opacity-50',
                userReaction === 'support'
                  ? 'bg-amendly-blue text-white'
                  : 'bg-surface-container-highest text-on-surface hover:bg-surface-container',
              ].join(' ')}
              aria-pressed={userReaction === 'support'}
            >
              {userReaction === 'support' ? t('document.react_support_active') : t('document.react_support')}
              {supportCount > 0 && (
                <span className={userReaction === 'support' ? 'text-white/80' : 'text-outline'}>
                  {supportCount}
                </span>
              )}
            </button>
            <button
              type="button"
              disabled={reacting}
              onClick={() => handleReact('oppose')}
              className={[
                'flex items-center gap-1.5 px-4 py-1.5 rounded-md font-body text-body-md transition-colors disabled:opacity-50',
                userReaction === 'oppose'
                  ? 'bg-error-container/60 text-on-error-container'
                  : 'bg-surface-container-highest text-on-surface hover:bg-surface-container',
              ].join(' ')}
              aria-pressed={userReaction === 'oppose'}
            >
              {userReaction === 'oppose' ? t('document.react_oppose_active') : t('document.react_oppose')}
              {opposeCount > 0 && (
                <span className={userReaction === 'oppose' ? 'text-on-error-container/70' : 'text-outline'}>
                  {opposeCount}
                </span>
              )}
            </button>
          </div>

          {/* Proportional reactions bar — only when at least one reaction exists */}
          {(supportCount + opposeCount) > 0 && (
            <div
              className="mt-2 flex rounded-full overflow-hidden h-1.5"
              aria-label={`${supportCount} support, ${opposeCount} oppose`}
              role="img"
            >
              {supportCount > 0 && (
                <div
                  className="bg-amendly-blue transition-all duration-300"
                  style={{ width: `${Math.round(supportCount / (supportCount + opposeCount) * 100)}%` }}
                />
              )}
              {opposeCount > 0 && (
                <div className="bg-error-container flex-1" />
              )}
            </div>
          )}
        </>
      ) : (
        <div className="flex items-center gap-2 pt-2">
          <p className="font-body text-label-sm text-outline">
            {t('document.reactions_upgrade_nudge')}
          </p>
          <a
            href={`/billing`}
            className="font-body text-label-sm text-secondary hover:underline shrink-0"
          >
            {t('document.reactions_upgrade_link')} →
          </a>
        </div>
      )}

      {/* Comment thread */}
      <CommentThread
        slug={slug}
        docId={docId}
        amendmentId={amendment.id}
        currentUserId={currentUserId}
        canModerate={canModerate}
        t={t}
      />

      {/* Withdraw button — author only, pending only */}
      {amendment.status === 'pending' && amendment.author_id === currentUserId && (
        <div className="flex justify-end pt-1">
          <button
            type="button"
            onClick={() => onWithdraw(amendment.id)}
            className="font-body text-label-sm text-outline hover:text-on-error-container hover:underline transition-colors"
          >
            {t('document.withdraw')}
          </button>
        </div>
      )}
      </>)}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Amendment detail modal
// ---------------------------------------------------------------------------

/**
 * Full-screen overlay showing the complete details of a single amendment.
 *
 * Displays amendment type, section, status badge, full diff (fetched on open),
 * justification, decision reason, author name/email, and submitted-at timestamp.
 *
 * For owners/admins, shows the same Accept/Reject controls as the card so they
 * can act without closing the modal.
 *
 * Pressing Escape or clicking the backdrop closes the modal.
 *
 * Props:
 *   slug          — Organisation slug.
 *   docId         — Document UUID.
 *   amendment     — The amendment object to display.
 *   canModerate   — Whether the current user can accept/reject (owner/admin).
 *   onAccept      — Called with (amendmentId, reason) on Accept confirm.
 *   onReject      — Called with (amendmentId, reason) on Reject confirm.
 *   onClose       — Called to dismiss the modal.
 *   t             — Translation function from useTranslation.
 */
function AmendmentDetailModal({ slug, docId, amendment, canModerate, onAccept, onReject, onClose, t }) {
  const [diffTokens, setDiffTokens] = useState(null)
  const [diffError, setDiffError] = useState(false)
  const [showDecisionModal, setShowDecisionModal] = useState(null) // 'accept' | 'reject' | null
  const [decisionReason, setDecisionReason] = useState('')
  const [deciding, setDeciding] = useState(false)

  const isGeneralComment = amendment.amendment_type === 'general_comment'

  // Fetch diff on open
  useEffect(() => {
    if (isGeneralComment) return
    let cancelled = false
    async function fetchDiff() {
      try {
        const data = await orgClient.getAmendmentDiff(slug, docId, amendment.id)
        if (!cancelled) setDiffTokens(data.tokens)
      } catch {
        if (!cancelled) setDiffError(true)
      }
    }
    fetchDiff()
    return () => { cancelled = true }
  }, [slug, docId, amendment.id, isGeneralComment])

  // Escape key closes modal
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  const date = new Date(amendment.created_at).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  async function handleDecisionConfirm() {
    setDeciding(true)
    try {
      if (showDecisionModal === 'accept') {
        await onAccept(amendment.id, decisionReason.trim() || undefined)
      } else {
        await onReject(amendment.id, decisionReason.trim() || undefined)
      }
      setShowDecisionModal(null)
      setDecisionReason('')
      onClose()
    } finally {
      setDeciding(false)
    }
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label={t('document.modal_title')}
    >
      {/* Panel */}
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-surface rounded-lg shadow-2xl mx-4">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-8 pt-8 pb-4">
          <div className="space-y-1.5 min-w-0">
            {isGeneralComment && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase bg-surface-container-highest text-outline">
                {t('document.type_general_comment')}
              </span>
            )}
            {amendment.section && (
              <p className="font-body text-label-sm text-outline tracking-[0.02em] uppercase">
                {amendment.section}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <AmendmentStatusBadge status={amendment.status} />
            <button
              type="button"
              onClick={onClose}
              aria-label={t('document.modal_close')}
              className="font-body text-body-md text-outline hover:text-on-surface transition-colors leading-none"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="px-8 pb-8 space-y-6">

          {/* Author + timestamp row */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 font-body text-label-sm text-outline tracking-[0.02em]">
            <span>
              <span className="uppercase mr-1">{t('document.modal_author')}</span>
              <span className="text-on-surface">
                {amendment.author_name || amendment.contributor_name || amendment.author_email || t('document.modal_unknown_author')}
              </span>
              {(amendment.author_name || amendment.contributor_name) && (amendment.author_email || amendment.contributor_email) && (
                <span className="ml-1">({amendment.author_email || amendment.contributor_email})</span>
              )}
              {!amendment.author_id && (amendment.contributor_name || amendment.contributor_email) && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded bg-surface-container-highest text-outline text-xs uppercase tracking-wide">
                  {t('document.contrib_anonymous_badge')}
                </span>
              )}
            </span>
            <span>
              <span className="uppercase mr-1">{t('document.modal_submitted')}</span>
              <span className="text-on-surface">{date}</span>
            </span>
          </div>

          {/* Diff / content block */}
          <div className="rounded-md bg-surface-container-low p-5 space-y-4">
            {isGeneralComment ? (
              <div>
                <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-2">
                  {t('document.comment_label')}
                </p>
                <p className="font-body text-body-md text-on-surface leading-relaxed whitespace-pre-wrap">
                  {amendment.justification}
                </p>
              </div>
            ) : (
              <>
                {diffTokens === null && !diffError ? (
                  <p className="font-body text-body-md text-outline">{t('document.loading_diff')}</p>
                ) : diffError || diffTokens === null ? (
                  <>
                    <div>
                      <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">{t('document.original_label')}</p>
                      <p className="font-body text-body-md text-on-surface line-through text-outline">{amendment.original_text}</p>
                    </div>
                    <div>
                      <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">{t('document.proposed_label')}</p>
                      <p className="font-body text-body-md bg-secondary-container text-on-secondary-fixed font-bold rounded px-1">{amendment.proposed_text}</p>
                    </div>
                  </>
                ) : (
                  <div>
                    <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-2">{t('document.diff_label')}</p>
                    <DiffView tokens={diffTokens} />
                  </div>
                )}

                {amendment.justification && (
                  <div>
                    <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">{t('document.justification_block_label')}</p>
                    <p className="font-body text-body-md text-on-surface">{amendment.justification}</p>
                  </div>
                )}
              </>
            )}

            {/* Decision reason */}
            {amendment.decision_reason && (
              <div className="pt-3 border-t border-surface-container-highest">
                <p className="text-label-sm text-outline uppercase tracking-[0.02em] mb-1">{t('document.decision_reason_block_label')}</p>
                <p className="font-body text-body-md text-on-surface italic">{amendment.decision_reason}</p>
              </div>
            )}
          </div>

          {/* Moderation controls — owner/admin + pending only */}
          {canModerate && amendment.status === 'pending' && !showDecisionModal && (
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { setShowDecisionModal('accept'); setDecisionReason('') }}
                className="px-6 py-1.5 bg-tertiary-fixed text-on-tertiary-fixed rounded-md font-body text-body-md"
              >
                {t('document.accept')}
              </button>
              <button
                type="button"
                onClick={() => { setShowDecisionModal('reject'); setDecisionReason('') }}
                className="px-6 py-1.5 bg-error-container/40 text-on-error-container rounded-md font-body text-body-md"
              >
                {t('document.reject')}
              </button>
            </div>
          )}

          {/* Decision confirmation */}
          {canModerate && showDecisionModal && (
            <div className="space-y-3 pt-2 border-t border-surface-container-highest">
              <p className="font-body text-body-md text-on-surface font-medium">
                {showDecisionModal === 'accept' ? t('document.confirm_accept') : t('document.confirm_reject')}
              </p>
              <textarea
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                placeholder={t('document.decision_reason_placeholder')}
                rows={2}
                className="w-full bg-surface rounded-md px-3 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary resize-none"
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleDecisionConfirm}
                  disabled={deciding}
                  className={[
                    'px-5 py-1.5 rounded-md font-body text-body-md disabled:opacity-50',
                    showDecisionModal === 'accept'
                      ? 'bg-tertiary-fixed text-on-tertiary-fixed'
                      : 'bg-error-container/40 text-on-error-container',
                  ].join(' ')}
                >
                  {deciding ? '…' : (showDecisionModal === 'accept' ? t('document.accept') : t('document.reject'))}
                </button>
                <button
                  type="button"
                  onClick={() => setShowDecisionModal(null)}
                  disabled={deciding}
                  className="px-5 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md"
                >
                  {t('document.cancel')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section TOC helpers
// ---------------------------------------------------------------------------

/**
 * Extract <h2> and <h3> headings from an HTML string.
 *
/**
 * Sticky mini table-of-contents bar derived from <h2>/<h3> headings.
 *
 * Renders as a compact sticky bar at the top of the left pane. Each heading
 * becomes a button that smooth-scrolls the left pane to the target element.
 * h2 headings are rendered in normal weight; h3 headings are indented and muted.
 *
 * Props:
 *   headings — Array of { id, level, text } from extractHeadings().
 *   selectedSectionId — Currently selected section id.
 *   onSelectSection   — Called when a section is selected.
 *   t                 — Translation function from useTranslation.
 */
function SectionToc({ headings, selectedSectionId, onSelectSection, t }) {
  if (headings.length === 0) return null

  function scrollTo(id) {
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <nav
      aria-label={t('document.toc_label')}
      className="sticky top-0 z-10 bg-surface-container-low border-b border-surface-container px-8 py-2.5"
    >
      <div className="flex items-center gap-1 flex-wrap">
        <span className="font-body text-label-sm text-outline tracking-[0.02em] uppercase mr-2 shrink-0">
          {t('document.toc_label')}
        </span>
        {computeSectionNumbers(headings).map((h) => (
          <button
            key={h.id}
            type="button"
            onClick={() => {
              scrollTo(h.id)
              onSelectSection?.(h.id)
            }}
            title={h.text}
            className={[
              'font-body text-label-sm rounded px-2 py-0.5 hover:bg-surface-container transition-colors truncate max-w-[180px]',
              selectedSectionId === h.id ? 'bg-amendly-blue text-white hover:bg-secondary' : '',
              h.level === 'h2'
                ? (selectedSectionId === h.id ? 'font-medium' : 'text-on-surface font-medium')
                : (selectedSectionId === h.id ? 'pl-5' : 'text-outline pl-5'),
            ].join(' ')}
          >
            <span className="opacity-60 mr-1">{h.number}</span>{h.text}
          </button>
        ))}
      </div>
    </nav>
  )
}

// ---------------------------------------------------------------------------
// DocumentView page
// ---------------------------------------------------------------------------

/**
 * DocumentView page component.
 * Protected — ProtectedRoute ensures the user is authenticated before rendering.
 */
export default function DocumentView() {
  const { slug, id } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const currentUser = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)

  const [doc, setDoc] = useState(null)
  const [contributorToken, setContributorToken] = useState(null)  // current token or null
  const [userRole, setUserRole] = useState(null)   // 'owner' | 'admin' | 'member'
  const [orgPlan, setOrgPlan] = useState('solo')   // 'solo' | 'team' | 'organisation'
  const hasReactionPlan = orgPlan === 'organisation'
  const [amendments, setAmendments] = useState([])
  const [amendTotal, setAmendTotal] = useState(0)
  const [amendPage, setAmendPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [showEditForm, setShowEditForm] = useState(false)
  const [showConsolidated, setShowConsolidated] = useState(false)
  const [error, setError] = useState(null)
  const [filterStatus, setFilterStatus] = useState('all')   // 'all' | 'pending' | 'accepted' | 'rejected' | 'withdrawn'
  const [filterType, setFilterType] = useState('all')       // 'all' | 'text_change' | 'general_comment'
  const [filterSection, setFilterSection] = useState('all') // 'all' | '__unsectioned__' | section text
  const [sortOrder, setSortOrder] = useState('newest')      // 'newest' | 'oldest'
  const [expandedAmendmentIds, setExpandedAmendmentIds] = useState(() => new Set())  // bulk thread expansion
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState(new Set())    // bulk selection: Set of amendment IDs
  const [bulkActing, setBulkActing] = useState(false)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const [activeAmendmentId, setActiveAmendmentId] = useState(null)  // scroll-synced active card
  const [lockedAmendmentId, setLockedAmendmentId] = useState(null) // click-locked highlight
  const [selectedSectionId, setSelectedSectionId] = useState(null)
  const [composerType, setComposerType] = useState('text_change')
  const [composerOriginalText, setComposerOriginalText] = useState('')
  const [composerProposedText, setComposerProposedText] = useState('')
  const [composerJustification, setComposerJustification] = useState('')
  const [composerError, setComposerError] = useState(null)
  const [composerSubmitting, setComposerSubmitting] = useState(false)
  const [selectedSnippet, setSelectedSnippet] = useState('')

  // Left-pane document search
  const [docSearchOpen, setDocSearchOpen] = useState(false)
  const [docSearchQuery, setDocSearchQuery] = useState('')
  const [docSearchIdx, setDocSearchIdx] = useState(0)
  const [docSearchTotal, setDocSearchTotal] = useState(0)
  const docSearchInputRef = useRef(null)

  const leftPaneRef = useRef(null)
  const rightPaneRef = useRef(null)
  const docBodyRef = useRef(null)
  const sectionGroupRefs = useRef(new Map())
  const editFormRef = useRef(null)
  const activeSectionIdRef = useRef(null)  // last section synced to right pane via heading
  const activePinIdRef = useRef(null)      // last amendment synced to right pane via pin
  const scrollRafRef = useRef(null)        // rAF handle for throttled left-pane scroll
  const composerIsDirtyRef = useRef(false)     // true when composer has unsaved text
  const composerProposedRef = useRef(null)     // ref to the "proposed text" textarea

  const PAGE_SIZE = 20
  const amendTotalPages = Math.ceil(amendTotal / PAGE_SIZE)
  const canModerate = userRole === 'owner' || userRole === 'admin'
  const isOpen = doc?.status === 'open'
  const canPropose = Boolean(doc) && isOpen

  // -------------------------------------------------------------------------
  // Initial load: document + user role
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const requests = [
          orgClient.getDocument(slug, id),
          orgClient.listMyOrgs(),
        ]
        // Hydrate auth store if the user refreshed the page and the store is empty
        if (!currentUser) {
          requests.push(authClient.getMe())
        }
      const [docData, myOrgs, meData] = await Promise.all(requests)
        if (!cancelled) {
          setDoc(docData)
          setContributorToken(docData.contributor_token ?? null)
          const membership = myOrgs.find((o) => o.slug === slug)
          setUserRole(membership?.role ?? 'member')
          setOrgPlan(membership?.plan ?? 'solo')
          if (meData) setUser(meData)
        }
      } catch (err) {
        if (!cancelled) {
          if (err.message?.includes('404') || err.message?.toLowerCase().includes('not found')) {
            navigate(`/orgs/${slug}`, { replace: true })
          } else {
            setError(err.message)
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [slug, id, currentUser, navigate, setUser])

  // -------------------------------------------------------------------------
  // Load amendments (re-runs when page changes)
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (!doc) return

    let cancelled = false

    async function loadAmendments() {
      try {
        const data = await orgClient.listAmendments(slug, id, amendPage)
        if (!cancelled) {
          setAmendments(data.items)
          setAmendTotal(data.total)
          setSelectedIds(new Set())
        }
      } catch {
        // Non-fatal — document still shows without amendments
      }
    }

    loadAmendments()
    return () => { cancelled = true }
  }, [doc, slug, id, amendPage])

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  function handleDocSaved(updated) {
    setDoc(updated)
    setShowEditForm(false)
  }

  async function handleAmendmentStatus(amendmentId, newStatus, decisionReason) {
    try {
      const updated = await orgClient.updateAmendmentStatus(
        slug, id, amendmentId, newStatus, decisionReason
      )
      setAmendments((prev) => prev.map((a) => (a.id === amendmentId ? updated : a)))
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleWithdraw(amendmentId) {
    if (!window.confirm(t('document.withdraw_confirm'))) return
    try {
      await orgClient.withdrawAmendment(slug, id, amendmentId)
      setAmendments((prev) =>
        prev.map((a) => (a.id === amendmentId ? { ...a, status: 'withdrawn' } : a))
      )
    } catch (err) {
      setError(err.message)
    }
  }

  function handleDocStatusUpdated(updated) {
    setDoc(updated)
  }

  async function handleReact(amendmentId, type) {
    const updated = await orgClient.reactToAmendment(slug, id, amendmentId, type)
    setAmendments((prev) => prev.map((a) => (a.id === amendmentId ? { ...a, ...updated } : a)))
    return updated
  }

  function handleToggleSelect(amendmentId) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(amendmentId)) next.delete(amendmentId)
      else next.add(amendmentId)
      return next
    })
  }

  async function handleBulkAction(newStatus) {
    if (selectedIds.size === 0 || bulkActing) return
    setBulkActing(true)
    try {
      await orgClient.bulkUpdateAmendmentStatus(slug, id, [...selectedIds], newStatus)
      // Refresh the amendment list
      const data = await orgClient.listAmendments(slug, id, amendPage)
      setAmendments(data.items)
      setAmendTotal(data.total)
      setSelectedIds(new Set())
    } catch (err) {
      setError(err.message)
    } finally {
      setBulkActing(false)
    }
  }

  // Search debounce (300 ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Extract headings from the document body for the sticky TOC.
  // Declared BEFORE any callback that references it to avoid TDZ errors.
  const {
    headings,
    highlightedBody,
    numberedHeadings,
    processedBody,
    wordCount,
  } = useDocumentBodyState(doc?.body ?? null, docSearchQuery)

  // Mirror headings into a ref so the scroll callback reads the latest value
  // without needing it in its dependency array.
  const headingsRef = useRef(headings)
  useEffect(() => { headingsRef.current = headings }, [headings])

  // Keep composerIsDirtyRef in sync so the scroll handler can read it without deps.
  useEffect(() => {
    composerIsDirtyRef.current =
      composerOriginalText !== '' || composerProposedText !== '' || composerJustification !== ''
  }, [composerOriginalText, composerProposedText, composerJustification])

  // Reset scroll-sync cursors when the document itself changes.
  useEffect(() => {
    activeSectionIdRef.current = null
    activePinIdRef.current = null
  }, [doc?.id])

  // Left-pane scroll: back-to-top + right-pane sync.
  // Throttled to one rAF per frame so querySelectorAll never runs 60×/s.
  //
  // Sync strategy:
  //   1. Section-based composer pre-fill — always runs when document has headings.
  //   2. Pin-based right-pane scroll — when gutterPins are available (HTML body with
  //      amendements whose original_text matches document content): scrolls the right
  //      pane to keep the amendment nearest the visible focus zone at the top.
  //   3. Section-group right-pane scroll — fallback when no pins are available but
  //      section groups exist.
  const handleLeftPaneScroll = useCallback(() => {
    if (scrollRafRef.current) cancelAnimationFrame(scrollRafRef.current)
    scrollRafRef.current = requestAnimationFrame(() => {
      const el = leftPaneRef.current
      if (!el) return
      setShowBackToTop(el.scrollTop > 300)

      const currentHeadings = headingsRef.current
      const pins = gutterPinsRef.current

      // 1. Section-based composer pre-fill (runs regardless of pin availability)
      if (docBodyRef.current && currentHeadings.length > 0) {
        const section = findRenderedSectionByTop(docBodyRef.current, el.scrollTop, currentHeadings)
        if (section && section.id !== activeSectionIdRef.current) {
          activeSectionIdRef.current = section.id
          // Silently pre-select the active section in the composer — only when the
          // composer is empty so we don't disturb an in-progress draft.
          if (!composerIsDirtyRef.current) {
            setSelectedSectionId(section.id)
          }
          // Fallback right-pane scroll via section group (only when no pins).
          if (pins.length === 0) {
            const rightGroup = sectionGroupRefs.current.get(section.id)
            if (rightGroup && rightPaneRef.current) {
              // 'auto' avoids compounding smooth animations when scrolling quickly.
              rightPaneRef.current.scrollTo({ top: rightGroup.offsetTop - 24, behavior: 'auto' })
            }
          }
        }
      }

      // 2. Pin-based right-pane scroll sync
      if (pins.length > 0 && docBodyRef.current && rightPaneRef.current) {
        const bodyEl = docBodyRef.current
        const paneRect = el.getBoundingClientRect()
        const bodyRect = bodyEl.getBoundingClientRect()
        // Offset of the doc body within the scrollable left pane.
        const bodyOffsetInPane = bodyRect.top - paneRect.top + el.scrollTop
        // How far into the doc body the visible area starts.
        const docVisibleTop = el.scrollTop - bodyOffsetInPane
        // Focus zone: 30% from the top of the visible area — the "reading line".
        const focusY = docVisibleTop + el.clientHeight * 0.30

        const sorted = [...pins].sort((a, b) => a.top - b.top)
        // Find the last pin whose top is at or before the focus line.
        let activeAmendment = sorted[0]?.amendment
        for (const pin of sorted) {
          if (pin.top <= focusY) activeAmendment = pin.amendment
          else break
        }

        if (activeAmendment && activeAmendment.id !== activePinIdRef.current) {
          activePinIdRef.current = activeAmendment.id
          setActiveAmendmentId(activeAmendment.id)
          const cardEl = document.getElementById(`amendment-${activeAmendment.id}`)
          if (cardEl) {
            const rpRect = rightPaneRef.current.getBoundingClientRect()
            const cardRect = cardEl.getBoundingClientRect()
            const targetTop = rightPaneRef.current.scrollTop + cardRect.top - rpRect.top - 24
            // 'auto' avoids compounding smooth animations when scrolling quickly.
            rightPaneRef.current.scrollTo({ top: targetTop, behavior: 'auto' })
          }
        }
      }
    })
  }, [])

  function scrollLeftPaneToTop() {
    leftPaneRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleGutterPinClick = useCallback((amendment) => {
    setExpandedAmendmentIds((prev) => {
      const next = new Set(prev)
      next.add(amendment.id)
      return next
    })
    requestAnimationFrame(() => {
      const el = document.getElementById(`amendment-${amendment.id}`)
      if (el && rightPaneRef.current) {
        const paneRect = rightPaneRef.current.getBoundingClientRect()
        const elRect = el.getBoundingClientRect()
        const targetTop = rightPaneRef.current.scrollTop + elRect.top - paneRect.top - 24
        rightPaneRef.current.scrollTo({ top: targetTop, behavior: 'smooth' })
      }
    })
  }, [rightPaneRef])

  const selectedSection = useMemo(
    () => headings.find((heading) => heading.id === selectedSectionId) ?? null,
    [headings, selectedSectionId]
  )

  const selectedSectionNumbered = useMemo(
    () => numberedHeadings.find((h) => h.id === selectedSectionId) ?? null,
    [numberedHeadings, selectedSectionId]
  )

  const { groupedAmendments, visibleAmendments } = useVisibleAmendments({
    amendments,
    filterSection,
    filterStatus,
    filterType,
    debouncedSearch,
    sortOrder,
    headings,
    t,
  })

  // Gutter pins: { amendment, top } where top is the layout offset of original_text
  // within docBodyRef. Computed here (not in DocumentContentPane) so the scroll
  // handler can use them for right-pane sync.
  const gutterPins = useAmendmentGutter(visibleAmendments, docBodyRef)
  const gutterPinsRef = useRef([])
  useEffect(() => { gutterPinsRef.current = gutterPins }, [gutterPins])

  useEffect(() => {
    if (headings.length === 0) {
      setSelectedSectionId(null)
      return
    }
    setSelectedSectionId((current) => (
      headings.some((heading) => heading.id === current) ? current : headings[0].id
    ))
  }, [headings])

  // After body re-renders with highlights, count marks and scroll to current match.
  useEffect(() => {
    if (!docSearchOpen || !docSearchQuery.trim()) {
      setDocSearchTotal(0)
      return
    }
    // Allow React to finish rendering before querying the DOM
    const frame = requestAnimationFrame(() => {
      const marks = Array.from(leftPaneRef.current?.querySelectorAll('.doc-search-mark') ?? [])
      setDocSearchTotal(marks.length)
      if (marks.length === 0) return
      const idx = ((docSearchIdx % marks.length) + marks.length) % marks.length
      marks.forEach((m, i) => {
        m.style.background = i === idx ? '#f59e0b' : '#fef08a'
        m.style.outline = i === idx ? '2px solid #d97706' : 'none'
      })
      marks[idx]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
    return () => cancelAnimationFrame(frame)
  }, [docSearchOpen, docSearchQuery, docSearchIdx, highlightedBody])

  // Scroll to edit form when it opens
  useEffect(() => {
    if (showEditForm && editFormRef.current) {
      const timer = setTimeout(() => editFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
      return () => clearTimeout(timer)
    }
  }, [showEditForm])

  // Open search: focus the input
  useEffect(() => {
    if (docSearchOpen) {
      // Small delay to allow the bar to mount
      const timer = setTimeout(() => docSearchInputRef.current?.focus(), 50)
      return () => clearTimeout(timer)
    } else {
      // Clear on close
      setDocSearchQuery('')
      setDocSearchIdx(0)
      setDocSearchTotal(0)
    }
  }, [docSearchOpen])

  /** Move to the next/previous match. */
  function moveDocSearch(delta) {
    setDocSearchIdx((i) => i + delta)
  }

  function focusSectionGroup(sectionId) {
    const target = sectionGroupRefs.current.get(sectionId)
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function handleSelectSection(sectionId, options = {}) {
    const section = headings.find((heading) => heading.id === sectionId)
    if (!section) return
    setSelectedSectionId(section.id)
    setComposerError(null)
    if (options.scrollGroup !== false) {
      requestAnimationFrame(() => focusSectionGroup(section.id))
    }
  }

  function clearSelectedSnippet() {
    setSelectedSnippet('')
    window.getSelection()?.removeAllRanges()
  }

  function handleDocumentClick(e) {
    const heading = e.target.closest?.('[data-section-id]')
    if (!heading) return
    handleSelectSection(heading.dataset.sectionId)
  }

  function handleDocumentSelection() {
    if (composerType !== 'text_change') return
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return
    const range = selection.getRangeAt(0)
    if (!docBodyRef.current?.contains(range.commonAncestorContainer)) return

    const text = selection.toString().trim()
    if (!text) return

    const containerRect = docBodyRef.current.getBoundingClientRect()
    const rangeRect = range.getBoundingClientRect()
    const top = rangeRect.top - containerRect.top + docBodyRef.current.scrollTop
    const section = findRenderedSectionByTop(docBodyRef.current, top, headings)
    if (section) handleSelectSection(section.id)

    setSelectedSnippet(text)
    setComposerOriginalText(text)
    setComposerError(null)
    // Bring the composer form into view and focus the "proposed text" field.
    rightPaneRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    requestAnimationFrame(() => composerProposedRef.current?.focus())
  }

  async function handleComposerSubmit(e) {
    e.preventDefault()
    setComposerError(null)

    if (!selectedSection && headings.length > 0) {
      setComposerError(t('document.compose_select_prompt'))
      return
    }

    if (composerType === 'text_change') {
      if (!composerOriginalText.trim()) {
        setComposerError(t('document.original_required'))
        return
      }
      if (!composerProposedText.trim()) {
        setComposerError(t('document.proposed_required'))
        return
      }
    } else if (!composerJustification.trim()) {
      setComposerError(t('document.comment_required'))
      return
    }

    setComposerSubmitting(true)
    try {
      const payload = {
        amendment_type: composerType,
        section: selectedSection?.text ?? null,
      }
      if (composerType === 'text_change') {
        payload.original_text = composerOriginalText.trim()
        payload.proposed_text = composerProposedText.trim()
        payload.justification = composerJustification.trim() || null
      } else {
        payload.justification = composerJustification.trim()
      }

      const amendment = await orgClient.createAmendment(slug, id, payload)
      const data = await orgClient.listAmendments(slug, id, amendPage)
      setAmendments(data.items)
      setAmendTotal(data.total)
      setExpandedAmendmentIds((prev) => new Set(prev).add(amendment.id))
      setComposerOriginalText('')
      setComposerProposedText('')
      setComposerJustification('')
      setSelectedSnippet('')
      requestAnimationFrame(() => {
        if (selectedSection?.id) focusSectionGroup(selectedSection.id)
      })
    } catch (err) {
      setComposerError(err.message)
    } finally {
      setComposerSubmitting(false)
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

  if (error) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <p className="font-body text-body-md text-on-error-container">{error}</p>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-surface overflow-hidden">
      {/* ------------------------------------------------------------------ */}
      {/* Top navigation bar                                                  */}
      {/* ------------------------------------------------------------------ */}
      <header className="shrink-0 bg-surface-container-low px-8 py-4 flex items-center gap-4">
        <button
          type="button"
          onClick={() => navigate(`/orgs/${slug}`)}
          className="font-body text-body-md text-secondary hover:underline"
        >
          ← {slug}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em] truncate">
          {doc?.title}
        </span>

        {/* Notification center — right-aligned */}
        <div className="ml-auto">
          <NotificationBell orgSlug={slug} />
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Split pane                                                           */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-1 overflow-hidden">
        <DocumentContentPane
          slug={slug}
          docId={id}
          doc={doc}
          canModerate={canModerate}
          isOpen={isOpen}
          orgPlan={orgPlan}
          amendTotal={amendTotal}
          contributorToken={contributorToken}
          headings={headings}
          selectedSectionId={selectedSectionId}
          showEditForm={showEditForm}
          showConsolidated={showConsolidated}
          showBackToTop={showBackToTop}
          docSearchOpen={docSearchOpen}
          docSearchQuery={docSearchQuery}
          docSearchIdx={docSearchIdx}
          docSearchTotal={docSearchTotal}
          wordCount={wordCount}
          highlightedBody={highlightedBody}
          processedBody={processedBody}
          leftPaneRef={leftPaneRef}
          docBodyRef={docBodyRef}
          editFormRef={editFormRef}
          docSearchInputRef={docSearchInputRef}
          gutterPins={gutterPins}
          visibleAmendments={visibleAmendments}
          onGutterPinClick={handleGutterPinClick}
          SectionToc={SectionToc}
          StatusToggle={StatusToggle}
          DocStatusBadge={DocStatusBadge}
          ExportMenu={ExportMenu}
          ShareContributionLink={ShareContributionLink}
          EditDocumentForm={EditDocumentForm}
          ConsolidatedPanel={ConsolidatedPanel}
          handleLeftPaneScroll={handleLeftPaneScroll}
          handleDocStatusUpdated={handleDocStatusUpdated}
          handleDocumentClick={handleDocumentClick}
          handleDocumentSelection={handleDocumentSelection}
          handleDocSaved={handleDocSaved}
          handleSelectSection={handleSelectSection}
          moveDocSearch={moveDocSearch}
          scrollLeftPaneToTop={scrollLeftPaneToTop}
          setDocSearchOpen={setDocSearchOpen}
          setDocSearchQuery={setDocSearchQuery}
          setDocSearchIdx={setDocSearchIdx}
          setShowEditForm={setShowEditForm}
          setShowConsolidated={setShowConsolidated}
          setContributorToken={setContributorToken}
          setDoc={setDoc}
          t={t}
        />

        <DocumentAmendmentsPane
          slug={slug}
          docId={id}
          doc={doc}
          headings={headings}
          numberedHeadings={numberedHeadings}
          selectedSection={selectedSection}
          selectedSectionId={selectedSectionId}
          selectedSnippet={selectedSnippet}
          amendments={amendments}
          visibleAmendments={visibleAmendments}
          groupedAmendments={groupedAmendments}
          expandedAmendmentIds={expandedAmendmentIds}
          selectedIds={selectedIds}
          amendTotal={amendTotal}
          amendPage={amendPage}
          amendTotalPages={amendTotalPages}
          filterStatus={filterStatus}
          filterType={filterType}
          filterSection={filterSection}
          sortOrder={sortOrder}
          searchQuery={searchQuery}
          composerType={composerType}
          composerOriginalText={composerOriginalText}
          composerProposedText={composerProposedText}
          composerJustification={composerJustification}
          composerError={composerError}
          composerSubmitting={composerSubmitting}
          canModerate={canModerate}
          canPropose={canPropose}
          hasReactionPlan={hasReactionPlan}
          bulkActing={bulkActing}
          orgPlan={orgPlan}
          rightPaneRef={rightPaneRef}
          leftPaneRef={leftPaneRef}
          docBodyRef={docBodyRef}
          sectionGroupRefs={sectionGroupRefs}
          composerProposedRef={composerProposedRef}
          ReactionSummary={ReactionSummary}
          AmendmentCard={AmendmentCard}
          activeAmendmentId={activeAmendmentId}
          lockedAmendmentId={lockedAmendmentId}
          setLockedAmendmentId={setLockedAmendmentId}
          currentUserId={currentUser?.id}
          clearSelectedSnippet={clearSelectedSnippet}
          handleSelectSection={handleSelectSection}
          handleComposerSubmit={handleComposerSubmit}
          handleToggleSelect={handleToggleSelect}
          handleAmendmentStatus={handleAmendmentStatus}
          handleWithdraw={handleWithdraw}
          handleReact={handleReact}
          handleBulkAction={handleBulkAction}
          setShowConsolidated={setShowConsolidated}
          setSelectedSectionId={setSelectedSectionId}
          setComposerType={setComposerType}
          setComposerOriginalText={setComposerOriginalText}
          setComposerProposedText={setComposerProposedText}
          setComposerJustification={setComposerJustification}
          setFilterStatus={setFilterStatus}
          setFilterType={setFilterType}
          setFilterSection={setFilterSection}
          setSearchQuery={setSearchQuery}
          setExpandedAmendmentIds={setExpandedAmendmentIds}
          setSelectedIds={setSelectedIds}
          setAmendPage={setAmendPage}
          t={t}
        />

      </div>

    </div>
  )
}
