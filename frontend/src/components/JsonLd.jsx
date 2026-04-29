/**
 * JsonLd — injects a <script type="application/ld+json"> block into <head>.
 *
 * Google and other search engines parse JSON-LD to understand page context
 * and may display rich results (e.g. site links, breadcrumbs, app info).
 *
 * The script tag is appended on mount and removed on unmount, so it is safe
 * to use in any route without polluting other pages.
 *
 * SSR-safe: the hook is a no-op during server-side rendering (prerendering).
 * The JSON-LD is only injected on the client — this is acceptable because
 * Google executes JavaScript when crawling. For Google's Rich Results parser
 * the client-side injection is equally valid.
 *
 * @param {{ data: object }} props
 *   data — Plain JavaScript object that will be serialised to JSON-LD.
 *          Must conform to a schema.org type (e.g. SoftwareApplication, WebSite).
 *
 * @returns {null} — renders nothing to the DOM body.
 */
import { useEffect } from 'react'

const isClient = typeof window !== 'undefined' && typeof document !== 'undefined'

export default function JsonLd({ data }) {
  useEffect(() => {
    if (!isClient) return

    const script = document.createElement('script')
    script.setAttribute('type', 'application/ld+json')
    script.textContent = JSON.stringify(data)
    document.head.appendChild(script)

    return () => {
      document.head.removeChild(script)
    }
  }, [data])

  return null
}
