/**
 * entry-server.jsx — Server-side render entry point for prerendering.
 *
 * This module is imported by scripts/prerender.js at build time.
 * It renders the application to a static HTML string for a given URL,
 * enabling search engine crawlers to see full HTML content without
 * executing JavaScript.
 *
 * All public routes are prerendered (see scripts/prerender.js for the full list):
 *   /                — LandingPage
 *   /pricing         — PricingPage
 *   /features        — FeaturesPage
 *   /help            — HelpPage
 *   /about           — AboutPage
 *   /contact         — ContactPage
 *   /blog            — BlogIndex
 *   /blog/:slug      — BlogPost (one per entry in src/blog/posts.js)
 *   /legal/terms     — TermsPage
 *   /legal/privacy   — PrivacyPage
 *   /legal/dpa       — DpaPage
 *   /login           — Login
 *
 * @param {string} url — The route path to render (e.g. "/legal/terms")
 * @returns {Promise<string>} — Rendered HTML string (no doctype/html/head tags)
 */
import React from 'react'
import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server'
import AppRoutes from './AppRoutes.jsx'

/**
 * Render the application at the given URL to an HTML string.
 *
 * @param {string} url
 * @returns {Promise<string>}
 */
export async function render(url) {
  const html = renderToString(
    <React.StrictMode>
      <StaticRouter location={url}>
        <AppRoutes />
      </StaticRouter>
    </React.StrictMode>
  )
  return html
}
