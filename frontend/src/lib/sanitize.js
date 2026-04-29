/**
 * sanitizeHtml — strip unsafe HTML tags/attributes before rendering.
 *
 * Uses DOMPurify (statically imported) in browser environments.
 * Falls back to stripping all tags in non-browser environments (SSR/Node).
 *
 * Only call this before passing content to dangerouslySetInnerHTML.
 *
 * Parameters:
 *   html — Raw HTML string to sanitise.
 *
 * Returns:
 *   Safe HTML string.
 */
import DOMPurify from 'dompurify'

export function sanitizeHtml(html) {
  if (!html) return ''

  // SSR / Node environment — strip all tags as a safe fallback
  if (typeof window === 'undefined') {
    return html.replace(/<[^>]*>/g, '')
  }

  // Browser — use DOMPurify with a conservative allowlist
  // (TipTap output already safe, but defence-in-depth for API data)
  try {
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [
        'p', 'br', 'strong', 'em', 'b', 'i',
        'h2', 'h3', 'h4',
        'ul', 'ol', 'li',
        'blockquote',
        'hr',
        'a',
        // Search-highlight marks (added by highlightHtml after sanitisation)
        'mark', 'span',
      ],
      ALLOWED_ATTR: [
        // Section anchor IDs injected by injectDocumentSectionAttributes —
        // required for the sticky TOC scroll-to-section feature.
        'id',
        'data-section-id',
        'data-section-label',
        // Search-highlight marks use inline style for background colour.
        'style',
        // mark class used by highlightHtml (doc-search-mark)
        'class',
        // Hyperlinks from imported DOCX files
        'href',
        'target',
        'rel',
      ],
    })
  } catch (err) {
    console.error('[sanitizeHtml] DOMPurify failed — returning escaped text fallback:', err)
    return html
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }
}

/**
 * initDOMPurify — no-op kept for backward compatibility.
 * DOMPurify is now statically imported; no async initialisation needed.
 */
export async function initDOMPurify() {
  // No-op: DOMPurify is now a static import, loaded synchronously with the bundle.
}
