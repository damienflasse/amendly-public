import { useMemo } from 'react'
import {
  appendDocumentSection,
  autoProposeSectionsFromParagraphs,
  computeSectionNumbers,
  extractBodyBlocks,
  extractDocumentSections,
  insertDocumentSectionAfter,
  insertHeadingBeforeBlock,
  removeDocumentSection,
  renameDocumentSection,
} from '../lib/documentSections'

/**
 * Empty-state placeholder shared by the structure editors.
 *
 * @param {{ message: string; label: string; onClick: () => void }} props
 */
function EmptySectionCTA({ message, label, onClick }) {
  return (
    <div className="rounded-md bg-surface-container-low px-4 py-6 flex flex-col items-center gap-3 text-center">
      <p className="font-body text-body-sm text-outline">{message}</p>
      <button
        type="button"
        onClick={onClick}
        className="rounded-md bg-amendly-blue text-white px-4 py-2 font-body text-label-sm hover:opacity-90 transition-opacity"
      >
        {label}
      </button>
    </div>
  )
}

/**
 * Full-document structure editor for draft documents.
 *
 * @param {{
 *   body: string;
 *   onChange: (nextBody: string) => void;
 *   t: (key: string) => string;
 * }} props
 */
export function DocumentStructurer({ body, onChange, t }) {
  const blocks = useMemo(() => extractBodyBlocks(body), [body])
  const sections = useMemo(() => computeSectionNumbers(extractDocumentSections(body)), [body])

  const hasContent = blocks.length > 0
  const hasSections = sections.length > 0

  function handleInsertBefore(blockIndex) {
    onChange(
      insertHeadingBeforeBlock(body, blockIndex, {
        level: 'h2',
        title: t('document.section_editor_new_title'),
      })
    )
  }

  function handleRename(sectionId, nextTitle) {
    onChange(renameDocumentSection(body, sectionId, nextTitle))
  }

  function handleRemove(sectionId) {
    if (!window.confirm(t('document.section_editor_remove_confirm'))) return
    onChange(removeDocumentSection(body, sectionId))
  }

  function handleAddAtEnd() {
    onChange(
      appendDocumentSection(body, {
        level: sections.at(-1)?.level ?? 'h2',
        title: t('document.section_editor_new_title'),
      })
    )
  }

  function handleAutoPropose() {
    onChange(autoProposeSectionsFromParagraphs(body))
  }

  const CONTENT_TAGS = { p: 'P', ul: 'B', ol: '1.', blockquote: 'Q', hr: '-' }

  return (
    <div className="mt-4 rounded-md bg-surface p-5 ring-1 ring-surface-container-highest">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="space-y-1">
          <h3 className="font-display text-title-md text-on-surface">
            {t('document.structurer_title')}
          </h3>
          <p className="font-body text-body-sm text-outline leading-relaxed">
            {t('document.structurer_hint')}
          </p>
        </div>
        <button
          type="button"
          onClick={handleAddAtEnd}
          className="shrink-0 rounded-md bg-surface-container-highest px-3 py-1.5 font-body text-label-sm text-on-surface hover:bg-surface-container transition-colors"
        >
          {t('document.section_editor_add')}
        </button>
      </div>

      {hasContent && !hasSections && (
        <div className="mb-4 rounded-md bg-primary-fixed px-4 py-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-body text-body-sm text-on-primary-fixed leading-relaxed">
            {t('document.structurer_no_sections_hint')}
          </p>
          <button
            type="button"
            onClick={handleAutoPropose}
            className="shrink-0 rounded-md bg-amendly-blue text-white px-3 py-1.5 font-body text-label-sm hover:opacity-90 transition-opacity whitespace-nowrap"
          >
            {t('document.structurer_auto_propose') ?? '✦ Proposer des sections'}
          </button>
        </div>
      )}

      {!hasContent ? (
        <EmptySectionCTA
          message={t('document.section_editor_empty')}
          label={`+ ${t('document.section_editor_add')}`}
          onClick={handleAddAtEnd}
        />
      ) : (
        <div className="space-y-1.5">
          {blocks.map((block) => {
            const isHeading = block.tag === 'h2' || block.tag === 'h3'
            const isHr = block.tag === 'hr'

            if (isHr) {
              return (
                <div
                  key={block.index}
                  className="flex items-center gap-3 px-2 py-1 opacity-40"
                >
                  <span className="font-body text-label-sm text-outline">-</span>
                  <hr className="flex-1 h-px border-0 bg-surface-container-highest" />
                </div>
              )
            }

            if (isHeading) {
              const section = sections[block.sectionIndex]
              if (!section) return null

              return (
                <div
                  key={block.index}
                  className="flex items-center gap-2 rounded-md bg-surface-container-low px-3 py-2.5"
                >
                  <span className="shrink-0 rounded-full bg-amendly-blue text-white px-2 py-0.5 font-body text-label-sm min-w-[2rem] text-center">
                    {section.number}
                  </span>
                  <input
                    type="text"
                    value={section.text}
                    onChange={(e) => handleRename(section.id, e.target.value)}
                    placeholder={t('document.section_editor_name_placeholder')}
                    className="min-w-0 flex-1 rounded-md bg-surface px-3 py-1.5 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-secondary"
                  />
                  <button
                    type="button"
                    onClick={() => handleRemove(section.id)}
                    className="shrink-0 rounded-md bg-error-container/40 px-2.5 py-1.5 font-body text-label-sm text-on-error-container hover:opacity-90 transition-opacity"
                  >
                    {t('document.section_editor_remove')}
                  </button>
                </div>
              )
            }

            return (
              <div
                key={block.index}
                className="flex items-center gap-2 rounded-md bg-surface-container-low/50 px-3 py-2"
              >
                <span className="shrink-0 font-body text-label-sm text-outline w-5 text-center select-none">
                  {CONTENT_TAGS[block.tag] ?? 'P'}
                </span>
                <p className="flex-1 min-w-0 font-body text-body-sm text-outline truncate">
                  {block.text || <em>{t('document.structurer_empty_block')}</em>}
                </p>
                <button
                  type="button"
                  onClick={() => handleInsertBefore(block.index)}
                  className="shrink-0 rounded-md bg-surface-container-highest px-2.5 py-1.5 font-body text-label-sm text-on-surface hover:bg-surface-container transition-colors whitespace-nowrap"
                >
                  ^ {t('document.structurer_add_section_before')}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/**
 * Inline section management panel embedded in the document edit form.
 *
 * @param {{ body: string; onChange: (nextBody: string) => void; t: (key: string) => string }} props
 */
export function SectionManager({ body, onChange, t }) {
  const isHtmlBody = Boolean(body?.trimStart().startsWith('<'))
  const sections = useMemo(() => computeSectionNumbers(extractDocumentSections(body)), [body])

  function handleRename(sectionId, nextTitle) {
    onChange(renameDocumentSection(body, sectionId, nextTitle))
  }

  function handleAddAtEnd() {
    onChange(
      appendDocumentSection(body, {
        level: sections.at(-1)?.level ?? 'h2',
        title: t('document.section_editor_new_title'),
      })
    )
  }

  function handleAddAfter(sectionId, level) {
    onChange(
      insertDocumentSectionAfter(body, sectionId, {
        level,
        title: t('document.section_editor_new_title'),
      })
    )
  }

  function handleRemove(sectionId) {
    if (!window.confirm(t('document.section_editor_remove_confirm'))) return
    onChange(removeDocumentSection(body, sectionId))
  }

  return (
    <div className="mt-4 rounded-md bg-surface p-5 ring-1 ring-surface-container-highest">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h3 className="font-display text-title-md text-on-surface">
            {t('document.section_editor_title')}
          </h3>
          <p className="font-body text-body-sm text-outline leading-relaxed">
            {t('document.section_editor_hint')}
          </p>
        </div>
        <button
          type="button"
          onClick={handleAddAtEnd}
          className="shrink-0 rounded-md bg-surface-container-highest px-3 py-1.5 font-body text-label-sm text-on-surface hover:bg-surface-container transition-colors"
        >
          {t('document.section_editor_add')}
        </button>
      </div>

      {!isHtmlBody && (
        <p className="mt-4 rounded-md bg-surface-container-low px-4 py-3 font-body text-body-sm text-outline">
          {t('document.section_editor_plain_text_hint')}
        </p>
      )}

      {sections.length > 0 ? (
        <div className="mt-4 space-y-3">
          {sections.map((section) => (
            <div key={section.id} className="rounded-md bg-surface-container-low px-4 py-4">
              <div className="flex items-center gap-3">
                <span className="shrink-0 rounded-full bg-amendly-blue text-white px-2 py-0.5 font-body text-label-sm min-w-[2rem] text-center select-none">
                  {section.number}
                </span>
                <input
                  type="text"
                  value={section.text}
                  onChange={(e) => handleRename(section.id, e.target.value)}
                  placeholder={t('document.section_editor_name_placeholder')}
                  className="min-w-0 flex-1 rounded-md bg-surface px-3 py-2 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-secondary"
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => handleAddAfter(section.id, section.level)}
                  className="rounded-md bg-amendly-blue/10 px-3 py-1.5 font-body text-label-sm text-amendly-blue hover:bg-amendly-blue/20 transition-colors"
                >
                  + {t('document.section_editor_add_after')}
                </button>
                <button
                  type="button"
                  onClick={() => handleRemove(section.id)}
                  className="rounded-md bg-error-container/40 px-3 py-1.5 font-body text-label-sm text-on-error-container hover:opacity-90 transition-opacity"
                >
                  {t('document.section_editor_remove')}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4">
          <EmptySectionCTA
            message={t('document.section_editor_empty')}
            label={`+ ${t('document.section_editor_add')}`}
            onClick={handleAddAtEnd}
          />
        </div>
      )}
    </div>
  )
}
