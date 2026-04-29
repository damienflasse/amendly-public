#!/usr/bin/env node
/**
 * new-post.js — Publish a new blog post from a markdown file.
 *
 * Usage:
 *   node scripts/new-post.js path/to/article.md
 *   node scripts/new-post.js            ← interactive mode (no markdown)
 *
 * When a .md file is provided the script:
 *   - Extracts title, author, date from the document
 *   - Converts the markdown body to JSX
 *   - Estimates reading time from word count
 *   - Pre-fills all prompts (just press Enter to confirm)
 *
 * In both modes, the script then:
 *   1. Creates  src/blog/posts/{slug}.jsx
 *   2. Updates  src/blog/posts.js          (manifest)
 *   3. Updates  src/pages/BlogPost.jsx     (lazy import map)
 *   4. Updates  public/sitemap.xml
 */

import fs from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root      = path.resolve(__dirname, '..')

const POSTS_JS  = path.join(root, 'src/blog/posts.js')
const POSTS_DIR = path.join(root, 'src/blog/posts')
const BLOG_POST = path.join(root, 'src/pages/BlogPost.jsx')
const SITEMAP   = path.join(root, 'public/sitemap.xml')

// ---------------------------------------------------------------------------
// Prompt helper
// ---------------------------------------------------------------------------
const rl = readline.createInterface({ input: process.stdin, output: process.stdout })

function ask(question, defaultValue = '') {
  return new Promise((resolve) => {
    const hint = defaultValue ? ` [${defaultValue}]` : ''
    rl.question(`${question}${hint}: `, (answer) => {
      resolve(answer.trim() || defaultValue)
    })
  })
}

// ---------------------------------------------------------------------------
// Markdown parser
// ---------------------------------------------------------------------------

const MONTH_MAP = {
  january: '01', february: '02', march: '03', april: '04',
  may: '05', june: '06', july: '07', august: '08',
  september: '09', october: '10', november: '11', december: '12',
}

/**
 * Parse "April 2026" or "2026-04-10" into an ISO date string.
 * Falls back to today if the format is not recognised.
 */
function parseDate(raw = '') {
  // Already ISO
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw.trim())) return raw.trim()

  // "Month YYYY"
  const match = raw.trim().match(/^(\w+)\s+(\d{4})$/)
  if (match) {
    const month = MONTH_MAP[match[1].toLowerCase()]
    if (month) return `${match[2]}-${month}-01`
  }

  return todayIso()
}

/**
 * Convert inline markdown to JSX string.
 * Handles: **bold**, *italic*, [text](url)
 */
function inlineToJsx(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" className="text-secondary hover:underline">$1</a>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
}

/**
 * Convert a markdown string to an array of JSX element strings.
 * Returns { jsxLines, title, author, date, wordCount }
 */
function parseMd(src) {
  const blocks = src.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean)

  let title     = ''
  let author    = 'Damien Flasse'
  let date      = todayIso()
  let wordCount = 0
  let bylineSeen = false
  let skipNextHr = false
  const jsxLines = []

  for (const block of blocks) {
    // H1 → title metadata, not rendered
    if (block.startsWith('# ')) {
      title = block.slice(2).trim()
      continue
    }

    // Byline: *By Author · Org · Month Year*
    if (/^\*By\s/.test(block)) {
      const inner  = block.replace(/^\*/, '').replace(/\*$/, '')
      const parts  = inner.split('·').map((s) => s.trim())
      // "By Damien Flasse" → strip "By "
      author       = parts[0]?.replace(/^By\s+/i, '').trim() || author
      const rawDate = parts[parts.length - 1] || ''
      date         = parseDate(rawDate)
      bylineSeen   = true
      skipNextHr   = true   // the --- right after the byline is decorative, skip it
      continue
    }

    // Skip the decorative --- that immediately follows the byline
    if (block === '---' && skipNextHr) {
      skipNextHr = false
      continue
    }
    skipNextHr = false

    // Count words for reading time (all content blocks)
    wordCount += block.split(/\s+/).length

    // --- → <hr />
    if (block === '---') {
      jsxLines.push('      <hr />')
      continue
    }

    // ## heading → <h2>
    if (block.startsWith('## ')) {
      const text = inlineToJsx(block.slice(3).trim())
      jsxLines.push(`      <h2>${text}</h2>`)
      continue
    }

    // Collapse soft-wrapped lines into a single string
    const oneLine = block.replace(/\n/g, ' ')

    // Paragraph-level italic: *entire paragraph*
    const italicMatch = oneLine.match(/^\*([^*].*[^*]|[^*])\*$/)
    if (italicMatch) {
      const inner = inlineToJsx(italicMatch[1])
      jsxLines.push(`      <p>\n        <em>${inner}</em>\n      </p>`)
      continue
    }

    // Regular paragraph
    const text = inlineToJsx(oneLine)
    jsxLines.push(`      <p>${text}</p>`)
  }

  return { jsxLines, title, author, date, wordCount }
}

function estimateReadingTime(wordCount) {
  return `${Math.max(1, Math.ceil(wordCount / 200))} min`
}

function autoDescription(jsxLines) {
  // Pull text from the first <p> block, strip tags, truncate
  for (const line of jsxLines) {
    if (line.startsWith('      <p>') && !line.includes('<em>')) {
      const text = line.replace(/<[^>]+>/g, '').trim()
      if (text.length > 20) {
        return text.length > 157 ? text.slice(0, 157) + '…' : text
      }
    }
  }
  return ''
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function toSlug(value) {
  return value
    .toLowerCase()
    .replace(/[àáâãäå]/g, 'a').replace(/[èéêë]/g, 'e')
    .replace(/[ìíîï]/g, 'i').replace(/[òóôõö]/g, 'o')
    .replace(/[ùúûü]/g, 'u').replace(/[ç]/g, 'c').replace(/[ñ]/g, 'n')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

// ---------------------------------------------------------------------------
// File writers
// ---------------------------------------------------------------------------

function createContentFile(slug, title, jsxLines) {
  const filePath = path.join(POSTS_DIR, `${slug}.jsx`)
  if (fs.existsSync(filePath)) {
    console.error(`\n✗ Already exists: ${filePath}`)
    process.exit(1)
  }

  const body = jsxLines.length
    ? jsxLines.join('\n\n')
    : '      <p>Write your content here.</p>'

  const content = `/**
 * Blog post: "${title}"
 *
 * Authoring guide:
 *   <h2>      Section headings
 *   <p>       Paragraphs
 *   <em>      Italic
 *   <strong>  Bold
 *   <hr />    Section break
 *   <a href="...">  Links
 */
export default function Post() {
  return (
    <>
${body}
    </>
  )
}
`
  fs.mkdirSync(POSTS_DIR, { recursive: true })
  fs.writeFileSync(filePath, content, 'utf-8')
  return filePath
}

function updatePostsJs(slug, title, description, date, author, readingTime) {
  let src = fs.readFileSync(POSTS_JS, 'utf-8')
  const entry = `  {
    slug: '${slug}',
    title: ${JSON.stringify(title)},
    description: ${JSON.stringify(description)},
    date: '${date}',
    author: '${author}',
    readingTime: '${readingTime}',
  },\n`
  src = src.replace(/^(export const posts = \[)\n/m, `$1\n${entry}`)
  fs.writeFileSync(POSTS_JS, src, 'utf-8')
}

function updateBlogPostJsx(slug) {
  let src = fs.readFileSync(BLOG_POST, 'utf-8')
  const entry = `  '${slug}': lazy(() =>\n    import('../blog/posts/${slug}.jsx')\n  ),\n`
  src = src.replace(/(const postComponents = \{[\s\S]*?)(^\})/m, `$1${entry}$2`)
  fs.writeFileSync(BLOG_POST, src, 'utf-8')
}

function updateSitemap(slug, date) {
  let src = fs.readFileSync(SITEMAP, 'utf-8')
  const entry = `
  <url>
    <loc>https://amendly.eu/blog/${slug}</loc>
    <lastmod>${date}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
`
  src = src.replace(
    /(<loc>https:\/\/amendly\.eu\/blog<\/loc>[\s\S]*?<\/url>)/,
    `$1\n${entry}`
  )
  fs.writeFileSync(SITEMAP, src, 'utf-8')
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  const mdPath = process.argv[2]
  let parsed   = { jsxLines: [], title: '', author: 'Damien Flasse', date: todayIso(), wordCount: 0 }

  if (mdPath) {
    const abs = path.resolve(process.cwd(), mdPath)
    if (!fs.existsSync(abs)) {
      console.error(`✗ File not found: ${abs}`)
      process.exit(1)
    }
    console.log(`\nParsing ${path.basename(abs)}…`)
    parsed = parseMd(fs.readFileSync(abs, 'utf-8'))
  }

  console.log('\n── New blog post ──────────────────────────────\n')

  const title = await ask('Title', parsed.title)
  if (!title) { console.error('Title is required.'); process.exit(1) }

  const slug = await ask('Slug', toSlug(title))
  if (!slug) { console.error('Slug is required.'); process.exit(1) }

  const descDefault   = autoDescription(parsed.jsxLines)
  const description   = await ask('Description (≤160 chars)', descDefault)
  const date          = await ask('Publication date', parsed.date)
  const author        = await ask('Author', parsed.author)
  const readingTime   = await ask('Reading time', estimateReadingTime(parsed.wordCount))

  rl.close()

  console.log('\nWriting files…')

  const contentPath = createContentFile(slug, title, parsed.jsxLines)
  updatePostsJs(slug, title, description, date, author, readingTime)
  updateBlogPostJsx(slug)
  updateSitemap(slug, date)

  console.log(`
✓ Created  src/blog/posts/${slug}.jsx
✓ Updated  src/blog/posts.js
✓ Updated  src/pages/BlogPost.jsx
✓ Updated  public/sitemap.xml

URL: https://amendly.eu/blog/${slug}
`)
}

main().catch((err) => {
  console.error('Error:', err.message)
  process.exit(1)
})
