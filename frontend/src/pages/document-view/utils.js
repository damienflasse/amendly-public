import {
  extractDocumentSections,
  injectDocumentSectionAttributes,
  normalizeSectionKey,
} from '../../lib/documentSections'

export function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function highlightHtml(html, query) {
  if (!query || !query.trim()) return html
  const re = new RegExp(`(${escapeRegex(query.trim())})(?![^<]*>)`, 'gi')
  return html.replace(
    re,
    '<mark class="doc-search-mark" style="background:#fef08a;color:#713f12;border-radius:2px;padding:0 1px">$1</mark>'
  )
}

export function extractHeadings(html) {
  return extractDocumentSections(html)
}

export function injectHeadingIds(html) {
  return injectDocumentSectionAttributes(html)
}

export function findRenderedSectionByTop(container, top, headings) {
  if (!container || headings.length === 0) return null
  const renderedHeadings = Array.from(container.querySelectorAll('[data-section-id]'))
  if (renderedHeadings.length === 0) return headings[0] ?? null

  let match = renderedHeadings[0]
  for (const heading of renderedHeadings) {
    if (heading.offsetTop <= top + 4) match = heading
    else break
  }
  return headings.find((item) => item.id === match.dataset.sectionId) ?? null
}

/**
 * Locates `text` in the document body pane, optionally scrolls to it, and
 * applies a temporary yellow highlight (<mark class="doc-locate-mark">).
 *
 * Returns a cleanup function that removes the mark and normalises the DOM,
 * or null if the text was not found or the operation failed.
 *
 * @param {React.RefObject} leftPaneRef  — ref to the scrollable left pane div
 * @param {React.RefObject} docBodyRef   — ref to the rendered document body div
 * @param {string}          text         — plain-text needle to look for
 * @param {{ scroll?: boolean }} options
 */
export function locateInPane(leftPaneRef, docBodyRef, text, { scroll = true } = {}) {
  const container = docBodyRef?.current
  const pane = leftPaneRef?.current
  const needle = text?.trim()
  if (!container || !pane || !needle) return null

  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  let node
  while ((node = walker.nextNode())) {
    const idx = node.nodeValue.indexOf(needle)
    if (idx === -1) continue

    const range = document.createRange()
    range.setStart(node, idx)
    range.setEnd(node, idx + needle.length)

    const mark = document.createElement('mark')
    mark.style.cssText =
      'background:#fef08a;color:#713f12;border-radius:2px;padding:0 1px'
    mark.className = 'doc-locate-mark'

    try {
      range.surroundContents(mark)
    } catch {
      return null
    }

    if (scroll) {
      const paneRect = pane.getBoundingClientRect()
      const markRect = mark.getBoundingClientRect()
      const targetTop =
        pane.scrollTop + markRect.top - paneRect.top - pane.clientHeight / 3
      pane.scrollTo({ top: targetTop, behavior: 'smooth' })
    }

    const cleanup = () => {
      if (!mark.parentNode) return
      const parent = mark.parentNode
      while (mark.firstChild) parent.insertBefore(mark.firstChild, mark)
      parent.removeChild(mark)
      parent.normalize()
    }
    return cleanup
  }
  return null
}

/**
 * Finds the vertical offset (in px) of `text` within `container`, measured
 * from the top of `container`. Uses Range.getBoundingClientRect() which is
 * scroll-independent: the difference between range.top and container.top is
 * a fixed layout measurement regardless of scroll position.
 *
 * Returns null if the text is not found or the container is not in the DOM.
 */
export function findTextOffsetTopInContainer(container, text) {
  if (!container || !text?.trim()) return null
  const needle = text.trim()
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  let node
  while ((node = walker.nextNode())) {
    const idx = node.nodeValue.indexOf(needle)
    if (idx === -1) continue
    try {
      const range = document.createRange()
      range.setStart(node, idx)
      range.setEnd(node, idx + needle.length)
      const rangeRect = range.getBoundingClientRect()
      const containerRect = container.getBoundingClientRect()
      return rangeRect.top - containerRect.top
    } catch {
      continue
    }
  }
  return null
}

export function groupAmendmentsBySection(amendments, headings, unsectionedLabel) {
  const grouped = new Map()
  const headingOrder = headings.map((heading) => ({
    key: normalizeSectionKey(heading.text),
    label: heading.text,
    id: heading.id,
  }))

  for (const amendment of amendments) {
    const key = normalizeSectionKey(amendment.section) || '__unsectioned__'
    const existingHeading = headingOrder.find((heading) => heading.key === key)
    const current = grouped.get(key) ?? {
      key,
      label: existingHeading?.label ?? amendment.section ?? unsectionedLabel,
      sectionId: existingHeading?.id ?? null,
      items: [],
    }
    current.items.push(amendment)
    grouped.set(key, current)
  }

  const ordered = []
  for (const heading of headingOrder) {
    if (grouped.has(heading.key)) {
      ordered.push(grouped.get(heading.key))
      grouped.delete(heading.key)
    }
  }

  if (grouped.has('__unsectioned__')) {
    ordered.push(grouped.get('__unsectioned__'))
    grouped.delete('__unsectioned__')
  }

  return [
    ...ordered,
    ...Array.from(grouped.values()).sort((left, right) => left.label.localeCompare(right.label)),
  ]
}
