/**
 * ContributorSubmission — 3-pane amendment proposal interface.
 *
 * Route: /orgs/:slug/documents/:id/contribute
 *
 * Pane 1 (Left): Document viewer with text selection and floating formatting toolbar.
 * Pane 2 (Center): Amendment proposal form — type toggle, section, original/proposed
 *   text, live diff preview (unified or split), justification.
 * Pane 3 (Right): Discussions — user's past amendments list; click one to view its
 *   comment thread and post new comments.
 *
 * On mount it fetches:
 *   1. GET /api/organisations/{slug}/documents/{id} — the target document.
 *   2. GET /api/organisations/{slug}/documents/{id}/amendments/mine — user's own amendments.
 *
 * Behaviour:
 *   - Collects section (optional), original_text (required), proposed_text (required),
 *     justification (optional) — matching the backend AmendmentCreate schema.
 *   - Character counters on proposed_text (max 5000) and justification (max 1000).
 *   - Live diff preview: unified (inline word-diff) or split (side-by-side) modes.
 *   - On submit calls POST /api/organisations/{slug}/documents/{id}/amendments.
 *   - Confirmation screen after successful submission; "Submit another" resets the form.
 *   - Right pane: shows the user's submissions; selecting one loads its comment thread.
 *   - If the document status is 'closed', shows a notice and disables the form.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - 3-pane layout: doc viewer / proposal form / discussions.
 *   - Tonal layering — surface base, cards on surface-container-lowest.
 *   - Manrope for headings, Inter for body/UI text.
 *   - No 1px borders; structure through background shifts and ambient shadows.
 *   - Diff tokens: additions = #dbe1ff bg + #003798 bold / deletions = strikethrough #717c82.
 *
 * Props: none (reads :slug and :id from React Router params)
 * Side effects:
 *   - Uses cookie-backed authenticated API calls.
 *   - Navigates to /orgs/:slug/documents/:id on success.
 *   - Navigates to /orgs/:slug on 404 (document not found or not a member).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { orgClient } from '../lib/organisations'
import { useTranslation } from '../hooks/useTranslation'
import { sanitizeHtml } from '../lib/sanitize'

// ---------------------------------------------------------------------------
// Client-side word diff
// ---------------------------------------------------------------------------

/**
 * Compute a simple word-level diff between two strings.
 *
 * Uses the longest common subsequence (LCS) algorithm on word tokens.
 * Returns an array of tokens with type 'equal', 'insert', or 'delete'.
 *
 * Parameters:
 *   original  — the baseline text
 *   proposed  — the proposed replacement text
 *
 * Returns:
 *   Array<{ text: string; type: 'equal' | 'insert' | 'delete' }>
 */
function computeClientDiff(original, proposed) {
  const tokenise = (s) => s.match(/\S+|\s+/g) ?? []
  const origTokens = tokenise(original)
  const propTokens = tokenise(proposed)
  const m = origTokens.length
  const n = propTokens.length

  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (origTokens[i - 1] === propTokens[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }

  const result = []
  let i = m
  let j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origTokens[i - 1] === propTokens[j - 1]) {
      result.push({ text: origTokens[i - 1], type: 'equal' })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ text: propTokens[j - 1], type: 'insert' })
      j--
    } else {
      result.push({ text: origTokens[i - 1], type: 'delete' })
      i--
    }
  }
  result.reverse()
  return result
}

// ---------------------------------------------------------------------------
// Document search helpers
// ---------------------------------------------------------------------------

/**
 * Escape special characters for use in a RegExp pattern.
 *
 * Parameters:
 *   s — string to escape
 * Returns:
 *   string with regex special chars escaped
 */
function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Inject <mark> tags around all text matches of `query` in a sanitized HTML string.
 *
 * Parameters:
 *   html  — sanitized HTML string
 *   query — search term (case-insensitive)
 * Returns:
 *   HTML string with <mark class="doc-search-mark"> wrappers on matches.
 */
function highlightHtml(html, query) {
  if (!query || !query.trim()) return html
  const re = new RegExp(`(${escapeRegex(query.trim())})(?![^<]*>)`, 'gi')
  return html.replace(
    re,
    '<mark class="doc-search-mark" style="background:#fef08a;color:#713f12;border-radius:2px;padding:0 1px">$1</mark>'
  )
}

// ---------------------------------------------------------------------------
// DiffPreview — unified inline word-diff
// ---------------------------------------------------------------------------

/**
 * Renders a word-level diff between original and proposed text (unified/inline mode).
 *
 * Props:
 *   original — string: the baseline text
 *   proposed — string: the proposed replacement text
 *   t        — translation function from useTranslation
 */
function DiffPreview({ original, proposed, t }) {
  if (!original.trim() || !proposed.trim()) {
    return (
      <p className="text-sm text-outline font-body italic">
        {t('contributor.diff_placeholder')}
      </p>
    )
  }
  const tokens = computeClientDiff(original, proposed)
  return (
    <p className="text-on-surface leading-loose text-base font-body">
      {tokens.map((tok, idx) => {
        if (tok.type === 'insert') {
          return (
            <span key={idx} className="px-0.5 rounded-sm bg-secondary-container text-on-secondary-fixed font-bold">
              {tok.text}
            </span>
          )
        }
        if (tok.type === 'delete') {
          return (
            <span key={idx} className="px-0.5 text-outline line-through">
              {tok.text}
            </span>
          )
        }
        return <span key={idx}>{tok.text}</span>
      })}
    </p>
  )
}

// ---------------------------------------------------------------------------
// SplitDiffPreview — side-by-side view
// ---------------------------------------------------------------------------

/**
 * Renders a side-by-side (split) diff between original and proposed text.
 *
 * Props:
 *   original — string: the baseline text
 *   proposed — string: the proposed replacement text
 *   t        — translation function from useTranslation
 */
function SplitDiffPreview({ original, proposed, t }) {
  if (!original.trim() || !proposed.trim()) {
    return (
      <p className="text-sm text-outline font-body italic">
        {t('contributor.diff_placeholder')}
      </p>
    )
  }
  const tokens = computeClientDiff(original, proposed)
  const origParts = tokens.filter((tk) => tk.type !== 'insert')
  const propParts = tokens.filter((tk) => tk.type !== 'delete')

  const renderSide = (parts, highlightType, highlightClass) =>
    parts.map((tok, idx) =>
      tok.type === highlightType ? (
        <span key={idx} className={highlightClass}>{tok.text}</span>
      ) : (
        <span key={idx}>{tok.text}</span>
      )
    )

  return (
    <div className="grid grid-cols-2 gap-2 text-sm font-body leading-relaxed">
      <div className="bg-surface rounded-lg p-3">
        <p className="text-[10px] font-bold tracking-widest text-outline uppercase mb-2">{t('document.original_text_label')}</p>
        <p className="text-on-surface">
          {renderSide(origParts, 'delete', 'px-0.5 text-outline line-through')}
        </p>
      </div>
      <div className="bg-surface rounded-lg p-3">
        <p className="text-[10px] font-bold tracking-widest text-outline uppercase mb-2">{t('document.proposed_text_label')}</p>
        <p className="text-on-surface">
          {renderSide(propParts, 'insert', 'px-0.5 rounded-sm bg-secondary-container text-on-secondary-fixed font-bold')}
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status badge helper
// ---------------------------------------------------------------------------

const STATUS_STYLES = {
  pending:   'bg-surface-container-highest text-on-surface-variant',
  accepted:  'bg-secondary-container text-on-secondary-fixed',
  rejected:  'bg-error-container text-on-error-container',
  withdrawn: 'bg-surface-container-highest text-outline',
}

// ---------------------------------------------------------------------------
// MyAmendmentCard (compact — for the right-pane list)
// ---------------------------------------------------------------------------

/**
 * Compact card summarising one of the user's submitted amendments (right pane).
 *
 * Props:
 *   amendment        — AmendmentResponse object from the API
 *   t                — translation function
 *   isSelected       — boolean — highlighted when its comment thread is open
 *   onSelect         — () => void — called when the card is clicked
 *   onWithdraw       — (id: string) => void — withdraw handler
 *   isWithdrawing    — boolean — disables the withdraw button while in-flight
 */
function MyAmendmentCard({ amendment, t, isSelected, onSelect, onWithdraw, isWithdrawing }) {
  const badgeClass = STATUS_STYLES[amendment.status] ?? STATUS_STYLES.pending
  const isComment = amendment.amendment_type === 'general_comment'
  const isPending = amendment.status === 'pending'
  const snippet = isComment
    ? (amendment.justification ?? '').slice(0, 70)
    : (amendment.proposed_text ?? '').slice(0, 70)

  return (
    <li
      className={[
        'rounded-xl p-3 space-y-2 cursor-pointer transition-all',
        isSelected
          ? 'bg-secondary-container shadow-ambient'
          : 'bg-surface-container-lowest hover:bg-surface-container',
      ].join(' ')}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-body text-outline uppercase tracking-wider truncate">
          {isComment ? t('document.type_general_comment') : t('document.type_text_change')}
          {amendment.section && <span className="ml-1 normal-case">· {amendment.section}</span>}
        </span>
        <span className={`text-[10px] font-body font-medium px-2 py-0.5 rounded-full shrink-0 ${badgeClass}`}>
          {t(`document.filter_${amendment.status}`)}
        </span>
      </div>
      <p className="text-xs text-on-surface font-body line-clamp-2 leading-relaxed">
        {snippet}{snippet.length < (isComment ? (amendment.justification ?? '').length : (amendment.proposed_text ?? '').length) ? '…' : ''}
      </p>
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-outline font-body">
          {new Date(amendment.created_at).toLocaleDateString()}
        </p>
        {isPending && onWithdraw && (
          <button
            type="button"
            disabled={isWithdrawing}
            onClick={(e) => { e.stopPropagation(); onWithdraw(amendment.id) }}
            className="text-[10px] font-body text-outline hover:text-on-error-container hover:underline transition-colors disabled:opacity-50"
          >
            {isWithdrawing ? '…' : t('document.withdraw')}
          </button>
        )}
      </div>
    </li>
  )
}

// ---------------------------------------------------------------------------
// ContributorSubmission (main component)
// ---------------------------------------------------------------------------

/**
 * Main 3-pane amendment submission interface.
 *
 * Reads :slug and :id from React Router params.
 *
 * Props: none
 */
export default function ContributorSubmission() {
  const { slug, id: docId } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation()

  // ── Document state ──────────────────────────────────────────────────────
  const [doc, setDoc] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)

  // ── Form state ──────────────────────────────────────────────────────────
  const [amendmentType, setAmendmentType] = useState('text_change')
  const [section, setSection] = useState('')
  const [originalText, setOriginalText] = useState('')
  const [proposedText, setProposedText] = useState('')
  const [justification, setJustification] = useState('')
  const [diffMode, setDiffMode] = useState('unified') // 'unified' | 'split'

  // ── Submission state ────────────────────────────────────────────────────
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [confirmedAmendment, setConfirmedAmendment] = useState(null)

  // ── Validation errors ───────────────────────────────────────────────────
  const [originalErr, setOriginalErr] = useState(null)
  const [proposedErr, setProposedErr] = useState(null)
  const [commentErr, setCommentErr] = useState(null)

  // ── My submissions ──────────────────────────────────────────────────────
  const [myAmendments, setMyAmendments] = useState([])
  const [myAmendmentsLoading, setMyAmendmentsLoading] = useState(false)
  const [withdrawingId, setWithdrawingId] = useState(null)

  // ── Text selection from document viewer ────────────────────────────────
  const [selectedText, setSelectedText] = useState('')
  const docBodyRef = useRef(null)

  // ── Left-pane document search ───────────────────────────────────────────
  const [docSearch, setDocSearch] = useState('')

  // ── Right pane — discussions ────────────────────────────────────────────
  const [selectedAmendmentId, setSelectedAmendmentId] = useState(null)
  const [comments, setComments] = useState([])
  const [commentsLoading, setCommentsLoading] = useState(false)
  const [commentInput, setCommentInput] = useState('')
  const [postingComment, setPostingComment] = useState(false)
  const commentInputRef = useRef(null)

  const PROPOSED_MAX = 5000
  const JUSTIFICATION_MAX = 1000

  /**
   * Document body with search-term highlights applied.
   */
  const highlightedBody = useMemo(() => {
    if (!doc?.body || !docSearch.trim()) return doc?.body ?? null
    if (doc.body.trimStart().startsWith('<')) {
      return highlightHtml(sanitizeHtml(doc.body), docSearch)
    }
    return doc.body
  }, [doc?.body, docSearch])

  // ── Fetch document ───────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setLoadError(null)
      try {
        const document = await orgClient.getDocument(slug, docId)
        if (!cancelled) setDoc(document)
      } catch (err) {
        if (!cancelled) {
          if (err.message?.includes('404') || err.message?.includes('not found')) {
            navigate(`/orgs/${slug}`)
          } else {
            setLoadError(err.message)
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [slug, docId, navigate])

  async function loadMyAmendments() {
    setMyAmendmentsLoading(true)
    try {
      const res = await orgClient.listMyAmendments(slug, docId)
      setMyAmendments(res.items ?? [])
    } catch {
      // Non-blocking
    } finally {
      setMyAmendmentsLoading(false)
    }
  }

  useEffect(() => {
    if (!loading && !loadError) {
      loadMyAmendments()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, loadError])

  // ── Load comments when a submission is selected ──────────────────────────

  const loadComments = useCallback(async (amendmentId) => {
    if (!amendmentId) return
    setCommentsLoading(true)
    try {
      const res = await orgClient.listComments(slug, docId, amendmentId)
      setComments(res.items ?? [])
    } catch {
      setComments([])
    } finally {
      setCommentsLoading(false)
    }
  }, [slug, docId])

  useEffect(() => {
    if (selectedAmendmentId) {
      loadComments(selectedAmendmentId)
    }
  }, [selectedAmendmentId, loadComments])

  /**
   * Select an amendment to view its comment thread.
   * If already selected, deselects it (toggle).
   *
   * Parameters:
   *   amendmentId — the amendment UUID to select
   */
  function handleSelectAmendment(amendmentId) {
    if (selectedAmendmentId === amendmentId) {
      setSelectedAmendmentId(null)
      setComments([])
    } else {
      setSelectedAmendmentId(amendmentId)
      setComments([])
    }
  }

  /**
   * Post a new comment on the selected amendment.
   *
   * Parameters:
   *   e — KeyboardEvent or React SyntheticEvent
   */
  async function handlePostComment(e) {
    e.preventDefault()
    if (!commentInput.trim() || !selectedAmendmentId || postingComment) return
    setPostingComment(true)
    try {
      const comment = await orgClient.postComment(slug, docId, selectedAmendmentId, commentInput.trim())
      setComments((prev) => [...prev, comment])
      setCommentInput('')
    } catch {
      // Non-fatal — user can retry
    } finally {
      setPostingComment(false)
    }
  }

  // ── Withdraw amendment ───────────────────────────────────────────────────

  /**
   * Withdraw a pending amendment submitted by the current user.
   *
   * Parameters:
   *   amendmentId — ID of the amendment to withdraw.
   *
   * Side effects:
   *   - Calls DELETE …/amendments/{amendmentId}.
   *   - On success marks the amendment as withdrawn in local state.
   */
  async function handleWithdraw(amendmentId) {
    if (!window.confirm(t('document.withdraw_confirm'))) return
    setWithdrawingId(amendmentId)
    try {
      await orgClient.withdrawAmendment(slug, docId, amendmentId)
      setMyAmendments((prev) =>
        prev.map((a) => (a.id === amendmentId ? { ...a, status: 'withdrawn' } : a))
      )
    } catch {
      // Non-fatal
    } finally {
      setWithdrawingId(null)
    }
  }

  // ── Form submission ───────────────────────────────────────────────────────

  async function handleSubmit(e) {
    e.preventDefault()
    setOriginalErr(null)
    setProposedErr(null)
    setCommentErr(null)
    setSubmitError(null)

    let valid = true
    if (amendmentType === 'text_change') {
      if (!originalText.trim()) { setOriginalErr(t('document.original_required')); valid = false }
      else if (
        doc?.body &&
        !doc.body.trimStart().startsWith('<') &&
        !doc.body.includes(originalText.trim())
      ) {
        setOriginalErr(t('contributor.anchor_not_found')); valid = false
      }
      if (!proposedText.trim()) { setProposedErr(t('document.proposed_required')); valid = false }
    } else {
      if (!justification.trim()) { setCommentErr(t('document.comment_required')); valid = false }
    }
    if (!valid) return

    setSubmitting(true)
    try {
      const payload = { amendment_type: amendmentType, section: section.trim() || null }
      if (amendmentType === 'text_change') {
        payload.original_text = originalText.trim()
        payload.proposed_text = proposedText.trim()
        payload.justification = justification.trim() || null
      } else {
        payload.justification = justification.trim()
      }
      const amendment = await orgClient.createAmendment(slug, docId, payload)
      setConfirmedAmendment(amendment)
      loadMyAmendments()
    } catch (err) {
      if (Array.isArray(err.detail)) {
        setSubmitError(err.detail.map((e) => e.msg ?? String(e)).join('; '))
      } else {
        setSubmitError(err.message)
      }
    } finally {
      setSubmitting(false)
    }
  }

  // ── Text selection handlers ──────────────────────────────────────────────

  /**
   * Captures text selected inside the document viewer on mouseup.
   * Only active for text_change amendments.
   */
  function handleTextSelection() {
    if (amendmentType !== 'text_change') return
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed) return
    const text = selection.toString().trim()
    if (!text) return
    if (docBodyRef.current?.contains(selection.getRangeAt(0).commonAncestorContainer)) {
      setSelectedText(text)
    }
  }

  /** Fills the originalText field with the current selection and clears it. */
  function applySelection() {
    setOriginalText(selectedText)
    if (originalErr) setOriginalErr(null)
    setSelectedText('')
    window.getSelection()?.removeAllRanges()
  }

  /** Clears the pending selection without applying it. */
  function clearSelection() {
    setSelectedText('')
    window.getSelection()?.removeAllRanges()
  }

  // ── Loading / error states ────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="bg-surface text-on-surface min-h-[calc(100vh-64px)] flex items-center justify-center">
        <p className="text-outline font-body">{t('common.loading')}</p>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="bg-surface text-on-surface min-h-[calc(100vh-64px)] flex items-center justify-center">
        <p className="text-error font-body">{loadError}</p>
      </div>
    )
  }

  const isClosed = doc?.status === 'closed'
  const selectedAmendment = myAmendments.find((a) => a.id === selectedAmendmentId) ?? null

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen flex flex-col bg-surface overflow-hidden">

      {/* ------------------------------------------------------------------ */}
      {/* Breadcrumb bar                                                       */}
      {/* ------------------------------------------------------------------ */}
      <div className="shrink-0 bg-surface-container-low px-8 py-4 flex items-center gap-2 text-sm text-outline font-body">
        <Link to="/dashboard" className="hover:text-on-surface transition-colors">
          {t('nav.dashboard')}
        </Link>
        <span>/</span>
        <Link to={`/orgs/${slug}`} className="hover:text-on-surface transition-colors">
          {slug}
        </Link>
        <span>/</span>
        <Link to={`/orgs/${slug}/documents/${docId}`} className="hover:text-on-surface transition-colors">
          {doc?.title}
        </Link>
        <span>/</span>
        <span className="text-on-surface">{t('contributor.breadcrumb')}</span>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* 3-pane split                                                         */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-1 overflow-hidden">

        {/* ================================================================ */}
        {/* PANE 1 — Document viewer                                          */}
        {/* ================================================================ */}
        <div className="flex-1 min-w-0 overflow-y-auto bg-surface">

          {/* Floating toolbar */}
          <div className="sticky top-4 z-10 flex justify-center pointer-events-none">
            <div className="pointer-events-auto inline-flex items-center bg-on-surface/90 backdrop-blur-md text-surface rounded-full shadow-xl px-2 py-1 gap-1">
              <button
                title="Bold"
                className="p-2 hover:bg-white/10 rounded-full transition-colors"
                tabIndex={-1}
              >
                <span className="material-symbols-outlined text-[18px] leading-none">format_bold</span>
              </button>
              <button
                title="Italic"
                className="p-2 hover:bg-white/10 rounded-full transition-colors"
                tabIndex={-1}
              >
                <span className="material-symbols-outlined text-[18px] leading-none">format_italic</span>
              </button>
              <button
                title="Highlight"
                className="p-2 hover:bg-white/10 rounded-full transition-colors"
                tabIndex={-1}
              >
                <span className="material-symbols-outlined text-[18px] leading-none" style={{ fontVariationSettings: "'FILL' 1" }}>ink_highlighter</span>
              </button>
              <div className="w-px h-4 bg-white/20 mx-1" />
              {selectedText ? (
                <button
                  type="button"
                  onClick={applySelection}
                  className="px-3 py-1 text-xs font-semibold bg-amendly-blue text-white rounded-full hover:opacity-90 transition-opacity"
                >
                  {t('contributor.use_selection')}
                </button>
              ) : (
                <span className="px-3 text-xs text-white/50 italic select-none">
                  {t('contributor.select_hint')}
                </span>
              )}
            </div>
          </div>

          {/* Doc header + search */}
          <div className="max-w-2xl mx-auto px-8 pt-6 pb-4">
            <span className="text-[10px] font-body font-bold tracking-[0.2em] text-amendly-blue uppercase block mb-2">
              {t('contributor.original_doc_label')}
            </span>
            <h2 className="font-display font-extrabold text-on-surface text-headline-sm tracking-tight mb-5">
              {doc?.title}
            </h2>
            <input
              type="search"
              value={docSearch}
              onChange={(e) => setDocSearch(e.target.value)}
              placeholder={t('contributor.doc_search_placeholder')}
              className="w-full bg-surface-container-low rounded-lg px-4 py-2 font-body text-body-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary mb-6"
            />

            {/* Document body */}
            {doc?.body ? (
              <div
                ref={docBodyRef}
                onMouseUp={handleTextSelection}
                className="bg-surface-container-lowest rounded-xl shadow-ambient p-8 cursor-text select-text"
              >
                {doc.body.trimStart().startsWith('<') ? (
                  <div
                    className="font-body text-body-md text-on-surface leading-relaxed
                      [&_h2]:font-display [&_h2]:text-headline-sm [&_h2]:mt-6 [&_h2]:mb-2
                      [&_h3]:font-display [&_h3]:text-title-md [&_h3]:mt-4 [&_h3]:mb-1
                      [&_p]:my-2 [&_ul]:pl-5 [&_ul]:list-disc [&_ul]:my-2
                      [&_ol]:pl-5 [&_ol]:list-decimal [&_ol]:my-2 [&_li]:my-0.5
                      [&_blockquote]:border-l-2 [&_blockquote]:border-amendly-blue
                      [&_blockquote]:pl-4 [&_blockquote]:text-outline [&_blockquote]:italic [&_blockquote]:my-2
                      [&_strong]:font-semibold [&_em]:italic"
                    dangerouslySetInnerHTML={{
                      __html: docSearch.trim() ? highlightedBody : sanitizeHtml(doc.body),
                    }}
                  />
                ) : docSearch.trim() ? (
                  <pre className="font-body text-body-md text-on-surface whitespace-pre-wrap">
                    {doc.body.split(new RegExp(`(${escapeRegex(docSearch.trim())})`, 'gi')).map((part, i) =>
                      part.toLowerCase() === docSearch.trim().toLowerCase()
                        ? <mark key={i} className="doc-search-mark" style={{ background: '#fef08a', color: '#713f12', borderRadius: '2px', padding: '0 1px' }}>{part}</mark>
                        : part
                    )}
                  </pre>
                ) : (
                  <pre className="font-body text-body-md text-on-surface whitespace-pre-wrap">
                    {doc.body}
                  </pre>
                )}
              </div>
            ) : (
              <div className="bg-surface-container-low rounded-xl p-12 text-center flex flex-col items-center gap-4">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <rect x="6" y="4" width="28" height="38" rx="3" stroke="#94a3b8" strokeWidth="2"/>
                  <line x1="13" y1="15" x2="28" y2="15" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round"/>
                  <line x1="13" y1="22" x2="28" y2="22" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round"/>
                  <line x1="13" y1="29" x2="22" y2="29" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round"/>
                  <circle cx="36" cy="36" r="8" fill="#f1f5f9" stroke="#94a3b8" strokeWidth="1.5"/>
                  <line x1="36" y1="32" x2="36" y2="36" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round"/>
                  <circle cx="36" cy="38.5" r="1" fill="#94a3b8"/>
                </svg>
                <p className="text-sm text-outline font-body">{t('contributor.no_body_notice')}</p>
                <Link to={`/orgs/${slug}/documents/${docId}`} className="font-body text-label-sm text-secondary hover:underline">
                  {t('contributor.back_to_document')}
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/* PANE 2 — Amendment proposal form                                  */}
        {/* ================================================================ */}
        <div className="w-[360px] shrink-0 bg-surface-container-low flex flex-col overflow-hidden">

          {/* Header */}
          <div className="shrink-0 px-5 py-4 bg-surface-container-lowest flex items-center justify-between">
            <div>
              <h2 className="font-display font-bold text-title-sm text-on-surface">
                {t('contributor.breadcrumb')}
              </h2>
              {isClosed && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-error-container text-on-error-container mt-1">
                  {t('contributor.doc_closed_title')}
                </span>
              )}
            </div>
            {/* Split / Unified toggle for diff preview */}
            {amendmentType === 'text_change' && !isClosed && !confirmedAmendment && (
              <div className="flex items-center bg-surface-container p-1 rounded-full">
                <button
                  type="button"
                  onClick={() => setDiffMode('unified')}
                  className={[
                    'px-3 py-1 text-[10px] font-semibold rounded-full transition-all',
                    diffMode === 'unified'
                      ? 'bg-surface-container-lowest shadow-sm text-amendly-blue'
                      : 'text-outline hover:text-on-surface',
                  ].join(' ')}
                >
                  {t('contributor.diff_unified')}
                </button>
                <button
                  type="button"
                  onClick={() => setDiffMode('split')}
                  className={[
                    'px-3 py-1 text-[10px] font-semibold rounded-full transition-all',
                    diffMode === 'split'
                      ? 'bg-surface-container-lowest shadow-sm text-amendly-blue'
                      : 'text-outline hover:text-on-surface',
                  ].join(' ')}
                >
                  {t('contributor.diff_split')}
                </button>
              </div>
            )}
          </div>

          {/* Scrollable form area */}
          <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">

            {/* ── Document closed notice ── */}
            {isClosed && !confirmedAmendment && (
              <div className="flex flex-col items-center justify-center min-h-[400px] gap-6 text-center px-4">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <rect x="10" y="22" width="28" height="20" rx="3" stroke="#94a3b8" strokeWidth="2"/>
                  <path d="M16 22v-6a8 8 0 0 1 16 0v6" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round"/>
                  <circle cx="24" cy="32" r="2.5" fill="#94a3b8"/>
                  <line x1="24" y1="34.5" x2="24" y2="38" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                <div className="space-y-2">
                  <p className="font-display font-bold text-headline-sm text-on-surface">
                    {t('contributor.doc_closed_title')}
                  </p>
                  <p className="font-body text-body-md text-outline">
                    {t('contributor.doc_closed_body')}
                  </p>
                </div>
                <Link to={`/orgs/${slug}/documents/${docId}`} className="font-body text-body-md text-secondary hover:underline">
                  {t('contributor.back_to_document')}
                </Link>
              </div>
            )}

            {/* ── Confirmation screen ── */}
            {confirmedAmendment && (
              <div className="space-y-5">
                <div className="bg-secondary-container rounded-xl px-5 py-5 space-y-2">
                  <span className="material-symbols-outlined text-on-secondary-fixed text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                  <p className="font-body text-label-sm text-on-secondary-fixed/70 tracking-[0.02em]">
                    {t('contributor.amendment_submitted_success')}
                  </p>
                  <p className="font-display font-bold text-on-secondary-fixed text-headline-sm">
                    {t('contributor.confirmation_title')}
                  </p>
                  <p className="font-body text-sm text-on-secondary-fixed/80">
                    {t('contributor.confirmation_submitted')}
                  </p>
                </div>
                <div className="bg-surface-container-lowest rounded-xl p-4 shadow-ambient space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-body text-outline uppercase tracking-wider">
                      {confirmedAmendment.amendment_type === 'general_comment'
                        ? t('document.type_general_comment')
                        : t('document.type_text_change')}
                    </span>
                    {confirmedAmendment.section && (
                      <span className="text-xs font-body text-outline">· {confirmedAmendment.section}</span>
                    )}
                  </div>
                  {confirmedAmendment.amendment_type === 'general_comment' ? (
                    <p className="text-sm text-on-surface font-body leading-relaxed">
                      {confirmedAmendment.justification}
                    </p>
                  ) : (
                    <div className="text-sm font-body leading-relaxed">
                      <DiffPreview
                        original={confirmedAmendment.original_text ?? ''}
                        proposed={confirmedAmendment.proposed_text ?? ''}
                        t={t}
                      />
                      {confirmedAmendment.justification && (
                        <p className="mt-2 text-xs text-outline italic">{confirmedAmendment.justification}</p>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <Link to={`/orgs/${slug}/documents/${docId}`} className="text-sm text-secondary hover:underline font-body">
                    {t('contributor.view_all_amendments')}
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setConfirmedAmendment(null)
                      setSection('')
                      setOriginalText('')
                      setProposedText('')
                      setJustification('')
                      setAmendmentType('text_change')
                    }}
                    className="bg-amendly-blue hover:opacity-90 text-white font-semibold px-6 py-2.5 rounded-xl transition-all font-body text-sm"
                  >
                    {t('contributor.submit_another')}
                  </button>
                </div>
              </div>
            )}

            {/* ── Pending amendments strip ── */}
            {!confirmedAmendment && !isClosed && myAmendments.filter((a) => a.status === 'pending').length > 0 && (
              <div className="bg-surface-container-lowest rounded-xl shadow-ambient p-3 space-y-2">
                <p className="font-body text-label-sm text-on-surface tracking-[0.02em] uppercase">
                  {t('contributor.pending_title')}
                </p>
                <ul className="space-y-1.5">
                  {myAmendments.filter((a) => a.status === 'pending').map((a) => {
                    const snippet = a.amendment_type === 'general_comment'
                      ? (a.justification ?? '').slice(0, 50)
                      : (a.proposed_text ?? '').slice(0, 50)
                    return (
                      <li key={a.id} className="flex items-center justify-between gap-3 bg-surface rounded-lg px-3 py-2">
                        <p className="font-body text-body-sm text-on-surface truncate flex-1 min-w-0">
                          {snippet}…
                        </p>
                        <button
                          type="button"
                          disabled={withdrawingId === a.id}
                          onClick={() => handleWithdraw(a.id)}
                          className="shrink-0 font-body text-label-sm text-outline hover:text-on-error-container hover:underline transition-colors disabled:opacity-50"
                        >
                          {withdrawingId === a.id ? '…' : t('document.withdraw')}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}

            {/* ── Amendment form ── */}
            {!confirmedAmendment && !isClosed && (
              <form onSubmit={handleSubmit} noValidate className="space-y-5">

                {/* Selected text quote */}
                {selectedText && (
                  <div>
                    <label className="block text-[10px] font-bold tracking-widest text-outline uppercase mb-2">
                      {t('contributor.selection_label')}
                    </label>
                    <div className="p-3 bg-surface-container-lowest rounded-xl border-l-4 border-amendly-blue italic text-xs text-on-surface-variant leading-relaxed">
                      "{selectedText.length > 120 ? selectedText.slice(0, 120) + '…' : selectedText}"
                    </div>
                  </div>
                )}

                {/* Amendment type toggle */}
                <div className="space-y-2">
                  <p className="text-[10px] font-bold tracking-widest text-outline uppercase">
                    {t('document.amendment_type_label')}
                  </p>
                  <div className="flex rounded-lg overflow-hidden bg-surface-container-highest">
                    <button
                      type="button"
                      disabled={isClosed || submitting}
                      onClick={() => setAmendmentType('text_change')}
                      className={[
                        'flex-1 py-2.5 text-sm font-body font-medium transition-colors',
                        amendmentType === 'text_change'
                          ? 'bg-amendly-blue text-white'
                          : 'text-outline hover:text-on-surface',
                      ].join(' ')}
                    >
                      {t('document.type_text_change')}
                    </button>
                    <button
                      type="button"
                      disabled={isClosed || submitting}
                      onClick={() => {
                        setAmendmentType('general_comment')
                        if (selectedText) { setSelectedText(''); window.getSelection()?.removeAllRanges() }
                      }}
                      className={[
                        'flex-1 py-2.5 text-sm font-body font-medium transition-colors',
                        amendmentType === 'general_comment'
                          ? 'bg-amendly-blue text-white'
                          : 'text-outline hover:text-on-surface',
                      ].join(' ')}
                    >
                      {t('document.type_general_comment')}
                    </button>
                  </div>
                </div>

                {/* Section */}
                <div className="space-y-2">
                  <label className="block text-[10px] font-bold tracking-widest text-outline uppercase">
                    {t('document.section_label')}{' '}
                    <span className="normal-case font-normal">({t('document.section_optional')})</span>
                  </label>
                  <input
                    type="text"
                    value={section}
                    onChange={(e) => setSection(e.target.value)}
                    placeholder={t('document.section_placeholder')}
                    disabled={isClosed || submitting}
                    className="w-full bg-surface-container-lowest ring-1 ring-inset ring-outline-variant/30 focus:ring-2 focus:ring-secondary border-none p-3 rounded-lg transition-all text-on-surface placeholder:text-outline/50 font-body text-sm disabled:opacity-50"
                  />
                </div>

                {/* TEXT CHANGE fields */}
                {amendmentType === 'text_change' && (
                  <>
                    {/* Original text */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] font-bold tracking-widest text-outline uppercase">
                          {t('document.original_text_label')}
                        </label>
                        {originalText && (
                          <button
                            type="button"
                            onClick={() => { setOriginalText(''); setOriginalErr(null) }}
                            className="text-[10px] text-outline hover:text-on-surface font-body transition-colors"
                          >
                            {t('contributor.clear_selection')}
                          </button>
                        )}
                      </div>
                      <textarea
                        value={originalText}
                        onChange={(e) => { setOriginalText(e.target.value); if (originalErr) setOriginalErr(null) }}
                        placeholder={t('document.original_text_placeholder')}
                        rows={3}
                        disabled={isClosed || submitting}
                        className="w-full bg-surface-container-lowest ring-1 ring-inset ring-outline-variant/30 focus:ring-2 focus:ring-secondary border-none p-3 rounded-xl transition-all text-on-surface font-body leading-relaxed text-sm disabled:opacity-50"
                      />
                      {originalErr && <p className="text-error text-xs font-body">{originalErr}</p>}
                    </div>

                    {/* Proposed text with mini toolbar */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] font-bold tracking-widest text-outline uppercase">
                          {t('document.proposed_text_label')}
                        </label>
                        <span className={`text-[10px] font-body tabular-nums ${proposedText.length > PROPOSED_MAX ? 'text-error' : 'text-outline'}`}>
                          {proposedText.length}/{PROPOSED_MAX}
                        </span>
                      </div>
                      <div className="bg-surface-container-lowest rounded-xl ring-1 ring-inset ring-outline-variant/30 focus-within:ring-2 focus-within:ring-secondary overflow-hidden transition-all">
                        <div className="flex items-center gap-1 px-2 py-1.5 bg-surface-container-low">
                          <button type="button" tabIndex={-1} className="p-1 hover:bg-surface-container rounded transition-colors">
                            <span className="material-symbols-outlined text-outline text-[16px] leading-none">format_list_bulleted</span>
                          </button>
                          <button type="button" tabIndex={-1} className="p-1 hover:bg-surface-container rounded transition-colors">
                            <span className="material-symbols-outlined text-outline text-[16px] leading-none">link</span>
                          </button>
                          <div className="w-px h-3 bg-outline-variant/50 mx-0.5" />
                          <button type="button" tabIndex={-1} className="p-1 hover:bg-surface-container rounded transition-colors">
                            <span className="material-symbols-outlined text-outline text-[16px] leading-none">spellcheck</span>
                          </button>
                        </div>
                        <textarea
                          value={proposedText}
                          onChange={(e) => { setProposedText(e.target.value); if (proposedErr) setProposedErr(null) }}
                          placeholder={t('document.proposed_text_placeholder')}
                          rows={4}
                          maxLength={PROPOSED_MAX}
                          disabled={isClosed || submitting}
                          className="w-full p-3 bg-transparent border-none focus:outline-none focus:ring-0 text-on-surface font-body leading-relaxed text-sm disabled:opacity-50 resize-none"
                        />
                      </div>
                      {proposedErr && <p className="text-error text-xs font-body">{proposedErr}</p>}
                    </div>

                    {/* Live diff preview */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold tracking-widest text-outline uppercase">{t('contributor.diff_label')}</span>
                        <span className="text-[10px] text-outline font-body">{t('contributor.diff_hint')}</span>
                      </div>
                      <div className="bg-surface-container-lowest shadow-ambient rounded-xl p-4">
                        {diffMode === 'split' ? (
                          <SplitDiffPreview original={originalText} proposed={proposedText} t={t} />
                        ) : (
                          <DiffPreview original={originalText} proposed={proposedText} t={t} />
                        )}
                      </div>
                    </div>

                    {/* Justification (optional for text changes) */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] font-bold tracking-widest text-outline uppercase">
                          {t('document.justification_label')}{' '}
                          <span className="normal-case font-normal">({t('document.justification_optional')})</span>
                        </label>
                        <span className={`text-[10px] font-body tabular-nums ${justification.length > JUSTIFICATION_MAX ? 'text-error' : 'text-outline'}`}>
                          {justification.length}/{JUSTIFICATION_MAX}
                        </span>
                      </div>
                      <textarea
                        value={justification}
                        onChange={(e) => setJustification(e.target.value)}
                        placeholder={t('document.justification_placeholder')}
                        rows={3}
                        maxLength={JUSTIFICATION_MAX}
                        disabled={isClosed || submitting}
                        className="w-full bg-surface-container-lowest ring-1 ring-inset ring-outline-variant/30 focus:ring-2 focus:ring-secondary border-none p-3 rounded-xl transition-all text-on-surface font-body text-sm disabled:opacity-50"
                      />
                    </div>
                  </>
                )}

                {/* GENERAL COMMENT field */}
                {amendmentType === 'general_comment' && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold tracking-widest text-outline uppercase">
                        {t('document.comment_label')}
                      </label>
                      <span className={`text-[10px] font-body tabular-nums ${justification.length > JUSTIFICATION_MAX ? 'text-error' : 'text-outline'}`}>
                        {justification.length}/{JUSTIFICATION_MAX}
                      </span>
                    </div>
                    <textarea
                      value={justification}
                      onChange={(e) => { setJustification(e.target.value); if (commentErr) setCommentErr(null) }}
                      placeholder={t('document.comment_placeholder')}
                      rows={6}
                      maxLength={JUSTIFICATION_MAX}
                      disabled={isClosed || submitting}
                      className="w-full bg-surface-container-lowest ring-1 ring-inset ring-outline-variant/30 focus:ring-2 focus:ring-secondary border-none p-3 rounded-xl transition-all text-on-surface font-body leading-relaxed text-sm disabled:opacity-50"
                    />
                    {commentErr && <p className="text-error text-xs font-body">{commentErr}</p>}
                  </div>
                )}

                {submitError && <p className="text-error text-sm font-body">{submitError}</p>}

              </form>
            )}
          </div>

          {/* Sticky submit footer */}
          {!confirmedAmendment && !isClosed && (
            <div className="shrink-0 px-5 py-4 bg-surface-container-lowest">
              <div className="flex items-center justify-between gap-3">
                <Link
                  to={`/orgs/${slug}/documents/${docId}`}
                  className="text-sm text-outline hover:text-on-surface transition-colors font-body"
                >
                  {t('contributor.back_to_document')}
                </Link>
                <button
                  type="submit"
                  form=""
                  disabled={isClosed || submitting}
                  onClick={handleSubmit}
                  className="bg-amendly-blue hover:opacity-90 text-white font-semibold px-6 py-2.5 rounded-xl transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed font-body text-sm"
                >
                  {submitting ? t('document.submitting') : t('document.submit_amendment')}
                  {!submitting && <span className="material-symbols-outlined text-[16px] leading-none">send</span>}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ================================================================ */}
        {/* PANE 3 — Discussions                                              */}
        {/* ================================================================ */}
        <div className="w-[280px] shrink-0 bg-surface flex flex-col overflow-hidden">

          {/* Header */}
          <div className="shrink-0 px-4 py-4 bg-surface-container-lowest flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-amendly-blue text-xl leading-none" style={{ fontVariationSettings: "'FILL' 1" }}>forum</span>
              <h2 className="font-display font-bold text-sm text-on-surface">
                {selectedAmendmentId ? t('contributor.discussions_title') : t('contributor.my_submissions_title')}
              </h2>
            </div>
            {selectedAmendmentId ? (
              <button
                type="button"
                onClick={() => { setSelectedAmendmentId(null); setComments([]) }}
                className="text-[10px] text-outline hover:text-on-surface font-body transition-colors flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[14px] leading-none">arrow_back</span>
                {t('common.back')}
              </button>
            ) : (
              <span className="bg-primary-container text-on-primary-container px-2 py-0.5 rounded-full text-[10px] font-bold">
                {myAmendments.length}
              </span>
            )}
          </div>

          {/* Submissions list */}
          {!selectedAmendmentId && (
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {myAmendmentsLoading ? (
                <p className="text-sm text-outline font-body italic text-center py-8">{t('common.loading')}</p>
              ) : myAmendments.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <span className="material-symbols-outlined text-outline-variant text-4xl" style={{ fontVariationSettings: "'FILL' 0" }}>edit_note</span>
                  <p className="text-sm text-outline font-body italic mt-3">{t('contributor.my_submissions_empty')}</p>
                </div>
              ) : (
                myAmendments.map((a) => (
                  <MyAmendmentCard
                    key={a.id}
                    amendment={a}
                    t={t}
                    isSelected={selectedAmendmentId === a.id}
                    onSelect={() => handleSelectAmendment(a.id)}
                    onWithdraw={handleWithdraw}
                    isWithdrawing={withdrawingId === a.id}
                  />
                ))
              )}
            </div>
          )}

          {/* Comment thread for selected amendment */}
          {selectedAmendmentId && (
            <>
              {/* Context block */}
              <div className="shrink-0 mx-3 mt-3 bg-secondary-container/40 px-3 py-2 rounded-lg">
                <p className="text-[10px] text-amendly-blue font-bold uppercase mb-1 flex items-center gap-1">
                  <span className="material-symbols-outlined text-[12px] leading-none">link</span>
                  {t('contributor.context_label')}
                </p>
                <p className="text-[11px] text-on-surface-variant line-clamp-2 italic">
                  {selectedAmendment?.amendment_type === 'general_comment'
                    ? (selectedAmendment?.justification ?? '').slice(0, 80)
                    : (selectedAmendment?.proposed_text ?? '').slice(0, 80)}
                  {((selectedAmendment?.amendment_type === 'general_comment'
                    ? (selectedAmendment?.justification ?? '')
                    : (selectedAmendment?.proposed_text ?? '')).length > 80) && '…'}
                </p>
              </div>

              {/* Comments list */}
              <div className="flex-1 overflow-y-auto p-3 space-y-4">
                {commentsLoading ? (
                  <p className="text-sm text-outline font-body italic text-center py-8">{t('common.loading')}</p>
                ) : comments.length === 0 ? (
                  <div className="text-center py-8 px-4">
                    <span className="material-symbols-outlined text-outline-variant text-3xl" style={{ fontVariationSettings: "'FILL' 0" }}>chat_bubble_outline</span>
                    <p className="text-xs text-outline font-body italic mt-2">
                      {t('contributor.no_comments')}
                    </p>
                  </div>
                ) : (
                  comments.map((comment) => (
                    <div key={comment.id} className="flex gap-2">
                      <div className="w-7 h-7 rounded-full bg-surface-container-highest flex items-center justify-center shrink-0 text-[10px] font-bold text-outline uppercase">
                        {(comment.author_name ?? comment.author_email ?? '?').slice(0, 2)}
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-on-surface">
                            {comment.author_name ?? comment.author_email ?? t('common.unknown')}
                          </span>
                          <span className="text-[10px] text-outline">
                            {new Date(comment.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <div className="bg-surface-container-high rounded-tr-xl rounded-br-xl rounded-bl-xl px-3 py-2">
                          <p className="text-xs text-on-surface-variant leading-relaxed">{comment.body}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}

          {/* Comment input — only when viewing a thread */}
          {selectedAmendmentId && (
            <div className="shrink-0 p-3 bg-surface-container-lowest">
              <div className="relative">
                <textarea
                  ref={commentInputRef}
                  value={commentInput}
                  onChange={(e) => setCommentInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handlePostComment(e)
                    }
                  }}
                  placeholder={t('contributor.comment_placeholder')}
                  rows={2}
                  maxLength={2000}
                  disabled={postingComment}
                  className="w-full pr-10 px-3 py-2 text-xs font-body bg-surface-container-low rounded-xl ring-1 ring-inset ring-outline-variant/20 focus:ring-2 focus:ring-secondary focus:outline-none resize-none transition-all disabled:opacity-50"
                />
                <button
                  type="button"
                  disabled={!commentInput.trim() || postingComment}
                  onClick={handlePostComment}
                  className="absolute right-2 top-2 p-1 text-amendly-blue hover:bg-amendly-blue/10 rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <span className="material-symbols-outlined text-xl leading-none">send</span>
                </button>
              </div>
              <p className="text-[10px] text-outline mt-1.5 text-right">{t('contributor.enter_to_post')}</p>
            </div>
          )}

          {/* Tips section (when not viewing thread) */}
          {!selectedAmendmentId && (
            <div className="shrink-0 p-3 bg-surface-container-low">
              <div className="space-y-2">
                <p className="text-[10px] font-bold tracking-widest text-outline uppercase">{t('contributor.tips_title')}</p>
                <ul className="space-y-1.5">
                  {['tip_1', 'tip_2', 'tip_3'].map((key) => (
                    <li key={key} className="flex gap-2">
                      <div className="w-1 h-1 rounded-full bg-secondary shrink-0 mt-1.5" />
                      <p className="text-[11px] text-on-surface-variant leading-relaxed font-body">
                        <strong className="text-on-surface font-semibold">{t(`contributor.${key}_title`)}: </strong>
                        {t(`contributor.${key}_body`)}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
