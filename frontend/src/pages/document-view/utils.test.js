// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'

import { locateInPane } from './utils'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build minimal ref-like objects pointing to real DOM nodes. */
function makeRefs(containerHtml) {
  const pane = document.createElement('div')
  const container = document.createElement('div')
  container.innerHTML = containerHtml
  pane.appendChild(container)
  document.body.appendChild(pane)

  const leftPaneRef = { current: pane }
  const docBodyRef = { current: container }

  return { pane, container, leftPaneRef, docBodyRef }
}

// ---------------------------------------------------------------------------
// locateInPane
// ---------------------------------------------------------------------------

describe('locateInPane', () => {
  it('returns null when docBodyRef is missing', () => {
    const leftPaneRef = { current: document.createElement('div') }
    expect(locateInPane(leftPaneRef, { current: null }, 'hello', { scroll: false })).toBeNull()
  })

  it('returns null when leftPaneRef is missing', () => {
    const docBodyRef = { current: document.createElement('div') }
    expect(locateInPane({ current: null }, docBodyRef, 'hello', { scroll: false })).toBeNull()
  })

  it('returns null when text is empty', () => {
    const { leftPaneRef, docBodyRef } = makeRefs('<p>Hello world</p>')
    expect(locateInPane(leftPaneRef, docBodyRef, '', { scroll: false })).toBeNull()
    expect(locateInPane(leftPaneRef, docBodyRef, '   ', { scroll: false })).toBeNull()
  })

  it('returns null when the needle is not found in the document', () => {
    const { leftPaneRef, docBodyRef } = makeRefs('<p>Hello world</p>')
    expect(locateInPane(leftPaneRef, docBodyRef, 'missing text', { scroll: false })).toBeNull()
  })

  it('wraps the matched text in a <mark class="doc-locate-mark">', () => {
    const { container, leftPaneRef, docBodyRef } = makeRefs('<p>Hello world</p>')

    const cleanup = locateInPane(leftPaneRef, docBodyRef, 'world', { scroll: false })

    expect(cleanup).toBeTypeOf('function')
    const mark = container.querySelector('mark.doc-locate-mark')
    expect(mark).not.toBeNull()
    expect(mark.textContent).toBe('world')
  })

  it('cleanup removes the mark and restores the original text node', () => {
    const { container, leftPaneRef, docBodyRef } = makeRefs('<p>Hello world</p>')

    const cleanup = locateInPane(leftPaneRef, docBodyRef, 'world', { scroll: false })
    expect(container.querySelector('mark.doc-locate-mark')).not.toBeNull()

    cleanup()

    expect(container.querySelector('mark.doc-locate-mark')).toBeNull()
    expect(container.textContent).toBe('Hello world')
  })

  it('cleanup is idempotent (safe to call twice)', () => {
    const { container, leftPaneRef, docBodyRef } = makeRefs('<p>Hello world</p>')

    const cleanup = locateInPane(leftPaneRef, docBodyRef, 'world', { scroll: false })
    cleanup()
    // Second call should not throw even though the mark is gone
    expect(() => cleanup()).not.toThrow()
    expect(container.querySelector('mark.doc-locate-mark')).toBeNull()
  })

  it('works on plain-text content (as in a <pre> wrapper)', () => {
    // Plain text documents render inside a <pre>; docBodyRef still wraps the
    // container div, so the TreeWalker finds the text node the same way.
    const { container, leftPaneRef, docBodyRef } = makeRefs(
      '<pre>Article 1. The board shall meet quarterly.</pre>'
    )

    const cleanup = locateInPane(leftPaneRef, docBodyRef, 'board shall', { scroll: false })

    expect(cleanup).toBeTypeOf('function')
    const mark = container.querySelector('mark.doc-locate-mark')
    expect(mark).not.toBeNull()
    expect(mark.textContent).toBe('board shall')

    cleanup()
    expect(container.querySelector('mark.doc-locate-mark')).toBeNull()
  })

  it('finds text that spans deep nested elements', () => {
    const { container, leftPaneRef, docBodyRef } = makeRefs(
      '<section><article><p><strong>Important</strong> clause here.</p></article></section>'
    )

    // "Important" lives inside a <strong> — TreeWalker should still reach it
    const cleanup = locateInPane(leftPaneRef, docBodyRef, 'Important', { scroll: false })

    expect(cleanup).toBeTypeOf('function')
    expect(container.querySelector('mark.doc-locate-mark')?.textContent).toBe('Important')

    cleanup()
    expect(container.querySelector('mark.doc-locate-mark')).toBeNull()
  })

  it('each call gets an independent cleanup (no cross-card interference)', () => {
    // Simulates two amendment cards each holding their own locateCleanupRef.
    // Each pair of refs is independent; cleaning one must not affect the other.
    const { container: c1, leftPaneRef: lp1, docBodyRef: db1 } = makeRefs('<p>Alpha token here</p>')
    const { container: c2, leftPaneRef: lp2, docBodyRef: db2 } = makeRefs('<p>Beta token here</p>')

    const cleanup1 = locateInPane(lp1, db1, 'Alpha token', { scroll: false })
    const cleanup2 = locateInPane(lp2, db2, 'Beta token', { scroll: false })

    // Both marks created independently
    expect(c1.querySelector('mark.doc-locate-mark')).not.toBeNull()
    expect(c2.querySelector('mark.doc-locate-mark')).not.toBeNull()

    // Cleaning card 1 leaves card 2 untouched
    cleanup1()
    expect(c1.querySelector('mark.doc-locate-mark')).toBeNull()
    expect(c2.querySelector('mark.doc-locate-mark')).not.toBeNull()

    cleanup2()
    expect(c2.querySelector('mark.doc-locate-mark')).toBeNull()
  })
})
