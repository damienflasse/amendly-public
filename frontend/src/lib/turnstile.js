const CONFIGURED_TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''

const LOCAL_HOSTNAMES = new Set(['localhost', '127.0.0.1'])

/**
 * Return the configured Turnstile site key when the current hostname should
 * enforce Cloudflare verification, else an empty string.
 *
 * Local development on localhost shares the repo `.env`, which may contain
 * production Turnstile keys that are not valid for localhost. Hiding the
 * widget here keeps the login and public contribution flows usable in dev.
 *
 * @returns {string}
 */
export function getTurnstileSiteKey() {
  if (!CONFIGURED_TURNSTILE_SITE_KEY) return ''
  if (typeof window === 'undefined') return CONFIGURED_TURNSTILE_SITE_KEY
  return LOCAL_HOSTNAMES.has(window.location.hostname)
    ? ''
    : CONFIGURED_TURNSTILE_SITE_KEY
}
