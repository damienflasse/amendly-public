/**
 * PublicContribution — unauthenticated amendment submission form.
 *
 * Route: /contribute/:token  (public — no auth required, no nav bar)
 *
 * On mount it fetches:
 *   GET /api/contribute/{token} — document metadata (title, body, org name, status).
 *
 * Behaviour:
 *   - Shows the organisation name and document title in a minimal branded header.
 *   - Left pane: read-only document body.
 *   - Right pane: amendment form with contributor_name (required),
 *     contributor_email (optional), and the same text-change / general-comment
 *     fields as the authenticated ContributorSubmission form.
 *   - On submit → POST /api/contribute/{token} → confirmation screen.
 *   - "Submit another" resets back to the form.
 *   - If the document is closed / token invalid → friendly error page.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Minimal layout — no authenticated nav bar.
 *   - Tonal layering and Inter font consistent with the rest of the app.
 *
 * Props: none (reads :token from React Router params)
 * Side effects:
 *   - No auth store reads — fully public.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Turnstile } from '@marsidev/react-turnstile'
import { useParams } from 'react-router-dom'
import { getPublicDocument, submitPublicAmendment } from '../lib/contribute'
import { getTurnstileSiteKey } from '../lib/turnstile'
import { useTranslation } from '../hooks/useTranslation'
import { sanitizeHtml } from '../lib/sanitize'
import Logo from '../components/Logo'

// ---------------------------------------------------------------------------
// Client-side word diff (same lightweight LCS impl as ContributorSubmission)
// ---------------------------------------------------------------------------

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

  const tokens = []
  let i = m, j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origTokens[i - 1] === propTokens[j - 1]) {
      tokens.unshift({ text: origTokens[i - 1], type: 'equal' })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      tokens.unshift({ text: propTokens[j - 1], type: 'insert' })
      j--
    } else {
      tokens.unshift({ text: origTokens[i - 1], type: 'delete' })
      i--
    }
  }
  return tokens
}

function DiffPreview({ original, proposed }) {
  const tokens = useMemo(
    () => computeClientDiff(original, proposed),
    [original, proposed]
  )
  return (
    <p className="font-body text-body-md text-on-surface leading-relaxed">
      {tokens.map((tok, i) => {
        if (tok.type === 'equal') return <span key={i}>{tok.text}</span>
        if (tok.type === 'insert')
          return (
            <span
              key={i}
              style={{ background: '#dbe1ff', color: '#003798', fontWeight: 700 }}
            >
              {tok.text}
            </span>
          )
        return (
          <span
            key={i}
            style={{ color: '#717c82', textDecoration: 'line-through' }}
          >
            {tok.text}
          </span>
        )
      })}
    </p>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

/**
 * PublicContribution page — unauthenticated amendment submission.
 *
 * @returns {React.ReactElement}
 */
export default function PublicContribution() {
  const { token } = useParams()
  const { t } = useTranslation()
  const turnstileSiteKey = getTurnstileSiteKey()

  const [docInfo, setDocInfo] = useState(null)   // PublicDocumentResponse
  const [loadError, setLoadError] = useState(null)
  const [loadClosed, setLoadClosed] = useState(false)
  const [loadExpired, setLoadExpired] = useState(false)
  const [loading, setLoading] = useState(true)

  // Form state
  const [amendmentType, setAmendmentType] = useState('text_change')
  const [section, setSection] = useState('')
  const [originalText, setOriginalText] = useState('')
  const [proposedText, setProposedText] = useState('')
  const [justification, setJustification] = useState('')
  const [contributorName, setContributorName] = useState('')
  const [contributorEmail, setContributorEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [submitted, setSubmitted] = useState(null)  // AmendmentResponse on success
  const [turnstileToken, setTurnstileToken] = useState('')
  const turnstileRef = useRef(null)

  const showDiff = amendmentType === 'text_change' && originalText.trim() && proposedText.trim()
  const isGeneralComment = amendmentType === 'general_comment'
  const isExpired = loadExpired || docInfo?.contributor_link_status === 'expired'
  const expiredAtLabel = docInfo?.contributor_token_expires_at
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(docInfo.contributor_token_expires_at))
    : null

  // -------------------------------------------------------------------------
  // Load document
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setLoadError(null)
      setLoadClosed(false)
      setLoadExpired(false)
      try {
        const data = await getPublicDocument(token)
        if (!cancelled) setDocInfo(data)
      } catch (err) {
        if (!cancelled) {
          if (err.status === 404) {
            setLoadClosed(true)
          } else if (err.status === 410) {
            setLoadExpired(true)
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
  }, [token])

  // -------------------------------------------------------------------------
  // Submit
  // -------------------------------------------------------------------------

  async function handleSubmit(e) {
    e.preventDefault()
    if (turnstileSiteKey && !turnstileToken) return
    setSubmitError(null)
    setSubmitting(true)
    try {
      const payload = {
        amendment_type: amendmentType,
        section: section.trim() || null,
        contributor_name: contributorName.trim(),
        contributor_email: contributorEmail.trim() || null,
        cf_turnstile_token: turnstileToken || null,
      }
      if (amendmentType === 'text_change') {
        payload.original_text = originalText.trim()
        payload.proposed_text = proposedText.trim()
        payload.justification = justification.trim() || null
      } else {
        payload.justification = justification.trim()
      }
      const result = await submitPublicAmendment(token, payload)
      setSubmitted(result)
    } catch (err) {
      turnstileRef.current?.reset()
      setTurnstileToken('')
      if (err.status === 410) {
        setDocInfo((prev) => (
          prev
            ? { ...prev, contributor_link_status: 'expired' }
            : prev
        ))
      }
      setSubmitError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  function handleSubmitAnother() {
    setSubmitted(null)
    setSection('')
    setOriginalText('')
    setProposedText('')
    setJustification('')
    setAmendmentType('text_change')
    setSubmitError(null)
    setTurnstileToken('')
    turnstileRef.current?.reset()
  }

  // -------------------------------------------------------------------------
  // Render helpers
  // -------------------------------------------------------------------------

  // Minimal branded header (no auth nav)
  function Header() {
    return (
      <header className="shrink-0 bg-surface-container-low px-6 py-4 flex items-center gap-3 border-b border-surface-container">
        <Logo />
        {docInfo && (
          <>
            <span className="font-body text-body-md text-outline">·</span>
            <span className="font-body text-body-md text-outline">{docInfo.org_name}</span>
            <span className="font-body text-body-md text-outline">/</span>
            <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em] truncate">
              {docInfo.title}
            </span>
          </>
        )}
      </header>
    )
  }

  // -------------------------------------------------------------------------
  // Loading
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex flex-col">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <span className="font-body text-body-md text-outline">{t('common.loading')}</span>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Error / closed states
  // -------------------------------------------------------------------------

  if (loadClosed || loadError) {
    return (
      <div className="min-h-screen bg-surface flex flex-col">
        <Header />
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="max-w-md w-full text-center space-y-4">
            <div className="w-16 h-16 mx-auto rounded-full bg-surface-container-highest flex items-center justify-center">
              <span className="text-2xl text-outline">×</span>
            </div>
            <h1 className="font-display text-headline-md text-on-surface tracking-[-0.01em]">
              {t('contribute.not_found_title')}
            </h1>
            <p className="font-body text-body-md text-outline">
              {loadClosed
                ? t('contribute.not_found_closed')
                : t('contribute.not_found_error')}
            </p>
          </div>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Confirmation screen
  // -------------------------------------------------------------------------

  if (submitted) {
    return (
      <div className="min-h-screen bg-surface flex flex-col">
        <Header />
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="max-w-lg w-full bg-surface-container-lowest rounded-md shadow-ambient p-8 space-y-5 text-center">
            <div className="w-14 h-14 mx-auto rounded-full bg-tertiary-fixed flex items-center justify-center">
              <span className="text-on-tertiary-fixed text-xl font-bold">✓</span>
            </div>
            <h1 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
              {t('contribute.submitted_title')}
            </h1>
            <p className="font-body text-body-md text-outline">
              {t('contribute.submitted_desc')}
            </p>
            <button
              type="button"
              onClick={handleSubmitAnother}
              className="px-6 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md hover:opacity-90 transition-opacity"
            >
              {t('contribute.submit_another')}
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (isExpired) {
    return (
      <div className="min-h-screen bg-surface flex flex-col">
        <Header />
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="max-w-lg w-full bg-surface-container-lowest rounded-md shadow-ambient p-8 space-y-5 text-center">
            <div className="w-14 h-14 mx-auto rounded-full bg-error-container/60 flex items-center justify-center">
              <span className="text-on-error-container text-xl font-bold">!</span>
            </div>
            <h1 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
              {t('contribute.expired_title')}
            </h1>
            <p className="font-body text-body-md text-outline">
              {expiredAtLabel
                ? t('contribute.expired_desc').replace('{date}', expiredAtLabel)
                : t('contribute.expired_desc_no_date')}
            </p>
            <p className="font-body text-body-md text-on-surface">
              {t('contribute.expired_regen_hint')}
            </p>
          </div>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Main layout: document body (left) + form (right)
  // -------------------------------------------------------------------------

  const isHtml = docInfo?.body?.trimStart().startsWith('<')

  return (
    <div className="h-screen flex flex-col bg-surface overflow-hidden">
      <Header />

      {/* Split pane */}
      <div className="flex flex-1 overflow-hidden">

        {/* -------------------------------------------------------- */}
        {/* LEFT PANE — read-only document body                      */}
        {/* -------------------------------------------------------- */}
        <div className="flex-1 min-w-0 overflow-y-auto border-r border-surface-container">
          <div className="px-8 py-10">
            <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em] mb-6">
              {docInfo?.title}
            </h1>

            {docInfo?.body ? (
              <div className="bg-surface-container-lowest rounded-md shadow-ambient p-8">
                {isHtml ? (
                  <div
                    className="font-body text-body-md text-on-surface leading-relaxed
                      [&_h2]:font-display [&_h2]:text-headline-sm [&_h2]:mt-6 [&_h2]:mb-2
                      [&_h3]:font-display [&_h3]:text-title-md [&_h3]:mt-4 [&_h3]:mb-1
                      [&_p]:my-2
                      [&_ul]:pl-5 [&_ul]:list-disc [&_ul]:my-2
                      [&_ol]:pl-5 [&_ol]:list-decimal [&_ol]:my-2
                      [&_li]:my-0.5
                      [&_strong]:font-semibold [&_em]:italic"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(docInfo.body) }}
                  />
                ) : (
                  <pre className="font-body text-body-md text-on-surface whitespace-pre-wrap">
                    {docInfo.body}
                  </pre>
                )}
              </div>
            ) : (
              <div className="bg-surface-container-low rounded-md p-12 text-center">
                <p className="font-body text-body-md text-outline">{t('document.no_body')}</p>
              </div>
            )}
          </div>
        </div>

        {/* -------------------------------------------------------- */}
        {/* RIGHT PANE — submission form                             */}
        {/* -------------------------------------------------------- */}
        <div className="w-[480px] shrink-0 overflow-y-auto bg-surface-container-low">
          <div className="px-8 py-10">
            <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-6">
              {t('contribute.form_title')}
            </h2>

            <form onSubmit={handleSubmit} className="space-y-5">

              {/* Contributor identity */}
              <div className="space-y-4 pb-5 border-b border-surface-container">
                <div>
                  <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-1.5">
                    {t('contribute.name_label')} <span className="text-secondary">*</span>
                  </label>
                  <input
                    type="text"
                    value={contributorName}
                    onChange={(e) => setContributorName(e.target.value)}
                    required
                    maxLength={100}
                    placeholder={t('contribute.name_placeholder')}
                    className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
                  />
                </div>
                <div>
                  <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-1.5">
                    {t('contribute.email_label')}{' '}
                    <span className="text-outline normal-case tracking-normal">{t('contribute.email_optional')}</span>
                  </label>
                  <input
                    type="email"
                    value={contributorEmail}
                    onChange={(e) => setContributorEmail(e.target.value)}
                    maxLength={254}
                    placeholder={t('contribute.email_placeholder')}
                    className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
                  />
                </div>
              </div>

              {/* Amendment type */}
              <div>
                <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-2">
                  {t('document.amendment_type_label')}
                </label>
                <div className="flex gap-4">
                  {['text_change', 'general_comment'].map((type) => (
                    <label key={type} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="amendment_type"
                        value={type}
                        checked={amendmentType === type}
                        onChange={() => setAmendmentType(type)}
                        className="accent-amendly-blue"
                      />
                      <span className="font-body text-body-md text-on-surface">
                        {t(`document.type_${type}`)}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Section (both types) */}
              <div>
                <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-1.5">
                  {t('document.section_label')}{' '}
                  <span className="text-outline normal-case tracking-normal">{t('document.section_optional')}</span>
                </label>
                <input
                  type="text"
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                  maxLength={500}
                  placeholder={t('document.section_placeholder')}
                  className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
                />
              </div>

              {/* Text-change fields */}
              {!isGeneralComment && (
                <>
                  <div>
                    <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-1.5">
                      {t('document.original_text_label')} <span className="text-secondary">*</span>
                    </label>
                    <textarea
                      value={originalText}
                      onChange={(e) => setOriginalText(e.target.value)}
                      required
                      rows={4}
                      placeholder={t('document.original_text_placeholder')}
                      className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary resize-none"
                    />
                  </div>
                  <div>
                    <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-1.5">
                      {t('document.proposed_text_label')} <span className="text-secondary">*</span>
                    </label>
                    <textarea
                      value={proposedText}
                      onChange={(e) => setProposedText(e.target.value)}
                      required
                      rows={4}
                      maxLength={5000}
                      placeholder={t('document.proposed_text_placeholder')}
                      className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary resize-none"
                    />
                  </div>

                  {/* Live diff preview */}
                  {showDiff && (
                    <div className="bg-surface-container-lowest rounded-md p-4 space-y-1">
                      <p className="font-body text-label-sm text-outline uppercase tracking-[0.02em]">
                        {t('document.diff_label')}
                      </p>
                      <DiffPreview original={originalText} proposed={proposedText} />
                    </div>
                  )}

                  {/* Justification (text_change — optional) */}
                  <div>
                    <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-1.5">
                      {t('document.justification_label')}{' '}
                      <span className="text-outline normal-case tracking-normal">{t('document.justification_optional')}</span>
                    </label>
                    <textarea
                      value={justification}
                      onChange={(e) => setJustification(e.target.value)}
                      rows={3}
                      maxLength={1000}
                      placeholder={t('document.justification_placeholder')}
                      className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary resize-none"
                    />
                  </div>
                </>
              )}

              {/* General comment body (required) */}
              {isGeneralComment && (
                <div>
                  <label className="block font-body text-label-sm text-on-surface uppercase tracking-[0.02em] mb-1.5">
                    {t('document.comment_label')} <span className="text-secondary">*</span>
                  </label>
                  <textarea
                    value={justification}
                    onChange={(e) => setJustification(e.target.value)}
                    required
                    rows={5}
                    maxLength={1000}
                    placeholder={t('document.comment_placeholder')}
                    className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary resize-none"
                  />
                </div>
              )}

              {/* Error */}
              {submitError && (
                <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
                  {submitError}
                </p>
              )}

              {turnstileSiteKey && (
                <div className="rounded-md bg-surface p-2">
                  <Turnstile
                    ref={turnstileRef}
                    siteKey={turnstileSiteKey}
                    onSuccess={(resolvedToken) => setTurnstileToken(resolvedToken)}
                    onExpire={() => setTurnstileToken('')}
                    onError={() => setTurnstileToken('')}
                    options={{ theme: 'light', size: 'flexible', action: 'public_contribution' }}
                  />
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={
                  submitting ||
                  !contributorName.trim() ||
                  (turnstileSiteKey && !turnstileToken)
                }
                className="w-full px-6 py-2.5 bg-amendly-blue text-white rounded-md font-body text-body-md disabled:opacity-50 hover:opacity-90 transition-opacity"
              >
                {submitting ? t('document.submitting') : t('contribute.submit_button')}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
