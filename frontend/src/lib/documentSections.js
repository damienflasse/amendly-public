function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function ensureRichTextHtml(html) {
  if (!html) return ''
  if (html.trimStart().startsWith('<')) return html
  return html
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => `<p>${escapeHtml(block)}</p>`)
    .join('')
}

const _parser =
  typeof window !== 'undefined' && typeof DOMParser !== 'undefined' ? new DOMParser() : null

function parseDocumentHtml(html) {
  if (!_parser) return null
  return _parser.parseFromString(ensureRichTextHtml(html), 'text/html')
}

function findHeadingIndexBySectionId(headings, sectionId) {
  return headings.findIndex((heading, idx) => `doc-section-${idx}` === sectionId)
}

function getSectionBoundary(headings, index) {
  const current = headings[index]
  if (!current) return { start: null, endExclusive: null }
  const currentLevel = Number(current.tagName[1])
  let endExclusive = null
  for (let i = index + 1; i < headings.length; i += 1) {
    const candidate = headings[i]
    if (Number(candidate.tagName[1]) <= currentLevel) {
      endExclusive = candidate
      break
    }
  }
  return { start: current, endExclusive }
}

function buildSectionNodes(doc, level, title) {
  const heading = doc.createElement(level)
  heading.textContent = title
  const paragraph = doc.createElement('p')
  paragraph.textContent = ''
  return [heading, paragraph]
}

export function normalizeSectionKey(value) {
  return (value ?? '').trim().toLowerCase().replace(/\s+/g, ' ')
}

/**
 * Compute hierarchical numbers for an array of sections.
 *
 * h2 sections are numbered sequentially: "1.", "2.", "3.", …
 * h3 sections are numbered relative to the last h2:  "1.1.", "1.2.", …
 *
 * Parameters:
 *   sections — Array of { id, level, text } from extractDocumentSections().
 * Returns:
 *   A new array with an added `number` string field on each item.
 */
export function computeSectionNumbers(sections) {
  let h2Count = 0
  const h3Counts = {}
  return sections.map((section) => {
    if (section.level === 'h2') {
      h2Count += 1
      h3Counts[h2Count] = 0
      return { ...section, number: `${h2Count}.` }
    }
    // h3
    if (!h3Counts[h2Count]) h3Counts[h2Count] = 0
    h3Counts[h2Count] += 1
    return { ...section, number: `${h2Count}.${h3Counts[h2Count]}.` }
  })
}

export function extractDocumentSections(html) {
  if (!html || !html.trimStart().startsWith('<')) return []
  const doc = parseDocumentHtml(html)
  if (!doc) {
    const results = []
    let idx = 0
    const re = /<(h[23])[^>]*>([\s\S]*?)<\/h[23]>/gi
    let match
    while ((match = re.exec(html)) !== null) {
      results.push({
        id: `doc-section-${idx++}`,
        level: match[1].toLowerCase(),
        text: match[2].replace(/<[^>]+>/g, '').trim(),
      })
    }
    return results
  }

  return Array.from(doc.body.querySelectorAll('h2, h3')).map((heading, idx) => ({
    id: `doc-section-${idx}`,
    level: heading.tagName.toLowerCase(),
    text: heading.textContent?.trim() || `Section ${idx + 1}`,
  }))
}

export function injectDocumentSectionAttributes(html) {
  if (!html || !html.trimStart().startsWith('<')) return html
  const doc = parseDocumentHtml(html)
  if (!doc) {
    let idx = 0
    return html.replace(/<(h[23])(\s[^>]*)?>/gi, (_, tag, attrs = '') => {
      const id = `doc-section-${idx++}`
      return `<${tag}${attrs} id="${id}" data-section-id="${id}">`
    })
  }

  Array.from(doc.body.querySelectorAll('h2, h3')).forEach((heading, idx) => {
    const id = `doc-section-${idx}`
    heading.id = id
    heading.setAttribute('data-section-id', id)
    heading.setAttribute('data-section-label', heading.textContent?.trim() || '')
  })
  return doc.body.innerHTML
}

export function appendDocumentSection(html, { level = 'h2', title = 'New section' } = {}) {
  const doc = parseDocumentHtml(html)
  if (!doc) return html
  const nodes = buildSectionNodes(doc, level, title)
  nodes.forEach((node) => doc.body.appendChild(node))
  return doc.body.innerHTML
}

export function insertDocumentSectionAfter(
  html,
  sectionId,
  { level = null, title = 'New section' } = {}
) {
  const doc = parseDocumentHtml(html)
  if (!doc) return html
  const headings = Array.from(doc.body.querySelectorAll('h2, h3'))
  const index = findHeadingIndexBySectionId(headings, sectionId)
  if (index === -1) return appendDocumentSection(html, { level: level ?? 'h2', title })

  const current = headings[index]
  const { endExclusive } = getSectionBoundary(headings, index)
  const nodes = buildSectionNodes(doc, level ?? current.tagName.toLowerCase(), title)
  nodes.forEach((node) => doc.body.insertBefore(node, endExclusive))
  return doc.body.innerHTML
}

export function renameDocumentSection(html, sectionId, nextTitle) {
  const doc = parseDocumentHtml(html)
  if (!doc) return html
  const headings = Array.from(doc.body.querySelectorAll('h2, h3'))
  const index = findHeadingIndexBySectionId(headings, sectionId)
  if (index === -1) return html
  const title = nextTitle.trim()
  if (!title) return html
  headings[index].textContent = title
  return doc.body.innerHTML
}

/**
 * Extract all top-level content blocks from an HTML body string.
 *
 * Returns an array of block descriptors, ordered as they appear in the document.
 * Heading blocks include a `sectionIndex` field (their ordinal within all headings).
 * Non-heading blocks have `sectionIndex: null`.
 *
 * Parameters:
 *   html — HTML string (document body).
 * Returns:
 *   Array of { index, tag, text, sectionIndex } objects.
 */
export function extractBodyBlocks(html) {
  if (!html) return []
  const doc = parseDocumentHtml(html)
  if (!doc) return []
  let headingCount = 0
  return Array.from(doc.body.children).map((el, index) => {
    const tag = el.tagName.toLowerCase()
    const isHeading = tag === 'h2' || tag === 'h3'
    const block = {
      index,
      tag,
      text: el.textContent?.trim().slice(0, 200) || '',
      sectionIndex: isHeading ? headingCount : null,
    }
    if (isHeading) headingCount++
    return block
  })
}

/**
 * Insert an h2 or h3 heading immediately before the block at `blockIndex`.
 *
 * If the body is plain text (does not start with '<'), it is first converted to
 * <p> blocks via the internal parser before the heading is inserted.
 *
 * Parameters:
 *   html       — Current document body HTML string.
 *   blockIndex — Zero-based index of the target block in doc.body.children.
 *   level      — 'h2' (default) or 'h3'.
 *   title      — Heading title text (default: 'Nouvelle section').
 * Returns:
 *   New HTML string with the heading inserted before the target block.
 */
export function insertHeadingBeforeBlock(html, blockIndex, { level = 'h2', title = 'Nouvelle section' } = {}) {
  const doc = parseDocumentHtml(html)
  if (!doc) return html
  const blocks = Array.from(doc.body.children)
  const target = blocks[blockIndex]
  if (!target) return html
  const heading = doc.createElement(level)
  heading.textContent = title
  doc.body.insertBefore(heading, target)
  return doc.body.innerHTML
}

export function removeDocumentSection(html, sectionId) {
  const doc = parseDocumentHtml(html)
  if (!doc) return html
  const headings = Array.from(doc.body.querySelectorAll('h2, h3'))
  const index = findHeadingIndexBySectionId(headings, sectionId)
  if (index === -1) return html

  const { start, endExclusive } = getSectionBoundary(headings, index)
  if (!start) return html

  let node = start
  while (node && node !== endExclusive) {
    const next = node.nextSibling
    node.remove()
    node = next
  }
  return doc.body.innerHTML
}

/**
 * Automatically insert an <h2> heading before each non-empty content block
 * when the document has no headings yet.
 *
 * The heading title is derived from the first 6 words of the paragraph text,
 * trimmed to 55 characters. If the block has no text, a fallback
 * "Section N" label is used.
 *
 * No-op if the document already contains at least one h2 or h3.
 *
 * Parameters:
 *   html        — Current document body HTML string.
 *   titlePrefix — Prefix used in the fallback label (default: 'Section').
 * Returns:
 *   New HTML string with h2 headings inserted before each content block,
 *   or the original string unchanged if headings already exist.
 */
export function autoProposeSectionsFromParagraphs(html, titlePrefix = 'Section') {
  const doc = parseDocumentHtml(html)
  if (!doc) return html

  // No-op if headings already exist
  if (doc.body.querySelectorAll('h2, h3').length > 0) return html

  const contentBlocks = Array.from(doc.body.children).filter((el) => {
    const tag = el.tagName.toLowerCase()
    return (
      (tag === 'p' || tag === 'ul' || tag === 'ol' || tag === 'blockquote') &&
      el.textContent?.trim().length > 0
    )
  })

  if (contentBlocks.length === 0) return html

  contentBlocks.forEach((block, idx) => {
    const rawText = block.textContent?.trim() ?? ''
    const words = rawText.split(/\s+/).slice(0, 6).join(' ')
    const title =
      words.length > 55
        ? words.slice(0, 55).trimEnd() + '…'
        : words || `${titlePrefix} ${idx + 1}`
    const heading = doc.createElement('h2')
    heading.textContent = title
    doc.body.insertBefore(heading, block)
  })

  return doc.body.innerHTML
}

