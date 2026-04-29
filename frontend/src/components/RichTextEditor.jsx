/**
 * RichTextEditor — TipTap-based WYSIWYG editor styled with the Editorial Ledger tokens.
 *
 * Provides a minimal but polished toolbar for document editing:
 *   Bold · Italic · § Section · §§ Sous-§ · Bullet list · Ordered list · Blockquote
 *
 * Shortcuts to insert a section:
 *   - Toolbar button "§ Section"
 *   - Right-click → context menu → § Insérer une section / §§ Sous-section
 *   - Type "## " at the start of a line (TipTap markdown input rule)
 *
 * The editor outputs standard HTML that is stored in the document body field.
 *
 * Props:
 *   value      — Current HTML content string.
 *   onChange   — Called with the new HTML string on every change.
 *   placeholder — Optional placeholder text shown when the editor is empty.
 *   minHeight  — Tailwind min-height class for the content area (default: "min-h-[240px]").
 *   maxHeight  — Optional Tailwind max-height class for the content area.
 */

import { useEditor, EditorContent } from '@tiptap/react'
import { TextSelection } from '@tiptap/pm/state'
import StarterKit from '@tiptap/starter-kit'
import { useEffect, useMemo, useRef, useState } from 'react'

// ---------------------------------------------------------------------------
// Toolbar button
// ---------------------------------------------------------------------------

/**
 * Single toolbar icon button.
 *
 * Props:
 *   onClick   — Click handler.
 *   active    — Whether this format is currently active in the selection.
 *   title     — Accessible tooltip text.
 *   children  — Button label/icon content.
 */
function ToolbarButton({ onClick, active, title, children }) {
  return (
    <button
      type="button"
      onMouseDown={(e) => {
        e.preventDefault()  // Prevent editor blur on click
        onClick()
      }}
      title={title}
      className={[
        'px-2 py-1 rounded font-body text-label-sm transition-colors select-none',
        active
          ? 'bg-amendly-blue text-white'
          : 'text-on-surface hover:bg-surface-container',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Count h2 headings in an HTML string to give a live section count.
 * @param {string} html
 * @returns {number}
 */
function countH2(html) {
  if (!html) return 0
  return (html.match(/<h2[\s>]/gi) ?? []).length
}

// ---------------------------------------------------------------------------
// RichTextEditor
// ---------------------------------------------------------------------------

export default function RichTextEditor({
  value,
  onChange,
  placeholder = 'Start typing…',
  minHeight = 'min-h-[240px]',
  maxHeight = '',
}) {
  const [ctxMenu, setCtxMenu] = useState(null) // { x, y } | null
  const ctxMenuRef = useRef(null)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Heading: only h2 and h3 for document body sections.
        // TipTap input rules: type "## " to get H2, "### " for H3.
        heading: { levels: [2, 3] },
        // Disable code blocks — not needed for legal/policy documents
        codeBlock: false,
        code: false,
      }),
    ],
    content: value || '',
    onUpdate({ editor: e }) {
      // Return empty string instead of "<p></p>" for truly empty documents
      const html = e.isEmpty ? '' : e.getHTML()
      onChange(html)
    },
    editorProps: {
      attributes: {
        class: [
          'doc-body outline-none',
          'font-body text-body-md text-on-surface leading-relaxed',
          minHeight,
          'px-6 py-5',
          // Direct descendant selectors are used here because this editor does
          // not rely on Tailwind's typography plugin.
          '[&_h2]:font-display [&_h2]:text-headline-sm [&_h2]:text-on-surface [&_h2]:mt-8 [&_h2]:mb-3',
          '[&_h3]:font-display [&_h3]:text-title-md [&_h3]:text-on-surface [&_h3]:mt-6 [&_h3]:mb-2',
          '[&_p]:my-0 [&_p+p]:mt-4',
          '[&_ul]:my-4 [&_ul]:pl-5 [&_ul]:list-disc',
          '[&_ol]:my-4 [&_ol]:pl-5 [&_ol]:list-decimal',
          '[&_li]:my-1',
          '[&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-amendly-blue',
          '[&_blockquote]:pl-4 [&_blockquote]:text-outline [&_blockquote]:italic',
          '[&_hr]:my-6 [&_hr]:h-px [&_hr]:border-0 [&_hr]:bg-surface-container-highest',
        ].join(' '),
      },
    },
  })

  // Sync external value changes (e.g. after document import)
  useEffect(() => {
    if (!editor) return
    if (editor.getHTML() !== value && !editor.isFocused) {
      editor.commands.setContent(value || '')
    }
  }, [value, editor])

  // Close context menu on outside click or Escape
  useEffect(() => {
    if (!ctxMenu) return
    function handleClick(e) {
      if (ctxMenuRef.current && !ctxMenuRef.current.contains(e.target)) {
        setCtxMenu(null)
      }
    }
    function handleKey(e) {
      if (e.key === 'Escape') setCtxMenu(null)
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [ctxMenu])

  // Live section count
  const sectionCount = useMemo(() => countH2(value), [value])

  function handleContextMenu(e) {
    e.preventDefault()
    // Compute position, keeping menu inside viewport
    const menuW = 220
    const menuH = 96
    const x = e.clientX + menuW > window.innerWidth ? e.clientX - menuW : e.clientX
    const y = e.clientY + menuH > window.innerHeight ? e.clientY - menuH : e.clientY
    setCtxMenu({ x, y })
  }

  function ctxInsertSection(level) {
    setCtxMenu(null)
    editor?.chain().focus().setHeading({ level }).run()
  }

  /**
   * Convert "## " / "### " typed at the start of a paragraph to a heading.
   * TipTap's built-in input rule only fires on completely empty paragraphs;
   * this handler covers all cases (non-empty line, cursor anywhere after the prefix).
   * Runs on the container onKeyDown to stay outside ProseMirror internals.
   * @param {React.KeyboardEvent} e
   */
  function handleMarkdownShortcut(e) {
    if (e.key !== ' ' || !editor) return
    const { state } = editor
    const { $from } = state.selection
    if ($from.parent.type.name !== 'paragraph') return
    const blockStart = $from.start()
    const cursorPos = $from.pos
    if (cursorPos <= blockStart) return
    const textBefore = state.doc.textBetween(blockStart, cursorPos)
    let level = 0
    let hashLength = 0
    if (textBefore.endsWith('###')) { level = 3; hashLength = 3 }
    else if (textBefore.endsWith('##')) { level = 2; hashLength = 2 }
    if (!level) return
    e.preventDefault()
    const hashStart = cursorPos - hashLength
    if (hashStart === blockStart) {
      // ## at the very start: convert entire block to heading
      editor.chain()
        .deleteRange({ from: blockStart, to: cursorPos })
        .setHeading({ level })
        .run()
    } else {
      // ## in the middle: split into [para before] [heading] [para after]
      editor.chain()
        .deleteRange({ from: hashStart, to: cursorPos })
        .splitBlock()
        .command(({ state: s, tr, dispatch: d }) => {
          const insertPos = s.selection.from - 1
          const headingNode = s.schema.nodes.heading.create({ level })
          tr.insert(insertPos, headingNode)
          tr.setSelection(TextSelection.create(tr.doc, insertPos + 1))
          if (d) d(tr)
          return true
        })
        .run()
    }
  }

  if (!editor) return null

  return (
    <div
      className={['relative bg-surface rounded-md ring-1 ring-surface-container-highest focus-within:ring-2 focus-within:ring-secondary transition-all', maxHeight].filter(Boolean).join(' ')}
      onContextMenu={handleContextMenu}
      onKeyDown={handleMarkdownShortcut}
    >
      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-center gap-0.5 px-3 py-2 bg-surface-container-low rounded-t-md">
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          active={editor.isActive('bold')}
          title="Gras"
        >
          <strong>B</strong>
        </ToolbarButton>

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          active={editor.isActive('italic')}
          title="Italique"
        >
          <em>I</em>
        </ToolbarButton>

        <span className="mx-1 h-4 w-px bg-surface-container-highest inline-block align-middle" />

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          active={editor.isActive('heading', { level: 2 })}
          title={'§ Section — chaque paragraphe reste amendable par défaut. Utilisez "## " sur une ligne vide pour créer un titre qui court jusqu’au prochain titre.'}
        >
          § Section
        </ToolbarButton>

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          active={editor.isActive('heading', { level: 3 })}
          title={'§§ Sous-section — ou tapez "### " au début d’une ligne pour créer un sous-titre sous la section courante.'}
        >
          §§ Sous-§
        </ToolbarButton>

        <span className="mx-1 h-4 w-px bg-surface-container-highest inline-block align-middle" />

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          active={editor.isActive('bulletList')}
          title="Liste à puces"
        >
          • Liste
        </ToolbarButton>

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          active={editor.isActive('orderedList')}
          title="Liste numérotée"
        >
          1. Liste
        </ToolbarButton>

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          active={editor.isActive('blockquote')}
          title="Citation"
        >
          ❝
        </ToolbarButton>

        {/* Live section counter */}
        {sectionCount > 0 && (
          <span className="ml-auto font-body text-label-sm text-outline select-none">
            {sectionCount} section{sectionCount > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* ── Editor area ── */}
      <EditorContent editor={editor} />

      {/* Placeholder overlay */}
      {editor.isEmpty && (
        <p
          className="absolute pointer-events-none font-body text-body-md text-outline px-6 py-5 top-[44px]"
          aria-hidden="true"
        >
          {placeholder}
        </p>
      )}

      {/* ── Context menu ── */}
      {ctxMenu && (
        <div
          ref={ctxMenuRef}
          style={{ position: 'fixed', top: ctxMenu.y, left: ctxMenu.x }}
          className="z-[9999] min-w-[220px] rounded-md bg-surface shadow-lg ring-1 ring-surface-container-highest py-1"
        >
          <p className="px-3 py-1.5 font-body text-label-sm text-outline select-none">
            Insérer
          </p>
          <button
            type="button"
            onMouseDown={(e) => { e.preventDefault(); ctxInsertSection(2) }}
            className="w-full text-left px-3 py-2 font-body text-body-sm text-on-surface hover:bg-surface-container transition-colors flex items-center gap-2"
          >
            <span className="rounded-full bg-amendly-blue text-white px-1.5 py-0.5 text-label-sm leading-none select-none">§</span>
            Section
          </button>
          <button
            type="button"
            onMouseDown={(e) => { e.preventDefault(); ctxInsertSection(3) }}
            className="w-full text-left px-3 py-2 font-body text-body-sm text-on-surface hover:bg-surface-container transition-colors flex items-center gap-2"
          >
            <span className="rounded-full bg-surface-container-highest text-outline px-1.5 py-0.5 text-label-sm leading-none select-none">§§</span>
            Sous-section
          </button>
        </div>
      )}
    </div>
  )
}
