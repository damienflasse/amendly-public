/**
 * useTranslation — lightweight i18n hook for Amendly.
 *
 * Reads the user's language preference from localStorage under the key
 * `amendly_lang` (default: "en"). Falls back to English for any missing
 * translation key.
 *
 * SSR-safe: reads localStorage only on the client. During prerendering
 * (Node.js environment) the default language "en" is always used.
 *
 * Supported locales: en, fr, de, es.
 *
 * Usage:
 *   const { t, lang, setLang } = useTranslation()
 *   t('nav.dashboard')   // → "Dashboard" (en) or "Tableau de bord" (fr)
 *   setLang('fr')        // → persists to localStorage, re-renders component
 *
 * @returns {{ t: (key: string) => string, lang: string, setLang: (lang: string) => void }}
 */

import { useCallback } from 'react'
import { create } from 'zustand'
import en from '../i18n/en.json'
import fr from '../i18n/fr.json'
import de from '../i18n/de.json'
import es from '../i18n/es.json'

const LOCALES = { en, fr, de, es }
const STORAGE_KEY = 'amendly_lang'
const DEFAULT_LANG = 'en'

/** Guard for SSR environments (Node.js prerendering) */
const isClient = typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'

const useLangStore = create((set) => ({
  lang: (() => {
    if (!isClient) return DEFAULT_LANG
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored && LOCALES[stored] ? stored : DEFAULT_LANG
  })(),
  setLang: (newLang) => set({ lang: newLang })
}))

/**
 * Resolve a dot-separated key path against a nested object.
 *
 * @param {object} obj - The translations object.
 * @param {string} key - Dot-separated key, e.g. "nav.dashboard".
 * @returns {string|undefined} The resolved string value or undefined.
 */
function resolve(obj, key) {
  return key.split('.').reduce((acc, part) => (acc != null ? acc[part] : undefined), obj)
}

export function useTranslation() {
  const { lang, setLang: setGlobalLang } = useLangStore()

  /** Persist a new language preference and re-render across all hooked components. */
  const setLang = useCallback((newLang) => {
    if (!LOCALES[newLang]) return
    if (isClient) {
      localStorage.setItem(STORAGE_KEY, newLang)
      // Small force-update to help React Router or meta tags update fully if needed
      document.documentElement.lang = newLang
    }
    setGlobalLang(newLang)
  }, [setGlobalLang])

  /**
   * Translate a dot-separated key.
   * Falls back to English if the key is missing in the active locale.
   *
   * @param {string} key - Dot-separated translation key.
   * @returns {string} Translated string, or the key itself if not found.
   */
  const t = useCallback(
    (key) => {
      const primary = resolve(LOCALES[lang], key)
      if (primary != null) return primary
      const fallback = resolve(LOCALES[DEFAULT_LANG], key)
      return fallback ?? key
    },
    [lang]
  )

  return { t, lang, setLang }
}
