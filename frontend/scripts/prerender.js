/**
 * scripts/prerender.js — Static HTML prerendering for public Amendly pages.
 *
 * This script runs AFTER `vite build` to generate pre-rendered HTML files
 * for all public routes. Search engine crawlers receive full HTML content
 * instead of an empty <div id="root"></div>.
 *
 * The prerendered HTML is injected into the Vite-built index.html shell,
 * replacing the empty root div. Per-page <head> meta tags (title, description,
 * canonical, og:url, og:title, og:description, og:type) are also patched so
 * that each page is correctly identified by Google — the default index.html
 * shell has canonical → "/" which would make every page look like a duplicate
 * of the homepage if left untouched.
 *
 * The client-side JS bundle then hydrates the static HTML on load (standard
 * React hydration pattern).
 *
 * Routes prerendered: all public routes in AppRoutes.jsx (see ROUTES below),
 * plus one entry per blog post derived from the posts manifest.
 *
 * Usage:
 *   node scripts/prerender.js
 *   (run automatically via `npm run build` — see package.json)
 *
 * Requires:
 *   - `vite build` to have run first (reads dist/index.html as the template)
 *   - `vite build --ssr src/entry-server.jsx` (SSR bundle at dist/server/)
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const distDir = path.resolve(__dirname, '..', 'dist')
const serverBundle = path.resolve(distDir, 'server', 'entry-server.js')

// Blog post manifest — plain JS, safe to import directly
const { posts } = await import('../src/blog/posts.js')

const SITE_URL = 'https://amendly.eu'

const HELP_FAQ_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: [
    {
      '@type': 'Question',
      name: 'How do I create a new collaborative document?',
      acceptedAnswer: { '@type': 'Answer', text: "Simply log into your dashboard, click on 'Documents' in the sidebar, and use the 'New Document' button to either upload a .docx file or write one from scratch." },
    },
    {
      '@type': 'Question',
      name: 'Can I invite external stakeholders to review?',
      acceptedAnswer: { '@type': 'Answer', text: 'Yes! You can share a secure review link with specific permissions. Guests will be able to submit amendments without needing full access to your organization workspace.' },
    },
    {
      '@type': 'Question',
      name: 'How does the consolidation feature work?',
      acceptedAnswer: { '@type': 'Answer', text: "Once your review period is over, the workspace owner or admin can review all submitted amendments. By clicking 'Accept' on an amendment, it automatically injects the diff into the final consolidation output. When done, you can export the clean version." },
    },
    {
      '@type': 'Question',
      name: 'What formats are supported for export?',
      acceptedAnswer: { '@type': 'Answer', text: 'Currently, you can export your consolidated final text to PDF and standard Word (DOCX) formats.' },
    },
    {
      '@type': 'Question',
      name: 'Are my documents secure and private?',
      acceptedAnswer: { '@type': 'Answer', text: 'Absolutely. We use enterprise-grade encryption at rest and in transit. Your documents are strictly accessible only by the members you explicitly invite.' },
    },
  ],
}

/**
 * Per-route SEO meta.
 * title       — injected into <title> and og:title
 * description — injected into <meta name="description"> and og:description
 * canonical   — injected into <link rel="canonical"> and og:url
 * ogType      — injected into og:type (default: "website")
 * noindex     — sets robots to "noindex, nofollow" when true
 * jsonLd      — optional extra JSON-LD block injected statically into <head>
 */
const ROUTE_META = {
  '/': {
    title: 'Amendly — Amendment management for organisations',
    description:
      'Amendly gives associations, NGOs, and federations a structured workflow to collect, review, and consolidate amendments — from first draft to final text.',
    canonical: `${SITE_URL}/`,
    ogType: 'website',
  },
  '/pricing': {
    title: 'Amendly Pricing — Solo, Team & Organisation plans',
    description:
      'Amendly pricing: Solo (€9/mo), Team (€29/mo, 3 users), Organisation (€99/mo, 10 users). 7-day free trial. No credit card required.',
    canonical: `${SITE_URL}/pricing`,
    ogType: 'website',
  },
  '/features': {
    title: 'Features — Amendly',
    description:
      'Discover all the powerful features Amendly offers for managing amendments: structured proposals, word-level diffs, consolidation, and export.',
    canonical: `${SITE_URL}/features`,
    ogType: 'website',
  },
  '/help': {
    title: 'Help Center — Amendly',
    description:
      'Find answers to frequently asked questions and learn how to use Amendly effectively for amendment management.',
    canonical: `${SITE_URL}/help`,
    ogType: 'website',
    jsonLd: HELP_FAQ_JSON_LD,
  },
  '/about': {
    title: 'About Us — Amendly',
    description:
      'Learn about Amendly, the platform bringing precision and convergence to amendment workflows for associations, NGOs, and federations.',
    canonical: `${SITE_URL}/about`,
    ogType: 'website',
  },
  '/contact': {
    title: 'Contact Us — Amendly',
    description:
      'Get in touch with the Amendly team. We are here to help you revolutionize the way you manage amendments.',
    canonical: `${SITE_URL}/contact`,
    ogType: 'website',
  },
  '/blog': {
    title: 'Blog — Amendly',
    description:
      'Insights on amendment management, governance, and collaborative decision-making for associations, federations, and NGOs.',
    canonical: `${SITE_URL}/blog`,
    ogType: 'website',
  },
  '/legal/terms': {
    title: 'Terms of Service — Amendly',
    description:
      'Read the Amendly Terms of Service governing your use of the amendment management platform.',
    canonical: `${SITE_URL}/legal/terms`,
    ogType: 'website',
  },
  '/legal/privacy': {
    title: 'Privacy Policy — Amendly',
    description:
      'Amendly Privacy Policy — how we collect, use, and protect your personal data under GDPR.',
    canonical: `${SITE_URL}/legal/privacy`,
    ogType: 'website',
  },
  '/legal/dpa': {
    title: 'Data Processing Agreement — Amendly',
    description:
      'Amendly Data Processing Agreement (DPA) — obligations of Amendly as a data processor under Article 28 GDPR.',
    canonical: `${SITE_URL}/legal/dpa`,
    ogType: 'website',
  },
  '/login': {
    title: 'Sign in — Amendly',
    description: 'Sign in to your Amendly workspace using a magic link or Google.',
    canonical: `${SITE_URL}/login`,
    ogType: 'website',
    noindex: true,
  },
}

// Blog post meta generated from the manifest
for (const post of posts) {
  ROUTE_META[`/blog/${post.slug}`] = {
    title: `${post.title} — Amendly Blog`,
    description: post.description,
    canonical: `${SITE_URL}/blog/${post.slug}`,
    ogType: 'article',
  }
}

// Routes to prerender — must match public routes in AppRoutes.jsx
const ROUTES = [
  { url: '/',              outFile: 'index.html' },
  { url: '/pricing',       outFile: 'pricing/index.html' },
  { url: '/features',      outFile: 'features/index.html' },
  { url: '/help',          outFile: 'help/index.html' },
  { url: '/about',         outFile: 'about/index.html' },
  { url: '/contact',       outFile: 'contact/index.html' },
  { url: '/blog',          outFile: 'blog/index.html' },
  { url: '/legal/terms',   outFile: 'legal/terms/index.html' },
  { url: '/legal/privacy', outFile: 'legal/privacy/index.html' },
  { url: '/legal/dpa',     outFile: 'legal/dpa/index.html' },
  { url: '/login',         outFile: 'login/index.html' },
  ...posts.map((p) => ({
    url: `/blog/${p.slug}`,
    outFile: `blog/${p.slug}/index.html`,
  })),
]

/**
 * Replace per-page SEO meta tags in the HTML template string.
 * The template always has the homepage defaults — this patches them for each route.
 */
function injectHeadMeta(html, meta) {
  const {
    title,
    description,
    canonical,
    ogType = 'website',
    noindex = false,
    jsonLd = null,
  } = meta

  const robots = noindex ? 'noindex, nofollow' : 'index, follow'

  return html
    // <title>
    .replace(
      /<title>[^<]*<\/title>/,
      `<title>${escHtml(title)}</title>`
    )
    // <meta name="description">
    .replace(
      /(<meta\s+name="description"\s+content=")[^"]*(")/,
      `$1${escHtml(description)}$2`
    )
    // <meta name="robots">
    .replace(
      /(<meta\s+name="robots"\s+content=")[^"]*(")/,
      `$1${robots}$2`
    )
    // <link rel="canonical">
    .replace(
      /(<link\s+rel="canonical"\s+href=")[^"]*(")/,
      `$1${canonical}$2`
    )
    // og:title
    .replace(
      /(<meta\s+property="og:title"\s+content=")[^"]*(")/,
      `$1${escHtml(title)}$2`
    )
    // og:description
    .replace(
      /(<meta\s+property="og:description"\s+content=")[^"]*(")/,
      `$1${escHtml(description)}$2`
    )
    // og:url
    .replace(
      /(<meta\s+property="og:url"\s+content=")[^"]*(")/,
      `$1${canonical}$2`
    )
    // og:type
    .replace(
      /(<meta\s+property="og:type"\s+content=")[^"]*(")/,
      `$1${ogType}$2`
    )
    // twitter:title
    .replace(
      /(<meta\s+name="twitter:title"\s+content=")[^"]*(")/,
      `$1${escHtml(title)}$2`
    )
    // twitter:description
    .replace(
      /(<meta\s+name="twitter:description"\s+content=")[^"]*(")/,
      `$1${escHtml(description)}$2`
    )
    // extra JSON-LD block (e.g. FAQPage) injected before </head>
    .replace(
      '</head>',
      jsonLd
        ? `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>\n  </head>`
        : '</head>'
    )
}

/** Minimal HTML attribute escaping for meta content values. */
function escHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

async function main() {
  // Load the HTML template produced by vite build
  const template = fs.readFileSync(path.join(distDir, 'index.html'), 'utf-8')

  // Dynamically import the SSR bundle
  const { render } = await import(serverBundle)

  for (const { url, outFile } of ROUTES) {
    console.log(`  prerendering ${url} → ${outFile}`)

    const meta = ROUTE_META[url]
    if (!meta) {
      console.warn(`  ⚠ No meta defined for ${url} — using homepage defaults`)
    }

    // Render the route to an HTML string
    const appHtml = await render(url)

    // Inject rendered HTML into the template shell
    let html = template.replace(
      '<div id="root"></div>',
      `<div id="root">${appHtml}</div>`
    )

    // Patch <head> meta for this specific route
    if (meta) {
      html = injectHeadMeta(html, meta)
    }

    // Write to the appropriate dist sub-directory
    const outputPath = path.join(distDir, outFile)
    const outputDir = path.dirname(outputPath)
    fs.mkdirSync(outputDir, { recursive: true })
    fs.writeFileSync(outputPath, html, 'utf-8')
  }

  console.log(`\n✓ Prerendered ${ROUTES.length} routes.`)
}

main().catch((err) => {
  console.error('Prerender failed:', err)
  process.exit(1)
})
