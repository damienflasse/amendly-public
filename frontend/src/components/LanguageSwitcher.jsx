/**
 * LanguageSwitcher — dropdown to switch the UI language.
 *
 * Reads and writes the `amendly_lang` key in localStorage via the
 * useTranslation hook. Supported locales: en, fr, de, es.
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Tonal background shift on hover — no 1px border.
 *   - Manrope not used here (UI control, not headline text).
 *   - Font: Inter body-md sizing.
 *
 * Props:
 *   lang    {string}            — The active locale code (e.g. "en").
 *   setLang {(lang: string) => void} — Callback to change the locale.
 *
 * Side effects:
 *   - Calls setLang which persists the choice to localStorage.
 */

import { useState, useRef, useEffect } from 'react'

const LOCALES = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'fr', label: 'FR', name: 'Français' },
  { code: 'de', label: 'DE', name: 'Deutsch' },
  { code: 'es', label: 'ES', name: 'Español' },
]

/**
 * @param {{ lang: string, setLang: (lang: string) => void }} props
 */
export default function LanguageSwitcher({ lang, setLang }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  // Close the dropdown when the user clicks outside of it
  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const active = LOCALES.find((l) => l.code === lang) ?? LOCALES[0]

  return (
    <div ref={ref} className="relative">
      {/* Trigger */}
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-surface-container-highest hover:bg-surface-container text-on-surface font-body text-label-sm tracking-[0.02em] uppercase transition-colors"
      >
        <span>{active.label}</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <ul
          role="listbox"
          aria-label="Select language"
          className="absolute right-0 mt-1 z-20 bg-surface-container-lowest rounded-md shadow-ambient py-1 min-w-[8rem]"
        >
          {LOCALES.map((locale) => (
            <li key={locale.code} role="option" aria-selected={locale.code === lang}>
              <button
                type="button"
                onClick={() => { setLang(locale.code); setOpen(false) }}
                className={`w-full text-left px-4 py-2 font-body text-body-md transition-colors
                  ${locale.code === lang
                    ? 'text-on-surface bg-surface-container'
                    : 'text-on-surface hover:bg-surface-container-low'
                  }`}
              >
                <span className="font-body text-label-sm tracking-[0.02em] uppercase mr-2">
                  {locale.label}
                </span>
                <span className="text-outline">{locale.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
