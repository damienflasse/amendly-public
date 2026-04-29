import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileInput,
  FileStack,
  FileUp,
  Upload,
  X,
} from 'lucide-react'
import {
  extractDocxFile,
  extractPdfFile,
  resolveImportedDocumentTitle,
  validateDocumentImportFile,
} from '../lib/documentImport'
import { extractBodyBlocks } from '../lib/documentSections'

/**
 * Summarize imported HTML for the review and success states.
 *
 * @param {string} html
 * @returns {{ headingCount: number; defaultSectionCount: number }}
 */
function summarizeImportedBody(html) {
  const blocks = extractBodyBlocks(html)
  return {
    headingCount: blocks.filter((block) => block.tag === 'h2' || block.tag === 'h3').length,
    defaultSectionCount: blocks.filter(
      (block) => block.tag !== 'h2' && block.tag !== 'h3' && block.tag !== 'hr'
    ).length,
  }
}

/**
 * Small metric pill used in the import review and success summary.
 *
 * @param {{ label: string; value: string | number; tone?: 'default' | 'accent' }} props
 */
function MetricPill({ label, value, tone = 'default' }) {
  const toneClass =
    tone === 'accent'
      ? 'bg-primary-fixed text-on-primary-fixed'
      : 'bg-surface-container-highest text-on-surface'

  return (
    <div className={`rounded-full px-3 py-1.5 font-body text-label-sm ${toneClass}`}>
      <span className="font-semibold">{value}</span> {label}
    </div>
  )
}

/**
 * Persistent summary shown once an import has been applied.
 *
 * @param {{
 *   summary: { fileName: string; kind: 'docx' | 'pdf'; charCount: number; headingCount: number; defaultSectionCount: number; warnings: string[] };
 *   t: (key: string) => string;
 *   onReviewStructure?: (() => void) | null;
 *   reviewLabel?: string;
 * }} props
 */
export function ImportedDocumentSummary({ summary, t, onReviewStructure = null, reviewLabel = null }) {
  const hasWarnings = summary.warnings.length > 0

  return (
    <div className="rounded-md bg-surface-container-low px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4.5 w-4.5 text-amendly-blue" aria-hidden="true" />
            <p className="font-body text-body-md text-on-surface">
              {t('document.import_applied_title')}
            </p>
          </div>
          <p className="font-body text-body-sm text-outline">
            {t('document.import_applied_body')
              .replace('{file}', summary.fileName)
              .replace('{kind}', summary.kind.toUpperCase())}
          </p>
        </div>
        {onReviewStructure && (
          <button
            type="button"
            onClick={onReviewStructure}
            className="rounded-md bg-amendly-blue text-white px-4 py-2 font-body text-body-md hover:opacity-90 transition-opacity"
          >
            {reviewLabel ?? t('document.import_review_structure_cta')}
          </button>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <MetricPill
          label={t('document.import_metric_blocks')}
          value={summary.defaultSectionCount}
          tone="accent"
        />
        <MetricPill
          label={t('document.import_metric_headings')}
          value={summary.headingCount}
        />
        <MetricPill
          label={t('document.import_metric_characters')}
          value={summary.charCount.toLocaleString()}
        />
      </div>

      <p className="mt-3 font-body text-body-sm text-outline">
        {t('document.import_default_sections_hint')}
      </p>

      {hasWarnings && (
        <div className="mt-3 rounded-md bg-error-container/20 px-3 py-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-on-error-container" aria-hidden="true" />
            <div className="space-y-1 font-body text-body-sm text-on-error-container">
              <p>{t('document.import_warning_title')}</p>
              {summary.warnings.includes('tables_ignored') && (
                <p>{t('document.import_tables_ignored')}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Modal shown after extraction and before applying the imported content.
 *
 * @param {{
 *   review: {
 *     kind: 'docx' | 'pdf';
 *     fileName: string;
 *     html: string;
 *     suggestedTitle: string;
 *     charCount: number;
 *     headingCount: number;
 *     defaultSectionCount: number;
 *     warnings: string[];
 *   };
 *   hasExistingBody: boolean;
 *   currentTitle: string;
 *   t: (key: string) => string;
 *   onApply: () => void;
 *   onClose: () => void;
 * }} props
 */
function ImportReviewModal({ review, hasExistingBody, currentTitle, t, onApply, onClose }) {
  const modalRef = useRef(null)
  const applyButtonRef = useRef(null)

  useEffect(() => {
    const id = window.requestAnimationFrame(() => applyButtonRef.current?.focus({ preventScroll: true }))
    return () => window.cancelAnimationFrame(id)
  }, [])

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const willKeepCurrentTitle = Boolean(currentTitle.trim())

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-amendly-dark/35 px-4 py-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={t('document.import_review_title')}
      onMouseDown={(event) => {
        if (modalRef.current && !modalRef.current.contains(event.target)) onClose()
      }}
    >
      <div
        ref={modalRef}
        className="w-full max-w-3xl rounded-2xl bg-white/90 p-8 shadow-ambient backdrop-blur-md"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="font-body text-label-sm uppercase tracking-[0.02em] text-outline">
              {t('document.import_review_eyebrow')}
            </p>
            <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
              {t('document.import_review_title')}
            </h2>
            <p className="font-body text-body-md text-outline leading-relaxed">
              {hasExistingBody
                ? t('document.import_review_replace_body')
                : t('document.import_review_apply_body')}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-surface-container-low p-2 text-outline transition-colors hover:text-on-surface"
            aria-label={t('document.modal_close')}
          >
            <X className="h-4.5 w-4.5" aria-hidden="true" />
          </button>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1.3fr_0.9fr]">
          <div className="rounded-xl bg-surface px-5 py-5">
            <div className="flex items-center gap-2">
              <FileStack className="h-4.5 w-4.5 text-amendly-blue" aria-hidden="true" />
              <p className="font-body text-body-md font-semibold text-on-surface">
                {review.fileName}
              </p>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <MetricPill
                label={t('document.import_metric_blocks')}
                value={review.defaultSectionCount}
                tone="accent"
              />
              <MetricPill
                label={t('document.import_metric_headings')}
                value={review.headingCount}
              />
              <MetricPill
                label={t('document.import_metric_characters')}
                value={review.charCount.toLocaleString()}
              />
            </div>

            <div className="mt-5 rounded-xl bg-surface-container-low px-4 py-4">
              <p className="font-body text-label-sm uppercase tracking-[0.02em] text-outline">
                {t('document.import_detected_title_label')}
              </p>
              <p className="mt-1 font-display text-title-md text-on-surface">
                {review.suggestedTitle}
              </p>
              <p className="mt-2 font-body text-body-sm text-outline">
                {willKeepCurrentTitle
                  ? t('document.import_detected_title_keep_current')
                  : t('document.import_detected_title_use_suggestion')}
              </p>
            </div>

            {review.warnings.length > 0 && (
              <div className="mt-4 rounded-xl bg-error-container/20 px-4 py-4">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-on-error-container" aria-hidden="true" />
                  <div className="space-y-1 font-body text-body-sm text-on-error-container">
                    <p>{t('document.import_warning_title')}</p>
                    {review.warnings.includes('tables_ignored') && (
                      <p>{t('document.import_tables_ignored')}</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl bg-surface-container-low px-5 py-5">
            <p className="font-body text-label-sm uppercase tracking-[0.02em] text-outline">
              {t('document.import_review_next_title')}
            </p>
            <div className="mt-3 space-y-3">
              <div className="rounded-lg bg-surface-container-highest px-4 py-3">
                <p className="font-body text-body-sm text-on-surface">
                  {t('document.import_review_next_step_1')}
                </p>
              </div>
              <div className="rounded-lg bg-surface-container-highest px-4 py-3">
                <p className="font-body text-body-sm text-on-surface">
                  {t('document.import_review_next_step_2')}
                </p>
              </div>
              <div className="rounded-lg bg-surface-container-highest px-4 py-3">
                <p className="font-body text-body-sm text-on-surface">
                  {t('document.import_review_next_step_3')}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md bg-surface-container-highest px-5 py-2.5 font-body text-body-md text-on-surface transition-colors hover:bg-surface-container"
          >
            {t('document.cancel')}
          </button>
          <button
            ref={applyButtonRef}
            type="button"
            onClick={onApply}
            className="rounded-md bg-amendly-blue px-5 py-2.5 font-body text-body-md text-white transition-opacity hover:opacity-90"
          >
            {hasExistingBody
              ? t('document.import_review_apply_replace_cta')
              : t('document.import_review_apply_cta')}
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * Shared document import workflow used on create and edit screens.
 *
 * @param {{
 *   slug: string;
 *   currentTitle: string;
 *   currentBody: string;
 *   disabled?: boolean;
 *   onBusyChange?: ((busy: boolean) => void) | null;
 *   t: (key: string) => string;
 *   onApplyImport: (payload: {
 *     body: string;
 *     suggestedTitle: string;
 *     summary: {
 *       fileName: string;
 *       kind: 'docx' | 'pdf';
 *       charCount: number;
 *       headingCount: number;
 *       defaultSectionCount: number;
 *       warnings: string[];
 *     };
 *   }) => void;
 * }} props
 */
export default function DocumentImportWorkflow({
  slug,
  currentTitle,
  currentBody,
  disabled = false,
  onBusyChange = null,
  t,
  onApplyImport,
}) {
  const [importing, setImporting] = useState(false)
  const [importKind, setImportKind] = useState(null)
  const [importError, setImportError] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [review, setReview] = useState(null)
  const docxInputRef = useRef(null)
  const pdfInputRef = useRef(null)

  const hasExistingBody = useMemo(() => Boolean(currentBody.trim()), [currentBody])

  useEffect(() => {
    onBusyChange?.(importing || Boolean(review))
  }, [importing, review, onBusyChange])

  async function handleImport(file, kind) {
    const validationError = validateDocumentImportFile(file, kind, t)
    if (validationError) {
      setImportError(validationError)
      return
    }

    setImportError(null)
    setImportKind(kind)
    setImporting(true)
    setUploadProgress(0)

    try {
      const extractor = kind === 'docx' ? extractDocxFile : extractPdfFile
      const result = await extractor(slug, file, {
        onProgress: (pct) => {
          if (pct < 100) setUploadProgress(pct)
          else setUploadProgress('processing')
        },
      })

      const summary = summarizeImportedBody(result.html)
      setReview({
        kind,
        fileName: file.name,
        html: result.html,
        suggestedTitle: resolveImportedDocumentTitle(file.name, result.title),
        charCount: result.char_count,
        headingCount: summary.headingCount,
        defaultSectionCount: summary.defaultSectionCount,
        warnings: result.warnings ?? [],
      })
    } catch (error) {
      setImportError(error.message)
    } finally {
      setImporting(false)
      setImportKind(null)
      setUploadProgress(null)
    }
  }

  function handleFileChange(kind, event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    handleImport(file, kind)
  }

  function applyReviewedImport() {
    if (!review) return
    onApplyImport({
      body: review.html,
      suggestedTitle: review.suggestedTitle,
      summary: {
        fileName: review.fileName,
        kind: review.kind,
        charCount: review.charCount,
        headingCount: review.headingCount,
        defaultSectionCount: review.defaultSectionCount,
        warnings: review.warnings,
      },
    })
    setReview(null)
  }

  return (
    <>
      <div className="rounded-md bg-surface-container-low px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl space-y-2">
            <p className="font-body text-label-sm uppercase tracking-[0.02em] text-outline">
              {t('document.import_panel_eyebrow')}
            </p>
            <div className="flex items-center gap-2">
              <Upload className="h-4.5 w-4.5 text-amendly-blue" aria-hidden="true" />
              <h3 className="font-display text-title-md text-on-surface">
                {t('document.import_panel_title')}
              </h3>
            </div>
            <p className="font-body text-body-sm text-outline leading-relaxed">
              {t('document.import_panel_body')}
            </p>
          </div>
          {hasExistingBody && (
            <div className="rounded-full bg-surface-container-highest px-3 py-1.5 font-body text-label-sm text-on-surface">
              {t('document.import_panel_replace_badge')}
            </div>
          )}
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <button
            type="button"
            disabled={disabled || importing}
            onClick={() => docxInputRef.current?.click()}
            className="rounded-xl bg-surface px-4 py-4 text-left transition-colors hover:bg-surface-container-lowest disabled:cursor-not-allowed disabled:opacity-50"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-primary-fixed p-2 text-on-primary-fixed">
                <FileInput className="h-4.5 w-4.5" aria-hidden="true" />
              </div>
              <div className="space-y-1">
                <p className="font-body text-body-md font-semibold text-on-surface">
                  {importing && importKind === 'docx'
                    ? t('document.importing_docx')
                    : t('document.import_docx_card_title')}
                </p>
                <p className="font-body text-body-sm text-outline">
                  {t('document.import_docx_card_body')}
                </p>
              </div>
            </div>
          </button>

          <button
            type="button"
            disabled={disabled || importing}
            onClick={() => pdfInputRef.current?.click()}
            className="rounded-xl bg-surface px-4 py-4 text-left transition-colors hover:bg-surface-container-lowest disabled:cursor-not-allowed disabled:opacity-50"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-amendly-blue p-2 text-white">
                <FileUp className="h-4.5 w-4.5" aria-hidden="true" />
              </div>
              <div className="space-y-1">
                <p className="font-body text-body-md font-semibold text-on-surface">
                  {importing && importKind === 'pdf'
                    ? `${t('document.import_pdf')}...`
                    : t('document.import_pdf_card_title')}
                </p>
                <p className="font-body text-body-sm text-outline">
                  {t('document.import_pdf_card_body')}
                </p>
              </div>
            </div>
          </button>
        </div>

        <input
          ref={docxInputRef}
          type="file"
          accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(event) => handleFileChange('docx', event)}
        />
        <input
          ref={pdfInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={(event) => handleFileChange('pdf', event)}
        />

        {uploadProgress !== null && (
          <div className="mt-5 rounded-xl bg-surface px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-body text-body-sm font-semibold text-on-surface">
                  {uploadProgress === 'processing'
                    ? t('document.import_progress_processing_title')
                    : t('document.import_progress_upload_title')}
                </p>
                <p className="mt-1 font-body text-body-sm text-outline">
                  {uploadProgress === 'processing'
                    ? t('document.import_processing')
                    : t('document.import_progress_upload_body')}
                </p>
              </div>
              <span className="rounded-full bg-surface-container-highest px-3 py-1 font-body text-label-sm text-on-surface">
                {uploadProgress === 'processing' ? t('document.import_processing_badge') : `${uploadProgress}%`}
              </span>
            </div>

            <div className="mt-4 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
              {uploadProgress === 'processing' ? (
                <div className="h-full w-1/3 rounded-full bg-amendly-blue animate-[progress-slide_1.2s_ease-in-out_infinite]" />
              ) : (
                <div
                  className="h-full rounded-full bg-amendly-blue transition-[width] duration-150"
                  style={{ width: `${uploadProgress}%` }}
                />
              )}
            </div>
          </div>
        )}

        {importError && (
          <div className="mt-4 rounded-md bg-error-container/20 px-4 py-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-on-error-container" aria-hidden="true" />
              <p className="font-body text-body-sm text-on-error-container">{importError}</p>
            </div>
          </div>
        )}
      </div>

      {review && (
        <ImportReviewModal
          review={review}
          hasExistingBody={hasExistingBody}
          currentTitle={currentTitle}
          t={t}
          onApply={applyReviewedImport}
          onClose={() => setReview(null)}
        />
      )}
    </>
  )
}
