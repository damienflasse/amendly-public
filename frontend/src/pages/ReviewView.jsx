/**
 * ReviewView — full-document review page shown before export.
 *
 * Route: /orgs/:slug/documents/:id/review
 *
 * On mount it fetches:
 *   GET /api/organisations/{slug}/documents/{id}/review
 *
 * Features:
 *   - Stats bar: counts of accepted / pending / rejected / withdrawn amendments.
 *   - Full-document inline diff (original → consolidated) rendered with word-level
 *     tokens: additions in secondary-container bg + on-secondary-fixed bold text,
 *     deletions in outline colour with line-through, equal text as-is.
 *   - Accordion list of all accepted amendments, each with its own per-amendment
 *     diff, author, date, section, and justification.
 *   - Export panel (owner/admin only): DOCX / PDF / TXT download buttons.
 *   - Back link navigates to /orgs/:slug/documents/:id.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Surface base, cards on surface-container-lowest.
 *   - font-display for headings, font-body for UI text.
 *   - No 1px borders; structure through tonal background shifts.
 *   - Diff tokens follow DESIGN.md section 5 (The Word-Level Diff System).
 *
 * Props: none (reads :slug and :id from React Router params)
 * Side effects:
 *   - Uses cookie-backed authenticated API calls.
 *   - Calls orgClient.exportDocument() to trigger browser downloads.
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { orgClient } from '../lib/organisations'
import { useTranslation } from '../hooks/useTranslation'
import useAuthStore from '../store/authStore'
import NotificationBell from '../components/NotificationBell'
import { sanitizeHtml } from '../lib/sanitize'

// ---------------------------------------------------------------------------
// Diff token renderer
// ---------------------------------------------------------------------------

/**
 * Renders a list of word-level diff tokens as inline spans.
 *
 * Tokens of type 'insert' use the secondary-container / on-secondary-fixed
 * palette from DESIGN.md section 5. Tokens of type 'delete' use the outline
 * colour with line-through. Equal tokens are rendered as plain text.
 *
 * @param {{ tokens: Array<{ text: string; type: 'equal' | 'insert' | 'delete' }> }} props
 */
function DiffTokens({ tokens }) {
  if (!tokens || tokens.length === 0) return null

  return (
    <span className="font-body text-body-md leading-relaxed">
      {tokens.map((token, i) => {
        if (token.type === 'insert') {
          return (
            <span
              key={i}
              className="bg-secondary-container text-on-secondary-fixed font-bold rounded-sm px-0.5 mx-0.5"
            >
              {token.text}
            </span>
          )
        }
        if (token.type === 'delete') {
          return (
            <span
              key={i}
              className="text-outline line-through mx-0.5"
            >
              {token.text}
            </span>
          )
        }
        // equal
        return (
          <span key={i} className="mx-0.5">
            {token.text}
          </span>
        )
      })}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Stats bar
// ---------------------------------------------------------------------------

/**
 * Horizontal bar showing amendment counts grouped by status.
 *
 * @param {{ accepted: number; pending: number; rejected: number; withdrawn: number; t: Function }} props
 */
function StatsBar({ accepted, pending, rejected, withdrawn, t }) {
  const stats = [
    {
      label: t('document.review_stats_accepted').replace('{n}', accepted),
      cls: 'bg-tertiary-fixed text-on-tertiary-fixed',
    },
    {
      label: t('document.review_stats_pending').replace('{n}', pending),
      cls: 'bg-primary-fixed text-on-primary-fixed',
    },
    {
      label: t('document.review_stats_rejected').replace('{n}', rejected),
      cls: 'bg-error-container/40 text-on-error-container',
    },
    {
      label: t('document.review_stats_withdrawn').replace('{n}', withdrawn),
      cls: 'bg-surface-container-highest text-on-surface',
    },
  ]

  return (
    <div className="flex flex-wrap gap-2">
      {stats.map(({ label, cls }) => (
        <span
          key={label}
          className={`inline-flex items-center px-3 py-1 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${cls}`}
        >
          {label}
        </span>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Accepted amendment card
// ---------------------------------------------------------------------------

/**
 * Collapsible card for one accepted amendment in the review list.
 *
 * Shows section label, author, date, a per-amendment diff (for text_change)
 * or a general comment badge, and a "copy link" button that copies a direct
 * anchor URL to the amendment on the DocumentView page.
 *
 * @param {{
 *   amendment: {
 *     id: string;
 *     section: string | null;
 *     original_text: string | null;
 *     proposed_text: string | null;
 *     justification: string | null;
 *     author_name: string;
 *     created_at: string;
 *     diff_tokens: Array<{ text: string; type: string }>;
 *   };
 *   index: number;
 *   slug: string;
 *   docId: string;
 *   t: Function;
 * }} props
 */
function AcceptedAmendmentCard({ amendment, index, slug, docId, t }) {
  const [open, setOpen] = useState(true)
  const [copied, setCopied] = useState(false)

  const isTextChange = amendment.diff_tokens && amendment.diff_tokens.length > 0
  const dateStr = new Date(amendment.created_at).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

  function handleCopyLink(e) {
    e.stopPropagation()
    const url = `${window.location.origin}/orgs/${slug}/documents/${docId}#amendment-${amendment.id}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="bg-surface-container-lowest rounded-lg overflow-hidden shadow-ambient">
      {/* Card header — always visible */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start justify-between gap-4 px-6 py-4 text-left hover:bg-surface-container transition-colors"
      >
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-body text-label-sm text-outline uppercase tracking-[0.04em]">
              #{index + 1}
            </span>
            {amendment.section && (
              <span className="font-body text-label-sm bg-surface-container px-2 py-0.5 rounded text-on-surface">
                {amendment.section}
              </span>
            )}
            {!isTextChange && (
              <span className="font-body text-label-sm bg-secondary-container text-on-secondary-fixed px-2 py-0.5 rounded uppercase tracking-[0.04em]">
                {t('document.review_general_comment')}
              </span>
            )}
          </div>
          <p className="font-body text-label-sm text-outline">
            {t('document.review_by').replace('{name}', amendment.author_name)}
            {' · '}
            {dateStr}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 mt-1">
          <button
            type="button"
            onClick={handleCopyLink}
            title={t('document.review_copy_link')}
            className="font-body text-label-sm text-outline hover:text-secondary px-2 py-0.5 rounded hover:bg-surface-container transition-colors"
          >
            {copied ? t('document.review_link_copied') : '🔗'}
          </button>
          <span className="text-outline text-sm">
            {open ? '▲' : '▼'}
          </span>
        </div>
      </button>

      {/* Card body — collapsible */}
      {open && (
        <div className="px-6 pb-5 flex flex-col gap-4">
          {isTextChange ? (
            <div className="bg-surface rounded-md px-4 py-3 leading-loose">
              <DiffTokens tokens={amendment.diff_tokens} />
            </div>
          ) : (
            <p className="font-body text-body-md text-on-surface leading-relaxed">
              {amendment.justification}
            </p>
          )}

          {isTextChange && amendment.justification && (
            <div>
              <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em] mb-1">
                {t('document.justification_block_label')}
              </p>
              <p className="font-body text-body-md text-on-surface leading-relaxed">
                {amendment.justification}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Export panel
// ---------------------------------------------------------------------------

/**
 * Export action panel shown at the bottom of the review page.
 *
 * Renders a short hint, three individual download buttons (DOCX / PDF / TXT),
 * and a "Download all as ZIP" button that bundles all three formats in one archive.
 * Only rendered when the caller is an owner or admin.
 *
 * @param {{ slug: string; docId: string; t: Function }} props
 */
function ExportPanel({ slug, docId, t }) {
  const [exporting, setExporting] = useState(null)
  const [error, setError] = useState(null)
  const [includeAmendments, setIncludeAmendments] = useState('none')

  async function handleExport(format) {
    setError(null)
    setExporting(format)
    try {
      await orgClient.exportDocument(slug, docId, format, includeAmendments)
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(null)
    }
  }

  async function handleExportZip() {
    setError(null)
    setExporting('zip')
    try {
      await orgClient.exportDocumentZip(slug, docId, includeAmendments)
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="bg-surface-container-lowest rounded-lg px-6 py-5 shadow-ambient flex flex-col gap-3">
      <div>
        <h2 className="font-display text-headline-sm text-amendly-dark">
          {t('document.review_export_heading')}
        </h2>
        <p className="font-body text-body-md text-outline mt-1">
          {t('document.review_export_hint')}
        </p>
      </div>

      {/* Amendment inclusion selector */}
      <div>
        <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em] mb-2">
          {t('document.export_include_amendments')}
        </p>
        <div className="flex flex-wrap gap-4">
          {['none', 'accepted', 'all'].map((opt) => (
            <label key={opt} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="review-export-amendments"
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
      </div>

      <div className="flex flex-wrap gap-3">
        {['docx', 'pdf', 'txt'].map((fmt) => (
          <button
            key={fmt}
            type="button"
            disabled={!!exporting}
            onClick={() => handleExport(fmt)}
            className="px-5 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md hover:opacity-90 transition-opacity disabled:opacity-50 uppercase tracking-[0.04em]"
          >
            {exporting === fmt ? t('document.exporting') : fmt}
          </button>
        ))}

        <button
          type="button"
          disabled={!!exporting}
          onClick={handleExportZip}
          className="px-5 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors disabled:opacity-50 uppercase tracking-[0.04em]"
        >
          {exporting === 'zip' ? t('document.exporting') : t('document.review_export_zip')}
        </button>
      </div>

      {error && (
        <p className="font-body text-label-sm text-on-error-container bg-error-container/40 rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

/**
 * ReviewView — full review page for a document before export.
 *
 * Fetches GET .../review and renders:
 *   1. Stats bar (amendment counts by status).
 *   2. Full-document diff (original → consolidated) with toggle between:
 *      - Inline mode: word-level DiffTokens (default when body is plain text)
 *      - Side-by-side mode: two panes rendering original and consolidated HTML
 *   3. Accepted amendments list (collapsible cards with per-amendment diffs
 *      and copy-link buttons).
 *   4. Export panel (owner/admin only) — individual formats + ZIP bundle.
 *
 * Props: none (reads :slug and :id from React Router params)
 */
export default function ReviewView() {
  const { slug, id } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)

  const [review, setReview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [role, setRole] = useState(null)
  const [diffMode, setDiffMode] = useState('inline') // 'preview' | 'inline'
  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        // Fetch role and review data in parallel
        const [orgs, data] = await Promise.all([
          orgClient.listMyOrgs(),
          orgClient.getDocumentReview(slug, id),
        ])

        if (cancelled) return

        const membership = orgs.find((o) => o.slug === slug)
        setRole(membership?.role ?? 'member')
        setReview(data)
      } catch (err) {
        if (!cancelled) {
          if (err.message?.includes('404') || err.message?.includes('not found')) {
            navigate(`/orgs/${slug}`)
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
  }, [slug, id, navigate])

  const isWriteRole = role === 'owner' || role === 'admin'
  const hasRichPreview =
    [review?.original_body, review?.consolidated_body].some(
      (body) => typeof body === 'string' && body.trimStart().startsWith('<')
    )

  useEffect(() => {
    setDiffMode(hasRichPreview ? 'preview' : 'inline')
  }, [hasRichPreview, id])

  // -------------------------------------------------------------------------
  // Render states
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <p className="font-body text-body-md text-outline">{t('document.review_loading')}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center gap-4">
        <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
          {error}
        </p>
        <Link
          to={`/orgs/${slug}/documents/${id}`}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {t('document.review_back')}
        </Link>
      </div>
    )
  }

  if (!review) return null

  const hasChanges = review.full_diff_tokens.some(
    (tok) => tok.type === 'insert' || tok.type === 'delete'
  )

  // -------------------------------------------------------------------------
  // Main render
  // -------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-surface">
      {/* Top navigation bar */}
      <nav className="bg-surface-container-lowest px-8 py-3 flex items-center justify-between gap-4">
        <Link
          to={`/orgs/${slug}/documents/${id}`}
          className="font-body text-body-md text-secondary hover:underline flex-shrink-0"
        >
          {t('document.review_back')}
        </Link>

        <h1 className="font-display text-headline-sm text-amendly-dark truncate">
          {review.title}
        </h1>

        <div className="flex items-center gap-3 flex-shrink-0">
          {user && <NotificationBell />}
        </div>
      </nav>

      {/* Page content */}
      <main className="max-w-4xl mx-auto px-8 py-12 flex flex-col gap-12">

        {/* Page title + stats */}
        <div className="flex flex-col gap-4">
          <h2 className="font-display text-headline-sm text-amendly-dark">
            {t('document.review_title')}
          </h2>
          <StatsBar
            accepted={review.count_accepted}
            pending={review.count_pending}
            rejected={review.count_rejected}
            withdrawn={review.count_withdrawn}
            t={t}
          />
        </div>

        {/* Full-document diff */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <h2 className="font-body text-title-sm text-on-surface uppercase tracking-[0.06em]">
              {t('document.review_diff_heading')}
            </h2>
            {hasChanges && (
              <div className="flex items-center bg-surface-container rounded-md p-0.5">
                {hasRichPreview && (
                  <button
                    type="button"
                    onClick={() => setDiffMode('preview')}
                    className={`px-3 py-1 rounded font-body text-label-sm transition-colors ${
                      diffMode === 'preview'
                        ? 'bg-surface-container-lowest text-on-surface shadow-ambient'
                        : 'text-outline hover:text-on-surface'
                    }`}
                  >
                    {t('document.review_preview')}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setDiffMode('inline')}
                  className={`px-3 py-1 rounded font-body text-label-sm transition-colors ${
                    diffMode === 'inline'
                      ? 'bg-surface-container-lowest text-on-surface shadow-ambient'
                      : 'text-outline hover:text-on-surface'
                  }`}
                >
                  {t('document.review_diff_inline')}
                </button>
              </div>
            )}
          </div>

          {!hasChanges ? (
            <div className="bg-surface-container-lowest rounded-lg px-6 py-5 shadow-ambient">
              <p className="font-body text-body-md text-outline">
                {t('document.review_no_changes')}
              </p>
            </div>
          ) : diffMode === 'preview' && hasRichPreview ? (
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em]">
                  {t('document.review_diff_original')}
                </p>
                <div
                  className="bg-surface-container-lowest rounded-lg px-6 py-5 shadow-ambient"
                >
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
                      [&_hr]:my-6 [&_hr]:h-px [&_hr]:border-0 [&_hr]:bg-surface-container-highest
                      [&_strong]:font-semibold [&_em]:italic"
                    dangerouslySetInnerHTML={{
                      __html: sanitizeHtml(review.original_body),
                    }}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em]">
                  {t('document.review_diff_consolidated')}
                </p>
                <div
                  className="bg-surface-container-lowest rounded-lg px-6 py-5 shadow-ambient"
                >
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
                      [&_hr]:my-6 [&_hr]:h-px [&_hr]:border-0 [&_hr]:bg-surface-container-highest
                      [&_strong]:font-semibold [&_em]:italic"
                    dangerouslySetInnerHTML={{
                      __html: sanitizeHtml(review.consolidated_body),
                    }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-surface-container-lowest rounded-lg px-6 py-5 shadow-ambient">
              <p className="font-body text-label-sm text-outline uppercase tracking-[0.04em] mb-3">
                {t('document.review_diff_text_label')}
              </p>
              <div className="leading-loose">
                <DiffTokens tokens={review.full_diff_tokens} />
              </div>
            </div>
          )}
        </section>

        {/* Accepted amendments list */}
        <section className="flex flex-col gap-4">
          <h2 className="font-body text-title-sm text-on-surface uppercase tracking-[0.06em]">
            {t('document.review_amendments_heading')}
            {review.count_accepted > 0 && (
              <span className="ml-2 font-body text-label-sm text-outline normal-case tracking-normal">
                ({review.count_accepted})
              </span>
            )}
          </h2>

          {review.accepted_amendments.length === 0 ? (
            <p className="font-body text-body-md text-outline">
              {t('document.review_no_accepted')}
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {review.accepted_amendments.map((amendment, i) => (
                <AcceptedAmendmentCard
                  key={amendment.id}
                  amendment={amendment}
                  index={i}
                  slug={slug}
                  docId={id}
                  t={t}
                />
              ))}
            </div>
          )}
        </section>

        {/* Export panel — owner/admin only */}
        {isWriteRole && (
          <section>
            <ExportPanel slug={slug} docId={id} t={t} />
          </section>
        )}
      </main>
    </div>
  )
}
