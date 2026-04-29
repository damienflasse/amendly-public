import { useCallback, useEffect, useMemo, useState } from 'react'
import { computeSectionNumbers, normalizeSectionKey } from '../../lib/documentSections'
import {
  extractHeadings,
  findTextOffsetTopInContainer,
  groupAmendmentsBySection,
  highlightHtml,
  injectHeadingIds,
} from './utils'

export function useDocumentBodyState(docBody, docSearchQuery) {
  const headings = useMemo(() => {
    if (!docBody || !docBody.trimStart().startsWith('<')) return []
    return extractHeadings(docBody)
  }, [docBody])

  const wordCount = useMemo(() => {
    if (!docBody) return 0
    let text = docBody
    if (text.trimStart().startsWith('<')) {
      text = text.replace(/<[^>]*>/g, ' ')
    }
    return text.trim().split(/\s+/).filter(Boolean).length
  }, [docBody])

  const processedBody = useMemo(() => {
    if (!docBody || !docBody.trimStart().startsWith('<')) return docBody ?? null
    return injectHeadingIds(docBody)
  }, [docBody])

  const highlightedBody = useMemo(() => {
    if (!processedBody || !docSearchQuery.trim()) return null
    return highlightHtml(processedBody, docSearchQuery)
  }, [processedBody, docSearchQuery])

  const numberedHeadings = useMemo(() => computeSectionNumbers(headings), [headings])

  return {
    headings,
    highlightedBody,
    numberedHeadings,
    processedBody,
    wordCount,
  }
}

export function useVisibleAmendments({
  amendments,
  filterSection,
  filterStatus,
  filterType,
  debouncedSearch,
  sortOrder,
  headings,
  t,
}) {
  const visibleAmendments = useMemo(() => {
    let visible = amendments
    if (filterStatus !== 'all') visible = visible.filter((amendment) => amendment.status === filterStatus)
    if (filterType !== 'all') visible = visible.filter((amendment) => amendment.amendment_type === filterType)
    if (filterSection !== 'all') {
      if (filterSection === '__unsectioned__') {
        visible = visible.filter((amendment) => !amendment.section || !amendment.section.trim())
      } else {
        visible = visible.filter(
          (amendment) => normalizeSectionKey(amendment.section) === normalizeSectionKey(filterSection)
        )
      }
    }
    if (debouncedSearch) {
      const query = debouncedSearch.toLowerCase()
      visible = visible.filter((amendment) =>
        (amendment.original_text ?? '').toLowerCase().includes(query) ||
        (amendment.proposed_text ?? '').toLowerCase().includes(query) ||
        (amendment.justification ?? '').toLowerCase().includes(query) ||
        (amendment.section ?? '').toLowerCase().includes(query) ||
        (amendment.author_name ?? '').toLowerCase().includes(query) ||
        (amendment.author_email ?? '').toLowerCase().includes(query)
      )
    }
    return sortOrder === 'newest' ? [...visible].reverse() : visible
  }, [
    amendments,
    debouncedSearch,
    filterSection,
    filterStatus,
    filterType,
    sortOrder,
  ])

  const groupedAmendments = useMemo(
    () => groupAmendmentsBySection(visibleAmendments, headings, t('document.unsectioned_group')),
    [headings, t, visibleAmendments]
  )

  return { groupedAmendments, visibleAmendments }
}

/**
 * Computes gutter pin positions for each visible amendment that has
 * `original_text` located in the rendered HTML body.
 *
 * Only active when the document body contains a `.doc-body` element (i.e. the
 * body is HTML, not plain text). Plain-text `<pre>` bodies are ignored.
 *
 * Returns an array of `{ amendment, top }` where `top` is the pixel offset
 * from the top of `docBodyRef.current`. Recalculates on `visibleAmendments`
 * change and on layout resize of `docBodyRef`.
 */
export function useAmendmentGutter(visibleAmendments, docBodyRef) {
  const [gutterPins, setGutterPins] = useState([])

  const computePins = useCallback(() => {
    const container = docBodyRef?.current
    if (!container || !container.querySelector('.doc-body')) {
      setGutterPins([])
      return
    }
    const pins = []
    for (const amendment of visibleAmendments) {
      const needle = amendment.original_text?.trim()
      if (!needle) continue
      const top = findTextOffsetTopInContainer(container, needle)
      if (top !== null && top >= 0) {
        pins.push({ amendment, top })
      }
    }
    setGutterPins(pins)
  }, [visibleAmendments, docBodyRef])

  useEffect(() => {
    computePins()
  }, [computePins])

  useEffect(() => {
    const container = docBodyRef?.current
    if (!container) return
    const observer = new ResizeObserver(computePins)
    observer.observe(container)
    return () => observer.disconnect()
  }, [docBodyRef, computePins])

  return gutterPins
}
