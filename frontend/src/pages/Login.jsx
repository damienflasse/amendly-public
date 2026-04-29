/**
 * Login page — entry point for unauthenticated users.
 *
 * Two sign-in methods are offered:
 *   1. Magic link — user enters their email; a one-time login link is sent.
 *   2. Google SSO — redirects to Google OAuth consent screen.
 *
 * Design follows "The Editorial Ledger" system (frontend/DESIGN.md):
 *   - Surface / tonal layering instead of borders.
 *   - Manrope for the product name headline, Inter for body/UI text.
 *   - Only design-token colours (no hardcoded hex values).
 *   - Ambient shadow for the card lift.
 *
 * Props: none
 * Side effects: calls authClient.requestMagicLink / signInWithGoogle on user interaction.
 */

import { useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { Turnstile } from '@marsidev/react-turnstile'
import { authClient } from '../lib/auth'
import { getTurnstileSiteKey } from '../lib/turnstile'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import LanguageSwitcher from '../components/LanguageSwitcher'

const REDIRECT_KEY = 'amendly_redirect_after_login'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * Thin divider with centred label text ("or continue with").
 * Uses tonal shift instead of a 1px line — see DESIGN.md §2.
 * @param {{ label: string }} props
 */
function OrDivider({ label }) {
  return (
    <div className="flex items-center gap-4 my-8">
      <div className="flex-1 h-px bg-slate-100" />
      <span className="font-body text-label-sm text-amendly-gray tracking-[0.02em] uppercase">
        {label}
      </span>
      <div className="flex-1 h-px bg-slate-100" />
    </div>
  )
}

/**
 * Google sign-in button.
 * @param {{ onClick: () => void, label: string }} props
 */
function GoogleButton({ onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="
        w-full flex items-center justify-center gap-2
        bg-slate-100 text-amendly-dark
        font-body text-title-sm
        rounded-md px-8 py-4
        hover:bg-slate-50
        transition-colors duration-150
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-amendly-blue
      "
    >
      {/* Google G logo (inline SVG — no external asset needed) */}
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path
          d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"
          fill="#4285F4"
        />
        <path
          d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"
          fill="#34A853"
        />
        <path
          d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
          fill="#FBBC05"
        />
        <path
          d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
          fill="#EA4335"
        />
      </svg>
      {label}
    </button>
  )
}



// ---------------------------------------------------------------------------
// Main Login component
// ---------------------------------------------------------------------------

/**
 * @typedef {'idle' | 'loading' | 'sent' | 'error'} MagicLinkState
 */

export default function Login() {
  const { t, lang, setLang } = useTranslation()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const turnstileSiteKey = getTurnstileSiteKey()

  // Determine redirect destination: ?redirect query param → location.state.from → /dashboard
  const redirectDestination =
    searchParams.get('redirect') ||
    (location.state?.from ? location.state.from.pathname + (location.state.from.search ?? '') : null) ||
    '/dashboard'

  useSeoMeta({
    title: 'Sign in — Amendly',
    description: 'Sign in to your Amendly workspace using a magic link or Google.',
    canonical: 'https://amendly.eu/login',
    lang: lang || 'en',
    noindex: true,
  })

  const [email, setEmail] = useState('')
  /** @type {[MagicLinkState, React.Dispatch<React.SetStateAction<MagicLinkState>>]} */
  const [magicState, setMagicState] = useState('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [turnstileToken, setTurnstileToken] = useState('')
  const turnstileRef = useRef(null)

  async function handleMagicLinkSubmit(e) {
    e.preventDefault()
    if (!email.trim()) return
    // If Turnstile is enabled, require a valid token before submitting.
    if (turnstileSiteKey && !turnstileToken) return

    setMagicState('loading')
    setErrorMessage('')

    try {
      await authClient.requestMagicLink(email.trim(), turnstileToken || null)
      // Save redirect so /auth/verify can navigate there after token exchange
      sessionStorage.setItem(REDIRECT_KEY, redirectDestination)
      setMagicState('sent')
    } catch (err) {
      // Reset Turnstile on error so the user can try again with a fresh token.
      turnstileRef.current?.reset()
      setTurnstileToken('')
      setErrorMessage(err.message ?? t('auth.error_fallback'))
      setMagicState('error')
    }
  }

  return (
    <div className="min-h-screen bg-amendly-light flex items-center justify-center px-8 py-12">
      {/*
        Card — Level 2 elevation: surface-container-lowest sitting on surface.
        No border. Ambient shadow for the "lifted" effect.
      */}
      <div
        className="w-full max-w-sm bg-white rounded-md shadow-ambient px-8 py-12"
      >
        {/* Language switcher — top right of card */}
        <div className="flex justify-end mb-6">
          <LanguageSwitcher lang={lang} setLang={setLang} />
        </div>

        {/* Header */}
        <div className="mb-12 text-left">
          <h1 className="font-display text-headline-sm text-amendly-dark tracking-[-0.01em]">
            Amendly
          </h1>
          <p className="mt-2 font-body text-body-md text-amendly-gray">
            {t('auth.sign_in_workspace')}
          </p>
        </div>

        {magicState === 'sent' ? (
          /* Success state */
          <div className="bg-blue-50 rounded-md px-8 py-8 text-center">
            <p className="font-body text-body-md text-amendly-blue font-medium">
              {t('auth.check_inbox')}
            </p>
            <p className="mt-2 font-body text-body-md text-amendly-blue">
              {t('auth.magic_link_sent').replace('{email}', email)}
            </p>
            <button
              type="button"
              onClick={() => { setMagicState('idle'); setEmail('') }}
              className="mt-8 font-body text-label-sm text-amendly-blue underline underline-offset-2"
            >
              {t('auth.use_different_email')}
            </button>
          </div>
        ) : (
          <>
            {/* Magic-link form */}
            <form onSubmit={handleMagicLinkSubmit} noValidate>
              <label
                htmlFor="email"
                className="block font-body text-label-sm text-amendly-dark tracking-[0.02em] uppercase mb-2"
              >
                {t('auth.email_address')}
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                placeholder={t('auth.email_placeholder')}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={magicState === 'loading'}
                className="
                  w-full bg-slate-50 text-amendly-dark
                  font-body text-body-md
                  rounded-md px-4 py-4
                  placeholder:text-amendly-gray
                  focus:outline focus:outline-2 focus:outline-amendly-blue
                  disabled:opacity-50
                "
              />

              {magicState === 'error' && (
                <p className="mt-2 font-body text-label-sm text-red-600" role="alert">
                  {errorMessage}
                </p>
              )}

              {/* Cloudflare Turnstile — only rendered when site key is configured */}
              {turnstileSiteKey && (
                <div className="mt-4">
                  <Turnstile
                    ref={turnstileRef}
                    siteKey={turnstileSiteKey}
                    onSuccess={(token) => setTurnstileToken(token)}
                    onExpire={() => setTurnstileToken('')}
                    onError={() => setTurnstileToken('')}
                    options={{ theme: 'light', size: 'flexible', action: 'auth_magic_link' }}
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={
                  magicState === 'loading' ||
                  !email.trim() ||
                  (turnstileSiteKey && !turnstileToken)
                }
                className="
                  mt-4 w-full
                  bg-amendly-blue text-white
                  font-body text-title-sm
                  rounded-md px-8 py-4
                  hover:opacity-90
                  transition-opacity duration-150
                  disabled:opacity-40 disabled:cursor-not-allowed
                  focus-visible:outline focus-visible:outline-2 focus-visible:outline-amendly-blue
                "
              >
                {magicState === 'loading' ? t('auth.sending') : t('auth.send_login_link')}
              </button>
            </form>

            <OrDivider label={t('auth.or_continue_with')} />

            {/* SSO buttons */}
            <div className="flex flex-col gap-4">
              <GoogleButton
                onClick={() => {
                  sessionStorage.setItem(REDIRECT_KEY, redirectDestination)
                  authClient.signInWithGoogle()
                }}
                label={t('auth.sign_in_google')}
              />
            </div>
          </>
        )}

        {/* Footer */}
        <p className="mt-12 font-body text-label-sm text-amendly-gray text-center">
          {t('auth.terms_notice')}{' '}
          <a
            href="/legal/terms"
            className="text-amendly-blue underline underline-offset-2 hover:opacity-80"
          >
            {t('auth.terms_of_service')}
          </a>{' '}
          {t('auth.and')}{' '}
          <a
            href="/legal/privacy"
            className="text-amendly-blue underline underline-offset-2 hover:opacity-80"
          >
            {t('auth.privacy_policy')}
          </a>
          .
        </p>
      </div>
    </div>
  )
}
