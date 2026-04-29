import { useState } from 'react'
import { Link } from 'react-router-dom'
import { computeSectionNumbers } from '../../lib/documentSections'
import { sanitizeHtml } from '../../lib/sanitize'
import { escapeRegex } from './utils'

// ---------------------------------------------------------------------------
// Amendment position gutter
// ---------------------------------------------------------------------------

const DOT_COLOR = {
  pending: '#2563EB',
  accepted: '#393c55',
  rejected: '#752121',
}

// Cluster pins whose `top` values fall within CLUSTER_THRESHOLD px of each other.
const CLUSTER_THRESHOLD = 14

function clusterPins(pins) {
  if (pins.length === 0) return []
  const sorted = [...pins].sort((a, b) => a.top - b.top)
  const clusters = []
  let current = { top: sorted[0].top, pins: [sorted[0]] }
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].top - current.top < CLUSTER_THRESHOLD) {
      current.pins.push(sorted[i])
    } else {
      clusters.push(current)
      current = { top: sorted[i].top, pins: [sorted[i]] }
    }
  }
  clusters.push(current)
  return clusters
}

function GutterPin({ pin, onPinClick, t }) {
  const [tooltip, setTooltip] = useState(false)
  const { amendment, top } = pin
  const color = DOT_COLOR[amendment.status] ?? DOT_COLOR.pending
  const excerpt = (amendment.proposed_text ?? '').slice(0, 60)

  return (
    <div
      className="absolute right-0 -translate-y-1/2 pointer-events-auto"
      style={{ top: `${top}px` }}
    >
      <button
        type="button"
        className="block rounded-full cursor-pointer transition-transform hover:scale-150 focus:outline-none animate-pin-in"
        style={{ width: '7px', height: '7px', background: color }}
        onMouseEnter={() => setTooltip(true)}
        onMouseLeave={() => setTooltip(false)}
        onClick={() => onPinClick(amendment)}
        aria-label={t('document.gutter_pin_label').replace('{author}', amendment.author_name ?? '—')}
      />
      {tooltip && (
        <div
          className="absolute left-3 top-0 z-50 w-48 rounded-md px-3 py-2 pointer-events-none"
          style={{
            background: 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
          }}
        >
          <p className="font-body text-label-sm font-semibold text-on-surface truncate">
            {amendment.author_name ?? '—'}
          </p>
          {excerpt && (
            <p className="font-body text-label-sm text-outline mt-0.5 line-clamp-2">
              {excerpt}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function GutterCluster({ cluster, onPinClick, t }) {
  const [tooltip, setTooltip] = useState(false)
  const { top, pins } = cluster

  function handleClick() {
    for (const pin of pins) onPinClick(pin.amendment)
  }

  return (
    <div
      className="absolute right-0 -translate-y-1/2 pointer-events-auto"
      style={{ top: `${top}px` }}
    >
      <button
        type="button"
        className="flex items-center justify-center rounded-full cursor-pointer transition-transform hover:scale-125 focus:outline-none text-white animate-pin-in"
        style={{
          width: '14px',
          height: '14px',
          background: '#2563eb',
          fontSize: '8px',
          fontWeight: 700,
          lineHeight: 1,
          fontFamily: 'Inter, sans-serif',
        }}
        onMouseEnter={() => setTooltip(true)}
        onMouseLeave={() => setTooltip(false)}
        onClick={handleClick}
        aria-label={t('document.gutter_cluster_label').replace('{n}', pins.length)}
      >
        {pins.length}
      </button>
      {tooltip && (
        <div
          className="absolute left-4 top-0 z-50 w-48 rounded-md px-3 py-2 pointer-events-none"
          style={{
            background: 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
          }}
        >
          {pins.slice(0, 3).map((pin) => (
            <p key={pin.amendment.id} className="font-body text-label-sm font-semibold text-on-surface truncate">
              {pin.amendment.author_name ?? '—'}
            </p>
          ))}
          {pins.length > 3 && (
            <p className="font-body text-label-sm text-outline mt-0.5">
              +{pins.length - 3}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function AmendmentGutter({ pins, onPinClick, t }) {
  if (pins.length === 0) return null
  const clusters = clusterPins(pins)
  return (
    <div
      aria-hidden="true"
      className="absolute top-0 bottom-0 overflow-visible pointer-events-none"
      style={{ right: '100%', width: '20px' }}
    >
      {clusters.map((cluster) =>
        cluster.pins.length === 1
          ? <GutterPin key={cluster.pins[0].amendment.id} pin={cluster.pins[0]} onPinClick={onPinClick} t={t} />
          : <GutterCluster key={`cluster-${cluster.top}`} cluster={cluster} onPinClick={onPinClick} t={t} />
      )}
    </div>
  )
}

export function DocumentContentPane({
  slug,
  docId,
  doc,
  canModerate,
  isOpen,
  orgPlan,
  amendTotal,
  contributorToken,
  headings,
  selectedSectionId,
  showEditForm,
  showConsolidated,
  showBackToTop,
  docSearchOpen,
  docSearchQuery,
  docSearchIdx,
  docSearchTotal,
  wordCount,
  highlightedBody,
  processedBody,
  leftPaneRef,
  docBodyRef,
  editFormRef,
  docSearchInputRef,
  gutterPins,
  visibleAmendments,
  onGutterPinClick,
  SectionToc,
  StatusToggle,
  DocStatusBadge,
  ExportMenu,
  ShareContributionLink,
  EditDocumentForm,
  ConsolidatedPanel,
  handleLeftPaneScroll,
  handleDocStatusUpdated,
  handleDocumentClick,
  handleDocumentSelection,
  handleDocSaved,
  handleSelectSection,
  moveDocSearch,
  scrollLeftPaneToTop,
  setDocSearchOpen,
  setDocSearchQuery,
  setDocSearchIdx,
  setShowEditForm,
  setShowConsolidated,
  setContributorToken,
  setDoc,
  t,
}) {
  return (
    <div className="flex-[3] min-w-0 overflow-y-auto" ref={leftPaneRef} onScroll={handleLeftPaneScroll}>
      {headings.length > 0 && (
        <SectionToc
          headings={headings}
          selectedSectionId={selectedSectionId}
          onSelectSection={handleSelectSection}
          t={t}
        />
      )}

      {docSearchOpen && (
        <div className="sticky top-0 z-20 bg-surface-container-low px-8 py-2.5 flex items-center gap-3 shadow-sm">
          <input
            ref={docSearchInputRef}
            type="search"
            value={docSearchQuery}
            onChange={(event) => {
              setDocSearchQuery(event.target.value)
              setDocSearchIdx(0)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') moveDocSearch(event.shiftKey ? -1 : 1)
              if (event.key === 'Escape') setDocSearchOpen(false)
            }}
            placeholder={t('document.doc_search_placeholder')}
            className="flex-1 bg-surface rounded-md px-4 py-1.5 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
          />
          {docSearchQuery.trim() && (
            <>
              <span className="font-body text-label-sm text-outline whitespace-nowrap shrink-0">
                {docSearchTotal > 0
                  ? t('document.search_count')
                      .replace('{current}', ((docSearchIdx % docSearchTotal + docSearchTotal) % docSearchTotal) + 1)
                      .replace('{total}', docSearchTotal)
                  : '0'}
              </span>
              <button
                type="button"
                onClick={() => moveDocSearch(-1)}
                aria-label="Previous match"
                className="px-2 py-1 bg-surface-container-highest text-on-surface rounded font-body text-body-md hover:bg-surface-container transition-colors disabled:opacity-40"
                disabled={docSearchTotal === 0}
              >
                ▲
              </button>
              <button
                type="button"
                onClick={() => moveDocSearch(1)}
                aria-label="Next match"
                className="px-2 py-1 bg-surface-container-highest text-on-surface rounded font-body text-body-md hover:bg-surface-container transition-colors disabled:opacity-40"
                disabled={docSearchTotal === 0}
              >
                ▼
              </button>
            </>
          )}
          <button
            type="button"
            onClick={() => setDocSearchOpen(false)}
            className="shrink-0 font-body text-label-sm text-outline hover:text-on-surface transition-colors px-2 py-1"
          >
            {t('document.search_close')}
          </button>
        </div>
      )}

      <div className="px-8 py-10 space-y-8">
        <section>
          <div className="flex items-center justify-end gap-4 mb-6">
            <button
              type="button"
              onClick={() => setDocSearchOpen((value) => !value)}
              className={[
                'font-body text-body-md hover:underline transition-colors',
                docSearchOpen ? 'text-on-surface font-medium' : 'text-secondary',
              ].join(' ')}
            >
              {t('document.search_in_doc')}
            </button>
            {canModerate ? (
              <StatusToggle
                slug={slug}
                docId={docId}
                current={doc?.status ?? 'draft'}
                onUpdated={handleDocStatusUpdated}
                t={t}
              />
            ) : (
              <DocStatusBadge status={doc?.status} />
            )}
            {canModerate && !showEditForm && amendTotal === 0 && (
              <button
                type="button"
                onClick={() => setShowEditForm(true)}
                className="px-3 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-label-sm hover:bg-surface-container transition-colors"
              >
                {t('document.edit')}
              </button>
            )}
            {canModerate && (
              <ExportMenu slug={slug} docId={docId} orgPlan={orgPlan} t={t} />
            )}
            {canModerate && isOpen && orgPlan !== 'solo' && (
              <ShareContributionLink
                slug={slug}
                docId={docId}
                token={contributorToken}
                linkStatus={doc?.contributor_link_status ?? 'revoked'}
                expiresAt={doc?.contributor_token_expires_at ?? null}
                onChange={(result) => {
                  setContributorToken(result.token ?? null)
                  setDoc((previous) => (
                    previous
                      ? {
                          ...previous,
                          contributor_token: result.token ?? null,
                          contributor_token_created_at: result.created_at ?? null,
                          contributor_token_expires_at: result.expires_at ?? null,
                          contributor_link_status: result.status,
                        }
                      : previous
                  ))
                }}
                t={t}
              />
            )}
            {canModerate && (
              <Link
                to={`/orgs/${slug}/documents/${docId}/review`}
                className="px-4 py-1.5 bg-amendly-blue text-white rounded-md font-body text-body-md hover:opacity-90 transition-opacity"
              >
                {t('document.review_export')}
              </Link>
            )}
          </div>

          <h1 className="font-display text-display-md text-on-surface tracking-[-0.02em] mb-6">
            {doc?.title}
          </h1>

          <div className={showEditForm ? 'hidden' : undefined}>
            {wordCount > 0 && (
              <p className="mb-4 font-body text-label-sm text-outline">
                {t('document.word_count').replace('{n}', wordCount.toLocaleString())}
              </p>
            )}

            {doc?.body ? (
              <div className="relative">
                <AmendmentGutter pins={gutterPins} onPinClick={onGutterPinClick} t={t} />
                <div
                  ref={docBodyRef}
                  onClick={handleDocumentClick}
                  onMouseUp={handleDocumentSelection}
                  className="bg-surface-container-lowest rounded-md shadow-ambient p-8"
                >
                {doc.body.trimStart().startsWith('<') ? (
                  <div
                    className="doc-body font-body text-body-md text-on-surface leading-relaxed
                      [&_h2]:cursor-pointer [&_h2]:font-display [&_h2]:text-headline-sm [&_h2]:mt-8 [&_h2]:mb-3
                      [&_h3]:cursor-pointer [&_h3]:font-display [&_h3]:text-title-md [&_h3]:mt-6 [&_h3]:mb-2
                      [&_p]:my-0 [&_p+p]:mt-4
                      [&_ul]:my-4 [&_ul]:pl-5 [&_ul]:list-disc
                      [&_ol]:my-4 [&_ol]:pl-5 [&_ol]:list-decimal
                      [&_li]:my-1
                      [&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-amendly-blue
                      [&_blockquote]:pl-4 [&_blockquote]:text-outline [&_blockquote]:italic
                      [&_hr]:my-6 [&_hr]:h-px [&_hr]:border-0 [&_hr]:bg-surface-container-highest
                      [&_strong]:font-semibold [&_em]:italic"
                    dangerouslySetInnerHTML={{
                      __html: docSearchQuery.trim() && highlightedBody
                        ? highlightedBody
                        : sanitizeHtml(processedBody),
                    }}
                  />
                ) : (
                  docSearchOpen && docSearchQuery.trim() ? (
                    <pre className="font-body text-body-md text-on-surface whitespace-pre-wrap">
                      {doc.body.split(new RegExp(`(${escapeRegex(docSearchQuery.trim())})`, 'gi')).map((part, index) =>
                        part.toLowerCase() === docSearchQuery.trim().toLowerCase()
                          ? <mark key={index} className="doc-search-mark" style={{ background: '#fef08a', color: '#713f12', borderRadius: '2px', padding: '0 1px' }}>{part}</mark>
                          : part
                      )}
                    </pre>
                  ) : (
                    <pre className="font-body text-body-md text-on-surface whitespace-pre-wrap">
                      {doc.body}
                    </pre>
                  )
                )}
                </div>
              </div>
            ) : (
              <div className="bg-surface-container-low rounded-md p-12 text-center">
                <p className="font-body text-body-md text-outline">{t('document.no_body')}</p>
                {canModerate && !showEditForm && (
                  <button
                    type="button"
                    onClick={() => setShowEditForm(true)}
                    className="mt-4 font-body text-body-md text-secondary hover:underline"
                  >
                    {t('document.add_body')}
                  </button>
                )}
              </div>
            )}
          </div>

          {showEditForm && (
            <div ref={editFormRef}>
              <EditDocumentForm
                slug={slug}
                docId={docId}
                docStatus={doc?.status ?? 'draft'}
                initial={{ title: doc?.title, body: doc?.body ?? '' }}
                onSaved={handleDocSaved}
                onCancel={() => setShowEditForm(false)}
                t={t}
              />
            </div>
          )}
        </section>

        {showConsolidated && (
          <ConsolidatedPanel
            slug={slug}
            docId={docId}
            onClose={() => setShowConsolidated(false)}
            t={t}
          />
        )}
      </div>

      {showBackToTop && (
        <div className="sticky bottom-8 flex justify-end pr-8 pointer-events-none">
          <button
            type="button"
            onClick={scrollLeftPaneToTop}
            aria-label={t('document.back_to_top')}
            className="pointer-events-auto flex items-center gap-2 px-4 py-2 bg-surface-container-lowest shadow-ambient rounded-full font-body text-label-sm text-on-surface hover:bg-surface-container transition-colors"
          >
            ↑ {t('document.back_to_top')}
          </button>
        </div>
      )}
    </div>
  )
}

export function DocumentAmendmentsPane({
  slug,
  docId,
  doc,
  headings,
  numberedHeadings,
  selectedSection,
  selectedSectionId,
  selectedSnippet,
  amendments,
  visibleAmendments,
  groupedAmendments,
  expandedAmendmentIds,
  selectedIds,
  amendTotal,
  amendPage,
  amendTotalPages,
  filterStatus,
  filterType,
  filterSection,
  sortOrder,
  searchQuery,
  composerType,
  composerOriginalText,
  composerProposedText,
  composerJustification,
  composerError,
  composerSubmitting,
  canModerate,
  canPropose,
  hasReactionPlan,
  bulkActing,
  orgPlan,
  rightPaneRef,
  leftPaneRef,
  docBodyRef,
  sectionGroupRefs,
  composerProposedRef,
  ReactionSummary,
  AmendmentCard,
  activeAmendmentId,
  lockedAmendmentId,
  setLockedAmendmentId,
  currentUserId,
  clearSelectedSnippet,
  handleSelectSection,
  handleComposerSubmit,
  handleToggleSelect,
  handleAmendmentStatus,
  handleWithdraw,
  handleReact,
  handleBulkAction,
  setShowConsolidated,
  setSelectedSectionId,
  setComposerType,
  setComposerOriginalText,
  setComposerProposedText,
  setComposerJustification,
  setFilterStatus,
  setFilterType,
  setFilterSection,
  setSearchQuery,
  setExpandedAmendmentIds,
  setSelectedIds,
  setAmendPage,
  t,
}) {
  return (
    <div ref={rightPaneRef} className="flex-[2] min-w-[360px] max-w-[600px] shrink-0 bg-surface-container-low overflow-y-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('document.amendments')}
          {amendTotal > 0 && (
            <span className="ml-3 font-body text-body-md text-outline">{amendTotal}</span>
          )}
        </h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowConsolidated(true)}
            className="px-3 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-label-sm hover:bg-surface-container transition-colors"
          >
            {t('document.view_consolidated')}
          </button>
          {canPropose && (
            <Link
              to={`/orgs/${slug}/documents/${docId}/contribute`}
              className="px-3 py-1.5 bg-surface-container-highest text-on-surface rounded-md font-body text-label-sm hover:bg-surface-container transition-colors"
            >
              {t('document.propose_amendment')}
            </Link>
          )}
        </div>
      </div>

      {canModerate && hasReactionPlan && (
        <ReactionSummary slug={slug} docId={docId} t={t} />
      )}

      {canPropose && (
        <div className="mb-6 rounded-md bg-surface-container-lowest p-5 shadow-ambient">
          <div className="space-y-2">
            <p className="font-body text-label-sm uppercase tracking-[0.02em] text-outline">
              {t('document.compose_heading')}
            </p>
            {headings.length > 0 ? (
              <select
                value={selectedSectionId ?? ''}
                onChange={(event) => {
                  const value = event.target.value
                  if (value) handleSelectSection(value, { scrollGroup: false })
                  else setSelectedSectionId(null)
                }}
                className="w-full bg-surface rounded-md px-3 py-2 font-body text-body-md text-on-surface ring-1 ring-surface-container-highest focus:outline-none focus:ring-2 focus:ring-secondary"
              >
                <option value="">{t('document.compose_select_prompt') ?? '— Choisir une section —'}</option>
                {numberedHeadings.map((heading) => (
                  <option key={heading.id} value={heading.id}>
                    {heading.level === 'h3' ? '\u00A0\u00A0' : ''}{heading.number} — {heading.text}
                  </option>
                ))}
              </select>
            ) : (
              <p className="font-body text-body-sm text-outline">
                {t('document.compose_no_sections') ?? 'Aucune section dans ce document.'}
              </p>
            )}
          </div>

          {selectedSnippet && (
            <div className="mt-4 rounded-md bg-primary-container px-4 py-3">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-body text-label-sm uppercase tracking-[0.02em] text-on-primary-container/75">
                    {t('document.compose_selection_label')}
                  </p>
                  <p className="mt-1 font-body text-body-sm text-on-primary-container leading-relaxed">
                    {selectedSnippet.length > 180 ? `${selectedSnippet.slice(0, 180)}…` : selectedSnippet}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={clearSelectedSnippet}
                  className="shrink-0 font-body text-label-sm text-on-primary-container underline decoration-transparent hover:decoration-current"
                >
                  {t('document.compose_clear_selection')}
                </button>
              </div>
            </div>
          )}

          <form onSubmit={handleComposerSubmit} className="mt-5 space-y-4">
            <div className="flex rounded-md overflow-hidden ring-1 ring-surface-container-highest">
              <button
                type="button"
                onClick={() => setComposerType('text_change')}
                className={[
                  'flex-1 px-4 py-2 font-body text-body-sm transition-colors',
                  composerType === 'text_change'
                    ? 'bg-amendly-blue text-white'
                    : 'bg-surface text-on-surface hover:bg-surface-container',
                ].join(' ')}
              >
                {t('document.type_text_change')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setComposerType('general_comment')
                  clearSelectedSnippet()
                }}
                className={[
                  'flex-1 px-4 py-2 font-body text-body-sm transition-colors',
                  composerType === 'general_comment'
                    ? 'bg-amendly-blue text-white'
                    : 'bg-surface text-on-surface hover:bg-surface-container',
                ].join(' ')}
              >
                {t('document.type_general_comment')}
              </button>
            </div>

            {composerType === 'text_change' && (
              <>
                {!selectedSnippet && (
                  <p className="font-body text-label-sm text-outline italic">
                    {t('document.compose_text_selection_hint') ?? 'Sélectionnez du texte dans le document (à gauche) pour pré-remplir le champ ci-dessous.'}
                  </p>
                )}
                <div>
                  <label className="mb-2 block font-body text-label-sm uppercase tracking-[0.02em] text-outline">
                    {t('document.original_text_label')}
                  </label>
                  <textarea
                    value={composerOriginalText}
                    onChange={(event) => setComposerOriginalText(event.target.value)}
                    rows={4}
                    placeholder={t('document.original_text_placeholder')}
                    className="w-full rounded-md bg-surface px-4 py-3 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-secondary"
                  />
                </div>
                <div>
                  <label className="mb-2 block font-body text-label-sm uppercase tracking-[0.02em] text-outline">
                    {t('document.proposed_text_label')}
                  </label>
                  <textarea
                    ref={composerProposedRef}
                    value={composerProposedText}
                    onChange={(event) => setComposerProposedText(event.target.value)}
                    rows={4}
                    placeholder={t('document.proposed_text_placeholder')}
                    className="w-full rounded-md bg-surface px-4 py-3 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-secondary"
                  />
                </div>
              </>
            )}

            <div>
              <label className="mb-2 block font-body text-label-sm uppercase tracking-[0.02em] text-outline">
                {composerType === 'general_comment'
                  ? t('document.comment_label')
                  : t('document.justification_label')}
              </label>
              <textarea
                value={composerJustification}
                onChange={(event) => setComposerJustification(event.target.value)}
                rows={composerType === 'general_comment' ? 5 : 3}
                placeholder={
                  composerType === 'general_comment'
                    ? t('document.comment_placeholder')
                    : t('document.justification_placeholder')
                }
                className="w-full rounded-md bg-surface px-4 py-3 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-secondary"
              />
            </div>

            {composerError && (
              <p className="rounded-md bg-error-container/40 px-4 py-2 font-body text-body-sm text-on-error-container">
                {composerError}
              </p>
            )}

            <button
              type="submit"
              disabled={composerSubmitting}
              className="w-full rounded-md bg-amendly-blue px-4 py-3 font-body text-body-md font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {composerSubmitting ? t('document.submitting') : t('document.submit_amendment')}
            </button>
          </form>
        </div>
      )}

      {amendments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label={t('document.filter_status_label')}>
          {[
            { value: 'all', label: t('document.filter_all_statuses'), count: amendments.length },
            { value: 'pending', label: t('document.filter_pending'), count: amendments.filter((amendment) => amendment.status === 'pending').length },
            { value: 'accepted', label: t('document.filter_accepted'), count: amendments.filter((amendment) => amendment.status === 'accepted').length },
            { value: 'rejected', label: t('document.filter_rejected'), count: amendments.filter((amendment) => amendment.status === 'rejected').length },
          ].map(({ value, label, count }) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilterStatus(value)}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-body text-label-sm transition-colors ${
                filterStatus === value
                  ? 'bg-amendly-blue text-white'
                  : 'bg-surface-container-highest text-on-surface hover:bg-surface-container'
              }`}
            >
              {label}
              <span className={`font-body text-label-sm ${filterStatus === value ? 'opacity-75' : 'text-outline'}`}>
                {count}
              </span>
            </button>
          ))}
        </div>
      )}

      {amendments.length > 0 && (
        <div className="relative mb-4">
          <input
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={t('document.search_placeholder')}
            aria-label={t('document.search_placeholder')}
            className="w-full bg-surface-container-highest text-on-surface rounded-md pl-4 pr-9 py-2 font-body text-body-md placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              aria-label={t('document.search_clear')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-outline hover:text-on-surface transition-colors text-sm leading-none"
            >
              ✕
            </button>
          )}
        </div>
      )}

      {amendments.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <select
            value={filterStatus}
            onChange={(event) => setFilterStatus(event.target.value)}
            aria-label={t('document.filter_status_label')}
            className="bg-surface-container-highest text-on-surface rounded-md px-3 py-1.5 font-body text-label-sm tracking-[0.02em] focus:outline-none focus:ring-2 focus:ring-secondary cursor-pointer"
          >
            <option value="all">{t('document.filter_all_statuses')}</option>
            <option value="pending">{t('document.filter_pending')}</option>
            <option value="accepted">{t('document.filter_accepted')}</option>
            <option value="rejected">{t('document.filter_rejected')}</option>
            <option value="withdrawn">{t('document.filter_withdrawn')}</option>
          </select>
          <select
            value={filterType}
            onChange={(event) => setFilterType(event.target.value)}
            aria-label={t('document.filter_type_label')}
            className="bg-surface-container-highest text-on-surface rounded-md px-3 py-1.5 font-body text-label-sm tracking-[0.02em] focus:outline-none focus:ring-2 focus:ring-secondary cursor-pointer"
          >
            <option value="all">{t('document.filter_all_types')}</option>
            <option value="text_change">{t('document.type_text_change')}</option>
            <option value="general_comment">{t('document.type_general_comment')}</option>
          </select>
          <select
            value={sortOrder}
            onChange={(event) => setSortOrder(event.target.value)}
            aria-label={t('document.sort_label')}
            className="bg-surface-container-highest text-on-surface rounded-md px-3 py-1.5 font-body text-label-sm tracking-[0.02em] focus:outline-none focus:ring-2 focus:ring-secondary cursor-pointer"
          >
            <option value="newest">{t('document.sort_newest')}</option>
            <option value="oldest">{t('document.sort_oldest')}</option>
          </select>
          {headings.length > 0 && (
            <select
              value={filterSection}
              onChange={(event) => setFilterSection(event.target.value)}
              aria-label={t('document.filter_section_label')}
              className="bg-surface-container-highest text-on-surface rounded-md px-3 py-1.5 font-body text-label-sm tracking-[0.02em] focus:outline-none focus:ring-2 focus:ring-secondary cursor-pointer"
            >
              <option value="all">{t('document.filter_all_sections')}</option>
              {computeSectionNumbers(headings).map((heading) => (
                <option key={heading.id} value={heading.text}>
                  {heading.number} {heading.text}
                </option>
              ))}
              <option value="__unsectioned__">{t('document.unsectioned_group')}</option>
            </select>
          )}
          {(filterStatus !== 'all' || filterType !== 'all' || filterSection !== 'all' || searchQuery) && (
            <button
              type="button"
              onClick={() => {
                setFilterStatus('all')
                setFilterType('all')
                setFilterSection('all')
                setSearchQuery('')
              }}
              className="font-body text-label-sm text-secondary hover:underline"
            >
              {t('document.filter_clear')}
            </button>
          )}
        </div>
      )}

      {visibleAmendments.length > 0 && (
        <div className="flex items-center gap-4 mb-4 justify-end">
          <button
            type="button"
            onClick={() => setExpandedAmendmentIds(new Set(visibleAmendments.map((amendment) => amendment.id)))}
            className="inline-flex items-center rounded-md bg-surface-container-highest px-4 py-2 font-body text-label-sm tracking-[0.02em] text-on-surface transition-colors hover:bg-surface-container focus:outline-none focus:ring-2 focus:ring-secondary"
          >
            {t('document.expand_all')}
          </button>
          <button
            type="button"
            onClick={() => setExpandedAmendmentIds(new Set())}
            className="inline-flex items-center rounded-md bg-surface-container-highest px-4 py-2 font-body text-label-sm tracking-[0.02em] text-on-surface transition-colors hover:bg-surface-container focus:outline-none focus:ring-2 focus:ring-secondary disabled:cursor-not-allowed disabled:opacity-50"
            disabled={expandedAmendmentIds.size === 0}
          >
            {t('document.collapse_all')}
          </button>
        </div>
      )}

      {!canPropose && doc?.status === 'draft' && (
        <div className="mb-6 rounded-md bg-surface-container-highest px-5 py-4 space-y-1">
          <p className="font-body text-body-md text-on-surface">{t('document.draft_banner')}</p>
          {canModerate && (
            <p className="font-body text-label-sm text-outline">{t('document.draft_banner_hint')}</p>
          )}
        </div>
      )}
      {!canPropose && doc?.status === 'closed' && (
        <div className="mb-6 rounded-md bg-surface-container-highest px-5 py-4">
          <p className="font-body text-body-md text-on-surface">{t('document.closed_banner')}</p>
        </div>
      )}

      {canModerate && selectedIds.size > 0 && (
        <div className="flex items-center gap-3 mb-4 px-4 py-3 bg-surface-container-highest rounded-md">
          <span className="font-body text-label-sm text-outline tracking-[0.02em]">
            {t('document.bulk_selected').replace('{n}', selectedIds.size)}
          </span>
          <div className="flex items-center gap-2 ml-auto">
            <button
              type="button"
              disabled={bulkActing}
              onClick={() => handleBulkAction('accepted')}
              className="px-4 py-1.5 bg-tertiary-fixed text-on-tertiary-fixed rounded-md font-body text-body-md disabled:opacity-50"
            >
              {bulkActing ? t('document.bulk_acting') : t('document.bulk_accept_all')}
            </button>
            <button
              type="button"
              disabled={bulkActing}
              onClick={() => handleBulkAction('rejected')}
              className="px-4 py-1.5 bg-error-container/40 text-on-error-container rounded-md font-body text-body-md disabled:opacity-50"
            >
              {bulkActing ? t('document.bulk_acting') : t('document.bulk_reject_all')}
            </button>
            <button
              type="button"
              disabled={bulkActing}
              onClick={() => setSelectedIds(new Set())}
              className="font-body text-label-sm text-outline hover:text-on-surface transition-colors"
            >
              {t('document.bulk_clear')}
            </button>
          </div>
        </div>
      )}

      {visibleAmendments.length > 0 ? (
        <div className="space-y-6">
          {groupedAmendments.map((group) => (
            <section
              key={group.key}
              ref={(node) => {
                if (group.sectionId && node) sectionGroupRefs.current.set(group.sectionId, node)
                else if (group.sectionId) sectionGroupRefs.current.delete(group.sectionId)
              }}
              className="space-y-3"
            >
              <div
                className={[
                  'sticky top-0 z-[1] flex items-center justify-between rounded-md px-4 py-3',
                  selectedSection?.id === group.sectionId
                    ? 'bg-primary-container'
                    : 'bg-surface-container-highest',
                ].join(' ')}
              >
                <div>
                  <p className="font-display text-title-sm text-on-surface">
                    {group.label}
                  </p>
                  <p className="font-body text-label-sm text-outline">
                    {group.items.length}
                  </p>
                </div>
                {group.sectionId && (
                  <button
                    type="button"
                    onClick={() => {
                      handleSelectSection(group.sectionId, { scrollGroup: false })
                      rightPaneRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
                    }}
                    className="font-body text-label-sm text-secondary hover:underline"
                  >
                    {t('document.compose_heading')}
                  </button>
                )}
              </div>

              <div className="space-y-4">
                {group.items.map((amendment) => (
                  <AmendmentCard
                    key={amendment.id}
                    slug={slug}
                    docId={docId}
                    amendment={amendment}
                    isActive={activeAmendmentId === amendment.id}
                    isLocked={lockedAmendmentId === amendment.id}
                    onLock={setLockedAmendmentId}
                    canModerate={canModerate}
                    currentUserId={currentUserId}
                    orgPlan={orgPlan}
                    isSelected={selectedIds.has(amendment.id)}
                    isExpanded={expandedAmendmentIds.has(amendment.id)}
                    onToggleSelect={handleToggleSelect}
                    onAccept={(amendmentId, reason) => handleAmendmentStatus(amendmentId, 'accepted', reason)}
                    onReject={(amendmentId, reason) => handleAmendmentStatus(amendmentId, 'rejected', reason)}
                    onWithdraw={handleWithdraw}
                    onReact={handleReact}
                    onToggleThread={() => setExpandedAmendmentIds((previous) => {
                      const next = new Set(previous)
                      if (next.has(amendment.id)) next.delete(amendment.id)
                      else next.add(amendment.id)
                      return next
                    })}
                    leftPaneRef={leftPaneRef}
                    docBodyRef={docBodyRef}
                    t={t}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="bg-surface-container rounded-md p-10 text-center flex flex-col items-center gap-4">
          {amendments.length === 0 ? (
            <>
              <svg
                width="64"
                height="64"
                viewBox="0 0 64 64"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <rect x="10" y="6" width="32" height="44" rx="4" stroke="#94a3b8" strokeWidth="2.5"/>
                <line x1="18" y1="18" x2="34" y2="18" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round"/>
                <line x1="18" y1="26" x2="34" y2="26" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round"/>
                <line x1="18" y1="34" x2="28" y2="34" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="48" cy="48" r="10" fill="#2563EB"/>
                <line x1="48" y1="43" x2="48" y2="53" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
                <line x1="43" y1="48" x2="53" y2="48" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
              <p className="font-body text-body-md text-outline">{t('document.no_amendments')}</p>
              {canPropose && (
                <p className="font-body text-body-sm text-outline">
                  {t('document.compose_select_prompt')}
                </p>
              )}
            </>
          ) : (
            <>
              <p className="font-body text-body-md text-outline">{t('document.no_amendments_filtered')}</p>
              <button
                type="button"
                onClick={() => {
                  setFilterStatus('all')
                  setFilterType('all')
                  setSearchQuery('')
                }}
                className="font-body text-body-md text-secondary hover:underline"
              >
                {t('document.filter_clear')}
              </button>
            </>
          )}
        </div>
      )}

      {amendTotalPages > 1 && (
        <div className="flex items-center gap-4 mt-8 justify-center">
          <button
            type="button"
            disabled={amendPage === 1}
            onClick={() => setAmendPage((page) => page - 1)}
            className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md disabled:opacity-40"
          >
            {t('document.previous')}
          </button>
          <span className="font-body text-body-md text-outline">
            {t('document.page_of').replace('{page}', amendPage).replace('{total}', amendTotalPages)}
          </span>
          <button
            type="button"
            disabled={amendPage === amendTotalPages}
            onClick={() => setAmendPage((page) => page + 1)}
            className="px-4 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md disabled:opacity-40"
          >
            {t('document.next')}
          </button>
        </div>
      )}
    </div>
  )
}
