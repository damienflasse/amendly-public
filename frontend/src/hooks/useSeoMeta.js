/**
 * useSeoMeta — lightweight SEO hook.
 *
 * Sets all SEO-related <meta> and <link> tags for the current route without
 * any external dependency. All tags are cleaned up on unmount / dep change so
 * navigating between routes never leaves stale meta behind.
 *
 * @param {{
 *   title:       string,
 *   description: string,
 *   ogImage?:    string,
 *   ogType?:     string,
 *   noindex?:    boolean,
 *   lang?:       string,
 *   canonical?:  string,
 * }} meta
 *   title       — Full <title> string (e.g. "Amendly — Amendment management")
 *   description — <meta name="description"> content (≤ 160 chars recommended)
 *   ogImage     — Absolute URL for og:image (optional; defaults to /og-image.png)
 *   ogType      — og:type value (optional; defaults to "website")
 *   noindex     — When true, sets <meta name="robots" content="noindex, nofollow">
 *                 Use for all authenticated / private pages.
 *   lang        — BCP-47 language code (e.g. "fr"). Updates <html lang> and adds
 *                 <link rel="alternate"> hreflang entries for the four supported
 *                 locales when a canonical URL is also provided.
 *   canonical   — Absolute canonical URL. Adds/updates <link rel="canonical">.
 *                 Defaults to window.location.origin + window.location.pathname
 *                 (strips query string / hash to avoid duplicate content).
 *
 * @returns {void}
 */
import { useEffect } from 'react'

const SITE_URL = 'https://amendly.eu'
const DEFAULT_OG_IMAGE = `${SITE_URL}/og-image.png`

/** Supported locales — must match frontend/src/i18n/*.json filenames */
const SUPPORTED_LANGS = ['en', 'fr', 'de', 'es']

/** Guard for SSR environments (Node.js prerendering — no window/document) */
const isClient = typeof window !== 'undefined' && typeof document !== 'undefined'

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

/** Upsert a <meta> element identified by name or property attribute. */
function upsertMeta(attr, value, content) {
  let el = document.querySelector(`meta[${attr}="${value}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, value)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
  return el
}

/** Remove a <meta> element if it exists. */
function removeMeta(attr, value) {
  const el = document.querySelector(`meta[${attr}="${value}"]`)
  if (el) el.remove()
}

/** Upsert a <link> element identified by rel + optional hreflang attribute. */
function upsertLink(rel, href, hreflang) {
  const selector = hreflang
    ? `link[rel="${rel}"][hreflang="${hreflang}"]`
    : `link[rel="${rel}"]`
  let el = document.querySelector(selector)
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    if (hreflang) el.setAttribute('hreflang', hreflang)
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
  return el
}

/** Remove a <link> element if it exists. */
function removeLink(rel, hreflang) {
  const selector = hreflang
    ? `link[rel="${rel}"][hreflang="${hreflang}"]`
    : `link[rel="${rel}"]`
  const el = document.querySelector(selector)
  if (el) el.remove()
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSeoMeta({
  title,
  description,
  ogImage,
  ogType = 'website',
  noindex = false,
  lang,
  canonical,
}) {
  useEffect(() => {
    // No-op during SSR prerendering — all DOM manipulation is client-only
    if (!isClient) return

    const prevTitle = document.title
    const prevLang = document.documentElement.getAttribute('lang')

    const img = ogImage || DEFAULT_OG_IMAGE

    // Strip query string + hash so canonical is always the clean path
    const canonicalUrl =
      canonical ||
      `${window.location.origin}${window.location.pathname}`

    // ------------------------------------------------------------------ //
    // <html lang>
    // ------------------------------------------------------------------ //
    if (lang) {
      document.documentElement.setAttribute('lang', lang)
    }

    // ------------------------------------------------------------------ //
    // <title>
    // ------------------------------------------------------------------ //
    document.title = title

    // ------------------------------------------------------------------ //
    // Robots — noindex for private/authenticated pages
    // ------------------------------------------------------------------ //
    upsertMeta('name', 'robots', noindex ? 'noindex, nofollow' : 'index, follow')

    // ------------------------------------------------------------------ //
    // Standard meta
    // ------------------------------------------------------------------ //
    upsertMeta('name', 'description', description)

    // ------------------------------------------------------------------ //
    // Open Graph
    // ------------------------------------------------------------------ //
    upsertMeta('property', 'og:title', title)
    upsertMeta('property', 'og:description', description)
    upsertMeta('property', 'og:type', ogType)
    upsertMeta('property', 'og:url', canonicalUrl)
    upsertMeta('property', 'og:image', img)
    upsertMeta('property', 'og:site_name', 'Amendly')
    if (lang) upsertMeta('property', 'og:locale', lang.replace('-', '_'))

    // ------------------------------------------------------------------ //
    // Twitter Card
    // ------------------------------------------------------------------ //
    upsertMeta('name', 'twitter:card', 'summary_large_image')
    upsertMeta('name', 'twitter:title', title)
    upsertMeta('name', 'twitter:description', description)
    upsertMeta('name', 'twitter:image', img)

    // ------------------------------------------------------------------ //
    // <link rel="canonical">
    // ------------------------------------------------------------------ //
    upsertLink('canonical', canonicalUrl)

    // ------------------------------------------------------------------ //
    // hreflang — only for public multilingual pages
    // When a canonical is provided and noindex is false, emit one
    // <link rel="alternate" hreflang="xx"> per supported locale.
    // The x-default always points to the English (default) version.
    // ------------------------------------------------------------------ //
    if (!noindex && lang) {
      const basePath = window.location.pathname
      SUPPORTED_LANGS.forEach((l) => {
        upsertLink('alternate', `${SITE_URL}${basePath}`, l)
      })
      // x-default → always English
      upsertLink('alternate', `${SITE_URL}${basePath}`, 'x-default')
    }

    // ------------------------------------------------------------------ //
    // Cleanup
    // ------------------------------------------------------------------ //
    return () => {
      document.title = prevTitle

      // Restore previous lang attribute (or remove if none existed)
      if (lang) {
        if (prevLang) {
          document.documentElement.setAttribute('lang', prevLang)
        } else {
          document.documentElement.removeAttribute('lang')
        }
      }

      removeMeta('name', 'description')
      removeMeta('name', 'robots')
      removeMeta('property', 'og:title')
      removeMeta('property', 'og:description')
      removeMeta('property', 'og:type')
      removeMeta('property', 'og:url')
      removeMeta('property', 'og:image')
      removeMeta('property', 'og:site_name')
      removeMeta('property', 'og:locale')
      removeMeta('name', 'twitter:card')
      removeMeta('name', 'twitter:title')
      removeMeta('name', 'twitter:description')
      removeMeta('name', 'twitter:image')
      removeLink('canonical')

      if (!noindex && lang) {
        SUPPORTED_LANGS.forEach((l) => removeLink('alternate', l))
        removeLink('alternate', 'x-default')
      }
    }
  }, [title, description, ogImage, ogType, noindex, lang, canonical])
}
